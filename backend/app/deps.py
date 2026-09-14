from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import services
from app.config import Settings
from app.database import Database
from app.errors import Unauthorized
from app.models import Group, User
from app.security import TokenClaims, decode_access_token

_bearer = HTTPBearer(auto_error=False)
_SESSION_EXPIRED = "Your session has expired. Please sign in again."


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


DbDep = Annotated[Database, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@dataclass(frozen=True)
class AuthContext:
    user: User
    claims: TokenClaims


def get_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: DbDep,
    settings: SettingsDep,
) -> AuthContext:
    if credentials is None:
        raise Unauthorized("Please sign in")
    try:
        claims = decode_access_token(credentials.credentials, settings)
    except jwt.PyJWTError:
        raise Unauthorized(_SESSION_EXPIRED) from None
    if db.is_token_revoked(claims.jti):
        raise Unauthorized(_SESSION_EXPIRED)
    user = db.get_user(claims.user_id)
    if user is None:
        raise Unauthorized(_SESSION_EXPIRED)
    return AuthContext(user=user, claims=claims)


AuthDep = Annotated[AuthContext, Depends(get_auth)]


def get_current_user(auth: AuthDep) -> User:
    return auth.user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def get_member_group(group_id: str, user: CurrentUserDep, db: DbDep) -> Group:
    return services.get_member_group(db, group_id, user.id)


MemberGroupDep = Annotated[Group, Depends(get_member_group)]
