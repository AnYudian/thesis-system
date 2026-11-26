"""密码哈希与 JWT。

只做纯粹的加解密工具，不碰数据库：
这样写单元测试和将来换认证方式（如微信扫码）时都能原地替换。
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.exceptions import AppError

# bcrypt 单次最多处理 72 字节，注册/改密时由 schema 控制长度
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(raw: str) -> str:
    return _pwd_context.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    return _pwd_context.verify(raw, hashed)


def create_access_token(user_id: int, role: str) -> tuple[str, int]:
    """返回 (token, 有效秒数)。"""
    settings = get_settings()
    expires_in = settings.jwt_expire_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm), expires_in


def create_evidence_ticket(user_id: int, record_id: int, ttl_seconds: int = 180) -> str:
    """签发"只读某一个证据文件"的短票据。

    为什么要单独做：浏览器新标签直接打开文件时带不了 Authorization 头，
    只能把凭据放进 URL。把 8 小时的登录令牌放进去，一旦被复制或进日志就等于泄露账号；
    票据只活 3 分钟、只对指定文件有效，泄露的代价可控。
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "scope": "evidence_read",
        "rid": record_id,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(seconds=ttl_seconds),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """解析并校验 token；任何异常都转成统一的 401，前端只需处理一种情况。"""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise AppError(40100, "登录已失效，请重新登录", http_status=401) from exc
