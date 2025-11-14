"""
Transaction enrichment service for adding categorization and other enrichments.
"""
from typing import Optional
import logging
from .categorization import TransactionCategorizer

logger = logging.getLogger(__name__)


class TransactionEnrichmentService:
    """
    Service that wraps categorization logic for transactions.

    Uses dependency injection pattern to allow flexible categorizer implementations.
    """

    def __init__(self, categorizer: TransactionCategorizer):
        """
        Initialize the enrichment service with a categorizer.

        Args:
            categorizer: Implementation of TransactionCategorizer interface
        """
        self.categorizer = categorizer

    def enrich_transaction(
        self,
        merchant_name: Optional[str] = None,
        description: Optional[str] = None
    ) -> str:
        """
        Enrich a transaction by determining its category.

        Uses merchant_name as primary source, falls back to description.

        Args:
            merchant_name: The merchant name from the transaction
            description: The transaction description

        Returns:
            Category name as a string (lowercase)
        """
        # Prioritize merchant_name over description
        text_to_categorize = merchant_name or description or ""

        if not text_to_categorize.strip():
            logger.debug("No text available for categorization")
            return "other"

        category = self.categorizer.categorize(text_to_categorize)
        logger.debug(f"Categorized '{text_to_categorize}' as '{category}'")

        return category

    def refresh_cache(self) -> None:
        """
        Refresh the categorizer's cache.

        Useful when patterns are updated in the database.
        """
        if hasattr(self.categorizer, 'refresh_cache'):
            self.categorizer.refresh_cache()
            logger.info("Categorizer cache refreshed")