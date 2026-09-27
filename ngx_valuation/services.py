# ngx_valuation/services.py
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

        clean_val = str(value).strip().replace(',', '')

        if not clean_val or clean_val.lower() in ['none', 'null', 'nan', '-']:
            return Decimal('0')

        try:
            return Decimal(clean_val)
        except (InvalidOperation, TypeError):
            return Decimal('0')

    @staticmethod
    def calculate_layer1_metrics(analysis_obj):
        d = analysis_obj

        # Core Inputs
        sector = str(d.sector or 'NON_BANK').upper()
        op_profit = Decimal(str(d.operating_profit))
        finance_income = ValuationService._parse_fin(d.finance_income)
        one_off_gains = ValuationService._parse_fin(d.one_off_gains)
        tax_expenses = Decimal(str(d.tax_expenses))
        current_sp = Decimal(str(d.current_sp))
        total_os = Decimal(str(d.total_os))
        quarter = d.report_quarter
        pat = Decimal(str(d.profit_after_tax))
        total_equity = Decimal(str(d.total_equity))
        total_div = ValuationService._parse_fin(d.total_div)
        inf_input = Decimal(str(d.current_inf))
        inflation_rate = inf_input / Decimal('100')

        # Branching Logic based on Sector
        is_bank = sector == 'BANK'

        if is_bank:
            # --- BANKING METRICS ---
            # ROE = PAT / Total Equity
            roe = pat / total_equity if total_equity > 0 else Decimal('0')
            real_roe = roe - inflation_rate

            # Cost to Income Ratio = Operating Expenses (stored in finance_cost) / Operating Profit (Operating Revenue)
            opex = ValuationService._parse_fin(d.finance_cost)
            cost_to_income = opex / \
                op_profit if op_profit > 0 else Decimal('0')

            # Non-applicable metrics for Banks defaulted to 0
            nopat = Decimal('0')
            roic = Decimal('0')
            real_roic = Decimal('0')
            fcf_conversion = Decimal('0')
        else:
            # --- NON-BANK INDUSTRIAL METRICS ---
            adj_ebit = op_profit + finance_income - one_off_gains
            nopat = adj_ebit - tax_expenses

            finance_cost = ValuationService._parse_fin(d.finance_cost)
            total_debt = ValuationService._parse_fin(d.total_debt)
            fcf = ValuationService._parse_fin(d.free_cash_flow)

            invested_capital = total_equity + total_debt
            roic = (pat + finance_cost) / \
                invested_capital if invested_capital > 0 else Decimal('0')
            real_roic = roic - inflation_rate

            fcf_conversion = fcf / pat if pat != 0 else Decimal('0')
            roe = Decimal('0')
            real_roe = Decimal('0')
            cost_to_income = Decimal('0')

        # Common Shareholder Yield & Market Cap Calculations
        total_div_full = total_div * Decimal('1000')
        market_cap = total_os * current_sp
        payout_ratio = total_div / pat if pat > 0 else Decimal('0')
        div_yield = total_div_full / \
            market_cap if market_cap > 0 else Decimal('0')

        # Forward Valuation Projector Engine
        pat_full_units = pat * Decimal('1000')
        interim_eps = pat_full_units / \
            total_os if total_os > 0 else Decimal('0')

        multipliers = {
            'Q1': Decimal('4'),
            'Q2': Decimal('2'),
            'Q3': Decimal('1.333333'),
            'FY': Decimal('1')
        }
        multiplier = multipliers.get(quarter, Decimal('1'))

        forward_eps = interim_eps * multiplier
        forward_pe = current_sp / \
            forward_eps if forward_eps > 0 else Decimal('0')

        return {
            "raw": {
                "sector": sector,
                "is_bank": is_bank,
                "nopat": nopat.quantize(Decimal('1'), ROUND_HALF_UP),
                "roic": (roic * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "real_roic": (real_roic * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "roe": (roe * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "real_roe": (real_roe * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "cost_to_income": (cost_to_income * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "fcf_conv": (fcf_conversion * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "payout": (payout_ratio * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "div_yield": (div_yield * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "inflation_used": inf_input,
                "current_sp": current_sp.quantize(Decimal('0.01'), ROUND_HALF_UP),
                "interim_eps": interim_eps.quantize(Decimal('0.01'), ROUND_HALF_UP),
                "forward_eps": forward_eps.quantize(Decimal('0.01'), ROUND_HALF_UP),
                "forward_pe": forward_pe.quantize(Decimal('0.02'), ROUND_HALF_UP),
                "period_analyzed": quarter,
            },
            "flags": {
                "is_efficient": (roe >= Decimal('0.18')) if is_bank else (roic >= Decimal('0.20')),
                "is_cash_backed": True if is_bank else (fcf_conversion >= Decimal('0.70')),
                "is_wealth_creator": (real_roe > 0) if is_bank else (real_roic > 0),
                "healthy_payout": Decimal('0.30') <= payout_ratio <= Decimal('0.70'),
                "is_undervalued_pe": Decimal('0') < forward_pe <= (Decimal('5.00') if is_bank else Decimal('10.00'))
            }
        }

    @staticmethod
    def get_ai_memo(ticker, metrics):
        """
        Fetches an AI-generated investment commentary based on calculated metrics.
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return "AI Commentary unavailable: Missing API Key."

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name='gemini-flash-latest')

            raw = metrics['raw']
            is_bank = raw['is_bank']

            # Dynamic prompt tailored to entity classification
            if is_bank:
                sector_metrics_prompt = f"""
            LAYER 1 BANKING OPERATIONAL METRICS:
            - Return on Equity (ROE): {raw['roe']}%
            - Real ROE: {raw['real_roe']}% (Hurdle Rate = Inflation: {raw['inflation_used']}%)
            - Cost-to-Income Ratio: {raw['cost_to_income']}%
            - Dividend Yield: {raw['div_yield']}%
            - Payout Ratio: {raw['payout']}%
            """
                rule_benchmark = "For commercial banks on the NGX, a Forward P/E at or below 5x represents a strong value benchmark."
            else:
                sector_metrics_prompt = f"""
            LAYER 1 INDUSTRIAL OPERATIONAL METRICS:
            - ROIC: {raw['roic']}%
            - Real ROIC: {raw['real_roic']}% (Hurdle Rate = Inflation: {raw['inflation_used']}%)
            - FCF Conversion: {raw['fcf_conv']}%
            - Dividend Yield: {raw['div_yield']}%
            - Payout Ratio: {raw['payout']}%
            """
                rule_benchmark = "For non-banking stocks, a Forward P/E at or below 10x represents an asymmetric value entry point."

            prompt = f"""
            Act as a senior equity analyst specializing in the Nigerian Stock Exchange (NGX).
            Analyze {ticker} ({'Commercial Bank' if is_bank else 'Non-Banking / Industrial'}) using these operational metrics, market data, and forward projections:

            CORE MARKET & MACRO DATA:
            - Current Share Price: ₦{raw['current_sp']}
            - Headline Inflation Rate: {raw['inflation_used']}%

            {sector_metrics_prompt}

            FORWARD VALUATION ENGINE:
            - Financial Statement Period: {raw['period_analyzed']}
            - Calculated Interim Annualized EPS: ₦{raw['interim_eps']}
            - Projected Full-Year Forward EPS: ₦{raw['forward_eps']}
            - Calculated Forward P/E Ratio: {raw['forward_pe']}x

            THEORETICAL FRAMEWORK TO APPLY (Forward Valuation Projector):
            "This projector states that equity markets fixate on past historical data, often missing massive inflection points in interim results. Forward valuation projects the true value of a stock based on future cash flows and annualized forward earnings. {rule_benchmark}"

            STRICT INSTRUCTIONS FOR THE ANALYSIS:
            1. Use Headline Inflation of {raw['inflation_used']}% for your macro assessment.
            2. Dividend tracking metrics must be ignored if the period analyzed is Q1 or Q3.
            3. Critically evaluate current price (₦{raw['current_sp']}) against Projected Forward EPS (₦{raw['forward_eps']}) using The Forward Projector Rule.
            {"4. Assess Cost-to-Income and ROE stability for banking performance." if is_bank else "4. Assess ROIC and Free Cash Flow conversion quality."}

            Format your output exactly with these 4 structural markdown headers:
            ### 1. Efficiency Check
            ### 2. Cash & Dividend Safety
            ### 3. Valuation & Trajectory Verdict (Apply Forward Projector Rule here)
            ### 4. Risk & Macro Verdict

            Focus your tone on whether the business is an operational 'Wealth Creator' or 'Wealth Destroyer' based on Real {'ROE' if is_bank else 'ROIC'}.
            """

            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error generating AI memo: {str(e)}"
