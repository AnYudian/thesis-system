"""管理员概览统计。

统计口径直接取自学生当前阶段（current_stage），
不依赖前端计算，避免以后接入审核流转时两处逻辑不一致。
"""

from typing import Annotated
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, select

from app.api.deps import DBDep, require_role
from app.core.response import ApiResponse, ok
from app.models.audit_log import AuditLog
from app.models.enums import AI_STAGES, STAGE_LABELS, STAGE_ORDER, Role, StudentStatus
from app.models.material import Material
from app.models.student import Student
from app.models.user import User
from app.schemas.stats import OverviewOut, RecentLogin, ReportOut, StageCount
from app.services import report_service
from app.services import export_service

router = APIRouter(prefix="/stats", tags=["统计"])

AdminUser = Annotated[User, Depends(require_role(Role.ADMIN))]


@router.get("/overview", response_model=ApiResponse[OverviewOut], summary="管理员概览（仅管理员）")
async def overview(db: DBDep, _: AdminUser) -> ApiResponse[OverviewOut]:
    students_total = await db.scalar(select(func.count()).select_from(Student)) or 0
    archived = await db.scalar(
        select(func.count()).select_from(Student).where(Student.status == StudentStatus.ARCHIVED.value)
    ) or 0
    teachers_total = await db.scalar(
        select(func.count()).select_from(User).where(User.role == Role.TEACHER.value, User.is_active.is_(True))
    ) or 0
    materials_total = await db.scalar(select(func.count()).select_from(Material)) or 0

    stage_rows = await db.execute(select(Student.current_stage, func.count()).group_by(Student.current_stage))
    stage_counts = {stage: count for stage, count in stage_rows.all()}

    stages = [
        StageCount(
            stage=stage,
            label=STAGE_LABELS[stage],
            count=stage_counts.get(stage.value, 0),
            ai_capable=stage in AI_STAGES,
        )
        for stage in STAGE_ORDER
    ]

    login_rows = await db.execute(
        select(AuditLog, User)
        .join(User, AuditLog.user_id == User.id, isouter=True)
        .where(AuditLog.action == "LOGIN")
        .order_by(AuditLog.id.desc())
        .limit(6)
    )
    recent_logins = [
        RecentLogin(
            id=log.id,
            username=user.username if user else "已删除账号",
            real_name=user.real_name if user else None,
            role=user.role if user else "UNKNOWN",
            created_at=log.created_at,
        )
        for log, user in login_rows.all()
    ]

    return ok(
        OverviewOut(
            students_total=students_total,
            teachers_total=teachers_total,
            in_progress=students_total - archived,
            archived=archived,
            materials_total=materials_total,
            stages=stages,
            recent_logins=recent_logins,
        )
    )


@router.get("/report", response_model=ApiResponse[ReportOut], summary="统计报表（仅管理员）")
async def report(
    db: DBDep,
    _: AdminUser,
    days: Annotated[int, Query(ge=7, le=90, description="动态图统计最近多少天")] = 14,
) -> ApiResponse[ReportOut]:
    # 报表全量返回，不分页：九环节 + 教师人数都是几十行级别，一次给前端更省事
    return ok(await report_service.build_report(db, days=days))


@router.get("/export.xlsx", summary="导出统计报表（Excel，仅管理员）")
async def export_xlsx(
    db: DBDep,
    _: AdminUser,
    days: Annotated[int, Query(ge=7, le=90, description="动态趋势统计最近多少天")] = 14,
) -> Response:
    report = await report_service.build_report(db, days=days)
    content = await export_service.build_workbook(db, report)

    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M")
    ascii_name = f"thesis-report-{stamp}.xlsx"
    utf8_name = quote(f"统计报表-{stamp}.xlsx")
    # 中文文件名走 filename*（RFC 5987），filename 留 ASCII 兜底给老浏览器
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={ascii_name}; filename*=UTF-8''{utf8_name}"
        },
    )
