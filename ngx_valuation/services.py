import os
import google.generativeai as genai
from decimal import Decimal, ROUND_HALF_UP
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class ValuationService:
    """
    Service layer for financial analysis and AI-driven commentary.
    Contains business logic for the NGX Fundamental Analysis project.
    """

    @staticmethod
    def calculate_layer1_metrics(analysis_obj):
        """
        Calculates efficiency, cash conversion, and dividend safety.

        Args:
            analysis_obj: An instance of the IntrinsicAnalysis Django model.

        Returns:
            dict: A nested dictionary of raw percentages and strategy flags.
        """
        d = analysis_obj

        # Standardize inputs to Decimal for precision across different OS
        pat = Decimal(str(d.profit_after_tax))
        fcf = Decimal(str(d.free_cash_flow))
        total_equity = Decimal(str(d.total_equity))
        total_debt = Decimal(str(d.total_debt))

        # 1. Operational Logic (NOPAT)
        # NOPAT represents the business profitability if it had no debt.
        adj_ebit = Decimal(str(d.operating_profit + d.finance_income - d.one_off_gains))
        nopat = adj_ebit - Decimal(str(d.tax_expenses))

        # 2. Return on Invested Capital (Efficiency)
        invested_capital = total_equity + total_debt
        roic = (pat + Decimal(str(d.finance_cost))) / invested_capital if invested_capital > 0 else Decimal('0')

        # 3. Real ROIC (Inflation-Adjusted Hurdle)
        inflation_rate = Decimal(str(d.current_inf)) / Decimal('100')
        real_roic = roic - inflation_rate

        # 4. Cash Flow & Dividend Safety
        fcf_conversion = fcf / pat if pat != 0 else Decimal('0')
        market_cap = Decimal(str(d.total_os)) * Decimal(str(d.current_sp))
        payout_ratio = Decimal(str(d.total_div)) / pat if pat > 0 else Decimal('0')
        div_yield = Decimal(str(d.total_div)) / \
            market_cap if market_cap > 0 else Decimal('0')

        return {
            "raw": {
                "nopat": nopat,
                "roic": (roic * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "real_roic": (real_roic * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "fcf_conv": (fcf_conversion * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "payout": (payout_ratio * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                # "div_yield": (div_yield * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
                "div_yield": (div_yield * 100).quantize(Decimal('0.01'), ROUND_HALF_UP),
            },
            "flags": {
                "is_efficient": roic >= Decimal('0.20'),
                "is_cash_backed": fcf_conversion >= Decimal('0.70'),
                "is_wealth_creator": real_roic > 0,
                "healthy_payout": Decimal('0.30') <= payout_ratio <= Decimal('0.70'),
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
                Act as a senior equity analyst for the Nigerian Stock Exchange.
                Analyze {ticker} with these metrics: ROIC {metrics['raw']['roic']}%, Real ROIC {metrics['raw']['real_roic']}%, FCF Conv {metrics['raw']['fcf_conv']}%, Div Yield {metrics['raw']['div_yield']}%, Payout {metrics['raw']['payout']}%.

                Format your response with these exact headers:
                ### 1. Efficiency Check
                ### 2. Cash & Dividend Safety
                ### 3. Risk & Macro Verdict

                Use bullet points. Be concise. Avoid conversational filler like "This analysis examines..."
                Focus on whether the business is a 'Wealth Creator' or 'Wealth Destroyer' in Nigeria's high-inflation environment.
                """

            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error generating AI memo: {str(e)}"