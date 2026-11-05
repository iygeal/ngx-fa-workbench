# ngx_valuation/views.py
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
    Redirects directly to the Layer 1 Quick Scan form.
    """
    return redirect('quick_scan')


def quick_scan_view(request):
    """
    Handles data entry for Layer 1 (Efficiency) & Layer 2 (Momentum) scan.
    Saves raw inputs, calculates operational and momentum metrics via ValuationService,
    fetches Gemini AI commentary, and redirects to the results view.
    """
    if request.method == "POST":
        form = AnalysisForm(request.POST)
        if form.is_valid():
            # 1. Save raw manual inputs
            analysis = form.save()

            # 2. Run mathematical calculations via Service Layer
            results = ValuationService.calculate_layer1_metrics(analysis)

            # 3. Generate AI Commentary
            memo = ValuationService.get_ai_memo(analysis.ticker, results)

            # 4. Save AI memo back to database record
            analysis.ai_commentary = memo
            analysis.save()

            return redirect('analysis_results', pk=analysis.pk)
    else:
        form = AnalysisForm()

    return render(request, 'ngx_valuation/scan_form.html', {
        'form': form,
        'title': 'Layer 1 & 2: Valuation Scan'
    })


def analysis_results_view(request, pk):
    """
    Displays calculated metrics and formatted AI investment commentary
    on the web results dashboard.
    """
    analysis = get_object_or_404(IntrinsicAnalysis, pk=pk)
    results = ValuationService.calculate_layer1_metrics(analysis)

    return render(request, 'ngx_valuation/results.html', {
        'analysis': analysis,
        'results': results,
    })


def export_pdf_view(request, pk):
    """
    Generates and downloads a clean, publication-ready PDF summary report.
    Includes sector-aware metrics tables, Layer 2 momentum metrics, and sanitized AI commentary.
    """
    analysis = get_object_or_404(IntrinsicAnalysis, pk=pk)
    results = ValuationService.calculate_layer1_metrics(analysis)

    raw = results['raw']
    flags = results['flags']
    mom = results.get('momentum', {})
    is_bank = raw['is_bank']

    def clean_text_for_pdf(text):
        if not text:
            return ""
        t = str(text).replace('₦', 'N')
        t = re.sub(r'\$\s*\\frac\{([^}]+)\}\{([^}]+)\}\s*\$', r'(\1 / \2)', t)
        t = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1 / \2)', t)
        t = t.replace(r'\le', '<=').replace(r'\ge', '>=')
        t = t.replace('$', '')
        t = re.sub(r'([.:;])\s*\*\s*', r'\1\n* ', t)
        return t

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Title'],
        fontSize=18,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=4,
        alignment=0
    )

    story.append(Paragraph(f"{analysis.ticker} Fundamental & Momentum Analysis", title_style))
    story.append(Paragraph(
        f"Sector: {'Commercial Bank' if is_bank else 'Non-Bank / Industrial'} | Analysis Date: {analysis.analysis_date.strftime('%B %d, %Y')}",
        styles['Normal']
    ))
    story.append(Spacer(1, 12))

    # Cell paragraph styles to guarantee text wrapping and prevent overlap
    th_style = ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=9, textColor=colors.whitesmoke, alignment=1)
    td_label = ParagraphStyle('TDLabel', fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#1e293b'), alignment=0)
    td_val = ParagraphStyle('TDVal', fontName='Helvetica', fontSize=9, textColor=colors.HexColor('#334155'), alignment=1)
    td_status = ParagraphStyle('TDStatus', fontName='Helvetica-Bold', fontSize=9, alignment=1)

    def get_color_hex(flag):
        return '#059669' if flag else '#dc2626'

    data = [[
        Paragraph("METRIC (LAYER 1 & 2)", th_style),
        Paragraph("VALUE", th_style),
        Paragraph("STATUS / VERDICT", th_style)
    ]]

    rows_to_build = []
    if is_bank:
        rows_to_build.append(('ROE', f"{raw['roe']}%", flags['is_efficient'], "PASS" if flags['is_efficient'] else "WATCH"))
        rows_to_build.append(('Real ROE', f"{raw['real_roe']}%", flags['is_wealth_creator'], "PASS" if flags['is_wealth_creator'] else "FAIL"))
        rows_to_build.append(('Cost-to-Income Ratio', f"{raw['cost_to_income']}%", True, "METRIC"))
    else:
        rows_to_build.append(('ROIC', f"{raw['roic']}%", flags['is_efficient'], "STRONG" if flags['is_efficient'] else "MODERATE"))
        rows_to_build.append(('Real ROIC', f"{raw['real_roic']}%", flags['is_wealth_creator'], "PASS" if flags['is_wealth_creator'] else "FAIL"))
        rows_to_build.append(('FCF Conversion', f"{raw['fcf_conv']}%", flags['is_cash_backed'], "PASS" if flags['is_cash_backed'] else "CAUTION"))

    rows_to_build.append(('Dividend Yield', f"{raw['div_yield']}%", True, "N/A"))
    rows_to_build.append(('Payout Ratio', f"{raw['payout']}%", flags['healthy_payout'], "HEALTHY" if flags['healthy_payout'] else "CAUTION"))
    rows_to_build.append((f"Forward EPS (Proj. {raw['period_analyzed']})", f"N{raw['forward_eps']}", True, "TRAJECTORY"))
    rows_to_build.append(('Forward P/E Ratio', f"{raw['forward_pe']}x", flags['is_undervalued_pe'], "UNDERVALUED" if flags['is_undervalued_pe'] else "FAIR / PREMIUM"))

    if mom.get('has_52w_data'):
        rows_to_build.append(('52-Week Range Position', f"{mom['range_pos_pct']}% from Low", True, "POSITIONING"))
    else:
        rows_to_build.append(('52-Week Range Position', "N/A", True, "OPTIONAL"))

    if mom.get('has_sma_data'):
        sma_sig = "BULLISH" if mom.get('golden_cross') else ("ABOVE SMA 200" if mom.get('above_sma_200') else "BEARISH")
        rows_to_build.append(('Moving Averages', f"SMA50: N{mom['sma_50']} | SMA200: N{mom['sma_200']}", True, sma_sig))
    else:
        rows_to_build.append(('Moving Averages', "N/A", True, "OPTIONAL"))

    rows_to_build.append(('Value-Momentum Setup', mom.get('matrix_status', 'N/A'), True, "SETUP"))

    t_style_commands = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
    ]

    for idx, (label, val, flag_ok, status_text) in enumerate(rows_to_build, start=1):
        color_hex = get_color_hex(flag_ok) if status_text in ["PASS", "FAIL", "STRONG"] else "#1e293b"
        status_style = ParagraphStyle(f'Status{idx}', parent=td_status, textColor=colors.HexColor(color_hex))

        data.append([
            Paragraph(label, td_label),
            Paragraph(str(val), td_val),
            Paragraph(status_text, status_style)
        ])

    t = Table(data, colWidths=[180, 202, 150])
    t.setStyle(TableStyle(t_style_commands))
    story.append(t)
    story.append(Spacer(1, 15))

    section_title_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Normal'],
        fontSize=12,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=10,
        spaceAfter=6
    )
    story.append(Paragraph("Analyst Commentary", section_title_style))

    header_style = ParagraphStyle(
        'CommentaryHeader',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#4f46e5'),
        fontName='Helvetica-Bold',
        spaceBefore=8,
        spaceAfter=3
    )

    body_style = ParagraphStyle(
        'CommentaryBody',
        parent=styles['Normal'],
        fontSize=9,
        leading=13,
        leftIndent=8,
        spaceAfter=4
    )

    clean_commentary = clean_text_for_pdf(analysis.ai_commentary)
    for line in clean_commentary.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.startswith('###'):
            header_text = re.sub(r'\*+', '', line.replace('###', '').strip())
            story.append(Paragraph(header_text, header_style))
        else:
            is_bullet = False
            if line.startswith('*') or line.startswith('-') or line.startswith('•'):
                is_bullet = True
                line = re.sub(r'^[*•-]\s*', '', line)
            line = re.sub(r'\*+([^*]+)\*+', r'<b>\1</b>', line)
            formatted_line = f"&bull; {line}" if is_bullet else line
            story.append(Paragraph(formatted_line, body_style))

    doc.build(story)
    buffer.seek(0)
    filename = f"{slugify(analysis.ticker)}_Analysis_{analysis.analysis_date.strftime('%Y-%m-%d')}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response