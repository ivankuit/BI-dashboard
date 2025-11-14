from django.urls import path
from .views import BatchIngestionView, AccountSummaryAPIView

urlpatterns = [
    path('integrations/transactions/', BatchIngestionView.as_view(), name='batch-ingestion'),
    path('reports/account/<str:account_id>/summary/', AccountSummaryAPIView.as_view(), name='account-summary'),
]