"""集中导出模型，保证 Alembic 的 target_metadata 能看到所有表。"""

from app.models.audit_log import AuditLog
from app.models.ai_run import AiRun
from app.models.base import Base
from app.models.enums import AiRunStatus, GuidanceMethod, ReviewAction, Role, Stage, StudentStatus
from app.models.guidance import GuidanceRecord
from app.models.material import Material
from app.models.reminder import Reminder
from app.models.stage_review import StageReview
from app.models.student import Student
from app.models.system_setting import SystemSetting
from app.models.topic import Topic
from app.models.user import User

__all__ = [
    "AiRun",
    "AiRunStatus",
    "AuditLog",
    "Base",
    "GuidanceMethod",
    "GuidanceRecord",
    "Material",
    "Reminder",
    "ReviewAction",
    "Role",
    "Stage",
    "StageReview",
    "Student",
    "StudentStatus",
    "SystemSetting",
    "Topic",
    "User",
]
