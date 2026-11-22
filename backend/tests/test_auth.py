"""Clerk session-token checks (#14), with a locally generated key (no Clerk)."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth import InvalidToken, clerk_verifier_from_env, make_clerk_verifier

ISSUER = "https://lucky-test.clerk.accounts.dev"
FRONTEND = "http://localhost:3000"

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def token(key=KEY, **overrides) -> str:
    now = int(time.time())
    claims = {"sub": "user_123", "iss": ISSUER, "iat": now, "nbf": now, "exp": now + 60, "azp": FRONTEND}
    claims.update(overrides)
    claims = {name: value for name, value in claims.items() if value is not None}
    return jwt.encode(claims, key, algorithm="RS256")


@pytest.fixture
def verify():
    return make_clerk_verifier(ISSUER, "unused://jwks", [FRONTEND], signing_key_for=lambda _: KEY.public_key())


def test_valid_token_returns_the_clerk_user_id(verify):
    assert verify(token()) == "user_123"


def test_token_signed_by_another_key_is_rejected(verify):
    with pytest.raises(InvalidToken):
        verify(token(key=OTHER_KEY))


def test_expired_token_is_rejected(verify):
    now = int(time.time())
    with pytest.raises(InvalidToken):
        verify(token(iat=now - 600, nbf=now - 600, exp=now - 300))


def test_token_not_valid_yet_is_rejected(verify):
    with pytest.raises(InvalidToken):
        verify(token(nbf=int(time.time()) + 300))


def test_token_from_another_issuer_is_rejected(verify):
    with pytest.raises(InvalidToken):
        verify(token(iss="https://evil.clerk.accounts.dev"))


def test_token_for_another_website_is_rejected(verify):
    with pytest.raises(InvalidToken):
        verify(token(azp="https://evil.example.com"))


def test_token_without_azp_is_accepted(verify):
    # Clerk omits azp for non-browser clients; the signature and issuer still bind it to our instance.
    assert verify(token(azp=None)) == "user_123"


def test_token_without_subject_is_rejected(verify):
    with pytest.raises(InvalidToken):
        verify(token(sub=None))


def test_garbage_is_rejected(verify):
    with pytest.raises(InvalidToken):
        verify("not-a-jwt")


def test_unsigned_token_is_rejected(verify):
    unsigned = jwt.encode({"sub": "user_123", "iss": ISSUER, "exp": int(time.time()) + 60}, None, algorithm="none")
    with pytest.raises(InvalidToken):
        verify(unsigned)


def test_key_lookup_failure_is_an_invalid_token():
    def unreachable(_token):
        raise jwt.PyJWKClientConnectionError("Clerk unreachable")

    verify = make_clerk_verifier(ISSUER, "unused://jwks", [FRONTEND], signing_key_for=unreachable)
    with pytest.raises(InvalidToken):
        verify(token())


def test_verifier_from_env_needs_issuer_and_jwks_url(monkeypatch):
    monkeypatch.delenv("CLERK_ISSUER", raising=False)
    monkeypatch.delenv("CLERK_JWKS_URL", raising=False)
    assert clerk_verifier_from_env([FRONTEND]) is None

    monkeypatch.setenv("CLERK_ISSUER", ISSUER)
    monkeypatch.setenv("CLERK_JWKS_URL", f"{ISSUER}/.well-known/jwks.json")
    assert callable(clerk_verifier_from_env([FRONTEND]))
