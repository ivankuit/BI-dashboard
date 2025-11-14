from django.contrib import admin
from django.core.cache import cache
from django.urls import path
from django.shortcuts import render
from django.contrib import messages
from .models import Account, Batch, Transaction, Category, CategoryPattern
from .forms import AccountSummaryForm
from .views import AccountSummaryAPIView


class CategoryPatternInline(admin.TabularInline):
    """
    Inline admin for category patterns.
    Allows editing patterns directly within the category admin page.
    """
    model = CategoryPattern
    extra = 3
    fields = ['pattern', 'created_at']
    readonly_fields = ['created_at']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """
    Admin interface for Category model with inline pattern editing.
    """
    list_display = ['name', 'pattern_count', 'created_at', 'updated_at']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [CategoryPatternInline]

    def pattern_count(self, obj):
        """Display the count of patterns for this category."""
        return obj.patterns.count()
    pattern_count.short_description = 'Patterns'

    def save_model(self, request, obj, form, change):
        """Override save to clear cache when category is saved."""
        super().save_model(request, obj, form, change)
        cache.delete('transaction_category_patterns')

    def delete_model(self, request, obj):
        """Override delete to clear cache when category is deleted."""
        super().delete_model(request, obj)
        cache.delete('transaction_category_patterns')


@admin.register(CategoryPattern)
class CategoryPatternAdmin(admin.ModelAdmin):
    """
    Admin interface for CategoryPattern model.
    """
    list_display = ['pattern', 'category', 'created_at']
    list_filter = ['category']
    search_fields = ['pattern', 'category__name']
    readonly_fields = ['created_at']

    def save_model(self, request, obj, form, change):
        """Override save to clear cache when pattern is saved."""
        super().save_model(request, obj, form, change)
        cache.delete('transaction_category_patterns')

    def delete_model(self, request, obj):
        """Override delete to clear cache when pattern is deleted."""
        super().delete_model(request, obj)
        cache.delete('transaction_category_patterns')


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    """Admin interface for Account model."""
    list_display = ['account_id', 'name', 'type', 'subtype', 'mask', 'created_at']
    search_fields = ['account_id', 'name']
    list_filter = ['type', 'subtype']
    readonly_fields = ['created_at', 'updated_at']

    change_list_template = 'admin/core/account_changelist.html'


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    """Admin interface for Batch model."""
    list_display = ['batch_id', 'request_id', 'total_transactions', 'status', 'created_at', 'updated_at']
    list_filter = ['status']
    search_fields = ['batch_id', 'request_id']
    readonly_fields = ['batch_id', 'created_at', 'updated_at']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """Admin interface for Transaction model."""
    list_display = [
        'transaction_id', 'account_id', 'merchant_name', 'amount',
        'currency', 'category', 'date', 'ingestion_status'
    ]
    list_filter = ['ingestion_status', 'category', 'currency', 'payment_channel']
    search_fields = ['transaction_id', 'account_id', 'merchant_name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'date'

    change_list_template = 'admin/core/transaction_changelist.html'


# Custom Admin Views

def account_summary_view(request):
    """
    View for account summary analytics.
    Displays a form to select account and date range, then shows API results.
    """
    context = {
        **admin.site.each_context(request),
        'title': 'Account Summary Analytics',
        'form': None,
        'summary_data': None,
        'error': None,
    }

    if request.method == 'POST':
        form = AccountSummaryForm(request.POST)
        if form.is_valid():
            # Get form data
            account_id = form.cleaned_data['account_id']
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']

            # Call the API view internally
            api_view = AccountSummaryAPIView()

            # Create a mock request with query params
            from django.test import RequestFactory
            from rest_framework.request import Request

            factory = RequestFactory()
            mock_request = factory.get(
                f'/api/reports/account/{account_id}/summary/',
                {'start_date': start_date.strftime('%Y-%m-%d'),
                 'end_date': end_date.strftime('%Y-%m-%d')}
            )
            # Wrap it in DRF Request
            drf_request = Request(mock_request)

            # Call the API view
            response = api_view.get(drf_request, account_id)

            if response.status_code == 200:
                context['summary_data'] = response.data
                messages.success(request, 'Account summary generated successfully!')
            else:
                context['error'] = response.data
                messages.error(request, 'Failed to generate account summary.')

        context['form'] = form
    else:
        # GET request - show empty form
        context['form'] = AccountSummaryForm()

    return render(request, 'admin/core/account_summary.html', context)


# Add custom URLs to admin site
original_get_urls = admin.site.get_urls

def custom_admin_urls():
    """Add custom admin URLs."""
    urls = original_get_urls()
    custom_urls = [
        path('analytics/account-summary/',
             admin.site.admin_view(account_summary_view),
             name='account_summary_analytics'),
    ]
    return custom_urls + urls

admin.site.get_urls = custom_admin_urls
