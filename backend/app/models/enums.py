from enum import Enum


class Role(str, Enum):
    ADMIN = "ADMIN"
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"


class TeacherType(str, Enum):
    """教师的两类身份。

    学校毕设流程里教师分两种身份：带学生、走阶段审核的是指导教师，
    另一种是就业老师。就业老师目前在本系统不承担任何审核任务，只作为
    身份占位（所以代码值仍是 REVIEWER，没有跟着改名，改值需要迁移数据）。
    中文文案集中放在前端 constants/teachers.ts 与 TEACHER_TYPE_LABELS，
    学校若再改叫法，只动文案即可。
    """

    SUPERVISOR = "SUPERVISOR"
    REVIEWER = "REVIEWER"


TEACHER_TYPE_LABELS: dict[TeacherType, str] = {
    TeacherType.SUPERVISOR: "指导教师",
    TeacherType.REVIEWER: "就业老师",
}


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

# 审核通过后进入的下一环节；最后一个环节没有下一站，通过即归档
STAGE_NEXT: dict[Stage, Stage] = {
    STAGE_ORDER[i]: STAGE_ORDER[i + 1] for i in range(len(STAGE_ORDER) - 1)
}


class ReviewAction(str, Enum):
    APPROVE = "APPROVE"
    RETURN = "RETURN"


class GuidanceMethod(str, Enum):
    """教师与学生的沟通方式。中期检查要求留痕，至少要能区分线下见面和线上沟通。"""

    MEET = "MEET"
    ONLINE = "ONLINE"


GUIDANCE_METHOD_LABELS: dict[GuidanceMethod, str] = {
    GuidanceMethod.MEET: "面谈",
    GuidanceMethod.ONLINE: "线上",
}

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


class AiRunStatus(str, Enum):
    """一次 AI 预审的生命周期。

    SKIPPED 不是错误：环节未接入、文件格式不支持、当日额度用完都会走到这里，
    保留一条记录是为了让老师和学生知道"为什么没有 AI 意见"，而不是干等。
    """

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


AI_RUN_STATUS_LABELS: dict[AiRunStatus, str] = {
    AiRunStatus.QUEUED: "排队中",
    AiRunStatus.RUNNING: "审阅中",
    AiRunStatus.DONE: "已完成",
    AiRunStatus.FAILED: "审阅失败",
    AiRunStatus.SKIPPED: "已跳过",
}
