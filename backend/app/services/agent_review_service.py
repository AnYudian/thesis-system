"""按「学生 + 环节」打包送审。

打包策略（为什么这么定）：
1. 目标环节只取该环节的**最终版本**，历次旧稿不送——一次审四五个版本没有意义，
   还会挤占对方 10 份/2MiB 的限额；
2. 目标环节之后的环节带上**前置环节的最终版**（任务书、开题报告），
   因为对方的跨材料核验需要"计划 vs 当前进度"两侧证据；
3. 不支持的文件格式不静默丢弃，而是记进清单并给出 skip_reason，
   老师问"为什么没审任务书"时界面能回答；
4. 超出限额时按"目标环节优先、前置环节其次、版本新的优先"取舍，并把被放弃的写进 warnings。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.agent_review import AgentReview, AgentReviewItem
from app.models.enums import AiRunStatus, Stage
from app.models.material import Material
from app.models.student import Student

# 环节与对方 roles 的映射。对方只认这四种，其余一律 other。
ROLE_BY_STAGE: dict[str, str] = {
    Stage.TASK_BOOK.value: "task_book",
    Stage.PROPOSAL.value: "proposal",
    Stage.MIDTERM.value: "progress",
}

# 每个环节打包时额外带上的前置环节（用于跨材料核验）
CONTEXT_STAGES: dict[str, list[str]] = {
    Stage.MIDTERM.value: [Stage.TASK_BOOK.value, Stage.PROPOSAL.value],
    Stage.THESIS.value: [Stage.TASK_BOOK.value, Stage.PROPOSAL.value, Stage.MIDTERM.value],
    Stage.PLAGIARISM.value: [Stage.PROPOSAL.value],
}

STAGE_LABELS: dict[str, str] = {
    Stage.TOPIC.value: "选题",
    Stage.TASK_BOOK.value: "任务书",
    Stage.PROPOSAL.value: "开题报告",
    Stage.MIDTERM.value: "中期检查",
    Stage.PLAGIARISM.value: "查重",
    Stage.THESIS.value: "论文定稿",
    Stage.REVIEW.value: "评阅",
    Stage.DEFENSE.value: "答辩",
    Stage.ARCHIVE.value: "归档",
}


@dataclass
class PackageFile:
    material_id: int
    stage: str
    version: int
    file_name: str
    file_size: int
    role: str
    included: bool = True
    skip_reason: str | None = None
    abs_path: Path | None = None


@dataclass
class Package:
    student_id: int
    stage: str
    project_id: str
    files: list[PackageFile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def included(self) -> list[PackageFile]:
        return [f for f in self.files if f.included]

    @property
    def missing_stages(self) -> list[str]:
        """目标环节没有材料时，告诉调用方缺什么，而不是送一个空包。"""
        if any(f.included and f.stage == self.stage for f in self.files):
            return []
        return [self.stage]


def project_id_for(student_id: int, stage: str) -> str:
    """对方按 project_id 串历史，必须稳定且满足它 1~48 位、首字符字母或数字的约束。"""
    return f"THS-{student_id}-{stage}"


def _role_for(stage: str) -> str:
    return ROLE_BY_STAGE.get(stage, "other")


async def _latest_by_stage(db: AsyncSession, student_id: int, stages: list[str]) -> dict[str, Material]:
    """每个环节取版本号最大的那一份。"""
    if not stages:
        return {}
    rows = (
        await db.execute(
            select(Material)
            .where(Material.student_id == student_id, Material.stage.in_(stages))
            .order_by(Material.stage, Material.version.desc())
        )
    ).scalars().all()
    latest: dict[str, Material] = {}
    for m in rows:
        latest.setdefault(m.stage, m)
    return latest


async def build_package(db: AsyncSession, student_id: int, stage: str) -> Package:
    settings = get_settings()
    supported = settings.agent_supported_set
    max_files = settings.agent_max_files
    max_bytes = settings.agent_max_file_mb * 1024 * 1024

    student = await db.get(Student, student_id)
    if student is None:
        raise AppError(40410, "学生不存在", http_status=404)

    pkg = Package(student_id=student_id, stage=stage, project_id=project_id_for(student_id, stage))

    # 目标环节优先，前置环节补充上下文
    order = [stage] + [s for s in CONTEXT_STAGES.get(stage, []) if s != stage]
    latest = await _latest_by_stage(db, student_id, order)

    candidates: list[PackageFile] = []
    for st in order:
        material = latest.get(st)
        if material is None:
            pkg.warnings.append(f"{STAGE_LABELS.get(st, st)}：没有已上传的材料")
            continue
        ext = Path(material.file_name).suffix.lower().lstrip(".")
        item = PackageFile(
            material_id=material.id,
            stage=material.stage,
            version=material.version,
            file_name=material.file_name,
            file_size=material.file_size,
            role=_role_for(material.stage),
            abs_path=settings.upload_path / material.stored_path,
        )
        if ext not in supported:
            item.included = False
            item.skip_reason = f"格式 .{ext or '未知'} 暂不支持智能审阅"
        elif material.file_size > max_bytes:
            item.included = False
            item.skip_reason = f"文件 {material.file_size / 1024 / 1024:.1f}MB 超过 {settings.agent_max_file_mb}MB 限制"
        elif not item.abs_path.exists():
            item.included = False
            item.skip_reason = "磁盘上的文件缺失"
        candidates.append(item)

    # 限额取舍：目标环节在前，天然优先保留
    kept = 0
    for item in candidates:
        if not item.included:
            continue
        if kept >= max_files:
            item.included = False
            item.skip_reason = f"超出单次 {max_files} 份限制，本次未送"
            pkg.warnings.append(f"{item.file_name} 未送：超出 {max_files} 份上限")
            continue
        kept += 1

    pkg.files = candidates
    if kept == 0:
        pkg.warnings.append("本次没有可送审的文件，请先上传受支持格式的材料")
    return pkg


async def create_review_record(db: AsyncSession, pkg: Package, *, triggered_by: int | None, trigger: str = "MANUAL") -> AgentReview:
    """先把"要送什么"落库，再提交给外部服务。提交本身在 P8.2 实现。

    先落库的好处：即使提交过程崩溃，也能看到当时准备送哪些材料。
    """
    review = AgentReview(
        student_id=pkg.student_id,
        stage=pkg.stage,
        project_id=pkg.project_id,
        status=AiRunStatus.QUEUED.value,
        trigger=trigger,
        triggered_by=triggered_by,
    )
    db.add(review)
    await db.flush()

    for f in pkg.files:
        db.add(
            AgentReviewItem(
                review_id=review.id,
                material_id=f.material_id,
                stage=f.stage,
                material_version=f.version,
                file_name=f.file_name,
                file_size=f.file_size,
                role=f.role,
                included=f.included,
                skip_reason=f.skip_reason,
            )
        )
    await db.commit()
    await db.refresh(review)
    return review
