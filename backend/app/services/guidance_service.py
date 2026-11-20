"""指导记录业务。

中期检查要求教师指导学生达到管理员配置的次数（默认 10 次），且要能追溯到
"时间 / 方式 / 内容 / 证据"。这里只负责记录本身；"不够次数不许放行"的判断在阶段审核服务里，
因为那属于流程规则，不属于记录维护。

证据文件和阶段材料分开存（data/uploads/guidance/...），
将来清理材料时不会把指导证据一起删掉。
"""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.enums import Stage
from app.models.guidance import GuidanceRecord
from app.models.student import Student
from app.models.user import User
from app.schemas.guidance import GuidanceOut, GuidanceSummary
from app.services import config_service

# 证据不再只限截图：代码、压缩包、视频也能作为"这次确实沟通过"的凭据。
# 按类型给不同上限：图片/PDF 小、压缩包中等、视频最大；
# 文件一律存原名之外的 UUID + 原后缀，下载接口按附件返回，不 inline 渲染。
EVIDENCE_IMAGE = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
EVIDENCE_DOC = {".pdf"}
EVIDENCE_ARCHIVE = {".zip", ".rar", ".7z"}
EVIDENCE_CODE = {
    ".py", ".js", ".ts", ".java", ".cpp", ".c", ".h", ".cs", ".go", ".rs",
    ".php", ".sql", ".html", ".css", ".vue", ".json", ".md", ".txt", ".ipynb",
}
EVIDENCE_VIDEO = {".mp4", ".webm", ".mov", ".m4v"}
EVIDENCE_EXT = (
    EVIDENCE_IMAGE | EVIDENCE_DOC | EVIDENCE_ARCHIVE | EVIDENCE_CODE | EVIDENCE_VIDEO
)

_MAX_MB_DEFAULT = 10
_MAX_MB_ARCHIVE = 30
_MAX_MB_VIDEO = 100
_CHUNK = 1024 * 1024


def _max_mb(suffix: str) -> int:
    if suffix in EVIDENCE_VIDEO:
        return _MAX_MB_VIDEO
    if suffix in EVIDENCE_ARCHIVE:
        return _MAX_MB_ARCHIVE
    return _MAX_MB_DEFAULT


def _evidence_dir(student_id: int) -> Path:
    path = get_settings().upload_path / "guidance" / str(student_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _abs_evidence(stored_path: str) -> Path:
    return get_settings().upload_path / stored_path


async def save_evidence(
    upload: UploadFile, student_id: int
) -> tuple[str, int, str, str]:
    """流式写盘并按类型限制大小，返回 (相对路径, 字节数, content_type, 原始文件名)。

    流式写而不是一次读进内存：视频动辄几十 MB，整块读会顶高进程内存。
    """
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in EVIDENCE_EXT:
        raise AppError(
            42250,
            "证据支持图片（jpg / png / webp / gif）、PDF、代码文件或压缩包（zip / rar / 7z）、"
            "视频（mp4 / webm / mov）",
            http_status=422,
        )

    target = _evidence_dir(student_id) / f"{uuid4().hex}{suffix}"
    max_mb = _max_mb(suffix)
    limit = max_mb * _CHUNK
    size = 0
    try:
        with target.open("wb") as fh:
            while chunk := await upload.read(_CHUNK):
                size += len(chunk)
                if size > limit:
                    raise AppError(
                        42251, f"证据文件不能超过 {max_mb}MB", http_status=413
                    )
                fh.write(chunk)
        if size == 0:
            raise AppError(42252, "证据文件内容为空，请重新选择", http_status=422)
    except Exception:
        target.unlink(missing_ok=True)
        raise

    return (
        f"guidance/{student_id}/{target.name}",
        size,
        upload.content_type or "",
        upload.filename or target.name,
    )


def normalize_when(value: datetime | None) -> datetime:
    """没填时间就按"现在"记：教师补录时往往记不清具体分钟，但日期不能空。"""
    if value is None:
        return datetime.now().astimezone()
    return value


def _validate_content(content: str) -> str:
    text = content.strip()
    if not text:
        raise AppError(42253, "请填写本次沟通的内容", http_status=422)
    if len(text) > 2000:
        raise AppError(42254, "沟通内容最多 2000 字", http_status=422)
    return text


async def create_record(
    db: AsyncSession,
    *,
    student: Student,
    teacher_id: int | None,
    stage: str,
    method: str,
    happened_at: datetime | None,
    content: str,
    upload: UploadFile | None = None,
) -> GuidanceRecord:
    text = _validate_content(content)
    stored = size = ctype = None
    name = None
    if upload is not None and (upload.filename or "").strip():
        stored, size, ctype, name = await save_evidence(upload, student.id)

    record = GuidanceRecord(
        student_id=student.id,
        teacher_id=teacher_id,
        stage=stage,
        method=method,
        happened_at=normalize_when(happened_at),
        content=text,
        evidence_name=name,
        evidence_path=stored,
        evidence_size=size,
        evidence_type=ctype or None,
    )
    try:
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record
    except Exception:
        if stored:
            _abs_evidence(stored).unlink(missing_ok=True)
        raise


def _base_query() -> Select:
    teacher = aliased(User)
    return (
        select(
            GuidanceRecord,
            Student.name,
            Student.sno,
            teacher.real_name,
            teacher.username,
        )
        .join(Student, GuidanceRecord.student_id == Student.id)
        .outerjoin(teacher, GuidanceRecord.teacher_id == teacher.id)
    )


async def list_records(
    db: AsyncSession,
    *,
    scope_teacher_id: int | None = None,
    scope_student_id: int | None = None,
    student_id: int | None = None,
    stage: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[GuidanceOut], int]:
    conditions = []
    if scope_student_id is not None:
        conditions.append(GuidanceRecord.student_id == scope_student_id)
    elif student_id is not None:
        conditions.append(GuidanceRecord.student_id == student_id)
    if scope_teacher_id is not None:
        conditions.append(Student.teacher_id == scope_teacher_id)
    if stage:
        conditions.append(GuidanceRecord.stage == stage)

    count_stmt = select(func.count()).select_from(GuidanceRecord).join(
        Student, GuidanceRecord.student_id == Student.id
    )
    for cond in conditions:
        count_stmt = count_stmt.where(cond)
    total = await db.scalar(count_stmt) or 0

    stmt = _base_query()
    for cond in conditions:
        stmt = stmt.where(cond)
    # 按"实际沟通时间"倒序：补录的记录不会因为录入晚而排到最前面
    stmt = (
        stmt.order_by(GuidanceRecord.happened_at.desc(), GuidanceRecord.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )

    rows = (await db.execute(stmt)).all()
    items = [
        GuidanceOut(
            id=record.id,
            student_id=record.student_id,
            student_name=name,
            sno=sno,
            teacher_id=record.teacher_id,
            teacher_name=teacher_name or teacher_username,
            stage=record.stage,  # type: ignore[arg-type]
            method=record.method,  # type: ignore[arg-type]
            happened_at=record.happened_at,
            content=record.content,
            evidence_name=record.evidence_name,
            evidence_size=record.evidence_size,
            evidence_type=record.evidence_type,
            created_at=record.created_at,
        )
        for record, name, sno, teacher_name, teacher_username in rows
    ]
    return items, total


async def get_or_404(db: AsyncSession, record_id: int) -> tuple[GuidanceRecord, Student]:
    row = (
        await db.execute(
            select(GuidanceRecord, Student)
            .join(Student, GuidanceRecord.student_id == Student.id)
            .where(GuidanceRecord.id == record_id)
        )
    ).first()
    if row is None:
        raise AppError(40405, "指导记录不存在", http_status=404)
    return row[0], row[1]


def absolute_evidence(record: GuidanceRecord) -> Path:
    if not record.evidence_path:
        raise AppError(40406, "这条记录没有上传证据", http_status=404)
    path = _abs_evidence(record.evidence_path)
    if not path.exists():
        raise AppError(40404, "证据文件已丢失，请联系管理员检查上传目录", http_status=404)
    return path


async def delete_record(db: AsyncSession, record: GuidanceRecord) -> None:
    path = _abs_evidence(record.evidence_path) if record.evidence_path else None
    await db.delete(record)
    await db.commit()
    # 先删记录再删文件：反过来一旦提交失败就会留下"有记录没文件"
    if path is not None:
        path.unlink(missing_ok=True)


async def count_midterm(db: AsyncSession, student_id: int) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(GuidanceRecord)
            .where(
                GuidanceRecord.student_id == student_id,
                GuidanceRecord.stage == Stage.MIDTERM.value,
            )
        )
    ) or 0


async def summary(db: AsyncSession, student_id: int) -> GuidanceSummary:
    rows = (
        await db.execute(
            select(GuidanceRecord.stage, func.count())
            .where(GuidanceRecord.student_id == student_id)
            .group_by(GuidanceRecord.stage)
        )
    ).all()
    by_stage = {stage: count for stage, count in rows}
    return GuidanceSummary(
        total=sum(by_stage.values()),
        by_stage=by_stage,
        midterm_count=by_stage.get(Stage.MIDTERM.value, 0),
        midterm_required=await config_service.get_midterm_min(db),
    )
