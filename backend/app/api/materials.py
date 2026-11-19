"""阶段材料接口。

权限：
- 学生：只能上传/查看/删除自己的材料
- 教师：可以查看名下学生的材料（只读）
- 管理员：可以查看全部，也可以代学生上传（批量补录历史材料时用得上）
"""

from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser, DBDep
from app.core.exceptions import AppError
from app.core.response import ApiResponse, ok
from app.models.enums import Role, Stage
from app.models.student import Student
from app.models.user import User
from app.schemas.material import MaterialOut, MaterialPage
from app.services import material_service as svc
from app.services import student_service as student_svc

router = APIRouter(prefix="/materials", tags=["材料"])


def _ensure_view(student: Student, actor: User) -> None:
    if actor.role == Role.ADMIN.value:
        return
    if actor.role == Role.TEACHER.value and student.teacher_id == actor.id:
        return
    if actor.role == Role.STUDENT.value and student.user_id == actor.id:
        return
    raise AppError(40300, "没有权限查看该学生的材料", http_status=403)


@router.get("", response_model=ApiResponse[MaterialPage], summary="材料列表")
async def list_materials(
    db: DBDep,
    actor: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    stage: Annotated[Stage | None, Query()] = None,
    keyword: Annotated[str | None, Query(max_length=50)] = None,
    student_id: Annotated[int | None, Query()] = None,
) -> ApiResponse[MaterialPage]:
    scope_teacher_id = actor.id if actor.role == Role.TEACHER.value else None
    scope_student_id: int | None = None

    if actor.role == Role.STUDENT.value:
        student = await student_svc.get_student_by_user(db, actor.id)
        if student is None:
            return ok(MaterialPage(items=[], total=0, page=page, size=size))
        scope_student_id = student.id
    elif actor.role not in (Role.ADMIN.value, Role.TEACHER.value):
        raise AppError(40300, "没有权限查看材料", http_status=403)

    items, total = await svc.list_materials(
        db,
        scope_teacher_id=scope_teacher_id,
        scope_student_id=scope_student_id,
        student_id=student_id,
        stage=stage.value if stage else None,
        keyword=keyword,
        page=page,
        size=size,
    )
    return ok(MaterialPage(items=items, total=total, page=page, size=size))


@router.post("", response_model=ApiResponse[MaterialOut], summary="上传材料（自动生成新版本）")
async def upload_material(
    db: DBDep,
    actor: CurrentUser,
    stage: Annotated[Stage, Form(description="所属环节")],
    title: Annotated[str, Form(min_length=1, max_length=120, description="材料名称")],
    file: Annotated[UploadFile, File(description="PDF / Word / 图片 / 压缩包，20MB 以内")],
    note: Annotated[str | None, Form(max_length=500)] = None,
    student_id: Annotated[int | None, Form(description="管理员代上传时指定学生")] = None,
) -> ApiResponse[MaterialOut]:
    if actor.role == Role.STUDENT.value:
        student = await student_svc.get_student_by_user(db, actor.id)
        if student is None:
            raise AppError(40302, "当前账号还没有学生档案，无法上传材料", http_status=403)
    elif actor.role == Role.ADMIN.value:
        if student_id is None:
            raise AppError(42213, "管理员上传时需指定学生", http_status=422)
        student = await student_svc.get_student_or_404(db, student_id)
    else:
        raise AppError(40300, "教师不直接上传材料，请让学生本人提交", http_status=403)

    material = await svc.create_material(
        db,
        student=student,
        stage=stage.value,
        title=title,
        note=note,
        upload=file,
        uploaded_by=actor.id,
    )
    item = MaterialOut(
        id=material.id,
        student_id=material.student_id,
        student_name=student.name,
        sno=student.sno,
        stage=material.stage,  # type: ignore[arg-type]
        title=material.title,
        version=material.version,
        file_name=material.file_name,
        file_size=material.file_size,
        content_type=material.content_type,
        note=material.note,
        uploader_name=actor.real_name or actor.username,
        created_at=material.created_at,
    )
    return ok(item, message=f"已上传，当前为第 {material.version} 版")


@router.get("/{material_id}/download", summary="下载材料")
async def download_material(db: DBDep, actor: CurrentUser, material_id: int) -> FileResponse:
    material, student = await svc.get_material_or_404(db, material_id)
    _ensure_view(student, actor)
    path = svc.absolute_file(material)
    return FileResponse(
        path,
        filename=material.file_name,
        media_type=material.content_type or "application/octet-stream",
    )


@router.delete("/{material_id}", response_model=ApiResponse[None], summary="删除材料")
async def delete_material(db: DBDep, actor: CurrentUser, material_id: int) -> ApiResponse[None]:
    material, student = await svc.get_material_or_404(db, material_id)
    if actor.role == Role.ADMIN.value:
        pass
    elif actor.role == Role.STUDENT.value and student.user_id == actor.id:
        pass
    else:
        raise AppError(40300, "只能删除自己上传的材料", http_status=403)
    await svc.delete_material(db, material)
    return ok(message="已删除该版本材料")
