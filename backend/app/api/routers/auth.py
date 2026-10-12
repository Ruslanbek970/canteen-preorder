from fastapi import APIRouter, Request

from app.api.deps import DB, client_ip
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    ResendCodeRequest,
    TokenPair,
    VerifyEmailRequest,
)
from app.schemas.common import OkResponse
from app.security import CurrentUser
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(data: RegisterRequest, db: DB) -> RegisterResponse:
    user, sent = auth_service.register(db, data)
    return RegisterResponse(user_id=user.id, email=user.email, verification_sent=sent)


@router.post("/verify-email", response_model=OkResponse)
def verify_email(data: VerifyEmailRequest, db: DB) -> OkResponse:
    auth_service.verify_email(db, data.email, data.code)
    return OkResponse()


@router.post("/resend-code", response_model=OkResponse)
def resend_code(data: ResendCodeRequest, db: DB) -> OkResponse:
    auth_service.resend_code(db, data.email)
    return OkResponse()


@router.post("/login", response_model=TokenPair)
def login(data: LoginRequest, request: Request, db: DB) -> TokenPair:
    return auth_service.login(db, data.email, data.password, client_ip(request))


@router.post("/refresh", response_model=TokenPair)
def refresh(data: RefreshRequest, db: DB) -> TokenPair:
    return auth_service.refresh(db, data.refresh_token)


@router.post("/logout", response_model=OkResponse)
def logout(data: RefreshRequest, _user: CurrentUser, db: DB) -> OkResponse:
    auth_service.logout(db, data.refresh_token)
    return OkResponse()
