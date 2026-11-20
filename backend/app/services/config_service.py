"""系统参数：中期检查最少沟通次数、各环节截止日期。

存取方式：key-value 表 + JSON 文本，默认值写在这里。
- 库里没记录 → 按默认值返回，新环境不用预置数据；
- 加新参数 → 加一个默认值 + 一个键，不用改表结构；
- 读取统一走这里，业务代码不直接查 system_settings，
  避免"这个接口读一条、那个接口读另一条"导致口径漂移。

读取一律按列查询而不是取 ORM 实体：保存参数时刚 commit，
实体的 server_default / onupdate 列处于过期状态，直接读属性会触发
同步的延迟加载（async 下报 MissingGreenlet），按列查既省事也不踩这个坑。
"""

import json
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import STAGE_ORDER, Stage
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.schemas.config import ConfigOut, ConfigUpdate
from app.services import log_service

KEY_MIDTERM = "midterm_min_guidance"
KEY_DEADLINES = "stage_deadlines"
# AI 预审开关：库里没记录时跟随 .env 的 AI_ENABLED，管理员可在参数配置页改
KEY_AI = "ai_enabled"

DEFAULT_MIDTERM_MIN_GUIDANCE = 10


@dataclass(frozen=True)
class _Row:
    value: str
    updated_at: datetime
    updated_by: int | None


async def _load(db: AsyncSession) -> dict[str, _Row]:
    rows = (
        await db.execute(
            select(
                SystemSetting.key,
                SystemSetting.value,
                SystemSetting.updated_at,
                SystemSetting.updated_by,
            )
        )
    ).all()
    return {key: _Row(value, updated_at, updated_by) for key, value, updated_at, updated_by in rows}


def _midterm_from(row: _Row | None) -> int:
    if row is None:
        return DEFAULT_MIDTERM_MIN_GUIDANCE
    try:
        value = int(json.loads(row.value))
    except (ValueError, TypeError):
        # 库里值被手工改坏时不要让整个审核挂掉，按默认值走
        return DEFAULT_MIDTERM_MIN_GUIDANCE
    return value if value > 0 else DEFAULT_MIDTERM_MIN_GUIDANCE


def _deadlines_from(row: _Row | None) -> dict[Stage, date]:
    """只返回真正设了日期的环节，调用方按需 .get(stage)。"""
    if row is None:
        return {}
    try:
        raw = json.loads(row.value)
    except (ValueError, TypeError):
        return {}
    if not isinstance(raw, dict):
        return {}

    result: dict[Stage, date] = {}
    for code, text in raw.items():
        if not text:
            continue
        try:
            result[Stage(code)] = date.fromisoformat(str(text))
        except ValueError:
            continue
    return result


async def get_midterm_min(db: AsyncSession) -> int:
    return _midterm_from((await _load(db)).get(KEY_MIDTERM))


def _ai_from(row: _Row | None) -> bool:
    """AI 开关的默认值来自 .env，管理员改过就以库里的为准。

    这样部署时 AI_ENABLED=false 表示"默认关闭"，管理员在界面上点开也能用；
    改坏库里的值同样退回 .env，不让一个坏 JSON 把预审锁死或误开。
    """
    if row is None:
        return get_settings().ai_enabled
    try:
        return bool(json.loads(row.value))
    except (ValueError, TypeError):
        return get_settings().ai_enabled


async def get_ai_enabled(db: AsyncSession) -> bool:
    return _ai_from((await _load(db)).get(KEY_AI))


async def set_ai_enabled(db: AsyncSession, actor: User, enabled: bool) -> bool:
    """管理员开关 AI：写库 + 记操作日志，下一步预审立刻按新状态走，不用重启。"""
    row = await db.get(SystemSetting, KEY_AI)
    if row is None:
        row = SystemSetting(key=KEY_AI, value="true")
        db.add(row)
    row.value = json.dumps(bool(enabled))
    row.updated_by = actor.id

    await log_service.record(
        db,
        user_id=actor.id,
        action="AI_TOGGLE",
        target_type="config",
        target_id=KEY_AI,
        detail={"enabled": bool(enabled)},
    )
    await db.commit()
    return bool(enabled)


async def get_stage_deadlines(db: AsyncSession) -> dict[Stage, date]:
    return _deadlines_from((await _load(db)).get(KEY_DEADLINES))


async def get_config(db: AsyncSession) -> ConfigOut:
    settings = await _load(db)
    deadlines = _deadlines_from(settings.get(KEY_DEADLINES))

    # 两个键一起保存，取较新的那个当作"最近修改"
    rows = [row for row in settings.values() if row]
    latest = max(rows, key=lambda row: row.updated_at) if rows else None

    updated_by_name = None
    if latest is not None and latest.updated_by is not None:
        updater = await db.get(User, latest.updated_by)
        if updater is not None:
            updated_by_name = updater.real_name or updater.username

    return ConfigOut(
        midterm_min_guidance=_midterm_from(settings.get(KEY_MIDTERM)),
        stage_deadlines={stage: deadlines.get(stage) for stage in STAGE_ORDER},
        ai_enabled=_ai_from(settings.get(KEY_AI)),
        updated_at=latest.updated_at if latest else None,
        updated_by_name=updated_by_name,
    )


async def update_config(db: AsyncSession, actor: User, data: ConfigUpdate) -> ConfigOut:
    """两个参数一起保存：管理员在同一个页面改，分开提交只会让人以为有一半没生效。"""
    deadlines = {
        stage.value: (day.isoformat() if day else None)
        for stage, day in data.stage_deadlines.items()
    }

    midterm_row = await db.get(SystemSetting, KEY_MIDTERM)
    if midterm_row is None:
        midterm_row = SystemSetting(key=KEY_MIDTERM, value="0")
        db.add(midterm_row)
    midterm_row.value = json.dumps(data.midterm_min_guidance)
    midterm_row.updated_by = actor.id

    deadline_row = await db.get(SystemSetting, KEY_DEADLINES)
    if deadline_row is None:
        deadline_row = SystemSetting(key=KEY_DEADLINES, value="{}")
        db.add(deadline_row)
    deadline_row.value = json.dumps(deadlines, ensure_ascii=False)
    deadline_row.updated_by = actor.id

    await log_service.record(
        db,
        user_id=actor.id,
        action="CONFIG_UPDATE",
        target_type="CONFIG",
        target_id=KEY_MIDTERM,
        detail={
            "midterm_min_guidance": data.midterm_min_guidance,
            "stage_deadlines": deadlines,
        },
    )
    await db.commit()
    return await get_config(db)
