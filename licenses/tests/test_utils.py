"""
Unit tests for utility functions.
"""
import pytest
from licenses.utils import generate_license_key


class TestGenerateLicenseKey:
    def test_generate_license_key_format(self):
        key = generate_license_key()
        parts = key.split('-')
        assert len(parts) == 4
        assert all(len(part) == 4 for part in parts)
        assert all(c.isalnum() for part in parts for c in part)

    def test_generate_license_key_uniqueness(self):
        keys = [generate_license_key() for _ in range(100)]
        assert len(keys) == len(set(keys))

    def test_generate_license_key_length(self):
        key = generate_license_key()
        assert len(key) == 19

