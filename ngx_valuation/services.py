import os
import google.generativeai as genai
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class ValuationService:
    """
    Service layer for financial analysis and AI-driven commentary.
    Contains business logic for the NGX Fundamental Analysis project.
    """

    @staticmethod
    def _parse_fin(value):
        """
        Internal utility to handle nullable fields and 'dirty' data.
        Ensures that None, empty strings, or strings like 'None'
        safely default to Decimal('0').
        """
        if value is None:
            return Decimal('0')

        # Convert to string and remove common formatting artifacts
        # This handles cases where data might have commas (e.g., "1,200.50")
        clean_val = str(value).strip().replace(',', '')

        # Check for empty strings or string-representations of nulls
        if not clean_val or clean_val.lower() in ['none', 'null', 'nan', '-']:
            return Decimal('0')

        try:
            return Decimal(clean_val)
        except (InvalidOperation, TypeError):
            return Decimal('0')

    @staticmethod
    def calculate_layer1_metrics(analysis_obj):
        d = analysis_obj

        # Standardize inputs (all in 000s)
        op_profit = Decimal(str(d.operating_profit))
        finance_income = ValuationService._parse_fin(d.finance_income)
        one_off_gains = ValuationService._parse_fin(d.one_off_gains)
        tax_expenses = Decimal(str(d.tax_expenses))
        current_sp = Decimal(str(d.current_sp))
        total_os = Decimal(str(d.total_os))
        quarter = d.report_quarter

        # NOPAT represents the business profitability if it had no debt.
        adj_ebit = op_profit + finance_income - one_off_gains
        nopat = adj_ebit - tax_expenses

        pat = Decimal(str(d.profit_after_tax))
        fcf = ValuationService._parse_fin(d.free_cash_flow)
        total_equity = Decimal(str(d.total_equity))
        total_debt = ValuationService._parse_fin(d.total_debt)
        total_div = ValuationService._parse_fin(d.total_div)
        finance_cost = ValuationService._parse_fin(d.finance_cost)

        # 1. ROIC Calculation (Inputs are all in 000s, so units cancel out correctly)
        invested_capital = total_equity + total_debt
        roic = (pat + finance_cost) / invested_capital if invested_capital > 0 else Decimal('0')

        # 2. Real ROIC (Uses the manual inflation input)
        inf_input = Decimal(str(d.current_inf))
        inflation_rate = inf_input / Decimal('100')
        real_roic = roic - inflation_rate

        # 3. Dividend & Market Cap Logic
        # Convert total_div (000s) to full units to match Share Price * OS
        total_div_full = total_div * Decimal('1000')
        market_cap = total_os * current_sp

        fcf_conversion = fcf / pat if pat != 0 else Decimal('0')
        payout_ratio = total_div / pat if pat > 0 else Decimal('0')
        div_yield = total_div_full / market_cap if market_cap > 0 else Decimal('0')

        # --- FORWARD VALUE PROJECTOR LOGIC ---
        # Convert PAT from thousands back to full base units to calculate accurate EPS
        pat_full_units = pat * Decimal('1000')
        interim_eps = pat_full_units / total_os if total_os > 0 else Decimal('0')

        # Assign multiplier map based on the active statement quarter
        multipliers = {
            'Q1': Decimal('4'),
            'Q2': Decimal('2'),
            'Q3': Decimal('1.333333'),
            'FY': Decimal('1')
        }
        multiplier = multipliers.get(quarter, Decimal('1'))

        forward_eps = interim_eps * multiplier
        forward_pe = current_sp / forward_eps if forward_eps > 0 else Decimal('0')

        return {
            "raw": {
                # We quantize NOPAT to 0 decimal places for a clean 'N' box display
                "nopat": nopat.quantize(Decimal('1'), ROUND_HALF_UP),
                "roic": (roic * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "real_roic": (real_roic * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "fcf_conv": (fcf_conversion * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "payout": (payout_ratio * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "div_yield": (div_yield * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "inflation_used": inf_input, # Sent to AI to ensure consistency

                "current_sp": current_sp.quantize(Decimal('0.01'), ROUND_HALF_UP),

                # Forward Valuation Projector Outputs
                "interim_eps": interim_eps.quantize(Decimal('0.01'), ROUND_HALF_UP),
                "forward_eps": forward_eps.quantize(Decimal('0.01'), ROUND_HALF_UP),
                "forward_pe": forward_pe.quantize(Decimal('0.02'), ROUND_HALF_UP),
                "period_analyzed": quarter,
            },
            "flags": {
                "is_efficient": roic >= Decimal('0.20'),
                "is_cash_backed": fcf_conversion >= Decimal('0.70'),
                "is_wealth_creator": real_roic > 0,
                "healthy_payout": Decimal('0.30') <= payout_ratio <= Decimal('0.70'),
                "is_undervalued_pe": Decimal('0') < forward_pe <= Decimal('10.00')
            }
        }

    @staticmethod
    def get_ai_memo(ticker, metrics):
        """
        Fetches an AI-generated investment commentary based on calculated metrics.

        Args:
            ticker (str): The stock symbol.
            metrics (dict): The dictionary returned by calculate_layer1_metrics.

        Returns:
            str: Professional commentary or a fallback message if API fails.
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return "AI Commentary unavailable: Missing API Key."

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name='gemini-flash-latest')

            prompt = f"""
            Act as a senior equity analyst specializing in the Nigerian Stock Exchange (NGX).
            Analyze {ticker} using these operational metrics, market data, and forward projections:

            CORE MARKET & MACRO DATA:
            - Current Share Price: ₦{metrics['raw']['current_sp']}
            - Headline Inflation Rate: {metrics['raw']['inflation_used']}%

            LAYER 1 OPERATIONAL METRICS:
            - ROIC: {metrics['raw']['roic']}%
            - Real ROIC: {metrics['raw']['real_roic']}% (Hurdle Rate = Inflation)
            - FCF Conversion: {metrics['raw']['fcf_conv']}%
            - Dividend Yield: {metrics['raw']['div_yield']}%
            - Payout Ratio: {metrics['raw']['payout']}%

            FORWARD VALUATION ENGINE:
            - Financial Statement Period: {metrics['raw']['period_analyzed']}
            - Calculated Interim Annualized EPS: ₦{metrics['raw']['interim_eps']}
            - Projected Full-Year Forward EPS: ₦{metrics['raw']['forward_eps']}
            - Calculated Forward P/E Ratio: {metrics['raw']['forward_pe']}x

            THEORETICAL FRAMEWORK TO APPLY (Forward Valuation Projector):
            "This projector states that equity markets are inherently backward-looking time machines that fixate on past historical data, often missing massive inflection points in interim results. The true value of a stock is based on the present value of its future cash flows, meaning stocks trade on forward earnings, not backwards.

            Under this rule, if a company delivers strong earnings acceleration in an interim quarter (like Q1 or H1) that projects a Forward P/E ratio at or below a conservative 10x benchmark or less, for a non-banking stock, it represents an asymmetric value entry point where the market has failed to price in the operational forward momentum."

            STRICT INSTRUCTIONS FOR THE ANALYSIS:
            1. Use the provided Headline Inflation of {metrics['raw']['inflation_used']}% for your macro assessment. Do not reference internal knowledge of historical Nigerian inflation statistics.
            2. Dividend tracking metrics must be ignored if the period analyzed is Q1 or Q3. Explicitly state that a 0% dividend yield is typical for Q1 on the NGX and steer the analysis toward how operational efficiency is compounding retained earnings.
            3. Critically evaluate the current share price (₦{metrics['raw']['current_sp']}) against the Projected Full-Year Forward EPS (₦{metrics['raw']['forward_eps']}) using The Forward Projector Rule. Determine if the resulting Forward P/E of {metrics['raw']['forward_pe']}x represents a mispricing by the market.

            Format your output exactly with these 4 structural markdown headers:
            ### 1. Efficiency Check
            ### 2. Cash & Dividend Safety
            ### 3. Valuation & Trajectory Verdict (Apply Forward Projector Rule here)
            ### 4. Risk & Macro Verdict

            Focus your tone on whether the business is an operational 'Wealth Creator' or 'Wealth Destroyer' based on its Real ROIC, and integrate the current stock price directly into your valuation narrative to explain why the market is right or wrong.
            """

            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error generating AI memo: {str(e)}"