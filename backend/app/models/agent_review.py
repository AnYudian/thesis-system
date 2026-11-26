"""按环节打包的智能审阅记录。

与 ai_runs 的区别：
- ai_runs 是"一份材料 → 一次模型调用"，粒度是单个文件；
- 本表是"一个学生的一个环节 → 一包材料 → 一次智能审阅"，粒度是环节。

为什么必须按环节打包：对方要做跨材料核验（任务书 vs 开题报告 vs 进度），
只送一份材料时它的核查项只能基于该材料自述，结论容易全过。
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import AiRunStatus, STAGE_ORDER

_STAGE_VALUES = ", ".join(f"'{stage.value}'" for stage in STAGE_ORDER)


class AgentReview(Base, TimestampMixin):
    __tablename__ = "agent_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)

    # 材料被删不应带走审阅记录：它是历史结论，学生和老师还要回看
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    stage: Mapped[str] = mapped_column(String(24), index=True, nullable=False)

    # 对方按 project_id 串历史，同一个学生同一环节必须始终用同一个值，
    # 否则"上次提的问题这次改没改"永远查不到。规则：THS-{student_id}-{STAGE}
    project_id: Mapped[str] = mapped_column(String(48), index=True, nullable=False)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AiRunStatus.QUEUED.value, index=True
    )
    # 对方的 review_id 与入库状态分开存：报告可能已出但对方入库失败，两者要能分别展示
    external_id: Mapped[str | None] = mapped_column(String(64), index=True)
    external_db_status: Mapped[str | None] = mapped_column(String(24))

    review_mode: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(64))
    # 对方在模拟模式下会给 true，界面据此打"模拟结果"标识，避免当成真实结论
    simulation_only: Mapped[bool | None] = mapped_column(Boolean)

    summary: Mapped[str | None] = mapped_column(Text)
    # 原始返回整体入库：对方还在迭代字段，解析放在展示层，加字段不用改表
    result: Mapped[dict | None] = mapped_column(JSON)
    # 计数冗余出来，列表页排序/统计不用反序列化整份 JSON
    check_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    check_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    check_pending: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(48))

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # AUTO = 上传/审核动作自动触发；MANUAL = 老师重跑
    trigger: Mapped[str] = mapped_column(String(16), nullable=False, default="MANUAL")
    triggered_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    items: Mapped[list["AgentReviewItem"]] = relationship(
        back_populates="review", cascade="all, delete-orphan", lazy="selectin"
    )


class AgentReviewItem(Base, TimestampMixin):
    """打包清单：这一次审阅送了哪几份材料，以及为什么没送其他材料。

    保留 included=False 的行很重要——老师问"为什么没审任务书"时，
    界面要能回答"因为该环节没有任务书"，而不是沉默。
    """

    __tablename__ = "agent_review_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(
        ForeignKey("agent_reviews.id", ondelete="CASCADE"), index=True, nullable=False
    )
    material_id: Mapped[int | None] = mapped_column(
        ForeignKey("materials.id", ondelete="SET NULL"), index=True
    )

    stage: Mapped[str] = mapped_column(String(24), nullable=False)
    material_version: Mapped[int | None] = mapped_column(Integer)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 送给对方的 roles 取值：task_book / proposal / progress / other
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="other")
    included: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    skip_reason: Mapped[str | None] = mapped_column(String(255))

    review: Mapped[AgentReview] = relationship(back_populates="items")
