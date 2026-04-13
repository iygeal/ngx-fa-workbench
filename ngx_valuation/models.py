# ngx_valuation/models.py
from django.db import models

class IntrinsicAnalysis(models.Model):
    ticker = models.CharField(max_length=15, help_text="e.g., DANGCEM, MTNN")
    analysis_date = models.DateTimeField(auto_now_add=True)

    # --- Raw Manual Inputs ---
    operating_profit = models.DecimalField(max_digits=20, decimal_places=2)
    finance_income = models.DecimalField(max_digits=20, decimal_places=2)
    one_off_gains = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    tax_expenses = models.DecimalField(max_digits=20, decimal_places=2)
    profit_after_tax = models.DecimalField(max_digits=20, decimal_places=2)
    finance_cost = models.DecimalField(max_digits=20, decimal_places=2)
    total_equity = models.DecimalField(max_digits=20, decimal_places=2)
    total_debt = models.DecimalField(max_digits=20, decimal_places=2)
    free_cash_flow = models.DecimalField(max_digits=20, decimal_places=2)

    # --- Market & Dividend Data ---
    total_os = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Total Shares Outstanding")
    current_sp = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Current Share Price")
    total_div = models.DecimalField(max_digits=20, decimal_places=2, default=0, verbose_name="Total Dividend Paid")

    # --- Macro Context ---
    current_inf = models.DecimalField(max_digits=5, decimal_places=2, default=15.10, verbose_name="Inflation %")

    # --- AI Commentary Cache ---
    ai_commentary = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.ticker} ({self.analysis_date.strftime('%Y-%m-%d')})"

    class Meta:
        verbose_name_plural = "Intrinsic Analyses"