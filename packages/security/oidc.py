"""Signature-verified OIDC access tokens with issuer, audience and expiry checks."""

import os
from urllib.parse import urlsplit

import jwt

from .identity import PermissionScope


class OIDCAuthenticator:
    def __init__(self, issuer: str, audience: str, jwks_url: str, key_client=None):
        for url in (issuer, jwks_url):
            parsed = urlsplit(url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.fragment:
                raise ValueError("OIDC issuer and JWKS URL must use HTTPS")
        if not audience:
            raise ValueError("OIDC audience is required")
        self.issuer, self.audience = issuer, audience
        self.keys = key_client or jwt.PyJWKClient(jwks_url, timeout=10)

    @classmethod
    def from_env(cls):
        return cls(*(os.environ.get(f"FINTAX_OIDC_{key}", "") for key in ("ISSUER", "AUDIENCE", "JWKS_URL")))

    def authenticate(self, token: str) -> PermissionScope:
        try:
            key = self.keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, key, algorithms=["RS256"], issuer=self.issuer,
                                audience=self.audience, options={"require": ["exp", "iat", "sub", "tid"]})
            if any(not isinstance(claims[k], str) or not claims[k].strip() for k in ("sub", "tid")):
                raise ValueError("Invalid identity")
            matters = claims.get("matter_ids", [])
            if not isinstance(matters, list) or any(not isinstance(m, str) or not m.strip() for m in matters):
                raise ValueError("Invalid matter grants")
            # This API serves only the frozen public corpus. Tokens cannot elevate it.
            return PermissionScope(claims["tid"], claims["sub"], ("tax_analyst",), tuple(matters))
        except Exception:
            raise ValueError("Invalid access token") from None
