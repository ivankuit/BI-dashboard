"""
Management command to seed initial transaction categories and patterns.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Category, CategoryPattern


class Command(BaseCommand):
    """
    Seed initial categories with common transaction patterns.

    Usage:
        python manage.py seed_categories
    """

    help = 'Seed initial transaction categories with common patterns'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing categories before seeding',
        )

    def handle(self, *args, **options):
        categories_data = {
            'groceries': [
                'shoprite',
                'checkers',
                'pick n pay',
                'woolworths',
                'grocery',
                'safeway',
                'kroger',
                'whole foods',
                'trader joes',
                'walmart',
                'costco',
            ],
            'shopping': [
                'takealot',
                'amazon',
                'target',
                'ebay',
                'etsy',
                'best buy',
                'ikea',
                'home depot',
                "lowe's",
                'macys',
                'nordstrom',
                'zara',
                'h&m',
                'nike',
                'adidas',
            ],
            'income': [
                'salary',
                'payroll',
                'deposit',
                'direct deposit',
                'payment received',
                'transfer from',
                'refund',
                'reimbursement',
                'dividend',
                'interest',
            ],
            'transport': [
                'engen',
                'shell',
                'uber',
                'lyft',
                'taxi',
                'gas station',
                'fuel',
                'petrol',
                'chevron',
                'exxon',
                'mobil',
                'bp gas',
                'parking',
                'metro',
                'transit',
                'airline',
                'delta',
                'united',
                'american airlines',
                'southwest',
            ],
            'entertainment': [
                'dstv',
                'multichoice',
                'netflix',
                'spotify',
                'apple music',
                'youtube premium',
                'hulu',
                'disney+',
                'hbo',
                'prime video',
            ],
            'software': [
                'apple.com',
                'google',
                'microsoft',
                'adobe',
                'github',
                'aws',
                'digitalocean',
                'heroku',
                'slack',
                'zoom',
                'dropbox',
                'icloud',
            ],
            'restaurants': [
                "nando's",
                'kfc',
                'steers',
                'restaurant',
                'cafe',
                'starbucks',
                'dunkin',
                "mcdonald's",
                'burger king',
                'subway',
                'chipotle',
                'panera',
                'pizza',
                'dominos',
                'papa johns',
                'taco bell',
                'wendys',
                'chick-fil-a',
                'food',
                'dining',
            ],
            'utilities': [
                'eskom',
                'mtn',
                'vodacom',
                'telkom',
                'city of cape town',
                'city of johannesburg',
                'electric',
                'electricity',
                'power',
                'gas company',
                'water',
                'internet',
                'comcast',
                'verizon',
                'at&t',
                'spectrum',
                't-mobile',
                'sprint',
                'phone bill',
                'cable',
                'mobile',
                'cell phone',
            ],
        }

        created_count = 0
        pattern_count = 0

        with transaction.atomic():
            for category_name, patterns in categories_data.items():
                category, created = Category.objects.get_or_create(name=category_name)

                if created:
                    created_count += 1

                for pattern_text in patterns:
                    pattern, pattern_created = CategoryPattern.objects.get_or_create(
                        category=category,
                        pattern=pattern_text
                    )
                    if pattern_created:
                        pattern_count += 1
