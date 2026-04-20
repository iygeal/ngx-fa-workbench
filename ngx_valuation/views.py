import io
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

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
    """
    Generates a simple PDF report of the analysis.
    """
    analysis = get_object_or_404(IntrinsicAnalysis, pk=pk)

    # Create a file-like buffer to receive PDF data.
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)

    # Basic PDF drawing (Header)
    p.drawString(100, 750, f"Investment Analysis Report: {analysis.ticker}")
    p.drawString(100, 735, f"Date: {analysis.analysis_date.strftime('%Y-%m-%d')}")

    # Content (AI Memo) - Simplistic wrap
    p.drawString(100, 700, "AI Commentary:")
    text_object = p.beginText(100, 680)
    text_object.setFont("Helvetica", 10)

    # Basic word wrap for memo
    lines = analysis.ai_commentary.split('\n')
    for line in lines:
        text_object.textLine(line[:100]) # Crude line clipping for now

    p.drawText(text_object)
    p.showPage()
    p.save()

    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf')