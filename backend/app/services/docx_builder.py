"""极简 DOCX 生成器。

为什么自己拼 OOXML 而不装 python-docx：
只用来把指导记录导出成一份纯文字文档给智能审阅服务读，不需要样式系统；
少一个依赖，部署时也少一个可能装不上的包。
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""


def _paragraph(text: str) -> str:
    return f"<w:p><w:r><w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"


def build_docx(paragraphs: list[str]) -> bytes:
    body = "".join(_paragraph(p) for p in paragraphs)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _RELS)
        zf.writestr("word/document.xml", document)
    return buf.getvalue()


def guidance_docx(
    student_name: str,
    student_no: str,
    stage_label: str,
    records: list[dict],
) -> bytes:
    """把指导记录导出成可读文档。记录里的字段由调用方整理好，这里只负责排版。"""
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"{stage_label}指导记录汇总",
        f"学生：{student_name}（{student_no}）",
        f"导出时间：{today}　合计 {len(records)} 次指导",
    ]
    meet = sum(1 for r in records if r.get("method") == "面谈")
    online = sum(1 for r in records if r.get("method") == "线上")
    evidence = sum(1 for r in records if r.get("evidence_name"))
    lines.append(f"其中面谈 {meet} 次、线上 {online} 次、附证据 {evidence} 条。")
    lines.append("")
    for i, r in enumerate(records, 1):
        lines.append(f"{i}. {r.get('happened_at', '')}｜{r.get('method', '')}｜{r.get('stage_label', '')}")
        lines.append(f"   内容：{r.get('content') or '（无）'}")
        if r.get("evidence_name"):
            lines.append(f"   证据：{r['evidence_name']}")
    return build_docx(lines)
