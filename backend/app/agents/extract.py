"""把上传的文件变成纯文本。

只做"够用"的抽取，不上 OCR：
- PDF 用 pypdf 抽文字层，扫描件抽不出来就直接跳过并说明原因；
- DOCX 是 zip + XML，用标准库解一遍即可，不必为此引入 python-docx；
- 其它格式（doc 老格式、压缩包、图片）第一版不审，返回可读的提示。
"""

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader

from app.agents.base import AiSkipped

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
# 连续空白在 PDF 抽取里很常见（分栏、表格线），压成单空格再交给模型
_BLANKS = re.compile(r"[ \t\u3000]+")


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _pdf_text(path)
    if suffix == ".docx":
        return _docx_text(path)
    if suffix == ".doc":
        raise AiSkipped("暂不支持 .doc 老格式，请另存为 .docx 或导出 PDF 后再上传")
    raise AiSkipped("该文件类型不是文档，无法做 AI 预审（仅支持 PDF / DOCX）")


def _pdf_text(path: Path) -> str:
    try:
        reader = PdfReader(str(path))
    except Exception as exc:  # 加密、损坏、不是真 PDF 都走这里
        raise AiSkipped(f"PDF 无法解析：{exc}") from None

    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            # 单页解析失败不影响其它页，缺一页总比整份放弃好
            continue
    text = "\n".join(pages).strip()
    if len(text) < 80:
        raise AiSkipped("这份 PDF 没有可提取的文字，可能是扫描件或图片拼接，请上传可复制文字的版本")
    return text


def _docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError):
        raise AiSkipped("Word 文件结构异常，无法读取正文") from None

    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        raise AiSkipped("Word 文件正文解析失败，请另存为 PDF 后再上传") from None

    paragraphs: list[str] = []
    for paragraph in root.iter(f"{_W}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{_W}t")).strip()
        if text:
            paragraphs.append(text)
    joined = "\n".join(paragraphs).strip()
    if len(joined) < 80:
        raise AiSkipped("这份 Word 文件几乎没有正文内容，请确认上传的是开题报告")
    return joined


def clean(text: str) -> str:
    return _BLANKS.sub(" ", text).strip()
