from django.shortcuts import render, redirect
from .forms import AnalysisForm

def quick_scan_view(request):
    form = AnalysisForm()
    results = None

    if request.method == "POST":
        form = AnalysisForm(request.POST)
        if form.is_valid():
            # Save the manual entry to the DB
            analysis = form.save()

            # TODO: Trigger the services.py math and AI commentary here
            return redirect('analysis_results', pk=analysis.pk)

    return render(request, 'ngx_valuation/scan_form.html', {
        'form': form,
        'title': 'Layer 1: Quick Scan'
    })