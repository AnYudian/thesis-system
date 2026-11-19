"""材料上传与查询。

文件写盘与数据库记录要尽量保持一致：先写盘、再落库，
落库失败就把刚写的文件删掉，避免磁盘上留下一堆没有记录可查的孤儿文件。
"""

from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.material import Material
from app.models.student import Student
from app.models.user import User
from app.schemas.material import MaterialOut

# 毕业设计材料以文档为主，附带少量扫描件与压缩包
ALLOWED_EXT = {".pdf", ".doc", ".docx", ".zip", ".rar", ".jpg", ".jpeg", ".png"}
_CHUNK = 1024 * 1024


def _abs_path(stored_path: str) -> Path:
    return get_settings().upload_path / stored_path


async def save_upload(upload: UploadFile, student_id: int, stage: str) -> tuple[str, int, str]:
    """流式写盘并限制大小，返回 (相对路径, 字节数, content_type)。"""
    settings = get_settings()
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXT:
        raise AppError(
            42210,
            f"不支持的文件类型 {suffix or '（无扩展名）'}，仅支持 PDF / Word / 压缩包 / 图片",
            http_status=422,
        )

    target_dir = settings.upload_path / str(student_id) / stage
    target_dir.mkdir(parents=True, exist_ok=True)
    abs_path = target_dir / f"{uuid4().hex}{suffix}"

    limit = settings.max_upload_mb * _CHUNK
    size = 0
    try:
        with abs_path.open("wb") as fh:
            while chunk := await upload.read(_CHUNK):
                size += len(chunk)
                # 边读边判，避免等整个文件传完才发现超限
                if size > limit:
                    raise AppError(
                        42211,
                        f"文件超过 {settings.max_upload_mb}MB 限制，请压缩后再上传",
                        http_status=413,
                    )
                fh.write(chunk)
        if size == 0:
            raise AppError(42212, "文件内容为空，请重新选择", http_status=422)
    except Exception:
        abs_path.unlink(missing_ok=True)
        raise

    return f"{student_id}/{stage}/{abs_path.name}", size, upload.content_type or ""


async def next_version(db: AsyncSession, student_id: int, stage: str) -> int:
    current = await db.scalar(
        select(func.max(Material.version)).where(
            Material.student_id == student_id, Material.stage == stage
        )
    )
    return (current or 0) + 1


async def create_material(
    db: AsyncSession,
    *,
    student: Student,
    stage: str,
    title: str,
    note: str | None,
    upload: UploadFile,
    uploaded_by: int,
) -> Material:
    stored_path, size, content_type = await save_upload(upload, student.id, stage)
    try:
        material = Material(
            student_id=student.id,
            stage=stage,
            title=title.strip(),
            version=await next_version(db, student.id, stage),
            file_name=upload.filename or f"{stage}.bin",
            stored_path=stored_path,
            file_size=size,
            content_type=content_type or None,
            note=note,
            uploaded_by=uploaded_by,
        )
        db.add(material)
        await db.commit()
        await db.refresh(material)
        return material
    except Exception:
        # 落库失败时把刚写的文件清掉，避免磁盘与数据库对不上
        _abs_path(stored_path).unlink(missing_ok=True)
        raise


def _base_query() -> Select:
    return (
        select(Material, Student.name, Student.sno, User.real_name)
        .join(Student, Material.student_id == Student.id)
        .outerjoin(User, Material.uploaded_by == User.id)
    )


async def list_materials(
    db: AsyncSession,
    *,
    scope_teacher_id: int | None = None,
    scope_student_id: int | None = None,
    student_id: int | None = None,
    stage: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[MaterialOut], int]:
    conditions = []
    if scope_student_id is not None:
        conditions.append(Material.student_id == scope_student_id)
    elif student_id is not None:
        conditions.append(Material.student_id == student_id)
    if scope_teacher_id is not None:
        conditions.append(Student.teacher_id == scope_teacher_id)
    if stage:
        conditions.append(Material.stage == stage)
    if keyword:
        like = f"%{keyword.strip()}%"
        conditions.append(
            or_(Student.name.ilike(like), Student.sno.ilike(like), Material.title.ilike(like))
        )

    count_stmt = select(func.count()).select_from(Material).join(Student, Material.student_id == Student.id)
    for cond in conditions:
        count_stmt = count_stmt.where(cond)
    total = await db.scalar(count_stmt) or 0

    stmt = _base_query()
    for cond in conditions:
        stmt = stmt.where(cond)
    # 新的在前：材料和版本都是"最近一版最有用"
    stmt = stmt.order_by(Material.created_at.desc(), Material.id.desc()).offset((page - 1) * size).limit(size)

    rows = (await db.execute(stmt)).all()
    items = [
        MaterialOut(
            id=m.id,
            student_id=m.student_id,
            student_name=name,
            sno=sno,
            stage=m.stage,  # type: ignore[arg-type]
            title=m.title,
            version=m.version,
            file_name=m.file_name,
            file_size=m.file_size,
            content_type=m.content_type,
            note=m.note,
            uploader_name=uploader_name,
            created_at=m.created_at,
        )
        for m, name, sno, uploader_name in rows
    ]
    return items, total


async def get_material_or_404(db: AsyncSession, material_id: int) -> tuple[Material, Student]:
    row = (
        await db.execute(
            select(Material, Student).join(Student, Material.student_id == Student.id).where(Material.id == material_id)
        )
    ).first()
    if row is None:
        raise AppError(40403, "材料不存在", http_status=404)
    return row[0], row[1]


def absolute_file(material: Material) -> Path:
    path = _abs_path(material.stored_path)
    if not path.exists():
        raise AppError(40404, "文件已丢失，请联系管理员检查上传目录", http_status=404)
    return path


async def delete_material(db: AsyncSession, material: Material) -> None:
    path = _abs_path(material.stored_path)
    await db.delete(material)
    await db.commit()
    # 先删记录再删文件：记录没了文件还在只是占空间，反过来则会出现"有记录下载不到"
    path.unlink(missing_ok=True)
    # 顺手清掉空的 学生/环节 目录，免得演示机上越积越多空文件夹
    for directory in (path.parent, path.parent.parent):
        try:
            directory.rmdir()
        except OSError:
            break
