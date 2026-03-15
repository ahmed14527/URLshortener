

import secrets
import string
from typing import Optional

from django.conf import settings

from urls_app.models import ShortenedURL

# Alphabet used for auto-generated codes (no confusing chars like 0/O, 1/l)
_ALPHABET = string.ascii_letters + string.digits
_MAX_ATTEMPTS = 10


def generate_short_code(length: Optional[int] = None) -> str:
   
    if length is None:
        length = getattr(settings, "SHORT_CODE_LENGTH", 6)

    for attempt in range(_MAX_ATTEMPTS):
        # secrets.choice is cryptographically random
        code = "".join(secrets.choice(_ALPHABET) for _ in range(length))

        if not ShortenedURL.objects.filter(short_code=code).exists():
            return code

        # Very unlikely, but increase length after several collisions
        if attempt >= 5:
            length += 1

    raise RuntimeError(
        f"Could not generate a unique short code after {_MAX_ATTEMPTS} attempts. "
        "Consider increasing SHORT_CODE_LENGTH in settings."
    )


def validate_custom_alias(alias: str) -> str:
  
    import re

    max_len = getattr(settings, "CUSTOM_ALIAS_MAX_LENGTH", 30)
    alias = alias.strip().lower()

    if len(alias) < 3:
        raise ValueError("Custom alias must be at least 3 characters long.")

    if len(alias) > max_len:
        raise ValueError(f"Custom alias must be at most {max_len} characters long.")

    # Only allow safe URL characters
    if not re.match(r"^[a-z0-9_-]+$", alias):
        raise ValueError(
            "Custom alias may only contain letters, digits, hyphens, and underscores."
        )

    # Reserved paths that would conflict with the application's URL structure
    reserved = {"api", "admin", "r", "static", "media", "health"}
    if alias in reserved:
        raise ValueError(f"'{alias}' is a reserved word and cannot be used as an alias.")

    if ShortenedURL.objects.filter(short_code=alias).exists():
        raise ValueError(f"The alias '{alias}' is already taken. Please choose another.")

    return alias
