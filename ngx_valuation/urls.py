from django.urls import path
from . import views

urlpatterns = [
    path('scan/', views.quick_scan_view, name='quick_scan'),
    path('results/<int:pk>/', views.analysis_results_view, name='analysis_results'),
    path('results/<int:pk>/pdf/', views.export_pdf_view, name='export_pdf'),
]
