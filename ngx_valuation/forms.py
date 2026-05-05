# ngx_valuation/forms.py
from django import forms
from .models import IntrinsicAnalysis

class AnalysisForm(forms.ModelForm):
    class Meta:
        model = IntrinsicAnalysis
        exclude = ['analysis_date', 'ai_commentary']

        # Adding labels to guide '000 input
        labels = {
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
            'total_os': 'Total Shares Outstanding (Full Units)', # OS is usually not in 000s
        }

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

        widgets['ticker'] = forms.TextInput(attrs={
            'class': 'w-full p-2 bg-slate-800 rounded focus:ring-2 focus:ring-indigo-500 outline-none uppercase',
            'placeholder': 'e.g. DANGCEM'
        })

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        optional_fields = ['one_off_gains', 'finance_cost', 'free_cash_flow', 'total_debt', 'finance_income', 'total_div']
        for field in optional_fields:
            self.fields[field].required = False