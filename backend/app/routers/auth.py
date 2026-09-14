from fastapi import APIRouter, Response, status

from app import services
from app.deps import AuthDep, DbDep, SettingsDep
from app.schemas import AuthOut, LoginIn, RegisterIn, UserOut
from app.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: DbDep, settings: SettingsDep) -> AuthOut:
    user = services.register_user(db, settings, body)
    return AuthOut(token=create_access_token(user.id, settings), user=UserOut.model_validate(user))


@router.post("/login", response_model=AuthOut)
def login(body: LoginIn, db: DbDep, settings: SettingsDep) -> AuthOut:
    user = services.authenticate(db, body.identifier, body.password)
    return AuthOut(token=create_access_token(user.id, settings), user=UserOut.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(auth: AuthDep, db: DbDep) -> Response:
    db.revoke_token(auth.claims.jti, auth.claims.expires_at)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
def me(auth: AuthDep) -> UserOut:
    return UserOut.model_validate(auth.user)
