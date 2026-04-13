from django.db import models
from django.db import db


class EmmaStrategyAnalysis(models.Model):
    ticker = models.CharField(max_length=15, help_text="e.g., ZENITHBANK")
    analysis_date = models.DateField(auto_now_add=True)

    # --- Raw Manual Inputs ---
    operating_profit = models.DecimalField(max_digits=20, decimal_places=2)
    finance_income = models.DecimalField(max_digits=20, decimal_places=2)
    one_off_gains = models.DecimalField(
        max_digits=20, decimal_places=2, default=0, help_text="Subtract from EBIT")
    tax_expenses = models.DecimalField(max_digits=20, decimal_places=2)
    pat = models.DecimalField(
        max_digits=20, decimal_places=2, verbose_name="Profit After Tax")
    finance_cost = models.DecimalField(max_digits=20, decimal_places=2)
    total_equity = models.DecimalField(max_digits=20, decimal_places=2)
    total_debt = models.DecimalField(max_digits=20, decimal_places=2)
    free_cash_flow = models.DecimalField(max_digits=20, decimal_places=2)
    current_inflation = models.DecimalField(
        max_digits=5, decimal_places=2, default=25.0, help_text="Current NGX Inflation %")

    # --- AI Commentary Cache ---
    ai_commentary = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.ticker} - {self.analysis_date}"

    class Meta:
        verbose_name_plural = "Emma Strategy Analyses"
