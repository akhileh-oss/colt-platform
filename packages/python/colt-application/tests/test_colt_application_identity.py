from __future__ import annotations

from colt_application.identity import (
    normalize_domain,
    normalize_email,
    normalize_linkedin_url,
    normalize_name,
)


def test_normalize_domain_strips_scheme_www_and_path() -> None:
    assert normalize_domain("https://www.Acme.com/about") == "acme.com"
    assert normalize_domain("acme.com") == "acme.com"
    assert normalize_domain("http://acme.com?utm=1") == "acme.com"


def test_normalize_email_lowercases_and_trims() -> None:
    assert normalize_email("  Jane.Doe@Acme.COM  ") == "jane.doe@acme.com"


def test_normalize_linkedin_url_strips_scheme_www_and_trailing_slash() -> None:
    assert (
        normalize_linkedin_url("https://www.linkedin.com/in/JaneDoe/") == "linkedin.com/in/janedoe"
    )
    assert normalize_linkedin_url("linkedin.com/in/janedoe") == "linkedin.com/in/janedoe"


def test_normalize_name_collapses_whitespace_and_lowercases() -> None:
    assert normalize_name("  Jane   Doe ") == "jane doe"
