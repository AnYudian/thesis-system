"""全局异常处理。

三类异常分别给出前端能直接展示的提示：
1. AppError      —— 我们主动抛的业务异常（如"论文不存在"）
2. 参数校验失败   —— FastAPI/Pydantic 自动触发（422）
3. 未预期异常     —— 兜底 500，日志里保留完整堆栈，响应里绝不暴露堆栈
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.response import ApiResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, code: int, message: str, http_status: int = 400):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(message)


def _json(status_code: int, code: int, message: str, data=None) -> JSONResponse:
    payload = ApiResponse(code=code, message=message, data=data)
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _json(exc.http_status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # errors() 里的 ctx 可能包含异常对象，不能直接序列化，这里只取可展示的三项
        details = [
            {
                "loc": ".".join(str(part) for part in err.get("loc", ())),
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
        first = details[0]["msg"] if details else "参数不合法"
        return _json(422, 42200, f"参数校验失败：{first}", details)

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # 401/403/404 等由框架抛出的异常也套上统一响应体，同时保留原 HTTP 状态码
        code = {401: 40100, 403: 40300, 404: 40400, 405: 40500}.get(
            exc.status_code, exc.status_code * 100
        )
        return _json(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("未处理异常 %s %s", request.method, request.url.path)
        return _json(500, 50000, "服务器内部错误，请稍后重试或联系管理员")
