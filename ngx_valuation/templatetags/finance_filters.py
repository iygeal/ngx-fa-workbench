from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def to_billions(value):
    try:
        # Assumes input is in '000s, divides by 1M to get Billions
        res = Decimal(str(value)) / Decimal('1000000')
        return f"{res:,.2f}B"
    except:
        return value