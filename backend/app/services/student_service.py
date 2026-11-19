"""学生档案与课题建档的业务逻辑。

写在这里而不是 API 层的原因：建档要同时动 users / students / topics 三张表，
接口只负责权限入口，规则集中在服务里，后面接入批量导入时可以直接复用。
"""

import csv
import re

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.exceptions import AppError
from app.core.security import hash_password
from app.models.enums import Role, Stage, StudentStatus, TeacherType
from app.models.student import Student
from app.models.topic import Topic
from app.models.user import User
from app.schemas.student import (
    ImportErrorItem,
    ImportResult,
    SNO_PATTERN,
    StudentCreate,
    StudentDetail,
    StudentOut,
    StudentUpdate,
    TeacherBrief,
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
    teacher_brief = None
    if student.teacher_id:
        teacher = await db.get(User, student.teacher_id)
        if teacher is not None:
            teacher_name = teacher.real_name
            # 详情页要显示导师的学院/专业/电话/QQ，一次取回整行，不再逐字段查
            teacher_brief = TeacherBrief(
                id=teacher.id,
                username=teacher.username,
                real_name=teacher.real_name,
                college=teacher.college,
                major=teacher.major,
                phone=teacher.phone,
                qq=teacher.qq,
            )
    username = None
    if student.user_id:
        username = await db.scalar(select(User.username).where(User.id == student.user_id))
    topic = await db.scalar(select(Topic).where(Topic.student_id == student.id))

    base = _to_out(student, teacher_name, username, topic.title if topic else None)
    return StudentDetail(
        **base.model_dump(),
        topic=TopicOut.model_validate(topic) if topic else None,
        teacher=teacher_brief,
    )


async def _validate_teacher(db: AsyncSession, teacher_id: int) -> None:
    teacher = await db.get(User, teacher_id)
    if teacher is None or teacher.role != Role.TEACHER.value:
        raise AppError(42201, "指导教师不存在或不是教师账号", http_status=422)
    if teacher.teacher_type != TeacherType.SUPERVISOR.value:
        raise AppError(42203, "该账号是就业老师，不能带学生", http_status=422)
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
_MAX_IMPORT_ROWS = 500
_MAX_IMPORT_BYTES = 5 * 1024 * 1024
_SNO_RE = re.compile(SNO_PATTERN)
_TAB = chr(9)


def _text_rows(text: str) -> list[list[str]]:
    """按行切分，自动识别制表符（从 Excel 复制）和逗号（CSV）。"""
    lines = text.splitlines()
    delimiter = _TAB if any(_TAB in line for line in lines if line.strip()) else ","
    return [cells for cells in csv.reader(lines, delimiter=delimiter)]


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    # Excel 里纯数字学号会读成 float（20220001.0），转回整数字符串
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _xlsx_rows(data: bytes) -> list[list[str]]:
    from io import BytesIO

    from openpyxl import load_workbook

    try:
        book = load_workbook(BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:
        raise AppError(
            42234, "无法读取 Excel，请确认文件是 .xlsx 格式且没有损坏", http_status=422
        ) from exc
    try:
        sheet = book.active
        return [[_cell_text(value) for value in row] for row in sheet.iter_rows(values_only=True)]
    finally:
        book.close()


async def import_students(
    db: AsyncSession,
    *,
    text: str | None = None,
    data: bytes | None = None,
    create_account: bool,
) -> ImportResult:
    """批量建档，支持粘贴文本和上传 .xlsx。

    逐行校验、能建的先建：一个学号填错不应该让整张名单都导不进去。
    但顺序仍然是"全部校验完 → 一次性写入 → 一次 commit"，
    避免中途报错留下半张名单。

    指导教师必填：没有导师的学生在阶段审核里没人能放行，
    导入时就要把归属定下来，后续可在学生列表里批量改派。
    """
    if data is not None:
        rows = _xlsx_rows(data)
    elif text is not None:
        rows = _text_rows(text)
    else:
        raise AppError(42235, "没有可导入的内容", http_status=422)

    parsed: list[tuple[int, str, str, str, str, str, str, str]] = []
    errors: list[ImportErrorItem] = []
    seen: set[str] = set()
    header_checked = False

    for line_no, cells in enumerate(rows, start=1):
        cells = [cell.strip() for cell in cells]
        if not any(cells):
            continue
        content = ",".join(cells)

        if not header_checked:
            header_checked = True
            if cells[0].lower() in ("学号", "sno", "student_no") or "学号" in cells[0]:
                continue  # 表头行，不当作数据

        if len(cells) < 6:
            errors.append(
                ImportErrorItem(
                    line=line_no,
                    content=content,
                    reason="至少需要 6 列：学号,姓名,专业,班级,年级,指导教师账号",
                )
            )
            continue

        sno, name, major, class_name, grade, teacher_username = cells[:6]

        if not _SNO_RE.fullmatch(sno) or not 4 <= len(sno) <= 30:
            errors.append(
                ImportErrorItem(
                    line=line_no,
                    content=content,
                    reason="学号只能是 4-30 位字母、数字、下划线或横线",
                )
            )
            continue
        if not name:
            errors.append(ImportErrorItem(line=line_no, content=content, reason="姓名为空"))
            continue
        if not major or not class_name or len(grade) < 2:
            errors.append(
                ImportErrorItem(line=line_no, content=content, reason="专业 / 班级 / 年级不能为空")
            )
            continue
        if not teacher_username:
            errors.append(
                ImportErrorItem(line=line_no, content=content, reason="指导教师账号必填")
            )
            continue
        if sno in seen:
            errors.append(ImportErrorItem(line=line_no, content=content, reason="名单里学号重复"))
            continue
        seen.add(sno)
        parsed.append((line_no, sno, name, major, class_name, grade, teacher_username, content))

    if len(parsed) > _MAX_IMPORT_ROWS:
        raise AppError(42233, f"单次最多导入 {_MAX_IMPORT_ROWS} 人，请分批", http_status=422)
    if not parsed:
        return ImportResult(created=0, skipped=len(errors), errors=errors, initial_password=None)

    snos = [row[1] for row in parsed]
    existing_sno = set((await db.scalars(select(Student.sno).where(Student.sno.in_(snos)))).all())
    existing_account = set(
        (await db.scalars(select(User.username).where(User.username.in_(snos)))).all()
    )

    wanted_teachers = {row[6] for row in parsed}
    teacher_map: dict[str, int] = {
        username: user_id
        for user_id, username in (
            await db.execute(
                select(User.id, User.username).where(
                    User.username.in_(wanted_teachers),
                    User.role == Role.TEACHER.value,
                    User.teacher_type == TeacherType.SUPERVISOR.value,
                    User.is_active.is_(True),
                )
            )
        ).all()
    }

    created = 0
    for line_no, sno, name, major, class_name, grade, teacher_username, content in parsed:
        if sno in existing_sno or (create_account and sno in existing_account):
            reason = "学号已存在" if sno in existing_sno else "账号已被占用"
            errors.append(ImportErrorItem(line=line_no, content=content, reason=reason))
            continue
        if teacher_username not in teacher_map:
            errors.append(
                ImportErrorItem(
                    line=line_no,
                    content=content,
                    reason=f"指导教师账号 {teacher_username} 不存在、已停用或不是指导教师",
                )
            )
            continue

        user_id: int | None = None
        if create_account:
            account = User(
                username=sno,
                real_name=name,
                role=Role.STUDENT.value,
                password_hash=hash_password(DEFAULT_PASSWORD),
            )
            db.add(account)
            await db.flush()
            user_id = account.id

        db.add(
            Student(
                user_id=user_id,
                sno=sno,
                name=name,
                major=major,
                class_name=class_name,
                grade=grade,
                teacher_id=teacher_map[teacher_username],
                current_stage=Stage.TOPIC.value,
                status=StudentStatus.ACTIVE.value,
            )
        )
        created += 1

    await db.commit()
    return ImportResult(
        created=created,
        skipped=len(errors),
        errors=errors,
        initial_password=DEFAULT_PASSWORD if create_account and created else None,
    )


async def assign_teacher(
    db: AsyncSession, *, student_ids: list[int], teacher_id: int
) -> tuple[int, str]:
    """批量改派导师。

    用于"新建了教师账号，把一批学生划给他"：一个一个改太慢，
    而且新建学生已经强制带导师，改派是这个流程的必要补充。
    """
    teacher = await db.get(User, teacher_id)
    if teacher is None or teacher.role != Role.TEACHER.value:
        raise AppError(42201, "指导教师不存在或不是教师账号", http_status=422)
    if teacher.teacher_type != TeacherType.SUPERVISOR.value:
        raise AppError(42203, "该账号是就业老师，不能带学生", http_status=422)
    if not teacher.is_active:
        raise AppError(42202, "该教师账号已停用，不能指派", http_status=422)

    ids = list(dict.fromkeys(student_ids))
    students = list((await db.scalars(select(Student).where(Student.id.in_(ids)))).all())
    if not students:
        raise AppError(40401, "没有找到要指派的学生", http_status=404)

    for student in students:
        student.teacher_id = teacher_id
    await db.commit()
    return len(students), teacher.real_name or teacher.username
