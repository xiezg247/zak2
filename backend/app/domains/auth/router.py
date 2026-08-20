from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.domains.auth.schemas import LoginRequest, TokenResponse, UserOut
from app.domains.auth.service import AuthService
from app.models.user import User
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=ApiResponse[TokenResponse])
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[TokenResponse]:
    ip = request.client.host if request.client else None
    data = AuthService.login(db, username=body.username, password=body.password, ip=ip)
    return ApiResponse(data=data)


@router.get("/me", response_model=ApiResponse[UserOut])
def me(user: User = Depends(get_current_user)) -> ApiResponse[UserOut]:
    return ApiResponse(data=UserOut(id=str(user.id), username=user.username, display_name=user.display_name))
