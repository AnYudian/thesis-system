"""系统级接口。"""

from datetime import datetime

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.response import ApiResponse, ok

router = APIRouter(tags=["系统"])


@router.get("/health", response_model=ApiResponse[dict], summary="健康检查")
async def health() -> ApiResponse:
    settings = get_settings()
    return ok(
        {
            "status": "up",
            "app": settings.app_name,
            "env": settings.app_env,
            # 用本机时区而不是 UTC，方便本机演示时肉眼对照
            "time": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
    )
