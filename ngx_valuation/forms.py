# ngx_valuation/forms.py
from django import forms
from .models import IntrinsicAnalysis


class AnalysisForm(forms.ModelForm):
    class Meta:
        model = IntrinsicAnalysis
        exclude = ['analysis_date', 'ai_commentary']

        # Labels guiding '000 input and unit expectations
        labels = {
            'ticker': 'Company Ticker Symbol',
            'sector': 'Sector Classification',
            'operating_profit': 'Operating Profit (in 000s)',
            'finance_income': 'Finance Income (in 000s)',
            'one_off_gains': 'One-off Gains (in 000s)',
            'tax_expenses': 'Tax Expenses (in 000s)',
            'profit_after_tax': 'Profit After Tax (in 000s)',
            'finance_cost': 'Finance Cost (in 000s)',
            'total_equity': 'Total Equity (in 000s)',
            'total_debt': 'Total Debt (in 000s)',
            'free_cash_flow': 'Free Cash Flow (in 000s)',
            'total_div': 'Total Dividend Paid (in 000s)',
            'total_os': 'Total Shares Outstanding (Full Units)',
            'current_sp': 'Current Share Price (in Naira)',
            'current_inf': 'Current Inflation Rate (%)',
            'report_quarter': 'Financial Statement Period',
        }

        # Number input widgets with consistent dark Tailwind styling
        widgets = {
            field: forms.NumberInput(attrs={
                'class': 'w-full p-2 bg-slate-800 border border-slate-700 rounded text-white focus:ring-2 focus:ring-indigo-500 outline-none',
                'placeholder': 'Enter exact digits from PDF FS'
            }) for field in [
                'operating_profit', 'finance_income', 'one_off_gains', 'tax_expenses',
                'profit_after_tax', 'finance_cost', 'total_equity', 'total_debt',
                'free_cash_flow', 'total_os', 'current_sp', 'total_div', 'current_inf'
            ]
        }

        # Text input widget for ticker
        widgets['ticker'] = forms.TextInput(attrs={
            'class': 'w-full p-2 bg-slate-800 border border-slate-700 rounded text-white focus:ring-2 focus:ring-indigo-500 outline-none uppercase',
            'placeholder': 'e.g. DANGCEM, GTCO'
        })

        # Dropdown selection widgets
        widgets['sector'] = forms.Select(attrs={
            'class': 'w-full p-2 bg-slate-800 border border-slate-700 rounded text-white focus:ring-2 focus:ring-indigo-500 outline-none'
        })

        widgets['report_quarter'] = forms.Select(attrs={
            'class': 'w-full p-2 bg-slate-800 border border-slate-700 rounded text-white focus:ring-2 focus:ring-indigo-500 outline-none'
        })

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set optional fields to prevent validation errors when left empty
        optional_fields = [
            'one_off_gains',
            'finance_cost',
            'free_cash_flow',
            'total_debt',
            'finance_income',
            'total_div'
        ]
        for field in optional_fields:
            if field in self.fields:
                self.fields[field].required = False