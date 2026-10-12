"""Identity and read-only authorization adapter shared with the agent workshop."""
from datetime import datetime, timezone
import hashlib
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.shared.errors import AppError
from app.shared.schemas import User, SessionContext, SessionProduct, TrainingEvent
from app.core.models import Account, Token, SessionRow, TaskRow, SessionProductRow, EventRow


def now():
    return datetime.now(timezone.utc)


def resolve_user(token: str, db: Session) -> User:
    row = db.get(Token, hashlib.sha256(token.encode()).hexdigest())
    if row is None or datetime.fromisoformat(row.expires_at) <= now():
        raise AppError(401, 'INVALID_TOKEN', '登录已失效，请重新登录')
    account = db.get(Account, row.user_id)
    if account is None or not account.active:
        raise AppError(401, 'ACCOUNT_DISABLED', '账号已停用')
    return User.model_validate(account)


def check_session_access(user: User, session_id: int, db: Session, *, write: bool = False):
    session = db.get(SessionRow, session_id)
    if session is None:
        raise AppError(404, 'SESSION_NOT_FOUND', '场次不存在')
    task = db.get(TaskRow, session.task_id)
    if task.class_id != user.class_id:
        raise AppError(403, 'SESSION_FORBIDDEN', '无权访问该场次')
    if user.role == 'teacher':
        if write:
            raise AppError(403, 'STUDENT_ACTION_REQUIRED', '经营操作须由本组学生完成')
        if task.teacher_id != user.id:
            raise AppError(403, 'SESSION_FORBIDDEN', '无权查看该教师场次')
    elif user.id not in [m['user_id'] for m in session.members_snapshot]:
        raise AppError(403, 'SESSION_FORBIDDEN', '只能操作本组场次')
    if write:
        if session.status in ('submitted', 'graded'):
            raise AppError(409, 'SESSION_LOCKED', '场次已提交，经营数据已锁定')
        if now() >= datetime.fromisoformat(session.rule_snapshot['ends_at']):
            raise AppError(409, 'DEADLINE_PASSED', '任务已截止，不能继续修改')
    return session


def read_session_context(user: User, session_id: int, db: Session) -> SessionContext:
    session = check_session_access(user, session_id, db)
    task = db.get(TaskRow, session.task_id)
    products = db.scalars(select(SessionProductRow).where(SessionProductRow.session_id == session_id).order_by(SessionProductRow.sort_order)).all()
    questions = db.scalars(select(EventRow).where(EventRow.session_id == session_id, EventRow.type == 'audience_question').order_by(EventRow.id.desc()).limit(10)).all()
    return SessionContext(session_id=session_id, class_id=task.class_id, team_id=session.team_id,
                          products=[SessionProduct.model_validate(p) for p in products],
                          recent_questions=[TrainingEvent.model_validate(e) for e in reversed(questions)],
                          sources=[f'session:{session_id}:authorized_products', f'session:{session_id}:audience_questions'])
