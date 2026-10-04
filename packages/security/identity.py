"""OIDC/OAuth2-compatible user identity and permission scope models."""

from dataclasses import dataclass
import json


@dataclass(frozen=True)
class UserIdentity:
    user_id: str
    tenant_id: str
    roles: tuple[str, ...] = ("tax_analyst",)
    email: str = ""


@dataclass(frozen=True)
class PermissionScope:
    tenant_id: str
    user_id: str
    roles: tuple[str, ...] = ("tax_analyst",)
    allowed_matter_ids: tuple[str, ...] = ()
    classifications: tuple[str, ...] = ("PUBLIC_OFFICIAL",)

    def allows_matter(self, matter_id: str) -> bool:
        return "admin" in self.roles or matter_id in self.allowed_matter_ids

    def allows_classification(self, classification: str) -> bool:
        return classification in self.classifications or "admin" in self.roles


DEFAULT_PUBLIC_SCOPE = PermissionScope(
    tenant_id="public-commonwealth",
    user_id="public-reader",
    roles=("public_reader",),
    classifications=("PUBLIC_OFFICIAL", "PUBLIC_SECONDARY"),
)


def create_permission_scope(
    user: UserIdentity,
    allowed_matter_ids: tuple[str, ...] = (),
    classifications: tuple[str, ...] = ("PUBLIC_OFFICIAL",),
) -> PermissionScope:
    return PermissionScope(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        roles=user.roles,
        allowed_matter_ids=allowed_matter_ids,
        classifications=classifications,
    )


def authenticate_bearer_token(token: str) -> UserIdentity:
    """Validate a signed token; mock identities are never accepted."""
    from .oidc import OIDCAuthenticator

    scope = OIDCAuthenticator.from_env().authenticate(token.removeprefix("Bearer ").strip())
    return UserIdentity(scope.user_id, scope.tenant_id, scope.roles)
