"""内置账号初始化：admin / teacher / student，密码均为 123456。

设计成幂等脚本而不是写进迁移：
1. 迁移只负责结构，测试数据不该混进生产库；
2. 重复执行不会报错，换环境时一条命令即可准备演示账号。
"""

import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.enums import Role
from app.models.user import User

SEED_USERS = [
    ("admin", "系统管理员", Role.ADMIN),
    ("teacher", "张老师", Role.TEACHER),
    ("student", "李同学", Role.STUDENT),
]
DEFAULT_PASSWORD = "123456"


async def seed() -> None:
    async with SessionLocal() as session:
        for username, real_name, role in SEED_USERS:
            existing = await session.scalar(select(User).where(User.username == username))
            if existing is not None:
                print(f"跳过已存在账号: {username}")
                continue
            session.add(
                User(
                    username=username,
                    real_name=real_name,
                    role=role.value,
                    password_hash=hash_password(DEFAULT_PASSWORD),
                )
            )
            print(f"创建账号: {username} / {DEFAULT_PASSWORD} ({role.value})")
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
