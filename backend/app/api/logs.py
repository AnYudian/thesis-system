"""操作日志查询（仅管理员）。

哪些操作会写日志由各业务模块决定，这里只负责检索：
登录、账号增改、学生建档 / 修改 / 删除、课题、材料上传 / 删除、阶段审核。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DBDep, require_role
from app.core.response import ApiResponse, ok
from app.models.enums import Role
from app.models.user import User
from app.schemas.audit import LogPage
from app.services import log_service

router = APIRouter(prefix="/logs", tags=["操作日志"])

AdminUser = Annotated[User, Depends(require_role(Role.ADMIN))]


@router.get("", response_model=ApiResponse[LogPage], summary="操作日志（仅管理员）")
async def list_logs(
    db: DBDep,
    _: AdminUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    action: Annotated[str | None, Query(max_length=32)] = None,
    keyword: Annotated[str | None, Query(max_length=50)] = None,
    target_type: Annotated[str | None, Query(max_length=32)] = None,
) -> ApiResponse[LogPage]:
    items, total = await log_service.list_logs(
        db, page=page, size=size, action=action, keyword=keyword, target_type=target_type
    )
    return ok(LogPage(items=items, total=total, page=page, size=size))
