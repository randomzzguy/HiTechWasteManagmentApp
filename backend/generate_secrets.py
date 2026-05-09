#!/usr/bin/env python3
"""
Generate secure secrets for Hi-Tech Waste Management application.
Run this script to generate all required secrets for production deployment.
"""

import secrets
import string


def generate_password(length=32, include_special=True):
    """Generate a secure random password."""
    chars = string.ascii_letters + string.digits
    if include_special:
        chars += "!@#$%^&*()_+-=[]{}|;:,.<>?"
    return ''.join(secrets.choice(chars) for _ in range(length))


def generate_jwt_secret(length=64):
    """Generate a secure JWT secret (minimum 64 characters recommended)."""
    return secrets.token_urlsafe(length)


def generate_minio_credentials():
    """Generate MinIO access key and secret key."""
    # Access key: 3-20 characters, only alphanumeric and dot, dash, underscore
    access_chars = string.ascii_letters + string.digits + '.-_'
    access_key = ''.join(secrets.choice(access_chars) for _ in range(20))
    
    # Secret key: 8-40 characters
    secret_key = generate_password(40)
    
    return access_key, secret_key


def main():
    print("=" * 70)
    print("Hi-Tech Waste Management - Secure Secrets Generator")
    print("=" * 70)
    print()
    
    # Generate all secrets
    postgres_password = generate_password(32)
    jwt_secret = generate_jwt_secret(64)
    nextauth_secret = generate_jwt_secret(64)
    minio_access_key, minio_secret_key = generate_minio_credentials()
    
    print("Generated secrets:")
    print("-" * 70)
    print()
    
    print(f"POSTGRES_PASSWORD={postgres_password}")
    print()
    print(f"JWT_SECRET={jwt_secret}")
    print()
    print(f"NEXTAUTH_SECRET={nextauth_secret}")
    print()
    print(f"MINIO_ACCESS_KEY={minio_access_key}")
    print()
    print(f"MINIO_SECRET_KEY={minio_secret_key}")
    print()
    
    print("=" * 70)
    print("Add these to your .env file:")
    print("=" * 70)
    print()
    print(f"POSTGRES_PASSWORD={postgres_password}")
    print(f"DATABASE_URL=postgresql://hitech:{postgres_password}@localhost:5432/hitech_waste")
    print(f"JWT_SECRET={jwt_secret}")
    print(f"NEXTAUTH_SECRET={nextauth_secret}")
    print(f"MINIO_ACCESS_KEY={minio_access_key}")
    print(f"MINIO_SECRET_KEY={minio_secret_key}")
    print()
    print("=" * 70)
    print("⚠️  IMPORTANT: Store these secrets securely!")
    print("   - Never commit .env file to version control")
    print("   - Use a secrets manager in production")
    print("   - Rotate secrets regularly")
    print("=" * 70)


if __name__ == "__main__":
    main()
