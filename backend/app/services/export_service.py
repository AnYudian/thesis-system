"""统计报表导出为 Excel。

为什么放在后端而不是前端拼表格：
- 学生明细是分页接口的数据，前端要导出全量得先翻完所有页；
- 多 Sheet + 列宽 + 冻结首行这些排版交给 openpyxl 更稳，
  前端用 xlsx 库还要多打一个包。
PDF 则由前端截屏生成（浏览器字体齐全，中文字形不会缺）。
"""

from datetime import datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import STAGE_LABELS, Stage, StudentStatus
from app.models.material import Material
from app.models.stage_review import StageReview
from app.models.student import Student
from app.models.user import User
from app.schemas.stats import ReportOut

# 与前端主题一致：深蓝表头 + 金色强调，打印出来也不刺眼
_HEAD_FILL = PatternFill("solid", fgColor="1D3354")
_HEAD_FONT = Font(color="FFFFFF", bold=True, size=11)
_TITLE_FONT = Font(bold=True, size=14, color="1D3354")
_THIN = Side(style="thin", color="D8D2C4")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _fmt_rate(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def _fmt_dt(value: datetime | None) -> str:
    return "—" if value is None else value.astimezone().strftime("%Y-%m-%d %H:%M")


def _write_head(ws: Worksheet, row: int, headers: list[str]) -> None:
    for col, text in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col, value=text)
        cell.fill = _HEAD_FILL
        cell.font = _HEAD_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = _BORDER
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def _write_rows(ws: Worksheet, start_row: int, rows: list[list]) -> None:
    for offset, values in enumerate(rows):
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=start_row + offset, column=col, value=value)
            cell.border = _BORDER
            # 数字右对齐：一列数字靠左会看不出量级差异
            if isinstance(value, (int, float)):
                cell.alignment = Alignment(horizontal="right")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=False)


def _fit_columns(ws: Worksheet, widths: list[int]) -> None:
    for col, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(col)].width = width


def _sheet_overview(wb: Workbook, report: ReportOut) -> None:
    ws = wb.active
    ws.title = "总览"

    ws["A1"] = "毕业设计（论文）统计报表"
    ws["A1"].font = _TITLE_FONT
    ws["A2"] = f"生成时间：{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M')}"
    ws["A2"].font = Font(size=10, color="6B6355")

    s = report.summary
    _write_head(ws, 4, ["指标", "数值"])
    _write_rows(
        ws,
        5,
        [
            ["学生总数", s.students_total],
            ["在途学生", s.in_progress],
            ["已归档", s.archived],
            ["指导教师", s.teachers_total],
            ["材料总数（含历次版本）", s.materials_total],
            ["审核次数", s.reviews_total],
            ["通过次数", s.approved],
            ["退回次数", s.returned],
            ["通过率", _fmt_rate(s.approve_rate)],
            ["平均审核时长（小时）", "—" if s.avg_review_hours is None else s.avg_review_hours],
            ["指导记录总数", report.guidance.total],
            ["有指导记录的学生", report.guidance.students_with_guidance],
            ["中期沟通总次数", report.guidance.midterm_total],
            ["中期达标学生（要求 %d 次）" % report.guidance.midterm_required, report.guidance.midterm_reached],
        ],
    )
    _fit_columns(ws, [34, 18])


def _sheet_stages(wb: Workbook, report: ReportOut) -> None:
    ws = wb.create_sheet("九环节")
    _write_head(ws, 1, ["环节", "在环节学生", "材料数", "审核次数", "通过", "退回", "通过率"])
    rows = [
        [
            row.label,
            row.students,
            row.materials,
            row.reviews,
            row.approved,
            row.returned,
            _fmt_rate(None if not row.reviews else row.approved / row.reviews),
        ]
        for row in report.stages
    ]
    _write_rows(ws, 2, rows)
    _fit_columns(ws, [24, 12, 10, 10, 8, 8, 10])


def _sheet_teachers(wb: Workbook, report: ReportOut) -> None:
    ws = wb.create_sheet("指导教师")
    _write_head(ws, 1, ["指导教师", "学生数", "在途", "已归档", "材料数", "审核次数", "通过率", "最近审核"])
    rows = [
        [
            row.name,
            row.students,
            row.active,
            row.archived,
            row.materials,
            row.reviews,
            _fmt_rate(row.approve_rate),
            _fmt_dt(row.last_reviewed_at),
        ]
        for row in report.teachers
    ]
    _write_rows(ws, 2, rows)
    _fit_columns(ws, [16, 10, 8, 8, 10, 10, 10, 18])


def _sheet_guidance(wb: Workbook, report: ReportOut) -> None:
    ws = wb.create_sheet("指导记录")
    g = report.guidance
    _write_head(ws, 1, ["指标", "数值"])
    _write_rows(
        ws,
        2,
        [
            ["指导记录总数", g.total],
            ["面谈", g.meet],
            ["线上", g.online],
            ["带证据的条数", g.evidence],
            ["有记录的学生数", g.students_with_guidance],
            ["中期沟通总次数", g.midterm_total],
            ["中期要求次数", g.midterm_required],
            ["中期达标学生数", g.midterm_reached],
        ],
    )
    _fit_columns(ws, [24, 14])


def _sheet_distribution(wb: Workbook, title: str, header: str, items: list) -> None:
    ws = wb.create_sheet(title)
    _write_head(ws, 1, [header, "人数"])
    _write_rows(ws, 2, [[item.name, item.count] for item in items])
    _fit_columns(ws, [30, 10])


def _sheet_activity(wb: Workbook, report: ReportOut) -> None:
    ws = wb.create_sheet("动态趋势")
    _write_head(ws, 1, ["日期", "材料提交", "通过", "退回"])
    _write_rows(ws, 2, [[p.date.isoformat(), p.materials, p.approvals, p.returns] for p in report.activity])
    _fit_columns(ws, [14, 12, 10, 10])


def _sheet_deadlines(wb: Workbook, report: ReportOut) -> None:
    ws = wb.create_sheet("截止与逾期")
    _write_head(ws, 1, ["环节", "截止日期", "在环节学生", "逾期人数"])
    rows = [
        [
            row.label,
            row.deadline.isoformat() if row.deadline else "未设置",
            row.students,
            row.overdue,
        ]
        for row in report.deadlines
    ]
    _write_rows(ws, 2, rows)
    _fit_columns(ws, [24, 14, 12, 12])


async def _student_rows(db: AsyncSession) -> list[list]:
    """学生明细：一次性查完再拼，避免在循环里补导师/材料数。"""
    teacher_names = {
        user_id: (real_name or username)
        for user_id, real_name, username in (
            await db.execute(select(User.id, User.real_name, User.username))
        ).all()
    }
    material_counts = {
        student_id: count
        for student_id, count in (
            await db.execute(select(Material.student_id, func.count()).group_by(Material.student_id))
        ).all()
    }
    last_reviews = {
        student_id: last_at
        for student_id, last_at in (
            await db.execute(
                select(StageReview.student_id, func.max(StageReview.created_at)).group_by(
                    StageReview.student_id
                )
            )
        ).all()
    }

    students = (
        await db.execute(
            select(
                Student.sno,
                Student.name,
                Student.major,
                Student.class_name,
                Student.grade,
                Student.teacher_id,
                Student.current_stage,
                Student.status,
                Student.id,
            ).order_by(Student.sno)
        )
    ).all()

    status_labels = {StudentStatus.ACTIVE.value: "进行中", StudentStatus.ARCHIVED.value: "已归档"}
    return [
        [
            sno,
            name,
            major,
            class_name,
            grade,
            teacher_names.get(teacher_id, "未指派"),
            STAGE_LABELS[Stage(current_stage)],
            status_labels.get(status, status),
            material_counts.get(student_id, 0),
            _fmt_dt(last_reviews.get(student_id)),
        ]
        for sno, name, major, class_name, grade, teacher_id, current_stage, status, student_id in students
    ]


async def build_workbook(db: AsyncSession, report: ReportOut) -> bytes:
    wb = Workbook()
    _sheet_overview(wb, report)
    _sheet_stages(wb, report)
    _sheet_teachers(wb, report)
    _sheet_guidance(wb, report)
    _sheet_distribution(wb, "专业分布", "专业", report.majors)
    _sheet_distribution(wb, "班级分布", "班级", report.classes)
    _sheet_distribution(wb, "年级分布", "年级", report.grades)
    _sheet_activity(wb, report)
    _sheet_deadlines(wb, report)

    ws = wb.create_sheet("学生明细")
    _write_head(
        ws,
        1,
        ["学号", "姓名", "专业", "班级", "年级", "指导教师", "当前环节", "状态", "材料数", "最近审核"],
    )
    _write_rows(ws, 2, await _student_rows(db))
    _fit_columns(ws, [16, 12, 24, 16, 8, 14, 20, 10, 10, 18])

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
