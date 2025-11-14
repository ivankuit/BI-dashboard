"""
Forms for admin interface.
"""
from django import forms
from django.core.exceptions import ValidationError
from .models import Transaction
from datetime import date, timedelta


class AccountSummaryForm(forms.Form):
    """
    Form for generating account summary reports in admin interface.
    """

    @staticmethod
    def get_account_choices():
        accounts = Transaction.objects.values_list('account_id', flat=True).distinct().order_by('account_id')
        return [(acc_id, acc_id) for acc_id in accounts]

    account_id = forms.ChoiceField(
        label='Account',
        required=True,
        help_text='Select an account to generate summary',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'style': 'height: 100%; padding: 6px;',
        })
    )

    start_date = forms.DateField(
        label='Start Date',
        required=True,
        initial=lambda: date.today() - timedelta(days=30),
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        help_text='Start date for the report (YYYY-MM-DD)'
    )

    end_date = forms.DateField(
        label='End Date',
        required=True,
        initial=date.today,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        help_text='End date for the report (YYYY-MM-DD)'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['account_id'].choices = self.get_account_choices()

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date:
            if end_date < start_date:
                raise ValidationError({
                    'end_date': 'End date must be greater than or equal to start date.'
                })

            date_diff = (end_date - start_date).days
            if date_diff > 365:
                raise ValidationError({
                    'end_date': f'Date range cannot exceed 365 days (current: {date_diff} days).'
                })

        return cleaned_data