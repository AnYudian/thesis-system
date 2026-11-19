"""学生档案与课题建档的业务逻辑。

写在这里而不是 API 层的原因：建档要同时动 users / students / topics 三张表，
接口只负责权限入口，规则集中在服务里，后面接入批量导入时可以直接复用。
"""

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.exceptions import AppError
from app.core.security import hash_password
from app.models.enums import Role, StudentStatus
from app.models.student import Student
from app.models.topic import Topic
from app.models.user import User
from app.schemas.student import (
    StudentCreate,
    StudentDetail,
    StudentOut,
    StudentUpdate,
    TopicIn,
    TopicOut,
)

# 内置初始密码：老师演示、学生首次登录都用它。
# 改密功能等登录方式定下来再做，现在不做半截的"改密页"。
DEFAULT_PASSWORD = "123456"


def _to_out(
    student: Student,
    teacher_name: str | None = None,
    username: str | None = None,
    topic_title: str | None = None,
) -> StudentOut:
    return StudentOut(
        id=student.id,
        sno=student.sno,
        name=student.name,
        major=student.major,
        class_name=student.class_name,
        grade=student.grade,
        teacher_id=student.teacher_id,
        teacher_name=teacher_name,
        current_stage=student.current_stage,  # type: ignore[arg-type]
        status=student.status,  # type: ignore[arg-type]
        username=username,
        topic_title=topic_title,
        created_at=student.created_at,
    )


def _base_query() -> Select:
    # users 表要连两次：一次取导师姓名，一次取学生自己的登录账号。
    # 用别名区分，否则两处都取到同一行（导师账号），列表里学生的账号会显示成老师。
    teacher = aliased(User)
    account = aliased(User)
    # 左连接：没指定教师、还没开通账号、还没选题的学生也要出现在列表里
    return (
        select(Student, teacher.real_name, account.username, Topic.title)
        .outerjoin(teacher, Student.teacher_id == teacher.id)
        .outerjoin(account, Student.user_id == account.id)
        .outerjoin(Topic, Topic.student_id == Student.id)
    )


def _apply_filters(
    stmt: Select,
    *,
    keyword: str | None,
    stage: str | None,
    status: str | None,
    teacher_id: int | None,
) -> Select:
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(Student.sno.ilike(like), Student.name.ilike(like)))
    if stage:
        stmt = stmt.where(Student.current_stage == stage)
    if status:
        stmt = stmt.where(Student.status == status)
    if teacher_id is not None:
        stmt = stmt.where(Student.teacher_id == teacher_id)
    return stmt


async def list_students(
    db: AsyncSession,
    *,
    scope_teacher_id: int | None,
    page: int,
    size: int,
    keyword: str | None = None,
    stage: str | None = None,
    status: str | None = None,
    teacher_id: int | None = None,
) -> tuple[list[StudentOut], int]:
    """scope_teacher_id 用于教师视角：只能看自己名下的学生。"""
    filters = {
        "keyword": keyword,
        "stage": stage,
        "status": status,
        # 教师视角强制覆盖，忽略前端传的 teacher_id，防止越权查别人的学生
        "teacher_id": scope_teacher_id if scope_teacher_id is not None else teacher_id,
    }

    count_stmt = _apply_filters(select(func.count()).select_from(Student), **filters)
    total = await db.scalar(count_stmt) or 0

    stmt = (
        _apply_filters(_base_query(), **filters)
        .order_by(Student.sno)
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = (await db.execute(stmt)).all()
    items = [_to_out(s, teacher_name, username, title) for s, teacher_name, username, title in rows]
    return items, total


async def get_student_or_404(db: AsyncSession, student_id: int) -> Student:
    student = await db.get(Student, student_id)
    if student is None:
        raise AppError(40401, "学生不存在", http_status=404)
    return student


async def get_student_by_user(db: AsyncSession, user_id: int) -> Student | None:
    """学生登录后查自己的档案；还没建档时返回 None，由接口给出友好提示。"""
    return await db.scalar(select(Student).where(Student.user_id == user_id))


async def get_detail(db: AsyncSession, student: Student) -> StudentDetail:
    teacher_name = None
    if student.teacher_id:
        teacher_name = await db.scalar(select(User.real_name).where(User.id == student.teacher_id))
    username = None
    if student.user_id:
        username = await db.scalar(select(User.username).where(User.id == student.user_id))
    topic = await db.scalar(select(Topic).where(Topic.student_id == student.id))

    base = _to_out(student, teacher_name, username, topic.title if topic else None)
    return StudentDetail(
        **base.model_dump(),
        topic=TopicOut.model_validate(topic) if topic else None,
    )


async def _validate_teacher(db: AsyncSession, teacher_id: int) -> None:
    teacher = await db.get(User, teacher_id)
    if teacher is None or teacher.role != Role.TEACHER.value:
        raise AppError(42201, "指导教师不存在或不是教师账号", http_status=422)
    if not teacher.is_active:
        raise AppError(42202, "该教师账号已停用，不能指派", http_status=422)


async def create_student(db: AsyncSession, data: StudentCreate) -> tuple[Student, str | None]:
    if await db.scalar(select(Student.id).where(Student.sno == data.sno)):
        raise AppError(40901, f"学号 {data.sno} 已存在", http_status=409)
    # 学号即账号，先查重避免触发 username 唯一约束后返回一句看不懂的数据库错误
    if await db.scalar(select(User.id).where(User.username == data.sno)):
        raise AppError(40902, f"账号 {data.sno} 已被占用，请检查学号", http_status=409)
    if data.teacher_id is not None:
        await _validate_teacher(db, data.teacher_id)

    initial_password: str | None = None
    user_id: int | None = None
    if data.create_account:
        account = User(
            username=data.sno,
            real_name=data.name,
            role=Role.STUDENT.value,
            password_hash=hash_password(DEFAULT_PASSWORD),
        )
        db.add(account)
        await db.flush()
        user_id = account.id
        initial_password = DEFAULT_PASSWORD

    student = Student(
        user_id=user_id,
        sno=data.sno,
        name=data.name,
        major=data.major,
        class_name=data.class_name,
        grade=data.grade,
        teacher_id=data.teacher_id,
        current_stage=data.current_stage.value,
        status=StudentStatus.ACTIVE.value,
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student, initial_password


async def update_student(db: AsyncSession, student: Student, data: StudentUpdate) -> Student:
    fields = data.model_dump(exclude_unset=True)
    fields.pop("clear_teacher", None)

    if "teacher_id" in fields and fields["teacher_id"] is not None:
        await _validate_teacher(db, fields["teacher_id"])

    if data.clear_teacher:
        student.teacher_id = None
        fields.pop("teacher_id", None)

    for key, value in fields.items():
        if value is None:
            continue
        # 枚举值落库统一存字符串，避免驱动写入枚举对象
        setattr(student, key, value.value if hasattr(value, "value") else value)

    # 姓名改了要同步账号上的姓名，否则列表里教师姓名和学生姓名会不一致
    if "name" in fields and student.user_id:
        account = await db.get(User, student.user_id)
        if account:
            account.real_name = student.name

    await db.commit()
    await db.refresh(student)
    return student


async def delete_student(db: AsyncSession, student: Student) -> None:
    user_id = student.user_id
    await db.delete(student)  # topics 由外键 ON DELETE CASCADE 一起清掉
    await db.flush()
    if user_id:
        account = await db.get(User, user_id)
        if account:
            await db.delete(account)
    await db.commit()


async def upsert_topic(db: AsyncSession, student: Student, data: TopicIn) -> Topic:
    topic = await db.scalar(select(Topic).where(Topic.student_id == student.id))
    if topic is None:
        topic = Topic(
            student_id=student.id,
            title=data.title.strip(),
            summary=data.summary,
            academic_year=data.academic_year,
        )
        db.add(topic)
    else:
        topic.title = data.title.strip()
        topic.summary = data.summary
        topic.academic_year = data.academic_year
    await db.commit()
    await db.refresh(topic)
    return topic


async def delete_topic(db: AsyncSession, student: Student) -> None:
    topic = await db.scalar(select(Topic).where(Topic.student_id == student.id))
    if topic is not None:
        await db.delete(topic)
        await db.commit()
