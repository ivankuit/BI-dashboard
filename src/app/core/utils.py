"""
Utility functions for API validation and helpers.
"""
from datetime import datetime, date
from django.http import Http404
from rest_framework.exceptions import ValidationError
from .models import Transaction


def validate_date_range(start_date_str: str, end_date_str: str) -> tuple[date, date]:
    """
    Validate and parse date range parameters.

    Args:
        start_date_str: Start date in YYYY-MM-DD format
        end_date_str: End date in YYYY-MM-DD format

    Returns:
        Tuple of (start_date, end_date) as date objects

    Raises:
        ValidationError: If dates are invalid, end_date < start_date, or range > 365 days
    """
    # Parse start_date
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        raise ValidationError({
            'error': 'Invalid date format',
            'detail': 'start_date must be in YYYY-MM-DD format'
        })

    # Parse end_date
    try:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        raise ValidationError({
            'error': 'Invalid date format',
            'detail': 'end_date must be in YYYY-MM-DD format'
        })

    # Validate end_date >= start_date
    if end_date < start_date:
        raise ValidationError({
            'error': 'Invalid date range',
            'detail': 'end_date must be greater than or equal to start_date'
        })

    # Validate date range <= 365 days
    date_diff = (end_date - start_date).days
    if date_diff > 365:
        raise ValidationError({
            'error': 'Invalid date range',
            'detail': f'Date range exceeds maximum of 365 days (provided: {date_diff} days)'
        })

    return start_date, end_date


def validate_account(account_id: str) -> bool:
    """
    Validate that an account exists by checking if there are any transactions for it.

    Args:
        account_id: The account identifier to validate

    Returns:
        True if account exists (has transactions)

    Raises:
        Http404: If account doesn't exist
    """

    if not Transaction.objects.filter(account_id=account_id).exists():
        raise Http404({
            'detail': 'Account not found'
        })

    return True