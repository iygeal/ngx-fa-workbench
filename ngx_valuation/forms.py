from django import forms
from .models import IntrinsicAnalysis

class AnalysisForm(forms.ModelForm):
    class Meta:
        model = IntrinsicAnalysis
        # We exclude analysis_date (auto) and ai_commentary (calculated)
        exclude = ['analysis_date', 'ai_commentary']

        # Adding Tailwind classes to the inputs for a clean look
        widgets = {
            field: forms.NumberInput(attrs={
                'class': 'w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500'
            }) for field in [
                'operating_profit', 'finance_income', 'one_off_gains', 'tax_expenses',
                'profit_after_tax', 'finance_cost', 'total_equity', 'total_debt',
                'free_cash_flow', 'total_os', 'current_sp', 'total_div', 'current_inf'
            ]
        }
        # Special case for the Ticker string input
        widgets['ticker'] = forms.TextInput(attrs={
            'class': 'w-full p-2 border border-gray-300 rounded uppercase',
            'placeholder': 'e.g. DANGCEM'
        })