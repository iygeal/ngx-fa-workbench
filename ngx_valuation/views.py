import io
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
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
    analysis = get_object_or_404(IntrinsicAnalysis, pk=pk)
    results = ValuationService.calculate_layer1_metrics(analysis)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    story.append(Paragraph(f"Financial Analysis: {analysis.ticker}", styles['Title']))
    story.append(Paragraph(f"Date: {analysis.analysis_date.strftime('%Y-%m-%d')}", styles['Normal']))
    story.append(Spacer(1, 20))

    # Metrics Table
    data = [
        ['Metric', 'Value', 'Status'],
        ['ROIC', f"{results['raw']['roic']}%", 'PASS' if results['flags']['is_efficient'] else 'FAIL'],
        ['Real ROIC', f"{results['raw']['real_roic']}%", 'PASS' if results['flags']['is_wealth_creator'] else 'FAIL'],
        ['FCF Conversion', f"{results['raw']['fcf_conv']}%", 'PASS' if results['flags']['is_cash_backed'] else 'FAIL'],
        ['Div. Yield', f"{results['raw']['div_yield']}%", 'N/A'],
    ]

    t = Table(data, colWidths=[150, 100, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.slategrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(t)
    story.append(Spacer(1, 25))

    # AI Commentary
    story.append(Paragraph("Analyst Commentary", styles['Heading2']))
    # Basic cleanup of markdown symbols for PDF
    clean_memo = analysis.ai_commentary.replace('#', '').replace('*', '')
    story.append(Paragraph(clean_memo, styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf')