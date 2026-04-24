import io
import re
from django.utils.text import slugify
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from .forms import AnalysisForm
from .models import IntrinsicAnalysis
from .services import ValuationService


def home_view(request):
    """
    Landing page for the workbench.
    Redirects to Quick Scan or shows a summary of recent analyses.
    """
    # For now, we redirect to the Quick Scan to get you straight to work.
    return redirect('quick_scan')

def quick_scan_view(request):
    """
    Handles the initial data entry for the Layer 1 (Efficiency) scan.
    """
    if request.method == "POST":
        form = AnalysisForm(request.POST)
        if form.is_valid():
            # 1. Save the raw manual inputs
            analysis = form.save()

            # 2. Run the math via Service Layer
            results = ValuationService.calculate_layer1_metrics(analysis)

            # 3. Get AI Commentary
            memo = ValuationService.get_ai_memo(analysis.ticker, results)

            # 4. Save AI memo back to the database object
            analysis.ai_commentary = memo
            analysis.save()

            return redirect('analysis_results', pk=analysis.pk)
    else:
        form = AnalysisForm()

    return render(request, 'ngx_valuation/scan_form.html', {
        'form': form,
        'title': 'Layer 1: Quick Scan'
    })

def analysis_results_view(request, pk):
    """
    Displays the calculated metrics and AI memo.
    """
    analysis = get_object_or_404(IntrinsicAnalysis, pk=pk)
    # Recalculate metrics for display (we don't store calculated metrics, only raw data)
    results = ValuationService.calculate_layer1_metrics(analysis)

    return render(request, 'ngx_valuation/results.html', {
        'analysis': analysis,
        'results': results,
    })

def export_pdf_view(request, pk):
    # 1. DATA RETRIEVAL
    analysis = get_object_or_404(IntrinsicAnalysis, pk=pk)
    results = ValuationService.calculate_layer1_metrics(analysis)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50
    )
    styles = getSampleStyleSheet()
    story = []

    # 2. HEADER SECTION
    title_style = ParagraphStyle('TitleStyle', parent=styles['Title'], fontSize=22, textColor=colors.black, spaceAfter=5)
    story.append(Paragraph(f"{analysis.ticker} Fundamental Analysis", title_style))
    story.append(Paragraph(f"Analysis Date: {analysis.analysis_date.strftime('%B %d, %Y')}", styles['Normal']))
    story.append(Spacer(1, 20))

    # 3. METRICS TABLE WITH BANK LOGIC
    def get_color(flag): return colors.darkgreen if flag else colors.maroon

    # Check if it's a bank once at the start
    is_bank = "bank" in analysis.ticker.lower()

    # Build the data rows dynamically
    data = [
        ['LAYER 1 METRIC', 'VALUE', 'STATUS'],
        ['ROIC', f"{results['raw']['roic']}%", "PASS" if results['flags']['is_efficient'] else "FAIL"],
        ['Real ROIC', f"{results['raw']['real_roic']}%", "PASS" if results['flags']['is_wealth_creator'] else "FAIL"],
    ]

    # Handle FCF row based on sector
    if is_bank:
        data.append(['FCF Conversion', 'N/A', 'SECTOR EXEMPT'])
    else:
        data.append(['FCF Conversion', f"{results['raw']['fcf_conv']}%", "PASS" if results['flags']['is_cash_backed'] else "FAIL"])

    data.append(['Dividend Yield', f"{results['raw']['div_yield']}%", "N/A"])
    data.append(['Payout Ratio', f"{results['raw']['payout']}%", "HEALTHY" if results['flags']['healthy_payout'] else "CAUTION"])

    t = Table(data, colWidths=[200, 100, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        # Metric-Specific Coloring (Conditional on indices)
        ('TEXTCOLOR', (2, 1), (2, 1), get_color(results['flags']['is_efficient'])),
        ('TEXTCOLOR', (2, 2), (2, 2), get_color(results['flags']['is_wealth_creator'])),
    ]))

    # Only apply FCF color if not a bank (to avoid row index errors)
    if not is_bank:
        t.setStyle(TableStyle([('TEXTCOLOR', (2, 3), (2, 3), get_color(results['flags']['is_cash_backed']))]))
    else:
        t.setStyle(TableStyle([('TEXTCOLOR', (2, 3), (2, 3), colors.slategrey)]))

    story.append(t)
    story.append(Spacer(1, 25))

    # 4. ANALYST COMMENTARY
    story.append(Paragraph("Analyst Commentary", styles['Heading2']))
    story.append(Spacer(1, 10))

    header_style = ParagraphStyle('CommentaryHeader', parent=styles['Normal'], fontSize=11,
                                  textColor=colors.HexColor('#4f46e5'), fontName='Helvetica-Bold',
                                  spaceBefore=10, spaceAfter=4)

    body_style = ParagraphStyle('CommentaryBody', parent=styles['Normal'], fontSize=10,
                                 leading=14, leftIndent=10, spaceAfter=6)

    lines = analysis.ai_commentary.split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        if line.startswith('###'):
            story.append(Paragraph(line.replace('###', '').strip(), header_style))
        elif line.startswith('*'):
            formatted = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line).replace('*', '&bull;', 1)
            story.append(Paragraph(formatted, body_style))
        else:
            formatted = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
            story.append(Paragraph(formatted, body_style))

    # 5. GENERATE AND RETURN
    doc.build(story)
    buffer.seek(0)

    filename = f"{slugify(analysis.ticker)}_Analysis_{analysis.analysis_date.strftime('%Y-%m-%d')}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response