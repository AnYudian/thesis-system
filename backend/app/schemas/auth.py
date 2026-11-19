from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Role


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    real_name: str | None = None
    role: Role


class LoginData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class ChangePasswordIn(BaseModel):
    """自助改密：必须验原密码，避免 token 被盗后直接改掉密码把人踢下线。"""

    old_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=6, max_length=72)
