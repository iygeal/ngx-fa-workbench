from decimal import Decimal

class ValuationService:
    """
    Handles core investment math and strategy checks.
    """

    @staticmethod
    def calculate_efficiency_metrics(analysis_obj):
        """
        Calculates the Layer 1 (Efficiency) metrics.
        Takes an IntrinsicAnalysis model instance as input.
        """
        data = analysis_obj

        # 1. Adjusted EBIT (Removing one-off fluff)
        adj_ebit = data.operating_profit + data.finance_income - data.one_off_gains

        # 2. NOPAT
        nopat = adj_ebit - data.tax_expenses

        # 3. ROIC Calculation
        invested_capital = data.total_equity + data.total_debt
        raw_roic = (data.profit_after_tax + data.finance_cost) / invested_capital if invested_capital > 0 else 0

        # 4. Real ROIC (Accounting for Inflation)
        # Convert inflation to decimal (e.g., 15.10 -> 0.151)
        inflation_decimal = data.current_inf / 100
        real_roic = raw_roic - inflation_decimal

        # 5. FCF Conversion
        fcf_conv = data.free_cash_flow / data.profit_after_tax if data.profit_after_tax != 0 else 0

        return {
            "adj_ebit": adj_ebit,
            "nopat": nopat,
            "roic_percent": round(raw_roic * 100, 2),
            "real_roic_percent": round(real_roic * 100, 2),
            "fcf_conversion_percent": round(fcf_conv * 100, 2),
            "is_efficient": raw_roic >= 0.20,
            "is_cash_rich": fcf_conv >= 0.70
        }

    @staticmethod
    def get_ai_commentary(metrics):
        """
        Placeholder for the AI API call.
        We will implement the Gemini API here next.
        """
        # Logic: If ROIC is high but FCF is low, prompt AI to explain the risk.
        pass