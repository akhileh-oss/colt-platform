"""Identity resolution (CLAUDE.md §22) — deterministic normalization and matching, not an LLM
judgment call (§2.1).

§22 explicitly forbids merging records "solely on fuzzy name similarity," so every matcher here
is an *exact* match on a normalized value; the only place "confidence" enters is as a gate on
whether a name-based match (§22's layers 4-5) is attempted at all, never as a fuzziness
threshold on the comparison itself.
"""

from __future__ import annotations

import re

#: §22's layer 4/5 name-based matching is the weakest signal in the list (no provider ID, no
#: email, no LinkedIn URL) - gated by a minimum candidate confidence so a low-confidence
#: provider guess can never silently merge into an existing record by name alone.
DEFAULT_NAME_MATCH_CONFIDENCE_THRESHOLD = 0.75

_WWW_PREFIX = re.compile(r"^www\.")
_URL_SCHEME = re.compile(r"^https?://")


def normalize_domain(value: str) -> str:
    """Lower-cases, strips a leading `http(s)://`, a leading `www.`, and any path/query."""
    stripped = _URL_SCHEME.sub("", value.strip().lower())
    stripped = _WWW_PREFIX.sub("", stripped)
    return stripped.split("/")[0].split("?")[0]


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_linkedin_url(value: str) -> str:
    """Lower-cases, strips scheme/`www.`, and a trailing slash, so
    `https://www.linkedin.com/in/janedoe/` and `linkedin.com/in/janedoe` match."""
    stripped = _URL_SCHEME.sub("", value.strip().lower())
    stripped = _WWW_PREFIX.sub("", stripped)
    return stripped.rstrip("/")


def normalize_name(value: str) -> str:
    return " ".join(value.strip().lower().split())
