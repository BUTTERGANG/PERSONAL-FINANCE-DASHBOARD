"""
Run once to generate the Fernet encryption key.
Add the output value to Replit Secrets as ENCRYPTION_KEY.
Never commit this value anywhere.

Usage:
    python scripts/generate_key.py
"""

from cryptography.fernet import Fernet

key = Fernet.generate_key().decode()
print("\n" + "=" * 60)
print("  Add this to Replit Secrets as:  ENCRYPTION_KEY")
print("=" * 60)
print(f"\n  {key}\n")
print("  ⚠️  Save this somewhere safe.")
print("  If you lose it, all stored Plaid tokens become unreadable")
print("  and you will need to re-link all accounts.\n")
