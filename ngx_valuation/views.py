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
    # Recalculate metrics for display
    results = ValuationService.calculate_layer1_metrics(analysis)

    return render(request, 'ngx_valuation/results.html', {
        'analysis': analysis,
        'results': results,
    })


def export_pdf_view(request, pk):
    # 1. DATA RETRIEVAL
    analysis = get_object_or_404(IntrinsicAnalysis, pk=pk)
    results = ValuationService.calculate_layer1_metrics(analysis)

    raw = results['raw']
    flags = results['flags']
    is_bank = raw['is_bank']

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
    story.append(Paragraph(f"Sector: {'Commercial Bank' if is_bank else 'Non-Bank / Industrial'} | Analysis Date: {analysis.analysis_date.strftime('%B %d, %Y')}", styles['Normal']))
    story.append(Spacer(1, 20))

    # 3. METRICS TABLE WITH BANK vs NON-BANK LOGIC
    def get_color(flag):
        return colors.darkgreen if flag else colors.maroon

    # Build the dynamic data rows depending on entity classification
    data = [['LAYER 1 METRIC', 'VALUE', 'STATUS']]

    if is_bank:
        data.append(['ROE', f"{raw['roe']}%", "PASS" if flags['is_efficient'] else "FAIL"])
        data.append(['Real ROE', f"{raw['real_roe']}%", "PASS" if flags['is_wealth_creator'] else "FAIL"])
        data.append(['Cost-to-Income Ratio', f"{raw['cost_to_income']}%", "METRIC"])
    else:
        data.append(['ROIC', f"{raw['roic']}%", "PASS" if flags['is_efficient'] else "FAIL"])
        data.append(['Real ROIC', f"{raw['real_roic']}%", "PASS" if flags['is_wealth_creator'] else "FAIL"])
        data.append(['FCF Conversion', f"{raw['fcf_conv']}%", "PASS" if flags['is_cash_backed'] else "FAIL"])

    data.append(['Dividend Yield', f"{raw['div_yield']}%", "N/A"])
    data.append(['Payout Ratio', f"{raw['payout']}%", "HEALTHY" if flags['healthy_payout'] else "CAUTION"])

    # Forward Value Projector Rows
    data.append([f"Forward EPS (Proj. {raw['period_analyzed']})", f"N{raw['forward_eps']}", "TRAJECTORY"])
    data.append(['Forward P/E Ratio', f"{raw['forward_pe']}x", "UNDERVALUED" if flags['is_undervalued_pe'] else "FAIR / PREMIUM"])

    t = Table(data, colWidths=[220, 90, 90])

    # Base table formatting setup
    t_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        # Primary Efficiency Colors
        ('TEXTCOLOR', (2, 1), (2, 1), get_color(flags['is_efficient'])),
        ('TEXTCOLOR', (2, 2), (2, 2), get_color(flags['is_wealth_creator'])),
    ]

    # Sector specific row styling
    if not is_bank:
        t_style.append(('TEXTCOLOR', (2, 3), (2, 3), get_color(flags['is_cash_backed'])))
    else:
        t_style.append(('TEXTCOLOR', (2, 3), (2, 3), colors.HexColor('#1e293b')))

    # Forward valuation row styling (rows index 6 and 7)
    t_style.extend([
        ('FONTNAME', (0, 6), (-1, 7), 'Helvetica-Bold'),
        ('TEXTCOLOR', (2, 7), (2, 7), get_color(flags['is_undervalued_pe'])),
    ])

    t.setStyle(TableStyle(t_style))
    story.append(t)
    story.append(Spacer(1, 25))

    # 4. ANALYST COMMENTARY
    story.append(Paragraph("Analyst Commentary", styles['Heading2']))
    story.append(Spacer(1, 10))

    header_style = ParagraphStyle(
        'CommentaryHeader',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#4f46e5'),
        fontName='Helvetica-Bold',
        spaceBefore=10,
        spaceAfter=4
    )

    body_style = ParagraphStyle(
        'CommentaryBody',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        leftIndent=10,
        spaceAfter=6
    )

    lines = analysis.ai_commentary.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
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