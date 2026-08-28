#!/usr/bin/env python3
"""
FastPST - Developer License Key Generator
Run this tool on your PC to issue signed offline license keys for clients.
"""

import sys
import os
import argparse
import datetime

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastpst.license import generate_license_token, verify_license_token


def main():
    parser = argparse.ArgumentParser(
        description="FastPST Offline License Key Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python keygen.py --client "Acme Corp" --days 30
  python keygen.py --client "John Doe" --expiry 2026-12-31
  python keygen.py (interactive wizard mode)
        """
    )
    parser.add_argument("-c", "--client", help="Customer name or organization")
    parser.add_argument("-d", "--days", type=int, help="License duration in days (from today)")
    parser.add_argument("-e", "--expiry", help="Exact expiration date (format: YYYY-MM-DD)")
    parser.add_argument("-t", "--tier", default="pro", help="License tier (default: pro)")

    args = parser.parse_args()

    client = args.client
    expiry = args.expiry
    days = args.days
    tier = args.tier

    # Interactive mode if arguments are missing
    if not client:
        print("=" * 65)
        print("       FastPST Offline License Key Generator Wizard")
        print("=" * 65)
        try:
            client = input("Enter Client Name / Organization: ").strip()
            while not client:
                client = input("Client Name cannot be empty. Please enter: ").strip()

            choice = input("Enter duration type ([1] Number of Days, [2] Specific Date): ").strip()
            if choice == "2":
                expiry = input("Enter Expiration Date (YYYY-MM-DD, e.g. 2026-12-31): ").strip()
            else:
                days_input = input("Enter Number of Days (e.g. 30, 90, 365) [default 30]: ").strip() or "30"
                days = int(days_input)
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(0)

    # Calculate expiration date
    if days is not None and not expiry:
        today = datetime.date.today()
        exp_date = today + datetime.timedelta(days=days)
        expiry = exp_date.strftime("%Y-%m-%d")

    if not expiry:
        print("[ERROR] Please specify either --days or --expiry YYYY-MM-DD")
        sys.exit(1)

    try:
        # Validate date format
        exp_dt = datetime.datetime.strptime(expiry, "%Y-%m-%d").date()
        today = datetime.date.today()
        days_left = (exp_dt - today).days
    except ValueError:
        print(f"[ERROR] Invalid date format '{expiry}'. Please use YYYY-MM-DD (e.g. 2026-12-31).")
        sys.exit(1)

    # Generate Token
    token = generate_license_token(client=client, expiry_date=expiry, tier=tier)

    # Verify generated token
    is_valid, msg, details = verify_license_token(token)

    print("\n" + "=" * 65)
    print("                 LICENSE GENERATED SUCCESSFULLY")
    print("=" * 65)
    print(f"  • Client Name:    {client}")
    print(f"  • Expiration:     {expiry} ({days_left} days remaining)")
    print(f"  • License Tier:   {tier.upper()}")
    print(f"  • Status:         {msg}")
    print("-" * 65)
    print("  LICENSE KEY (Send this exact key string to your client):")
    print(f"\n  {token}\n")
    print("=" * 65)
    print("Clients can click the bottom license space in FastPST and paste this key.")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
