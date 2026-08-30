"""JWT bearer token verification against Keycloak's JWKS endpoint (CLAUDE.md §26.1, ADR-0005).

Keycloak proves *who* is asking (a verified `sub` claim). It knows nothing about Colt
organizations — that resolution happens downstream, in `colt_application`'s
`ResolveOrganizationContext`, using the `User` table as the sole authority. This module's only
job is: is this a genuine, unexpired token issued by our configured realm for our API's audience?
"""

from __future__ import annotations

from typing import Any

import jwt
from jwt import PyJWKClient, PyJWTError


class TokenVerificationError(Exception):
    """The bearer token is missing, malformed, expired, or not from a trusted issuer.

    One exception type for every case, deliberately: the API boundary maps all of them to the
    same 401, and a more specific message would help an attacker distinguish "wrong signature"
    from "right signature, wrong audience" from "expired" — none of which the caller needs.
    """


class JwtVerifier:
    """Verifies a bearer token's signature, issuer, audience, and expiry.

    One instance per process. `PyJWKClient` caches the signing keys itself
    (`AUTH_JWKS_CACHE_SECONDS`), so this does not re-fetch Keycloak's JWKS endpoint on every
    request.
    """

    def __init__(self, *, issuer_url: str, audience: str, jwks_cache_seconds: int) -> None:
        self._issuer_url = issuer_url
        self._audience = audience
        jwks_uri = f"{issuer_url}/protocol/openid-connect/certs"
        self._jwk_client = PyJWKClient(jwks_uri, cache_keys=True, lifespan=jwks_cache_seconds)

    def verify(self, token: str) -> dict[str, Any]:
        """Return the token's verified claims, or raise `TokenVerificationError`."""
        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token)
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer_url,
                options={"require": ["exp", "iat", "sub"]},
            )
        except PyJWTError as exc:
            raise TokenVerificationError("Bearer token failed verification.") from exc
        return claims
