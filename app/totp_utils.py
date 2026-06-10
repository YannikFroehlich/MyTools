import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote


TOTP_DIGITS = 6
TOTP_PERIOD = 30


def generate_totp_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _normalize_secret(secret):
    cleaned = (secret or "").replace(" ", "").upper()
    padding = "=" * ((8 - len(cleaned) % 8) % 8)
    return cleaned + padding


def _totp_at(secret, counter):
    key = base64.b32decode(_normalize_secret(secret), casefold=True)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** TOTP_DIGITS)).zfill(TOTP_DIGITS)


def current_totp(secret, for_time=None):
    timestamp = int(time.time() if for_time is None else for_time)
    return _totp_at(secret, timestamp // TOTP_PERIOD)


def verify_totp(secret, token, for_time=None, window=1):
    token = "".join(ch for ch in str(token or "") if ch.isdigit())
    if len(token) != TOTP_DIGITS or not secret:
        return False

    timestamp = int(time.time() if for_time is None else for_time)
    counter = timestamp // TOTP_PERIOD
    for offset in range(-window, window + 1):
        if hmac.compare_digest(_totp_at(secret, counter + offset), token):
            return True
    return False


def provisioning_uri(secret, username, issuer="MyTools"):
    label = f"{issuer}:{username}"
    return (
        "otpauth://totp/"
        f"{quote(label)}?secret={quote(secret)}&issuer={quote(issuer)}"
        f"&algorithm=SHA1&digits={TOTP_DIGITS}&period={TOTP_PERIOD}"
    )
