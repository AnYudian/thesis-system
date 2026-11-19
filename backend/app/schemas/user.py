"""账号管理的出入参。

管理员只管理教师 / 管理员账号；学生账号随学生建档一起开通，
避免同一个账号在两个页面都能改、状态对不上。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Role

# 和登录框一致的账号规则：不能带空格、中文，避免以后接扫码/统一认证时映射冲突
USERNAME_PATTERN = r"^[0-9A-Za-z_.-]{3,50}$"


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    real_name: str | None = None
    role: Role
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class AccountPage(BaseModel):
    items: list[AccountOut]
    total: int
    page: int
    size: int


class AccountCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=USERNAME_PATTERN)
    real_name: str = Field(min_length=1, max_length=50)
    role: Role = Role.TEACHER
    # 不填就用统一初始密码 123456，和 P2 学生账号的口径保持一致
    password: str | None = Field(default=None, min_length=6, max_length=72)


class AccountUpdate(BaseModel):
    real_name: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None


class AccountCreated(BaseModel):
    user: AccountOut
    initial_password: str


class ResetPasswordOut(BaseModel):
    password: str
