"""系统参数。

按 key 一行一个参数、value 存 JSON 文本：以后加参数不用改表结构，
默认值写在 config_service 里，库里没有记录时按默认值走，
所以部署一套新环境不需要预置数据。
"""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SystemSetting(Base, TimestampMixin):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    # 记下是谁改的参数：审核口径变了要能追溯到人
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
