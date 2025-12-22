"""
Management command to set up test data for US1 verification.
"""
from django.core.management.base import BaseCommand
from licenses.models import Brand, Product
import secrets


class Command(BaseCommand):
    help = 'Creates test brands and products for testing US1'

    def handle(self, *args, **options):
        # Create RankMath brand
        rankmath_brand, created = Brand.objects.get_or_create(
            name='RankMath',
            defaults={
                'api_key': 'rankmath-api-key-' + secrets.token_urlsafe(16),
                'is_active': True
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created RankMath brand with API key: {rankmath_brand.api_key}'))
        else:
            self.stdout.write(self.style.WARNING(f'RankMath brand already exists with API key: {rankmath_brand.api_key}'))

        # Create WP Rocket brand
        wprocket_brand, created = Brand.objects.get_or_create(
            name='WP Rocket',
            defaults={
                'api_key': 'wprocket-api-key-' + secrets.token_urlsafe(16),
                'is_active': True
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created WP Rocket brand with API key: {wprocket_brand.api_key}'))
        else:
            self.stdout.write(self.style.WARNING(f'WP Rocket brand already exists with API key: {wprocket_brand.api_key}'))

        # Create RankMath product
        rankmath_product, created = Product.objects.get_or_create(
            brand=rankmath_brand,
            slug='rankmath',
            defaults={
                'name': 'RankMath SEO',
                'is_active': True
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('Created RankMath product'))
        else:
            self.stdout.write(self.style.WARNING('RankMath product already exists'))

        # Create Content AI product (addon for RankMath)
        contentai_product, created = Product.objects.get_or_create(
            brand=rankmath_brand,
            slug='content-ai',
            defaults={
                'name': 'Content AI',
                'is_active': True
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('Created Content AI product'))
        else:
            self.stdout.write(self.style.WARNING('Content AI product already exists'))

        # Create WP Rocket product
        wprocket_product, created = Product.objects.get_or_create(
            brand=wprocket_brand,
            slug='wp-rocket',
            defaults={
                'name': 'WP Rocket',
                'is_active': True
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('Created WP Rocket product'))
        else:
            self.stdout.write(self.style.WARNING('WP Rocket product already exists'))

        self.stdout.write(self.style.SUCCESS('\n=== Test Data Setup Complete ==='))
        self.stdout.write(f'\nRankMath API Key: {rankmath_brand.api_key}')
        self.stdout.write(f'WP Rocket API Key: {wprocket_brand.api_key}')
        self.stdout.write('\nYou can now test US1 with these API keys!')

