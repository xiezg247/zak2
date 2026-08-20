from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import Forbidden, RateLimited, Unauthorized
from app.core.security import create_access_token, verify_password
from app.domains.auth import login_guard
from app.domains.auth.repository import UserRepository
from app.domains.auth.schemas import TokenResponse, UserOut


class AuthService:
    @staticmethod
    def login(db: Session, *, username: str, password: str, ip: str | None) -> TokenResponse:
        if login_guard.is_locked(username, ip):
            raise RateLimited("尝试次数过多，请稍后再试")
        user = UserRepository(db).get_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            login_guard.record_failure(username, ip)
            raise Unauthorized("用户名或密码错误")
        if not user.is_active:
            raise Forbidden("用户已禁用")
        login_guard.reset(username, ip)
        token = create_access_token(user_id=str(user.id), username=user.username)
        return TokenResponse(
            access_token=token,
            user=UserOut(id=str(user.id), username=user.username, display_name=user.display_name),
        )
