from django.db import models
from django.core.validators import MinLengthValidator, MaxLengthValidator
from django.db.models import Func
from decimal import Decimal

class Status(models.TextChoices):
    PENDING = 'P', 'pending'
    COMPLETED = 'C', 'completed'
    FAILED = 'F', 'failed'
    PROCESSING = 'I', 'processing'


class Account(models.Model):
    """
    Model representing financial accounts.
    account id being unique is a bit risky - more information would be required to figure out composite unique keys,
    perhaps bank name and account id
    """
    account_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="External account identifier"
    )

    name = models.CharField(
        max_length=255,
        help_text="Account name"
    )

    type = models.CharField(
        max_length=100,
        help_text="Account type (e.g., depository, credit, loan)"
    )

    subtype = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Account subtype (e.g., checking, savings, credit card)"
    )

    mask = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text="Last 4 digits of account number"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when record was created"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when record was last updated"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Account'
        verbose_name_plural = 'Accounts'

    def __str__(self):
        return f"{self.name} ({self.account_id})"


class Batch(models.Model):
    """
    Model representing batch ingestion requests.
    """
    batch_id = models.UUIDField(
        primary_key=True,
        db_default=Func(function="uuidv7"),
        editable=False,
        help_text="Unique batch identifier"
    )

    request_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="External request identifier"
    )

    total_transactions = models.IntegerField(
        help_text="Total number of transactions in this batch"
    )

    status = models.CharField(
        max_length=1,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        help_text="Current status of batch processing"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when batch was created"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when batch was last updated"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Batch'
        verbose_name_plural = 'Batches'

    def __str__(self):
        return f"Batch {self.batch_id} - {self.total_transactions} transactions"


class Transaction(models.Model):
    """
    Model representing financial transactions with enrichment capabilities.
    """

    transaction_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="External transaction identifier"
    )

    account_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Account identifier associated with this transaction"
    )

    batch = models.ForeignKey(
        Batch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        help_text="Batch this transaction belongs to"
    )

    amount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        help_text="Transaction amount"
    )

    currency = models.CharField(
        max_length=3,
        validators=[
            MinLengthValidator(3),
            MaxLengthValidator(3)
        ],
        help_text="ISO 4217 currency code (e.g., USD, EUR, GBP)"
    )

    date = models.DateTimeField(
        db_index=True,
        help_text="Transaction date and time"
    )

    authorized_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date the transaction was authorized"
    )

    merchant_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Name of the merchant"
    )

    description = models.TextField(
        help_text="Transaction description"
    )

    payment_channel = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Payment channel (e.g., online, in store, other)"
    )

    pending = models.BooleanField(
        default=False,
        help_text="Whether the transaction is pending"
    )

    category = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="Transaction category (populated by enrichment)"
    )

    ingestion_status = models.CharField(
        max_length=1,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        help_text="Current status of transaction ingestion"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when record was created"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when record was last updated"
    )

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['account_id', 'date']),
            models.Index(fields=['ingestion_status', 'created_at']),
            models.Index(fields=['category', 'date']),
        ]
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'

    def __str__(self):
        return f"{self.transaction_id} - {self.amount} {self.currency}"

    def __repr__(self):
        return f"<Transaction {self.transaction_id}: {self.amount} {self.currency}>"


class Category(models.Model):
    """
    Model representing transaction categories for enrichment.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Category name (e.g., shopping, income, transport)"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when category was created"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when category was last updated"
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


class CategoryPattern(models.Model):
    """
    Model representing patterns used to match transactions to categories.
    """
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='patterns',
        help_text="Category this pattern belongs to"
    )

    pattern = models.CharField(
        max_length=255,
        help_text="Pattern to match against merchant name or description"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when pattern was created"
    )

    class Meta:
        ordering = ['category__name', '-created_at']
        verbose_name = 'Category Pattern'
        verbose_name_plural = 'Category Patterns'
        constraints = [
            models.UniqueConstraint(
                fields=['category', 'pattern'],
                name='unique_category_pattern'
            )
        ]

    def __str__(self):
        return f"{self.category.name}: {self.pattern}"