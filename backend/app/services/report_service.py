"""统计报表聚合。

口径集中在这里，避免每个页面各算一套：
- 学生按档案的当前环节 / 状态统计
- 材料数含历次版本，不去重（老师看到的“份数”就是版本数）
- 通过率 = 通过次数 / 审核总次数；没有审核记录时为 None，前端显示“—”
- 平均审核时长 = 教师处理时间 - 该环节最新一份材料的提交时间；
  没交材料就批的（比如直接放行选题）不计入，否则会把平均值拉成 0
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import STAGE_LABELS, STAGE_ORDER, ReviewAction, Role, Stage, StudentStatus
from app.models.guidance import GuidanceRecord
from app.models.material import Material
from app.models.stage_review import StageReview
from app.models.student import Student
from app.models.user import User
from app.schemas.stats import (
    ActivityPoint,
    DeadlineRow,
    DistributionItem,
    GuidanceStats,
    ReportOut,
    ReportSummary,
    StageReportRow,
    TeacherReportRow,
)
from app.services import config_service


def _rate(approved: int, total: int) -> float | None:
    if not total:
        return None
    return round(approved / total, 4)


async def _avg_review_hours(db: AsyncSession) -> float | None:
    material_rows = (
        await db.execute(
            select(Material.student_id, Material.stage, func.max(Material.created_at)).group_by(
                Material.student_id, Material.stage
            )
        )
    ).all()
    latest_material = {
        (student_id, stage): last_at for student_id, stage, last_at in material_rows
    }

    review_rows = (
        await db.execute(select(StageReview.student_id, StageReview.stage, StageReview.created_at))
    ).all()

    spans: list[float] = []
    for student_id, stage, reviewed_at in review_rows:
        submitted_at = latest_material.get((student_id, stage))
        if submitted_at is None:
            continue
        seconds = (reviewed_at - submitted_at).total_seconds()
        # 材料晚于审核时间的情况（先批后补材料）没有参考价值，跳过负值
        if seconds <= 0:
            continue
        spans.append(seconds / 3600)

    if not spans:
        return None
    return round(sum(spans) / len(spans), 2)


async def _activity(
    db: AsyncSession, *, days: int
) -> list[ActivityPoint]:
    today = datetime.now().astimezone().date()
    start_day = today - timedelta(days=days - 1)
    start = datetime.combine(start_day, time.min).astimezone()

    buckets: dict[date, dict[str, int]] = {
        start_day + timedelta(days=i): {"materials": 0, "approvals": 0, "returns": 0}
        for i in range(days)
    }

    material_times = (
        await db.scalars(select(Material.created_at).where(Material.created_at >= start))
    ).all()
    for created_at in material_times:
        day = created_at.astimezone().date()
        if day in buckets:
            buckets[day]["materials"] += 1

    review_rows = (
        await db.execute(
            select(StageReview.created_at, StageReview.action).where(StageReview.created_at >= start)
        )
    ).all()
    for created_at, action in review_rows:
        day = created_at.astimezone().date()
        if day not in buckets:
            continue
        key = "approvals" if action == ReviewAction.APPROVE.value else "returns"
        buckets[day][key] += 1

    return [
        ActivityPoint(date=day, materials=value["materials"], approvals=value["approvals"], returns=value["returns"])
        for day, value in sorted(buckets.items())
    ]


async def build_report(db: AsyncSession, *, days: int = 14) -> ReportOut:
    students_total = await db.scalar(select(func.count()).select_from(Student)) or 0
    archived_total = await db.scalar(
        select(func.count()).select_from(Student).where(Student.status == StudentStatus.ARCHIVED.value)
    ) or 0
    teachers_total = await db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == Role.TEACHER.value, User.is_active.is_(True))
    ) or 0
    materials_total = await db.scalar(select(func.count()).select_from(Material)) or 0

    # ---- 按环节 ----
    stage_students = {
        stage: count
        for stage, count in (
            await db.execute(select(Student.current_stage, func.count()).group_by(Student.current_stage))
        ).all()
    }
    stage_materials = {
        stage: count
        for stage, count in (
            await db.execute(select(Material.stage, func.count()).group_by(Material.stage))
        ).all()
    }
    stage_reviews: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "APPROVE": 0, "RETURN": 0})
    for stage, action, count in (
        await db.execute(
            select(StageReview.stage, StageReview.action, func.count()).group_by(
                StageReview.stage, StageReview.action
            )
        )
    ).all():
        stage_reviews[stage]["total"] += count
        stage_reviews[stage][action] += count

    stages = [
        StageReportRow(
            stage=stage,
            label=STAGE_LABELS[stage],
            students=stage_students.get(stage.value, 0),
            materials=stage_materials.get(stage.value, 0),
            reviews=stage_reviews[stage.value]["total"],
            approved=stage_reviews[stage.value]["APPROVE"],
            returned=stage_reviews[stage.value]["RETURN"],
        )
        for stage in STAGE_ORDER
    ]

    # ---- 按教师 ----
    # 先按 (导师, 状态) 汇总学生，再补材料 / 审核；一次一个查询，不在循环里查库
    teacher_students: dict[int | None, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "active": 0, "archived": 0}
    )
    for teacher_id, status, count in (
        await db.execute(
            select(Student.teacher_id, Student.status, func.count()).group_by(
                Student.teacher_id, Student.status
            )
        )
    ).all():
        teacher_students[teacher_id]["total"] += count
        if status == StudentStatus.ARCHIVED.value:
            teacher_students[teacher_id]["archived"] += count
        else:
            teacher_students[teacher_id]["active"] += count

    teacher_materials = {
        teacher_id: count
        for teacher_id, count in (
            await db.execute(
                select(Student.teacher_id, func.count(Material.id))
                .join(Student, Material.student_id == Student.id)
                .group_by(Student.teacher_id)
            )
        ).all()
    }
    teacher_reviews: dict[int | None, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "APPROVE": 0, "RETURN": 0}
    )
    for teacher_id, action, count in (
        await db.execute(
            select(Student.teacher_id, StageReview.action, func.count())
            .join(Student, StageReview.student_id == Student.id)
            .group_by(Student.teacher_id, StageReview.action)
        )
    ).all():
        teacher_reviews[teacher_id]["total"] += count
        teacher_reviews[teacher_id][action] += count

    last_reviews = {
        teacher_id: last_at
        for teacher_id, last_at in (
            await db.execute(
                select(Student.teacher_id, func.max(StageReview.created_at))
                .join(Student, StageReview.student_id == Student.id)
                .group_by(Student.teacher_id)
            )
        ).all()
    }

    teacher_names = {
        user_id: (real_name or username)
        for user_id, real_name, username in (
            await db.execute(
                select(User.id, User.real_name, User.username).where(User.role == Role.TEACHER.value)
            )
        ).all()
    }

    # 有学生的教师 + 未指派那一组；没带学生的教师不占一行，避免表格里全是 0
    rows_teachers: list[TeacherReportRow] = []
    for teacher_id in set(teacher_students) | set(teacher_materials) | set(teacher_reviews):
        if teacher_id is None and not teacher_students.get(None):
            # 只有“材料/审核”挂在无导师学生上时才需要这行，理论上不会出现
            continue
        stats = teacher_students.get(teacher_id, {"total": 0, "active": 0, "archived": 0})
        review_stats = teacher_reviews.get(teacher_id, {"total": 0, "APPROVE": 0, "RETURN": 0})
        rows_teachers.append(
            TeacherReportRow(
                teacher_id=teacher_id,
                name="未指派" if teacher_id is None else teacher_names.get(teacher_id, f"#{teacher_id}"),
                students=stats["total"],
                active=stats["active"],
                archived=stats["archived"],
                materials=teacher_materials.get(teacher_id, 0),
                reviews=review_stats["total"],
                approve_rate=_rate(review_stats["APPROVE"], review_stats["total"]),
                last_reviewed_at=last_reviews.get(teacher_id),
            )
        )

    # 按学生数降序，未指派垫底：一眼看出谁带的组大、谁还没分到学生
    rows_teachers.sort(key=lambda row: (row.teacher_id is None, -row.students, row.name))

    # ---- 总计与平均 ----
    review_action_counts = {
        action: count
        for action, count in (
            await db.execute(select(StageReview.action, func.count()).group_by(StageReview.action))
        ).all()
    }
    approved = review_action_counts.get(ReviewAction.APPROVE.value, 0)
    returned = review_action_counts.get(ReviewAction.RETURN.value, 0)
    reviews_total = approved + returned

    summary = ReportSummary(
        students_total=students_total,
        in_progress=students_total - archived_total,
        archived=archived_total,
        teachers_total=teachers_total,
        materials_total=materials_total,
        reviews_total=reviews_total,
        approved=approved,
        returned=returned,
        approve_rate=_rate(approved, reviews_total),
        avg_review_hours=await _avg_review_hours(db),
    )

    # ---- 指导记录：中期检查的硬要求在报表里也要能看出来 ----
    guidance_by_method = {
        method: count
        for method, count in (
            await db.execute(
                select(GuidanceRecord.method, func.count()).group_by(GuidanceRecord.method)
            )
        ).all()
    }
    evidence_total = await db.scalar(
        select(func.count())
        .select_from(GuidanceRecord)
        .where(GuidanceRecord.evidence_path.is_not(None))
    ) or 0
    students_with_guidance = await db.scalar(
        select(func.count(func.distinct(GuidanceRecord.student_id)))
    ) or 0
    midterm_counts = (
        await db.execute(
            select(GuidanceRecord.student_id, func.count())
            .where(GuidanceRecord.stage == Stage.MIDTERM.value)
            .group_by(GuidanceRecord.student_id)
        )
    ).all()
    midterm_required = await config_service.get_midterm_min(db)
    guidance = GuidanceStats(
        total=sum(guidance_by_method.values()),
        meet=guidance_by_method.get("MEET", 0),
        online=guidance_by_method.get("ONLINE", 0),
        evidence=evidence_total,
        students_with_guidance=students_with_guidance,
        midterm_total=sum(count for _, count in midterm_counts),
        midterm_required=midterm_required,
        midterm_reached=sum(1 for _, count in midterm_counts if count >= midterm_required),
    )

    # ---- 学生结构：专业 / 班级 / 年级 ----
    async def _distribution(column) -> list[DistributionItem]:
        rows = (
            await db.execute(
                select(column, func.count())
                .where(column.is_not(None))
                .group_by(column)
                .order_by(func.count().desc(), column)
            )
        ).all()
        return [DistributionItem(name=name or "未填写", count=count) for name, count in rows]

    majors = await _distribution(Student.major)
    classes = await _distribution(Student.class_name)
    grades = await _distribution(Student.grade)

    # ---- 截止与逾期：只统计当前停在某环节的学生，已放行的不再算逾期 ----
    deadline_map = await config_service.get_stage_deadlines(db)
    today = datetime.now().astimezone().date()
    deadlines = [
        DeadlineRow(
            stage=stage,
            label=STAGE_LABELS[stage],
            deadline=deadline_map.get(stage),
            students=stage_students.get(stage.value, 0),
            overdue=(stage_students.get(stage.value, 0) if deadline_map.get(stage) and deadline_map[stage] < today else 0),
        )
        for stage in STAGE_ORDER
    ]

    return ReportOut(
        summary=summary,
        stages=stages,
        teachers=rows_teachers,
        activity=await _activity(db, days=days),
        guidance=guidance,
        majors=majors,
        classes=classes,
        grades=grades,
        deadlines=deadlines,
    )
