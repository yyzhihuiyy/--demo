from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.shared.db import DbSession
from app.shared.errors import AppError
from app.shared.schemas import User, SessionContext

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise AppError(401, "AUTH_REQUIRED", "请先登录")
    # Lazy import avoids models/auth circular dependencies between A and C.
    from app.core.access import resolve_user
    user = User.model_validate(resolve_user(credentials.credentials, db))
    if not user.active:
        raise AppError(401, "ACCOUNT_DISABLED", "账号已停用")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_teacher_for_class(user: User, class_id: int) -> None:
    if user.role != "teacher" or user.class_id != class_id:
        raise AppError(403, "CLASS_FORBIDDEN", "无权管理该班级")


def require_session_access(user: User, session_id: int, db: Session, *, write: bool = False):
    from app.core.access import check_session_access
    return check_session_access(user, session_id, db, write=write)


def get_authorized_session_context(user: User, session_id: int, db: Session) -> SessionContext:
    from app.core.access import read_session_context
    return SessionContext.model_validate(read_session_context(user, session_id, db))
