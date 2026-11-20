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
# AI 预审开关与每日上限：库里没记录时跟随 .env，管理员可在参数配置页改
KEY_AI = "ai_enabled"
KEY_AI_LIMIT = "ai_daily_limit"

DEFAULT_MIDTERM_MIN_GUIDANCE = 10
# 上限 200：参数页按校方需要调，但给个硬顶，避免手滑填出天文数字
AI_DAILY_LIMIT_MAX = 200


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


def _ai_limit_from(row: _Row | None) -> int:
    """每日上限默认取 .env；管理员改过就按库里的来。

    0 是合法值（表示不限），所以不能像开关那样把 0 当"没配"退回默认值，
    只对负数、非整数这类明显坏值退回 .env。
    """
    if row is None:
        return get_settings().ai_daily_limit
    try:
        value = int(json.loads(row.value))
    except (ValueError, TypeError):
        return get_settings().ai_daily_limit
    if value < 0:
        return get_settings().ai_daily_limit
    return min(value, AI_DAILY_LIMIT_MAX)


async def get_ai_enabled(db: AsyncSession) -> bool:
    return _ai_from((await _load(db)).get(KEY_AI))


async def get_ai_daily_limit(db: AsyncSession) -> int:
    return _ai_limit_from((await _load(db)).get(KEY_AI_LIMIT))


async def get_ai_settings(db: AsyncSession) -> tuple[bool, int]:
    """开关和额度一次读出来：预审排队时两个都要判断，没必要查两遍。"""
    rows = await _load(db)
    return _ai_from(rows.get(KEY_AI)), _ai_limit_from(rows.get(KEY_AI_LIMIT))


async def set_ai_config(
    db: AsyncSession,
    actor: User,
    *,
    enabled: bool | None = None,
    daily_limit: int | None = None,
) -> None:
    """管理员改 AI 开关 / 每日上限：只写传进来的项，下一次预审立刻按新值走。

    两项合在一个接口里，是因为它们同属一张卡片、同一个生效时机；
    传 None 表示"这次不改"，而不是"清空"。
    """
    changes: dict[str, object] = {}
    if enabled is not None:
        row = await db.get(SystemSetting, KEY_AI)
        if row is None:
            row = SystemSetting(key=KEY_AI, value="true")
            db.add(row)
        row.value = json.dumps(bool(enabled))
        row.updated_by = actor.id
        changes["enabled"] = bool(enabled)

    if daily_limit is not None:
        limit = max(0, min(int(daily_limit), AI_DAILY_LIMIT_MAX))
        row = await db.get(SystemSetting, KEY_AI_LIMIT)
        if row is None:
            row = SystemSetting(key=KEY_AI_LIMIT, value="0")
            db.add(row)
        row.value = json.dumps(limit)
        row.updated_by = actor.id
        changes["daily_limit"] = limit

    if not changes:
        return

    await log_service.record(
        db,
        user_id=actor.id,
        action="AI_CONFIG",
        target_type="config",
        target_id=KEY_AI,
        detail=changes,
    )
    await db.commit()


async def get_stage_deadlines(db: AsyncSession) -> dict[Stage, date]:
    return _deadlines_from((await _load(db)).get(KEY_DEADLINES))


async def get_config(db: AsyncSession) -> ConfigOut:
    settings = await _load(db)
    deadlines = _deadlines_from(settings.get(KEY_DEADLINES))

    # 参数都存 key-value，取更新时间最晚的那行当作"最近修改"
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
        ai_daily_limit=_ai_limit_from(settings.get(KEY_AI_LIMIT)),
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
