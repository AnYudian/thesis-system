from enum import Enum


class Role(str, Enum):
    ADMIN = "ADMIN"
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"


class Stage(str, Enum):
    """毕业设计全流程节点。

    其中 TOPIC / PROPOSAL / MIDTERM / PLAGIARISM / THESIS 后期会接入智能体审阅，
    但流程本身是完整的九节点，不能只做这五个。
    """

    TOPIC = "TOPIC"
    TASK_BOOK = "TASK_BOOK"
    PROPOSAL = "PROPOSAL"
    MIDTERM = "MIDTERM"
    PLAGIARISM = "PLAGIARISM"
    THESIS = "THESIS"
    REVIEW = "REVIEW"
    DEFENSE = "DEFENSE"
    ARCHIVE = "ARCHIVE"


STAGE_ORDER: list[Stage] = [
    Stage.TOPIC,
    Stage.TASK_BOOK,
    Stage.PROPOSAL,
    Stage.MIDTERM,
    Stage.PLAGIARISM,
    Stage.THESIS,
    Stage.REVIEW,
    Stage.DEFENSE,
    Stage.ARCHIVE,
]

STAGE_LABELS: dict[Stage, str] = {
    Stage.TOPIC: "选题/双向选择",
    Stage.TASK_BOOK: "任务书下达",
    Stage.PROPOSAL: "开题报告/开题答辩",
    Stage.MIDTERM: "中期检查",
    Stage.PLAGIARISM: "查重检测",
    Stage.THESIS: "论文定稿",
    Stage.REVIEW: "评阅",
    Stage.DEFENSE: "答辩",
    Stage.ARCHIVE: "归档/评优",
}

# 后期可能接入智能体审阅的节点
AI_STAGES: set[Stage] = {
    Stage.TOPIC,
    Stage.PROPOSAL,
    Stage.MIDTERM,
    Stage.PLAGIARISM,
    Stage.THESIS,
}


class StudentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
