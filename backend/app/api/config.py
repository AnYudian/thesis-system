"""系统参数（参数配置页）。

读取对所有登录用户开放：教师端、学生端都要用它显示"中期要几次""本环节截止哪天"；
只有管理员能改。
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import DBDep, CurrentUser, require_role
from app.core.response import ApiResponse, ok
from app.models.enums import Role
from app.models.user import User
from app.schemas.config import ConfigOut, ConfigUpdate
from app.services import config_service

router = APIRouter(prefix="/config", tags=["系统参数"])

AdminUser = Annotated[User, Depends(require_role(Role.ADMIN))]


@router.get("", response_model=ApiResponse[ConfigOut], summary="读取系统参数（所有登录用户）")
async def read_config(db: DBDep, _: CurrentUser) -> ApiResponse[ConfigOut]:
    return ok(await config_service.get_config(db))


@router.put("", response_model=ApiResponse[ConfigOut], summary="保存系统参数（仅管理员）")
async def save_config(
    db: DBDep, admin: AdminUser, payload: ConfigUpdate
) -> ApiResponse[ConfigOut]:
    return ok(await config_service.update_config(db, admin, payload))
