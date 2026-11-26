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
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.agent_review import AgentReview, AgentReviewItem
from app.models.enums import GUIDANCE_METHOD_LABELS, AiRunStatus, GuidanceMethod, Stage
from app.models.guidance import GuidanceRecord
from app.models.material import Material
from app.models.student import Student
from app.services import docx_builder

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
    # 指导记录导出件、聊天截图没有对应的 materials 行，用 None 而不是 0（0 会撞外键）
    material_id: int | None
    stage: str
    version: int
    file_name: str
    file_size: int
    role: str | None
    included: bool = True
    skip_reason: str | None = None
    abs_path: Path | None = None
    # 由系统现场生成（如指导记录汇总），不是学生上传的材料
    generated: bool = False


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
        """目标环节没有学生自己上传的材料时，告诉调用方缺什么。

        只有 material_id 不为空的才是学生上传的正式材料；指导记录导出件、
        聊天截图这类过程材料不能替代中期报告本身。
        """
        if any(f.included and f.stage == self.stage and f.material_id is not None for f in self.files):
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


async def _guidance_package(db: AsyncSession, student: Student, stage: str) -> tuple[list[PackageFile], list[str]]:
    """把指导记录导成 docx，并把沟通证据（截图/代码包）一起纳入送审。

    为什么必须导出：对方只认 docx/图片/zip，而指导记录是数据库里的结构化数据。
    为什么证据要挑：对方单次最多 10 份、每份 2MB，全带会超限，按时间从近到远取。
    """
    settings = get_settings()
    records = (
        await db.execute(
            select(GuidanceRecord)
            .where(GuidanceRecord.student_id == student.id)
            .order_by(GuidanceRecord.happened_at.desc())
            .limit(200)
        )
    ).scalars().all()
    if not records:
        return [], ["指导记录：还没有登记任何指导记录，中期审查缺少沟通依据"]

    warnings: list[str] = []
    rows: list[dict] = []
    for r in reversed(records):  # 文档按时间正序，读起来更像一份过程记录
        try:
            method = GUIDANCE_METHOD_LABELS.get(GuidanceMethod(r.method), r.method)
        except ValueError:
            method = r.method
        rows.append(
            {
                "happened_at": r.happened_at.strftime("%Y-%m-%d"),
                "method": method,
                "stage_label": STAGE_LABELS.get(r.stage, r.stage),
                "content": r.content,
                "evidence_name": r.evidence_name,
            }
        )

    data = docx_builder.guidance_docx(student.name, student.sno, STAGE_LABELS.get(stage, "阶段"), rows)
    gen_dir = settings.upload_path / str(student.id) / "generated"
    gen_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"指导记录汇总-{datetime.now():%Y%m%d}.docx"
    path = gen_dir / file_name
    path.write_bytes(data)

    files = [
        PackageFile(
            material_id=None,
            stage=stage,
            version=0,
            file_name=file_name,
            file_size=len(data),
            role="progress",
            abs_path=path,
            generated=True,
        )
    ]

    supported = settings.agent_supported_set
    max_bytes = settings.agent_max_file_mb * 1024 * 1024
    skipped_formats: set[str] = set()
    for r in records:  # 最近的证据优先
        if not r.evidence_name or not r.evidence_path:
            continue
        ext = Path(r.evidence_name).suffix.lower().lstrip(".")
        item = PackageFile(
            material_id=None,
            stage=r.stage,
            version=0,
            file_name=r.evidence_name,
            file_size=r.evidence_size or 0,
            # 截图/代码包交给对方自动分类：对方明确要求这类文件 roles 传 null
            role=None,
            abs_path=settings.upload_path / r.evidence_path,
        )
        if ext not in supported:
            item.included = False
            item.skip_reason = f"证据格式 .{ext or '未知'} 不支持智能审阅"
            skipped_formats.add(ext or "未知")
        elif r.evidence_size and r.evidence_size > max_bytes:
            item.included = False
            item.skip_reason = f"证据 {r.evidence_size / 1024 / 1024:.1f}MB 超过 2MB 限制"
        elif not item.abs_path.exists():
            item.included = False
            item.skip_reason = "证据文件缺失"
        files.append(item)

    if skipped_formats:
        warnings.append(f"有证据因格式不支持未送审：{', '.join(sorted(skipped_formats))}")
    return files, warnings


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

    # 中期/定稿：把指导记录导成一份文档，并把沟通证据（截图/代码包）一起送。
    # 对方只能读 docx/图片/zip，指导记录在库里是结构化数据，必须现场导出。
    if stage in (Stage.MIDTERM.value, Stage.THESIS.value):
        guidance_files, guidance_warnings = await _guidance_package(db, student, stage)
        candidates.extend(guidance_files)
        pkg.warnings.extend(guidance_warnings)

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
    elif pkg.missing_stages:
        label = STAGE_LABELS.get(stage, stage)
        pkg.warnings.append(f"缺少{label}报告（学生未上传），本次只送指导记录与过程证据")
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

    settings = get_settings()
    for f in pkg.files:
        rel_path = None
        if f.abs_path is not None:
            try:
                rel_path = str(f.abs_path.relative_to(settings.upload_path)).replace("\\", "/")
            except ValueError:
                rel_path = str(f.abs_path)
        db.add(
            AgentReviewItem(
                review_id=review.id,
                material_id=f.material_id,
                stored_path=rel_path,
                stage=f.stage,
                material_version=f.version,
                file_name=f.file_name,
                file_size=f.file_size,
                role=f.role or "",
                included=f.included,
                skip_reason=f.skip_reason,
            )
        )
    await db.commit()
    await db.refresh(review)
    return review
