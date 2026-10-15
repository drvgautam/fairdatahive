from __future__ import annotations

import hashlib
import hmac
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.config import settings
from app.core import auth
from app.core.exceptions import UnauthorizedError

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_KID = "test-key"


def _jwks() -> dict:
    jwk = RSAAlgorithm.to_jwk(_PRIVATE_KEY.public_key(), as_dict=True)
    jwk.update({"kid": _KID, "alg": "RS256", "use": "sig"})
    return {"keys": [jwk]}


def _token(**overrides) -> str:
    now = int(time.time())
    claims = {"sub": "user-1", "iss": settings.issuer_url, "iat": now, "exp": now + 300}
    claims.update(overrides)
    return jwt.encode(claims, _PRIVATE_KEY, algorithm="RS256", headers={"kid": _KID})


@pytest.fixture(autouse=True)
def _patch_jwks(monkeypatch):
    async def fake_fetch():
        return _jwks()

    monkeypatch.setattr(auth, "_fetch_jwks", fake_fetch)
    monkeypatch.setattr(settings, "keycloak_client_id", None)


async def test_valid_token_is_accepted():
    claims = await auth._decode_token(_token())
    assert claims["sub"] == "user-1"


async def test_wrong_issuer_is_rejected():
    with pytest.raises(UnauthorizedError):
        await auth._decode_token(_token(iss="https://evil.example/realms/x"))


async def test_expired_token_is_rejected():
    with pytest.raises(UnauthorizedError):
        await auth._decode_token(_token(exp=int(time.time()) - 10))


async def test_audience_is_enforced_when_client_id_set(monkeypatch):
    monkeypatch.setattr(settings, "keycloak_client_id", "fairdatahive-ui")
    with pytest.raises(UnauthorizedError):
        await auth._decode_token(_token(aud="other-client"))
    claims = await auth._decode_token(_token(aud="fairdatahive-ui"))
    assert claims["aud"] == "fairdatahive-ui"


async def test_hmac_signed_with_public_key_is_rejected():
    public_pem = _PRIVATE_KEY.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    def b64(data: bytes) -> str:
        return jwt.utils.base64url_encode(data).decode()

    header = {"kid": _KID, "alg": "HS256", "typ": "JWT"}
    payload = {"sub": "attacker", "iss": settings.issuer_url, "exp": int(time.time()) + 300}
    signing_input = f"{b64(json.dumps(header).encode())}.{b64(json.dumps(payload).encode())}"
    signature = hmac.new(public_pem, signing_input.encode(), hashlib.sha256).digest()
    forged = f"{signing_input}.{b64(signature)}"
    with pytest.raises(UnauthorizedError):
        await auth._decode_token(forged)
