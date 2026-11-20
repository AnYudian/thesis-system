"""学生与课题建档接口。

权限口径：
- 管理员：全部学生，可增删改、指派导师、设置课题
- 教师：只看自己名下的学生，可为自己名下学生设置课题（选题阶段实际由教师出题）
- 学生：只能看自己
"""

from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DBDep, require_role
from app.core.exceptions import AppError
from app.core.response import ApiResponse, ok
from app.models.enums import Role, Stage, StudentStatus
from app.models.student import Student
from app.models.user import User
from app.schemas.student import (
    AssignTeacherIn,
    AssignTeacherOut,
    ImportIn,
    ImportResult,
    StudentCreate,
    StudentCreated,
    StudentDetail,
    StudentOut,
    StudentPage,
    StudentUpdate,
    TopicIn,
    TopicOut,
)
from app.services import log_service
from app.services import student_service as svc

router = APIRouter(prefix="/students", tags=["学生与课题"])

AdminUser = Annotated[User, Depends(require_role(Role.ADMIN))]


def _ensure_view(student: Student, actor: User) -> None:
    if actor.role == Role.ADMIN.value:
        return
    if actor.role == Role.TEACHER.value and student.teacher_id == actor.id:
        return
    if actor.role == Role.STUDENT.value and student.user_id == actor.id:
        return
    raise AppError(40300, "没有权限查看该学生", http_status=403)


def _ensure_topic_write(student: Student, actor: User) -> None:
    if actor.role == Role.ADMIN.value:
        return
    if actor.role == Role.TEACHER.value and student.teacher_id == actor.id:
        return
    raise AppError(40300, "只有管理员或该生的指导教师可以设置课题", http_status=403)


@router.get("", response_model=ApiResponse[StudentPage], summary="学生列表")
async def list_students(
    db: DBDep,
    actor: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    keyword: Annotated[str | None, Query(max_length=50)] = None,
    stage: Annotated[Stage | None, Query()] = None,
    status: Annotated[StudentStatus | None, Query()] = None,
    teacher_id: Annotated[int | None, Query()] = None,
) -> ApiResponse[StudentPage]:
    if actor.role not in (Role.ADMIN.value, Role.TEACHER.value):
        raise AppError(40300, "没有权限查看学生列表", http_status=403)

    items, total = await svc.list_students(
        db,
        scope_teacher_id=actor.id if actor.role == Role.TEACHER.value else None,
        page=page,
        size=size,
        keyword=keyword,
        stage=stage.value if stage else None,
        status=status.value if status else None,
        teacher_id=teacher_id,
    )
    return ok(StudentPage(items=items, total=total, page=page, size=size))


# 必须放在 /{student_id} 之前，否则 "me" 会被当成路径参数
@router.get("/me", response_model=ApiResponse[StudentDetail | None], summary="学生查看自己的档案")
async def my_profile(db: DBDep, actor: CurrentUser) -> ApiResponse[StudentDetail | None]:
    student = await svc.get_student_by_user(db, actor.id)
    # 账号已开通但还没建档是正常状态，不是错误：返回 null 让前端展示引导文案，
    # 而不是弹一个红色错误提示。
    if student is None:
        return ok(None, message="尚未建立学生档案")
    return ok(await svc.get_detail(db, student))


@router.get("/{student_id}", response_model=ApiResponse[StudentDetail], summary="学生详情")
async def get_student(db: DBDep, actor: CurrentUser, student_id: int) -> ApiResponse[StudentDetail]:
    student = await svc.get_student_or_404(db, student_id)
    _ensure_view(student, actor)
    return ok(await svc.get_detail(db, student))


@router.post("/import", response_model=ApiResponse[ImportResult], summary="批量导入学生（仅管理员）")
async def import_students(db: DBDep, actor: AdminUser, data: ImportIn) -> ApiResponse[ImportResult]:
    result = await svc.import_students(
        db, text=data.text, create_account=data.create_account
    )
    await log_service.commit_record(
        db,
        user_id=actor.id,
        action="STUDENT_IMPORT",
        target_type="STUDENT",
        detail={"created": result.created, "skipped": result.skipped},
    )
    return ok(result, message=f"已导入 {result.created} 人" + (f"，跳过 {result.skipped} 行" if result.skipped else ""))


@router.post(
    "/import/file", response_model=ApiResponse[ImportResult], summary="批量导入学生（Excel）"
)
async def import_students_file(
    db: DBDep,
    actor: AdminUser,
    file: Annotated[UploadFile, File(description=".xlsx 文件，第一行可为表头")],
    create_account: Annotated[bool, Form()] = True,
) -> ApiResponse[ImportResult]:
    filename = (file.filename or "").lower()
    if not filename.endswith(".xlsx"):
        raise AppError(42236, "只支持 .xlsx 文件，请在 Excel 里另存为 .xlsx 后重试", http_status=422)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise AppError(42237, "Excel 文件不能超过 5MB", http_status=422)

    result = await svc.import_students(db, data=content, create_account=create_account)
    await log_service.commit_record(
        db,
        user_id=actor.id,
        action="STUDENT_IMPORT",
        target_type="STUDENT",
        detail={"created": result.created, "skipped": result.skipped, "source": "xlsx"},
    )
    return ok(
        result,
        message=f"已导入 {result.created} 人" + (f"，跳过 {result.skipped} 行" if result.skipped else ""),
    )


@router.get("/import/template", summary="下载学生批量导入模板（仅管理员）")
async def import_template(_: AdminUser) -> StreamingResponse:
    """给管理员一份带表头与示例行的 .xlsx。

    列顺序与 import_students 的解析保持一致，改列时两处必须同步；
    说明放在第二个 Sheet，导入只读第一个 Sheet，不会把说明当成数据。
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    book = Workbook()
    sheet = book.active
    sheet.title = "学生名单"

    headers = ["学号", "姓名", "专业", "班级", "年级", "指导教师账号"]
    sheet.append(headers)
    sheet.append(["20220001", "张三", "软件工程", "软工2201", "2022", "teacher"])

    for index, width in enumerate([16, 10, 18, 14, 10, 18], start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="F2EFE6")
        cell.alignment = Alignment(horizontal="center")
    sheet.freeze_panes = "A2"

    notes = book.create_sheet("填写说明")
    notes.column_dimensions["A"].width = 92
    for line in [
        "1. 第一行是表头，可保留也可删除；从第二行开始，每行填一个学生。",
        "2. 列顺序固定：学号、姓名、专业、班级、年级、指导教师账号。",
        "3. 学号 4-30 位，只能用字母、数字、下划线或横线；年级填入学年份，如 2022。",
        "4. 指导教师账号填教师的登录账号（如 teacher），必须是指导教师身份且已启用。",
        "5. 单次最多 500 行、文件不超过 5MB；名单内或库里已存在的学号会跳过并在结果里提示。",
        "6. 示例行导入前请删除或替换成真实学生。",
    ]:
        notes.append([line])

    buffer = BytesIO()
    book.save(buffer)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="students_import_template.xlsx"'},
    )


@router.post(
    "/assign-teacher",
    response_model=ApiResponse[AssignTeacherOut],
    summary="批量指派导师（仅管理员）",
)
async def assign_teacher(
    db: DBDep, actor: AdminUser, data: AssignTeacherIn
) -> ApiResponse[AssignTeacherOut]:
    updated, teacher_name = await svc.assign_teacher(
        db, student_ids=data.student_ids, teacher_id=data.teacher_id
    )
    await log_service.commit_record(
        db,
        user_id=actor.id,
        action="STUDENT_ASSIGN_TEACHER",
        target_type="USER",
        target_id=data.teacher_id,
        detail={"teacher": teacher_name, "count": updated},
    )
    return ok(
        AssignTeacherOut(updated=updated, teacher_name=teacher_name),
        message=f"已把 {updated} 名学生指派给 {teacher_name}",
    )


@router.post("", response_model=ApiResponse[StudentCreated], summary="新建学生（仅管理员）")
async def create_student(
    db: DBDep, actor: AdminUser, data: StudentCreate
) -> ApiResponse[StudentCreated]:
    student, initial_password = await svc.create_student(db, data)
    await log_service.commit_record(
        db,
        user_id=actor.id,
        action="STUDENT_CREATE",
        target_type="STUDENT",
        target_id=student.id,
        detail={"sno": student.sno, "name": student.name},
    )
    detail = await svc.get_detail(db, student)
    return ok(
        StudentCreated(
            student=StudentOut(**detail.model_dump(exclude={"topic"})),
            initial_password=initial_password,
        ),
        message="学生已建档" if initial_password is None else "学生已建档，登录账号已开通",
    )


@router.patch("/{student_id}", response_model=ApiResponse[StudentDetail], summary="修改学生（仅管理员）")
async def update_student(
    db: DBDep, actor: AdminUser, student_id: int, data: StudentUpdate
) -> ApiResponse[StudentDetail]:
    student = await svc.get_student_or_404(db, student_id)
    changed = data.model_dump(exclude_unset=True)
    student = await svc.update_student(db, student, data)
    await log_service.commit_record(
        db,
        user_id=actor.id,
        action="STUDENT_UPDATE",
        target_type="STUDENT",
        target_id=student.id,
        detail={"sno": student.sno, "fields": sorted(changed)},
    )
    return ok(await svc.get_detail(db, student), message="已保存")


@router.delete("/{student_id}", response_model=ApiResponse[None], summary="删除学生（仅管理员）")
async def delete_student(db: DBDep, actor: AdminUser, student_id: int) -> ApiResponse[None]:
    student = await svc.get_student_or_404(db, student_id)
    sno, name = student.sno, student.name
    await svc.delete_student(db, student)
    await log_service.commit_record(
        db,
        user_id=actor.id,
        action="STUDENT_DELETE",
        target_type="STUDENT",
        target_id=student_id,
        detail={"sno": sno, "name": name},
    )
    return ok(message="已删除学生及其登录账号")


@router.put("/{student_id}/topic", response_model=ApiResponse[TopicOut], summary="设置/修改课题")
async def upsert_topic(
    db: DBDep, actor: CurrentUser, student_id: int, data: TopicIn
) -> ApiResponse[TopicOut]:
    student = await svc.get_student_or_404(db, student_id)
    _ensure_topic_write(student, actor)
    topic = await svc.upsert_topic(db, student, data)
    await log_service.commit_record(
        db,
        user_id=actor.id,
        action="TOPIC_UPDATE",
        target_type="STUDENT",
        target_id=student.id,
        detail={"sno": student.sno, "title": topic.title},
    )
    return ok(TopicOut.model_validate(topic), message="课题已保存")


@router.delete("/{student_id}/topic", response_model=ApiResponse[None], summary="清除课题")
async def delete_topic(db: DBDep, actor: CurrentUser, student_id: int) -> ApiResponse[None]:
    student = await svc.get_student_or_404(db, student_id)
    _ensure_topic_write(student, actor)
    await svc.delete_topic(db, student)
    await log_service.commit_record(
        db,
        user_id=actor.id,
        action="TOPIC_DELETE",
        target_type="STUDENT",
        target_id=student.id,
        detail={"sno": student.sno},
    )
    return ok(message="课题已清除")
