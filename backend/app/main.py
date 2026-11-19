"""应用入口。

以后每加一个业务模块（auth / theses / stats / review），
在这里 include_router 挂上去即可，main.py 本身保持很薄。
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.stats import router as stats_router
from app.api.students import router as students_router
from app.api.users import router as users_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.response import ApiResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="毕业论文（设计）全过程进度跟踪与智能审阅系统。当前阶段：P2 学生与课题建档。",
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
    app.include_router(users_router, prefix="/api")
    app.include_router(stats_router, prefix="/api")
    app.include_router(students_router, prefix="/api")

    @app.get("/", include_in_schema=False)
    async def index() -> ApiResponse:
        return ApiResponse(code=0, message="ok", data={"docs": "/docs", "health": "/api/health"})

    return app


app = create_app()
