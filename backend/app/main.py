"""应用入口。

以后每加一个业务模块（auth / theses / stats / review），
在这里 include_router 挂上去即可，main.py 本身保持很薄。
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ai import router as ai_router
from app.api.auth import router as auth_router
from app.api.config import router as config_router
from app.api.guidance import router as guidance_router
from app.api.health import router as health_router
from app.api.logs import router as logs_router
from app.api.materials import router as materials_router
from app.api.reminders import router as reminders_router
from app.api.reviews import router as reviews_router
from app.api.stats import router as stats_router
from app.api.students import router as students_router
from app.api.users import router as users_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.response import ApiResponse
from app.services import ai_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


def _mask(key: str) -> str:
    return f"{key[:5]}****{key[-4:]}" if len(key) > 12 else ("已配置" if key else "未配置")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.ai_enabled:
        logger.info(
            "AI 预审默认启用：provider=%s model=%s key=%s 默认每日上限=%s（管理员可在参数配置页改）",
            settings.ai_provider,
            settings.ai_model,
            _mask(settings.ai_api_key),
            settings.ai_daily_limit or "不限",
        )
    else:
        logger.info("AI 预审默认未启用（AI_ENABLED=false），管理员可在参数配置页打开")

    # 清理与开关无关：上次进程若在开启状态下中断，这里要把 RUNNING 收尾，
    # 否则即使关掉 AI，历史记录里也会一直挂着"审阅中"
    try:
        stale = await ai_service.fail_stale_runs()
        if stale:
            logger.info("已把 %s 条上次中断的预审标记为失败", stale)
    except Exception:
        # 数据库没起来时仍要能打开 /docs，启动自检失败只记警告
        logger.warning("启动自检失败：无法清理中断的预审任务", exc_info=True)
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "毕业论文（设计）全过程进度跟踪与智能审阅系统。当前阶段：P7.2 真实模型（DeepSeek）+ 自动重试。\n\n"
            "- AI 只出建议，是否放行由指导老师决定；有必改项时先由学生改稿，再进入老师复核\n"
            "- /api/ai/status 的示例值是字段结构演示，实际值以 Try it out 的响应为准\n"
            "- 管理员可在「参数配置」里随时开关 AI 预审，立即生效"
        ),
        openapi_tags=[
            {
                "name": "AI 预审",
                "description": (
                    "模型按评分细则给出参考意见，不改变流程。\n\n"
                    "- 学生上传开题报告后自动排队；教师与管理员可手动重跑，学生不可触发\n"
                    "- 有「必改」项时先由学生改稿重交，重审无必改后才计入老师待审核\n"
                    "- 管理员可在「参数配置」里关闭 AI；关闭后状态接口仍可读，但不会再新建预审\n"
                    "- 真实模型失败会自动重试一次（超时 / 限流 / 5xx / 输出截断）"
                ),
            }
        ],
        lifespan=lifespan,
        redoc_url=None,  # 只保留 /docs，少一个入口少一份维护成本
    )

    # 开发期前端跑在 5173，与后端不同源，必须放行；生产同源部署时这里可清空
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(config_router, prefix="/api")
    app.include_router(users_router, prefix="/api")
    app.include_router(logs_router, prefix="/api")
    app.include_router(stats_router, prefix="/api")
    app.include_router(students_router, prefix="/api")
    app.include_router(materials_router, prefix="/api")
    app.include_router(reviews_router, prefix="/api")
    app.include_router(guidance_router, prefix="/api")
    app.include_router(reminders_router, prefix="/api")
    app.include_router(ai_router, prefix="/api")

    @app.get("/", include_in_schema=False)
    async def index() -> ApiResponse:
        return ApiResponse(code=0, message="ok", data={"docs": "/docs", "health": "/api/health"})

    return app


app = create_app()
