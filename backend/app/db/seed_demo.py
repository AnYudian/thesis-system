"""演示学生数据。

只用于把管理员的阶段分布看板撑起来，方便向老师演示；
真实使用时由管理员在“学生管理”里建档。重复执行会跳过。
"""

import asyncio

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.enums import STAGE_ORDER, Stage, StudentStatus
from app.models.student import Student
from app.models.user import User

NAMES = [
    "王思远", "李佳琪", "张宇航", "刘欣然", "陈子豪", "杨雨萌",
    "赵一鸣", "黄诗涵", "周明轩", "吴晓彤", "徐嘉豪", "孙怡宁",
    "马天宇", "朱婉清", "胡俊杰", "郭子涵", "何雨晴", "高志远",
    "林可欣", "罗浩然", "郑雅文", "谢泽宇", "唐若曦", "韩立诚",
]

MAJORS = [
    ("计算机科学与技术", "计科2201"),
    ("计算机科学与技术", "计科2202"),
    ("软件工程", "软工2201"),
    ("数据科学与大数据技术", "数据2201"),
]

# 每个阶段安排多少名演示学生，合计 24 人
STAGE_PLAN = {
    Stage.TOPIC: 4,
    Stage.TASK_BOOK: 5,
    Stage.PROPOSAL: 4,
    Stage.MIDTERM: 3,
    Stage.PLAGIARISM: 2,
    Stage.THESIS: 2,
    Stage.REVIEW: 1,
    Stage.DEFENSE: 1,
    Stage.ARCHIVE: 2,
}


async def seed_demo() -> None:
    async with SessionLocal() as session:
        existing = await session.scalar(select(func.count()).select_from(Student)) or 0
        if existing:
            print(f"已存在 {existing} 名学生，跳过演示数据")
            return

        teacher = await session.scalar(select(User).where(User.username == "teacher"))
        if teacher is None:
            print("未找到 teacher 账号，请先执行 python -m app.db.seed")
            return

        index = 0
        for stage in STAGE_ORDER:
            for _ in range(STAGE_PLAN[stage]):
                name = NAMES[index]
                major, class_name = MAJORS[index % len(MAJORS)]
                session.add(
                    Student(
                        sno=f"2022{index + 1:04d}",
                        name=name,
                        major=major,
                        class_name=class_name,
                        grade="2022",
                        teacher_id=teacher.id,
                        current_stage=stage.value,
                        status=(
                            StudentStatus.ARCHIVED.value
                            if stage is Stage.ARCHIVE
                            else StudentStatus.ACTIVE.value
                        ),
                    )
                )
                index += 1

        await session.commit()
        print(f"已创建 {index} 名演示学生，指导教师：{teacher.real_name}")


if __name__ == "__main__":
    asyncio.run(seed_demo())
