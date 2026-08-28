"""
FastPST - Offline Cryptographic Licensing Engine
Provides 100% offline HMAC-SHA256 signed license verification,
expiration tracking, remaining days calculation, and anti-clock-rollback protection.
"""

import os
import sys
import json
import time
import hmac
import base64
import hashlib
import logging
import datetime
from typing import Tuple, Dict, Any, Optional

from fastpst.utils import get_app_directory

logger = logging.getLogger("fastpst.license")

# Dedicated Master Signing Secret for FastPST Offline Licenses
# (Used by keygen.py to sign and by FastPST to verify)
_LICENSE_SECRET_KEY = b"FASTPST-OFFLINE-SECURE-SIGNING-KEY-v1-9874a6bf2c1e"


def _get_license_file_path() -> str:
    """Returns the path to the saved license key file."""
    app_dir = get_app_directory()
    return os.path.join(app_dir, "fastpst.lic")


def generate_license_token(client: str, expiry_date: str, tier: str = "pro") -> str:
    """
    Generates a cryptographically signed offline license key token.
    expiry_date format: 'YYYY-MM-DD'
    """
    # Validate date format
    datetime.datetime.strptime(expiry_date, "%Y-%m-%d")

    payload = {
        "client": client.strip(),
        "expiry": expiry_date.strip(),
        "tier": tier.strip(),
        "issued_at": datetime.date.today().strftime("%Y-%m-%d")
    }

    # Encode payload as URL-safe base64 JSON string
    payload_json = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")

    # Compute HMAC-SHA256 signature
    sig = hmac.new(_LICENSE_SECRET_KEY, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()[:24]

    return f"FPST-{payload_b64}.{sig}"


def verify_license_token(key_str: str, db_manager=None) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Verifies an offline license key token.
    Returns (is_valid, message, info_dict).
    """
    if not key_str or not isinstance(key_str, str):
        return False, "No license key provided.", {"status": "missing", "days_remaining": 0}

    key_str = key_str.strip()
    if not key_str.startswith("FPST-") or "." not in key_str:
        return False, "Invalid license key format.", {"status": "invalid", "days_remaining": 0}

    try:
        raw_body = key_str[5:]  # strip 'FPST-'
        payload_b64, sig = raw_body.rsplit(".", 1)

        # 1. Verify Cryptographic HMAC Signature
        expected_sig = hmac.new(_LICENSE_SECRET_KEY, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
        if not hmac.compare_digest(sig.lower(), expected_sig.lower()):
            return False, "License signature verification failed (key is invalid or altered).", {
                "status": "invalid", "days_remaining": 0
            }

        # 2. Decode and parse payload
        # Restore base64 padding if needed
        pad_len = 4 - (len(payload_b64) % 4)
        if pad_len != 4:
            payload_b64 += "=" * pad_len
        payload_bytes = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))
        payload = json.loads(payload_bytes.decode("utf-8"))

        client = payload.get("client", "Unknown Client")
        expiry_str = payload.get("expiry")
        if not expiry_str:
            return False, "License key missing expiration date.", {"status": "invalid", "days_remaining": 0}

        expiry_date = datetime.datetime.strptime(expiry_str, "%Y-%m-%d").date()
        today = datetime.date.today()
        now_ts = time.time()

        # 3. Anti-Clock-Rollback Protection
        if db_manager:
            last_seen_ts = db_manager.get_last_clock_seen()
            # Allow max 1 hour clock skew (3600 seconds) for daylight saving / minor adjustments
            if last_seen_ts > 0 and (last_seen_ts - now_ts) > 86400:
                logger.warning(f"Clock rollback detected! Last recorded: {last_seen_ts}, Current: {now_ts}")
                return False, "System clock tampering detected. Please restore the system clock.", {
                    "status": "tampered",
                    "client": client,
                    "expiry": expiry_str,
                    "days_remaining": 0
                }
            # Record current valid timestamp as high-water mark
            db_manager.record_clock_seen(now_ts)

        # 4. Expiration Calculation
        days_remaining = (expiry_date - today).days

        if days_remaining < 0:
            return False, f"License expired on {expiry_str}.", {
                "status": "expired",
                "client": client,
                "expiry": expiry_str,
                "days_remaining": 0
            }

        status = "expiring_soon" if days_remaining <= 7 else "active"
        msg = f"Active ({days_remaining} day{'s' if days_remaining != 1 else ''} remaining)"

        return True, msg, {
            "status": status,
            "client": client,
            "expiry": expiry_str,
            "days_remaining": days_remaining,
            "tier": payload.get("tier", "pro")
        }

    except Exception as e:
        logger.error(f"License verification error: {e}")
        return False, f"Invalid license key ({e}).", {"status": "invalid", "days_remaining": 0}


def save_license(key_str: str) -> bool:
    """Saves the license key to disk."""
    try:
        lic_path = _get_license_file_path()
        with open(lic_path, "w", encoding="utf-8") as f:
            f.write(key_str.strip())
        return True
    except Exception as e:
        logger.error(f"Failed to save license file: {e}")
        return False


def load_saved_license() -> Optional[str]:
    """Loads the saved license key from disk if present."""
    try:
        lic_path = _get_license_file_path()
        if os.path.isfile(lic_path):
            with open(lic_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
    except Exception as e:
        logger.debug(f"Could not load license file: {e}")
    return None


def remove_saved_license():
    """Removes the saved license file."""
    try:
        lic_path = _get_license_file_path()
        if os.path.isfile(lic_path):
            os.remove(lic_path)
    except Exception:
        pass
