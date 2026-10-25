"""Authentication for the trusted chat backend's public-corpus calls."""

from dataclasses import dataclass
import hmac
import os

from packages.security import PermissionScope


@dataclass(frozen=True)
class ServiceTokenAuthenticator:
    """Accept one configured bearer secret and issue a least-privilege scope."""

    api_key: str

    @classmethod
    def from_env(cls):
        key = os.environ.get("FINTAX_CHAT_SERVICE_API_KEY", "").strip()
        return cls(key) if key else None

    def authenticate(self, authorization: str | None) -> PermissionScope | None:
        if not authorization or not authorization.startswith("Bearer "):
            return None
        token = authorization[7:]
        try:
            token_bytes = token.encode("ascii")
            expected_bytes = self.api_key.encode("ascii")
        except UnicodeEncodeError:
            return None
        if not hmac.compare_digest(token_bytes, expected_bytes):
            return None
        return PermissionScope(
            tenant_id="fintax-chat",
            user_id="fintax-backend",
            roles=("tax_analyst",),
            classifications=("PUBLIC_OFFICIAL",),
        )
