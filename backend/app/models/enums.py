from enum import Enum


class Role(str, Enum):
    ADMIN = "ADMIN"
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"


class TeacherType(str, Enum):
    """教师的两类身份。

    学校毕设流程里教师不止一种分工：带学生、走阶段审核的是指导教师，
    另一类负责评阅等环节。具体叫法还在等校方确认，所以这里只固化代码值和
    两个技术标识，中文文案集中放在前端 constants/teachers.ts 与
    TEACHER_TYPE_LABELS，确认后改文案不用动数据。
    """

    SUPERVISOR = "SUPERVISOR"
    REVIEWER = "REVIEWER"


TEACHER_TYPE_LABELS: dict[TeacherType, str] = {
    TeacherType.SUPERVISOR: "指导教师",
    TeacherType.REVIEWER: "评阅教师",
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
