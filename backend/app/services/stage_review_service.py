"""阶段审核业务。

规则：
- 只能审核学生"当前停着"的那个环节，不能跳着批
- 通过 → 进入下一环节；已是最后一个环节则学生归档
- 退回 → 学生留在原环节，必须写原因
- 审核连点两下不能推进两个环节：查学生时加行锁，第二个请求会看到已经变了的状态
"""

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.audit_log import AuditLog
from app.models.enums import STAGE_NEXT, STAGE_ORDER, ReviewAction, Stage, StudentStatus
from app.models.material import Material
from app.models.stage_review import StageReview
from app.models.student import Student
from app.models.user import User
from app.schemas.review import PendingItem, ReviewOut


async def decide(
    db: AsyncSession,
    *,
    student_id: int,
    reviewer: User,
    action: ReviewAction,
    comment: str | None,
) -> tuple[StageReview, Student]:
    # FOR UPDATE：同一学生的两次点击串行执行，避免一次通过直接跨两环
    student = await db.scalar(select(Student).where(Student.id == student_id).with_for_update())
    if student is None:
        raise AppError(40401, "学生不存在", http_status=404)
    if student.status == StudentStatus.ARCHIVED.value:
        raise AppError(40910, "该学生已归档，无需再审核", http_status=409)

    current = Stage(student.current_stage)
    text = (comment or "").strip() or None
    if action is ReviewAction.RETURN and text is None:
        raise AppError(42220, "退回必须填写原因，学生要知道改什么", http_status=422)

    # 审核时该环节的最新版本，写进记录里方便回溯"当时看的是哪一版"
    material_version = await db.scalar(
        select(func.max(Material.version)).where(
            Material.student_id == student.id, Material.stage == current.value
        )
    )

    if action is ReviewAction.APPROVE:
        next_stage = STAGE_NEXT.get(current)
        to_stage = next_stage or current
    else:
        next_stage = None
        to_stage = current

    review = StageReview(
        student_id=student.id,
        stage=current.value,
        action=action.value,
        from_stage=current.value,
        to_stage=to_stage.value,
        material_version=material_version,
        comment=text,
        reviewer_id=reviewer.id,
    )
    db.add(review)

    if action is ReviewAction.APPROVE:
        if next_stage is None:
            student.status = StudentStatus.ARCHIVED.value
        else:
            student.current_stage = next_stage.value

    db.add(
        AuditLog(
            user_id=reviewer.id,
            action=f"STAGE_{action.value}",
            target_type="STUDENT",
            target_id=str(student.id),
            detail={
                "stage": current.value,
                "to_stage": to_stage.value,
                "comment": text,
            },
        )
    )

    await db.commit()
    await db.refresh(review)
    await db.refresh(student)
    return review, student


def _review_query() -> Select:
    return (
        select(StageReview, Student.name, Student.sno, User.real_name)
        .join(Student, StageReview.student_id == Student.id)
        .outerjoin(User, StageReview.reviewer_id == User.id)
    )


async def list_reviews(
    db: AsyncSession,
    *,
    scope_teacher_id: int | None = None,
    scope_student_id: int | None = None,
    student_id: int | None = None,
    stage: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[ReviewOut], int]:
    conditions = []
    if scope_student_id is not None:
        conditions.append(StageReview.student_id == scope_student_id)
    elif student_id is not None:
        conditions.append(StageReview.student_id == student_id)
    if scope_teacher_id is not None:
        conditions.append(Student.teacher_id == scope_teacher_id)
    if stage:
        conditions.append(StageReview.stage == stage)

    count_stmt = select(func.count()).select_from(StageReview).join(
        Student, StageReview.student_id == Student.id
    )
    for cond in conditions:
        count_stmt = count_stmt.where(cond)
    total = await db.scalar(count_stmt) or 0

    stmt = _review_query()
    for cond in conditions:
        stmt = stmt.where(cond)
    stmt = stmt.order_by(StageReview.id.desc()).offset((page - 1) * size).limit(size)

    rows = (await db.execute(stmt)).all()
    items = [
        ReviewOut(
            id=review.id,
            student_id=review.student_id,
            student_name=name,
            sno=sno,
            stage=review.stage,  # type: ignore[arg-type]
            action=review.action,  # type: ignore[arg-type]
            from_stage=review.from_stage,  # type: ignore[arg-type]
            to_stage=review.to_stage,  # type: ignore[arg-type]
            material_version=review.material_version,
            comment=review.comment,
            reviewer_name=reviewer_name,
            created_at=review.created_at,
        )
        for review, name, sno, reviewer_name in rows
    ]
    return items, total


async def pending(
    db: AsyncSession, *, teacher_id: int | None
) -> list[PendingItem]:
    stmt = select(Student).where(Student.status == StudentStatus.ACTIVE.value)
    if teacher_id is not None:
        stmt = stmt.where(Student.teacher_id == teacher_id)
    students = list((await db.scalars(stmt)).all())
    if not students:
        return []

    ids = [s.id for s in students]

    # 一次把材料统计和最近审核取回来，避免每个学生各查一遍（N+1）
    material_rows = (
        await db.execute(
            select(
                Material.student_id,
                Material.stage,
                func.count(Material.id),
                func.max(Material.created_at),
                func.max(Material.version),
            )
            .where(Material.student_id.in_(ids))
            .group_by(Material.student_id, Material.stage)
        )
    ).all()
    material_stats = {
        (sid, stage): (count, last_at, version)
        for sid, stage, count, last_at, version in material_rows
    }

    # 管理员要跨教师看，列表里得知道这个学生归谁带；一次查齐，别在循环里查
    teacher_ids = {s.teacher_id for s in students if s.teacher_id is not None}
    teacher_names: dict[int, str] = {}
    if teacher_ids:
        teacher_names = {
            uid: (name or username)
            for uid, name, username in (
                await db.execute(
                    select(User.id, User.real_name, User.username).where(User.id.in_(teacher_ids))
                )
            ).all()
        }

    review_rows = (
        await db.scalars(
            select(StageReview)
            .where(StageReview.student_id.in_(ids))
            .order_by(StageReview.id.desc())
        )
    ).all()
    last_review: dict[tuple[int, str], StageReview] = {}
    for review in review_rows:
        key = (review.student_id, review.stage)
        last_review.setdefault(key, review)

    items: list[PendingItem] = []
    for student in students:
        count, last_at, version = material_stats.get(
            (student.id, student.current_stage), (0, None, None)
        )
        review = last_review.get((student.id, student.current_stage))
        items.append(
            PendingItem(
                student_id=student.id,
                sno=student.sno,
                name=student.name,
                teacher_name=teacher_names.get(student.teacher_id) if student.teacher_id else None,
                stage=student.current_stage,  # type: ignore[arg-type]
                material_count=count,
                latest_material_at=last_at,
                latest_version=version,
                last_action=review.action if review else None,  # type: ignore[arg-type]
                last_comment=review.comment if review else None,
                last_reviewed_at=review.created_at if review else None,
            )
        )

    # 按流程顺序排，教师从上往下批就是顺着流程走
    order = {stage.value: i for i, stage in enumerate(STAGE_ORDER)}
    items.sort(key=lambda item: (order.get(item.stage, 99), item.sno))
    return items
