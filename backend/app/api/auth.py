from functools import lru_cache
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError, PyJWKClient, PyJWKClientError
from pydantic import BaseModel, Field

from app.config import get_settings


bearer_scheme = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    id: UUID
    role: str | None = None
    claims: dict[str, Any] = Field(default_factory=dict)


def _unauthorized(detail: str = "Invalid authentication credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _auth_issuer() -> str:
    settings = get_settings()
    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL must be configured for JWT verification")
    return settings.supabase_url.rstrip("/") + "/auth/v1"


def _jwks_url() -> str:
    return _auth_issuer() + "/.well-known/jwks.json"


@lru_cache
def _get_jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url)


def _decode_with_jwks(token: str) -> dict[str, Any]:
    settings = get_settings()
    header = jwt.get_unverified_header(token)
    algorithm = header.get("alg")
    if not algorithm or algorithm.startswith("HS"):
        raise InvalidTokenError("Token is not signed with an asymmetric key")

    signing_key = _get_jwks_client(_jwks_url()).get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=[algorithm],
        audience=settings.supabase_jwt_audience,
        issuer=_auth_issuer(),
    )


def _decode_with_legacy_secret(token: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.supabase_jwt_secret:
        raise InvalidTokenError("Legacy JWT secret is not configured")

    return jwt.decode(
        token,
        settings.supabase_jwt_secret,
        algorithms=["HS256"],
        audience=settings.supabase_jwt_audience,
        issuer=_auth_issuer(),
    )


def verify_supabase_jwt(token: str) -> AuthenticatedUser:
    try:
        try:
            claims = _decode_with_jwks(token)
        except (InvalidTokenError, PyJWKClientError):
            claims = _decode_with_legacy_secret(token)
    except (InvalidTokenError, PyJWKClientError, ValueError) as exc:
        raise _unauthorized() from exc

    subject = claims.get("sub")
    if not subject:
        raise _unauthorized()

    try:
        user_id = UUID(str(subject))
    except ValueError as exc:
        raise _unauthorized() from exc

    return AuthenticatedUser(
        id=user_id,
        role=claims.get("role"),
        claims=claims,
    )


async def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Authentication required")
    return verify_supabase_jwt(credentials.credentials)
