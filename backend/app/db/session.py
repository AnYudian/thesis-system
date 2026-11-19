"""数据库会话。

说明：create_async_engine 不会在 import 时真正建连（懒连接），
所以数据库还没起的时候应用也能启动、/docs 也能看——D0 验收需要的正是这一点。
D1 起所有接口通过 get_db 依赖拿会话，绝不在业务代码里手写 Session()。
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_settings = get_settings()

engine = create_async_engine(_settings.database_url, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
