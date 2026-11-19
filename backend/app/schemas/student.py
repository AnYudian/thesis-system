"""学生与课题的出入参。

列表项带上教师姓名、账号、课题题目，前端表格就不用再逐行发请求。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Stage, StudentStatus

# 学号同时用作登录账号，限制成不会和用户名规则冲突的字符集
SNO_PATTERN = r"^[0-9A-Za-z_-]+$"


class TopicIn(BaseModel):
    title: str = Field(min_length=2, max_length=200, description="课题题目")
    summary: str | None = Field(default=None, max_length=2000, description="课题简介/主要工作")
    academic_year: str = Field(default="2026", min_length=4, max_length=9)


class TopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    summary: str | None = None
    academic_year: str
    updated_at: datetime


class StudentCreate(BaseModel):
    sno: str = Field(min_length=4, max_length=30, pattern=SNO_PATTERN, description="学号，同时作为登录账号")
    name: str = Field(min_length=1, max_length=50)
    major: str = Field(min_length=1, max_length=100)
    class_name: str = Field(min_length=1, max_length=50)
    grade: str = Field(min_length=2, max_length=10)
    teacher_id: int | None = None
    current_stage: Stage = Stage.TOPIC
    create_account: bool = Field(default=True, description="是否同时开通学生登录账号")


class StudentUpdate(BaseModel):
    """全部可选：传了哪个字段就改哪个，没传的保持原值。"""

    name: str | None = Field(default=None, min_length=1, max_length=50)
    major: str | None = Field(default=None, min_length=1, max_length=100)
    class_name: str | None = Field(default=None, min_length=1, max_length=50)
    grade: str | None = Field(default=None, min_length=2, max_length=10)
    teacher_id: int | None = None
    current_stage: Stage | None = None
    status: StudentStatus | None = None
    # 单独用布尔位判断"是否要清空指导教师"，避免 None 既表示"不改"又表示"清空"
    clear_teacher: bool = False


class StudentOut(BaseModel):
    id: int
    sno: str
    name: str
    major: str
    class_name: str
    grade: str
    teacher_id: int | None = None
    teacher_name: str | None = None
    current_stage: Stage
    status: StudentStatus
    username: str | None = None
    topic_title: str | None = None
    created_at: datetime


class StudentDetail(StudentOut):
    topic: TopicOut | None = None


class StudentPage(BaseModel):
    items: list[StudentOut]
    total: int
    page: int
    size: int


class StudentCreated(BaseModel):
    student: StudentOut
    # 初始密码只在创建时返回一次，管理员负责转告学生
    initial_password: str | None = None


class ImportIn(BaseModel):
    """批量导入：前端把 CSV / 表格文本原样传上来，解析放在后端，
    以后接 Excel 上传也只是换解析器。"""

    text: str = Field(min_length=1, max_length=100_000)
    create_account: bool = True


class ImportErrorItem(BaseModel):
    line: int
    content: str
    reason: str


class ImportResult(BaseModel):
    created: int
    skipped: int
    errors: list[ImportErrorItem]
    initial_password: str | None = None
