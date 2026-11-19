"""演示学生数据。

只用于把管理员的看板和学生列表撑起来，方便向老师演示；
真实使用时由管理员在“学生与课题”里建档。
可重复执行：已存在的学生会跳过，缺账号/缺课题的会补上。
"""

import asyncio

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.enums import STAGE_ORDER, Role, Stage, StudentStatus
from app.models.student import Student
from app.models.topic import Topic
from app.models.user import User
from app.services.student_service import DEFAULT_PASSWORD

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

TITLES = [
    "基于深度学习的课堂专注度识别系统设计与实现",
    "面向校园场景的知识图谱构建与问答应用",
    "基于微服务架构的在线选课系统设计与优化",
    "轻量级目标检测算法在无人机巡检中的应用",
    "基于大语言模型的论文格式自动校验工具",
    "校园二手交易平台的设计与实现",
    "基于时序预测的图书馆座位推荐系统",
    "面向中小企业的进销存管理系统重构",
    "基于图神经网络的学术合作推荐方法研究",
    "移动端健身数据可视化应用开发",
    "基于对比学习的文本相似度检测方法",
    "面向毕业设计的文档协同编辑平台",
    "基于YOLO的实验室安全行为检测",
    "高校学生画像与学业预警模型研究",
    "基于强化学习的智能排课算法实现",
    "云原生环境下日志分析平台设计",
    "基于语音识别的会议纪要生成工具",
    "面向视障用户的图像描述生成系统",
    "基于区块链的学历证书存证原型",
    "校园快递代取系统的设计与实现",
    "基于多模态特征的短视频推荐算法",
    "面向教学场景的代码自动评测平台",
    "基于知识蒸馏的轻量化图像分类模型",
    "毕业设计过程管理系统的设计与实现",
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


async def _seed_students(session) -> int:
    existing = await session.scalar(select(func.count()).select_from(Student)) or 0
    if existing:
        print(f"已存在 {existing} 名学生，跳过名单创建")
        return 0

    teacher = await session.scalar(select(User).where(User.username == "teacher"))
    if teacher is None:
        print("未找到 teacher 账号，请先执行 python -m app.db.seed")
        return 0

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
    return index


async def _backfill(session) -> None:
    """给还没有登录账号的演示学生开账号，给还没选题的学生补一条课题。"""
    students = (await session.scalars(select(Student).order_by(Student.sno))).all()
    accounts = 0
    topics = 0

    for i, student in enumerate(students):
        if student.user_id is None:
            taken = await session.scalar(select(User.id).where(User.username == student.sno))
            if taken is None:
                account = User(
                    username=student.sno,
                    real_name=student.name,
                    role=Role.STUDENT.value,
                    password_hash=hash_password(DEFAULT_PASSWORD),
                )
                session.add(account)
                await session.flush()
                student.user_id = account.id
                accounts += 1

        has_topic = await session.scalar(select(Topic.id).where(Topic.student_id == student.id))
        if has_topic is None:
            session.add(
                Topic(
                    student_id=student.id,
                    title=TITLES[i % len(TITLES)],
                    summary="演示数据：课题简介由 seed 自动生成，可随时在管理端修改。",
                    academic_year="2026",
                )
            )
            topics += 1

    await session.commit()
    print(f"补齐学生账号 {accounts} 个、课题 {topics} 条；演示账号密码均为 {DEFAULT_PASSWORD}")


async def seed_demo() -> None:
    async with SessionLocal() as session:
        await _seed_students(session)
        await _backfill(session)


if __name__ == "__main__":
    asyncio.run(seed_demo())
