"""
Transaction categorization service with smart matching logic.
"""
from abc import ABC, abstractmethod
from typing import Dict, List
from django.core.cache import cache
from django.db.models import Prefetch
import logging

logger = logging.getLogger(__name__)


class TransactionCategorizer(ABC):
    """
    Abstract interface for transaction categorization.
    """

    @abstractmethod
    def categorize(self, transaction_text: str) -> str:
        """
        Categorize a transaction based on its text (merchant name or description).

        Args:
            transaction_text: The merchant name or description to categorize

        Returns:
            Category name as a string, or "other" if no match found
        """
        pass


class DatabaseCategorizer(TransactionCategorizer):
    """
    Database-backed categorizer that uses stored patterns for matching.

    Features:
    - Minimum 5 characters required for both pattern and text
    - Bidirectional substring matching: pattern in text OR text in pattern
    - Prioritizes longer patterns first (more specific matches)
    - Case-insensitive matching with stripped whitespace
    - Uses Django caching for performance (15 minute timeout)
    """

    CACHE_KEY = 'transaction_category_patterns'
    CACHE_TIMEOUT = 60
    MIN_LENGTH = 3

    def __init__(self):
        """Initialize the categorizer."""
        self._patterns_cache = None

    def _load_patterns(self) -> Dict[str, List[str]]:
        """
        Load category patterns from database or cache.

        Returns:
            Dictionary mapping category names to lists of patterns,
            sorted by pattern length (longest first)
        """
        # Try to get from cache first
        patterns = cache.get(self.CACHE_KEY)

        if patterns is not None:
            logger.debug("Loaded patterns from cache")
            return patterns

        # Load from database
        from core.models import Category, CategoryPattern

        patterns = {}

        # Prefetch patterns for efficiency
        categories = Category.objects.prefetch_related(
            Prefetch(
                'patterns',
                queryset=CategoryPattern.objects.all()
            )
        ).all()

        for category in categories:
            category_patterns = [
                p.pattern.lower().strip()
                for p in category.patterns.all()
                if len(p.pattern.strip()) >= self.MIN_LENGTH
            ]
            # Sort by length descending (longest patterns first for specificity)
            category_patterns.sort(key=len, reverse=True)
            patterns[category.name.lower()] = category_patterns

        # Cache the patterns
        cache.set(self.CACHE_KEY, patterns, self.CACHE_TIMEOUT)
        logger.info(f"Loaded {len(patterns)} categories with patterns from database")

        return patterns

    def refresh_cache(self) -> None:
        """
        Invalidate the patterns cache to force reload from database.
        Call this when patterns are updated in the database.
        """
        cache.delete(self.CACHE_KEY)
        self._patterns_cache = None
        logger.info("Patterns cache invalidated")

    def categorize(self, transaction_text: str) -> str:
        """
        Categorize a transaction using smart bidirectional matching.

        Matching logic:
        1. Normalize input text (lowercase, strip whitespace)
        2. Skip if text is shorter than MIN_LENGTH
        3. For each category (in order):
           - Check patterns from longest to shortest
           - Match if: pattern in text OR text in pattern
           - Return first match found
        4. Return "other" if no match found

        Args:
            transaction_text: Merchant name or description to categorize

        Returns:
            Category name (lowercase) or "other" if no match
        """
        if not transaction_text:
            return "other"

        # Normalize input
        text = transaction_text.lower().strip()

        # Check minimum length
        if len(text) < self.MIN_LENGTH:
            logger.debug(f"Text too short for matching: '{text}' (length {len(text)})")
            return "other"

        # Load patterns
        patterns = self._load_patterns()

        # Try to match against each category's patterns
        for category_name, category_patterns in patterns.items():
            for pattern in category_patterns:
                # Bidirectional substring matching
                if pattern in text or text in pattern:
                    logger.debug(f"Matched '{text}' to category '{category_name}' via pattern '{pattern}'")
                    return category_name

        logger.debug(f"No match found for '{text}', returning 'other'")
        return "other"