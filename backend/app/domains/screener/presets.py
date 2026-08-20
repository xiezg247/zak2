"""选股 preset / 内置 recipe 元数据。"""

from __future__ import annotations

from dataclasses import dataclass

from app.domains.screener.schemas import BuiltinRecipeOut, PresetOut


@dataclass(frozen=True)
class PresetDef:
    name: str
    source: str
    rule_kind: str
    description: str
    implemented: bool = True


BUILTIN_PRESETS: tuple[PresetDef, ...] = (
    PresetDef("涨幅榜", "quote", "change_top", "Redis 行情 · 涨幅排序"),
    PresetDef("强势上涨", "quote", "strong_up", "Redis 行情 · 涨幅 ≥ 5%"),
    PresetDef("换手率排行", "quote", "turnover", "Redis 行情 · 换手率排序"),
    PresetDef("量比排行", "quote", "volume_ratio", "Redis 行情 · 量比排序"),
    PresetDef("成交量放大", "quote", "volume", "Redis 行情 · 成交量排序"),
    PresetDef("自定义筛选", "quote", "custom", "Redis 行情 · 自定义区间"),
    PresetDef("涨停股", "quote", "limit_up", "Redis 行情 · 连板/涨停（limit_times 或涨幅≥9.5%）"),
    PresetDef("低 PE", "tushare", "low_pe", "Tushare daily_basic · PE(TTM) < 15 升序"),
    PresetDef("中大盘", "tushare", "large_cap", "Tushare daily_basic · 总市值 ≥ 50 亿降序"),
    PresetDef("主力净流入", "tushare", "moneyflow_in", "Tushare moneyflow · 净流入 > 0 降序"),
)

_PRESET_MAP = {p.name: p for p in BUILTIN_PRESETS}

BUILTIN_RECIPES: tuple[BuiltinRecipeOut, ...] = (
    BuiltinRecipeOut(
        recipe_id="intraday_multi", name="盘中多因子", trigger_kind="intraday", top_n=20, implemented=True
    ),
    BuiltinRecipeOut(
        recipe_id="ultra_short_unified",
        name="极致短线·雷达统一",
        trigger_kind="intraday",
        top_n=12,
        implemented=True,
    ),
    BuiltinRecipeOut(
        recipe_id="post_close_multi",
        name="盘后多因子",
        trigger_kind="post_close",
        top_n=20,
        implemented=True,
    ),
    BuiltinRecipeOut(
        recipe_id="radar_leader",
        name="雷达龙头",
        trigger_kind="intraday",
        top_n=12,
        implemented=True,
    ),
    BuiltinRecipeOut(
        recipe_id="radar_resonance",
        name="雷达共振",
        trigger_kind="intraday",
        top_n=20,
        implemented=True,
    ),
)

_RECIPE_MAP = {r.recipe_id: r for r in BUILTIN_RECIPES}


def list_presets() -> list[PresetOut]:
    return [
        PresetOut(
            name=p.name,
            source=p.source,
            rule_kind=p.rule_kind,
            description=p.description,
            implemented=p.implemented,
        )
        for p in BUILTIN_PRESETS
    ]


def get_preset(name: str) -> PresetDef | None:
    return _PRESET_MAP.get(name.strip())


def list_builtin_recipes() -> list[BuiltinRecipeOut]:
    return list(BUILTIN_RECIPES)


def get_builtin_recipe(recipe_id: str) -> BuiltinRecipeOut | None:
    return _RECIPE_MAP.get(recipe_id.strip())
