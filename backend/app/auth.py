"""Clerk sign-in (#14): turn a Clerk session token into a user ID the backend can trust.

The frontend sends `Authorization: Bearer <token>` from Clerk's `getToken()`.
We check the token's RS256 signature against the Clerk instance's public keys
(JWKS), its issuer, its time window (exp / nbf), and, when present, its `azp`
("authorized party"): the website that requested it must be one of our
frontend origins. No Clerk secret key is needed.

Settings: CLERK_ISSUER (e.g. https://<app>.clerk.accounts.dev) and CLERK_JWKS_URL.
"""

import logging
import os
from collections.abc import Callable, Sequence

import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

CLERK_ISSUER_ENV = "CLERK_ISSUER"
CLERK_JWKS_URL_ENV = "CLERK_JWKS_URL"
CLOCK_LEEWAY_S = 5  # small allowance for clock differences between Clerk and us

# A function that returns the user ID in a valid token, or raises InvalidToken.
TokenVerifier = Callable[[str], str]


class InvalidToken(Exception):
    """The token can't be trusted. The message is safe to log, not to show users."""


def make_clerk_verifier(
    issuer: str,
    jwks_url: str,
    authorized_parties: Sequence[str],
    *,
    signing_key_for: Callable[[str], object] | None = None,
) -> TokenVerifier:
    """`signing_key_for` replaces the JWKS lookup (tests use a local key)."""
    if signing_key_for is None:
        client = PyJWKClient(jwks_url, cache_keys=True)

        def signing_key_for(token: str) -> object:
            return client.get_signing_key_from_jwt(token).key

    allowed = set(authorized_parties)

    def verify(token: str) -> str:
        try:
            claims = jwt.decode(
                token,
                signing_key_for(token),
                algorithms=["RS256"],
                issuer=issuer,
                leeway=CLOCK_LEEWAY_S,
                options={"require": ["exp", "iat", "iss", "sub"]},
            )
        except jwt.PyJWTError as error:  # bad signature, expired, wrong issuer, JWKS unreachable, ...
            raise InvalidToken(f"{type(error).__name__}: {error}") from None
        azp = claims.get("azp")
        if azp is not None and azp not in allowed:
            raise InvalidToken(f"token was issued to {azp!r}, not one of our frontend origins")
        return claims["sub"]

    return verify


def clerk_verifier_from_env(authorized_parties: Sequence[str]) -> TokenVerifier | None:
    """A verifier from CLERK_ISSUER and CLERK_JWKS_URL, or None if either is missing."""
    issuer = os.environ.get(CLERK_ISSUER_ENV, "").strip()
    jwks_url = os.environ.get(CLERK_JWKS_URL_ENV, "").strip()
    if not issuer or not jwks_url:
        return None
    return make_clerk_verifier(issuer, jwks_url, authorized_parties)
