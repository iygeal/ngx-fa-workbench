# ngx_valuation/models.py
from django.db import models


class IntrinsicAnalysis(models.Model):
    # Sector Classification Choices
    SECTOR_CHOICES = [
        ('NON_BANK', 'Non-Banking / Industrial / Commercial'),
        ('BANK', 'Banking / Financial Institution'),
    ]

    # Reporting Period Choices
    QUARTER_CHOICES = [
        ('Q1', 'Q1 (First Quarter - 3 Months)'),
        ('Q2', 'Q2 / H1 (Half Year - 6 Months Cumulative)'),
        ('Q3', 'Q3 (Nine Months - 9 Months Cumulative)'),
        ('FY', 'FY (Full Year - 12 Months)'),
    ]

    # --- Header Information ---
    ticker = models.CharField(
        max_length=15,
        db_index=True,
        help_text="e.g., DANGCEM, MTNN, UBA, GTCO"
    )
    sector = models.CharField(
        max_length=10,
        choices=SECTOR_CHOICES,
        default='NON_BANK',
        verbose_name="Sector Type",
        help_text="Determines whether cash flow metrics like FCF apply."
    )
    analysis_date = models.DateTimeField(auto_now_add=True)

    # --- Raw Income Statement Inputs ---
    operating_profit = models.DecimalField(max_digits=20, decimal_places=2)
    finance_income = models.DecimalField(
        max_digits=20, decimal_places=2, default=0, null=True, blank=True
    )
    one_off_gains = models.DecimalField(
        max_digits=20, decimal_places=2, default=0, null=True, blank=True,
        help_text="Non-recurring income to subtract from operating profit."
    )
    tax_expenses = models.DecimalField(max_digits=20, decimal_places=2)
    profit_after_tax = models.DecimalField(max_digits=20, decimal_places=2)
    finance_cost = models.DecimalField(
        max_digits=20, decimal_places=2, default=0, null=True, blank=True
    )

    # --- Balance Sheet & Cash Flow Inputs ---
    total_equity = models.DecimalField(max_digits=20, decimal_places=2)
    total_debt = models.DecimalField(
        max_digits=20, decimal_places=2, default=0, null=True, blank=True
    )
    free_cash_flow = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True,
        help_text="Leave blank or set 0 for banking sector records."
    )

    # --- Market & Dividend Data ---
    total_os = models.DecimalField(
        max_digits=20, decimal_places=2, verbose_name="Total Shares Outstanding (Millions)"
    )
    current_sp = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Current Share Price (₦)"
    )
    total_div = models.DecimalField(
        max_digits=20, decimal_places=2, default=0, null=True, blank=True,
        verbose_name="Total Dividend Paid (₦)"
    )

    # --- Projection & Macro Context ---
    report_quarter = models.CharField(
        max_length=2,
        choices=QUARTER_CHOICES,
        default='Q1',
        verbose_name="Reporting Period"
    )
    current_inf = models.DecimalField(
        max_digits=5, decimal_places=2, default=15.10, verbose_name="Inflation %"
    )

    # --- Cached AI Commentary ---
    ai_commentary = models.TextField(blank=True, default="")

    class Meta:
        ordering = ['-analysis_date']
        verbose_name = "Intrinsic Analysis"
        verbose_name_plural = "Intrinsic Analyses"

    def __str__(self):
        return f"{self.ticker} [{self.report_quarter}] - {self.analysis_date.strftime('%Y-%m-%d')}"

    @property
    def is_bank(self):
        """Helper check to eliminate fragile ticker string matching across views and PDF logic."""
        return self.sector == 'BANK'