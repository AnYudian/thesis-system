"""统一响应体。

设计目的：前端只需要认一种结构 {code, message, data}，
成功和失败走同一个解析分支；HTTP 状态码仍如实返回，供 axios 拦截器判断。
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: T | None = None


def ok(data: Any = None, message: str = "ok") -> ApiResponse:
    return ApiResponse(code=0, message=message, data=data)
