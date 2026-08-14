from dataclasses import dataclass
from typing import Optional

import logging

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from app.core.config import get_settings
from app.core.supabase import get_user_client

settings = get_settings()
logger = logging.getLogger("localmart.auth")

# auto_error=False so we can return a clean 401 for public-but-personalizable
# routes instead of FastAPI's default error shape.
bearer_scheme = HTTPBearer(auto_error=False)

# Supabase projects created since the JWT Signing Keys rollout sign access
# tokens asymmetrically (ES256) by default and publish the public keys here.
# jwt.PyJWKClient fetches + caches them and picks the right one by the
# token's `kid` header, so this handles key rotation automatically (it's why
# the dashboard shows both a "current" and "previous" key — old tokens
# signed with the previous key still verify fine).
_jwks_client = jwt.PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")


@dataclass
class CurrentUser:
    id: str
    email: Optional[str]
    role: str
    access_token: str


def _decode_token(token: str) -> dict:
    try:
        # leeway=30 tolerates up to 30s of clock drift between this machine
        # and Supabase's auth server when checking iat/exp/nbf. Without it,
        # a local clock that's even a couple seconds ahead makes PyJWT
        # reject freshly-minted tokens as "not yet valid" (ImmatureSignatureError),
        # which is why /me was intermittently 401ing right after sign-in.
        alg = jwt.get_unverified_header(token).get("alg")

        if alg == "HS256":
            # Legacy shared-secret projects (Project Settings -> API -> JWT
            # Keys -> "Legacy JWT Secret" tab). Skipped entirely for projects
            # on the newer asymmetric keys, which sign with ES256/RS256.
            if not settings.supabase_jwt_secret:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Your session is invalid or has expired.",
                )
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                leeway=30,
            )

        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=[alg],
            audience="authenticated",
            leeway=30,
        )
    except HTTPException:
        raise
    except (jwt.PyJWTError, jwt.PyJWKClientError) as exc:
        # The 401 response body stays generic on purpose (don't leak
        # verification internals to the client), but log the real reason for
        # local debugging.
        logger.warning("JWT verification failed: %s: %s", type(exc).__name__, exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session is invalid or has expired.",
        ) from exc


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to continue.",
        )
    payload = _decode_token(credentials.credentials)
    # app_metadata.role is set by the handle_new_user trigger via profiles.role;
    # fall back to 'customer' for tokens minted before a profile role synced.
    role = (payload.get("app_metadata") or {}).get("role", "customer")
    return CurrentUser(
        id=payload["sub"],
        email=payload.get("email"),
        role=role,
        access_token=credentials.credentials,
    )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[CurrentUser]:
    if credentials is None:
        return None
    payload = _decode_token(credentials.credentials)
    role = (payload.get("app_metadata") or {}).get("role", "customer")
    return CurrentUser(
        id=payload["sub"],
        email=payload.get("email"),
        role=role,
        access_token=credentials.credentials,
    )


def get_scoped_client(user: CurrentUser = Depends(get_current_user)) -> Client:
    """A Supabase client that queries as the authenticated user (RLS-scoped)."""
    return get_user_client(user.access_token)


def require_role(*allowed_roles: str):
    """Dependency factory: 403s unless the user's role is in allowed_roles.

    Note this checks the JWT's app_metadata.role claim, which should be kept
    in sync with profiles.role (e.g. via a Supabase Auth hook or an admin
    endpoint that updates both). Sensitive writes are still protected by RLS
    regardless of this check.
    """

    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to do that.",
            )
        return user

    return dependency
