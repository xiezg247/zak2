from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.schemas.common import ApiResponse
from app.services import login_guard

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=ApiResponse[TokenResponse])
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[TokenResponse]:
    ip = request.client.host if request.client else None
    if login_guard.is_locked(body.username, ip):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="尝试次数过多，请稍后再试")

    user = UserRepository(db).get_by_username(body.username)
    if user is None or not verify_password(body.password, user.password_hash):
        login_guard.record_failure(body.username, ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已禁用")

    login_guard.reset(body.username, ip)
    token = create_access_token(user_id=str(user.id), username=user.username)
    return ApiResponse(
        data=TokenResponse(
            access_token=token,
            user=UserOut(id=str(user.id), username=user.username, display_name=user.display_name),
        )
    )


@router.get("/me", response_model=ApiResponse[UserOut])
def me(user: User = Depends(get_current_user)) -> ApiResponse[UserOut]:
    return ApiResponse(data=UserOut(id=str(user.id), username=user.username, display_name=user.display_name))
