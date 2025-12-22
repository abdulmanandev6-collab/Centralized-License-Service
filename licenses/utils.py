import secrets
import string


def generate_license_key():
    """
    Generate a unique license key.
    Format: 4 groups of 4 uppercase alphanumeric characters separated by hyphens
    Example: ABCD-1234-EFGH-5678
    """
    chars = string.ascii_uppercase + string.digits
    parts = []
    for i in range(4):
        part = ''.join(secrets.choice(chars) for _ in range(4))
        parts.append(part)
    return '-'.join(parts)

