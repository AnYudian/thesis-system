"""AI 预审运行记录。

一次"材料版本 → 模型 → 结果"就是一行，只增不改（重跑另起一行）。
为什么单独成表而不是塞进 materials：
- 同一份材料可能被重跑多次（换模型、改 prompt、老师手动重跑），要能对比；
- 结果要先存原始 JSON 再渲染，模型改了输出结构也不会污染历史记录；
- 学生在改稿，老师看的是"这一版 AI 怎么说"，版本必须跟着材料版本走。
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import AiRunStatus


class AiRun(Base, TimestampMixin):
    __tablename__ = "ai_runs"

    id: Mapped[int] = mapped_column(primary_key=True)

    # 材料被删除时它的 AI 记录一起删：没有材料的结果没有意义
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # 冗余存环节与版本：材料被删后仍想保留统计口径时不用回表，也方便按环节筛选
    stage: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    material_version: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AiRunStatus.QUEUED.value, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    # prompt 版本号：模型输出不满意时能回答"当时用的是哪版提示词"
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)

    score: Mapped[float | None] = mapped_column(Float)
    # 0-100 的完成度，前端画进度条；与 score 分开是因为"分数高但缺章节"很常见
    completion: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[str | None] = mapped_column(Text)
    # 结构化结果（维度得分 / 问题清单 / 建议），保持原始形状，前端按字段渲染
    result: Mapped[dict | None] = mapped_column(JSON)

    raw_response: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)

    tokens_input: Mapped[int | None] = mapped_column(Integer)
    tokens_output: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)

    # UPLOAD = 上传后自动触发；MANUAL = 教师/管理员点重跑
    trigger: Mapped[str] = mapped_column(String(16), nullable=False, default="UPLOAD")
    triggered_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
