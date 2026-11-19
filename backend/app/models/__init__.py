"""集中导出模型，保证 Alembic 的 target_metadata 能看到所有表。"""

from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.enums import Role, Stage, StudentStatus
from app.models.material import Material
from app.models.student import Student
from app.models.topic import Topic
from app.models.user import User

__all__ = [
    "AuditLog",
    "Base",
    "Material",
    "Role",
    "Stage",
    "Student",
    "StudentStatus",
    "Topic",
    "User",
]
