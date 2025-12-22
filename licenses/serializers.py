from rest_framework import serializers
from .models import Brand, Product, LicenseKey, License, LicenseStatus


class LicenseSerializer(serializers.ModelSerializer):
    product_slug = serializers.CharField(write_only=True, required=False)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug_read = serializers.CharField(source='product.slug', read_only=True)
    
    class Meta:
        model = License
        fields = ['id', 'product', 'product_slug', 'product_name', 'product_slug_read', 'status', 'expiration_date', 'max_seats', 'created_at']
        read_only_fields = ['id', 'product', 'created_at']


class LicenseKeySerializer(serializers.ModelSerializer):
    licenses = LicenseSerializer(many=True, read_only=True)
    
    class Meta:
        model = LicenseKey
        fields = ['id', 'key', 'brand', 'customer_email', 'licenses', 'created_at']
        read_only_fields = ['id', 'key', 'brand', 'created_at']


class ProvisionLicenseRequestSerializer(serializers.Serializer):
    customer_email = serializers.EmailField(required=True)
    products = serializers.ListField(
        child=serializers.DictField(),
        required=True,
        min_length=1
    )
    
    def validate_products(self, value):
        for product_data in value:
            if 'slug' not in product_data:
                raise serializers.ValidationError("Each product must have a 'slug' field")
        return value


class AddProductToLicenseRequestSerializer(serializers.Serializer):
    product_slug = serializers.CharField(required=True)
    expiration_date = serializers.DateTimeField(required=False, allow_null=True)
    max_seats = serializers.IntegerField(required=False, allow_null=True, min_value=1)

