"""地点選択からダウンロード・正規化・指標計算・統計解析までを結ぶ処理の橋渡し。

Streamlit UI（ui/配下）はこのモジュールの関数を呼び出すことで、
下位モジュール（jma/, processing/, indices/, statistics/）を直接意識せずに
一連の処理を実行できる。
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

from amedas_rainfall.config import AppConfig, load_tank_model_config
from amedas_rainfall.indices.continuous_rainfall import calculate_continuous_rainfall
from amedas_rainfall.indices.effective_rainfall import calculate_all_effective_rainfall
from amedas_rainfall.indices.rolling_rainfall import calculate_rolling_rainfall
from amedas_rainfall.indices.soil_tank import TankModelConfig, calculate_estimated_soil_rainfall_index
from amedas_rainfall.jma.csv_parser import parse_jma_hourly_precipitation_csv
from amedas_rainfall.processing.merging import merge_hourly_frames
from amedas_rainfall.processing.normalization import add_used_rainfall_column, reindex_to_continuous_hourly
from amedas_rainfall.statistics.annual_maxima import (
    ALL_YEAR_BOUNDARIES,
    calculate_annual_completeness,
    calculate_annual_maxima,
)

INDICATOR_COLUMNS_FOR_ANNUAL_MAXIMA = [
    "rainfall_raw_mm",
    "rainfall_used_mm",
    "continuous_rainfall_12h_mm",
    "rolling_rainfall_24h_mm",
    "effective_rainfall_1_5h_mm",
    "effective_rainfall_6h_mm",
    "effective_rainfall_24h_mm",
    "estimated_soil_rainfall_mm",
]


def normalized_hourly_path(config: AppConfig, station_code: str) -> Path:
    base = config.resolved_path("paths.normalized_dir")
    return base / station_code / "hourly.parquet"


def raw_station_dir(config: AppConfig, station_code: str, station_name: str) -> Path:
    base = config.resolved_path("paths.raw_dir")
    return base / f"{station_code}_{station_name}"


def rebuild_normalized_from_raw(config: AppConfig, station_code: str, station_name: str) -> pd.DataFrame:
    """data/raw配下の全CSVを解析・統合し、正規化済み時別Parquetを再構築する。"""
    raw_dir = raw_station_dir(config, station_code, station_name)
    csv_files = sorted(raw_dir.glob("*.csv")) if raw_dir.exists() else []
    if not csv_files:
        raise FileNotFoundError(f"生データが見つかりません: {raw_dir}")

    frames = []
    names = []
    for f in csv_files:
        parsed = parse_jma_hourly_precipitation_csv(f.read_bytes())
        frames.append(parsed.frame)
        names.append(f.name)

    merged = merge_hourly_frames(frames, names)
    merged = reindex_to_continuous_hourly(merged)
    merged = add_used_rainfall_column(merged)

    out_path = normalized_hourly_path(config, station_code)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(out_path)
    return merged


def load_normalized_hourly(config: AppConfig, station_code: str) -> pd.DataFrame:
    path = normalized_hourly_path(config, station_code)
    return pd.read_parquet(path)


def compute_all_indices(config: AppConfig, hourly_df: pd.DataFrame) -> pd.DataFrame:
    """全ての雨量指標（8節・9節）をまとめて計算する。"""
    used = hourly_df["rainfall_used_mm"]

    continuous = calculate_continuous_rainfall(used, dry_hours_reset=config.get("rainfall.dry_hours_reset", 12))
    rolling = calculate_rolling_rainfall(used, window_hours=config.get("rainfall.rolling_window_hours", 24))
    effective = calculate_all_effective_rainfall(
        used, half_lives_hours=config.get("rainfall.effective_half_lives_hours", [1.5, 6, 24])
    )

    tank_raw = load_tank_model_config()
    tank_config = TankModelConfig.from_dict(tank_raw)
    tank_10min, tank_hourly = calculate_estimated_soil_rainfall_index(used, tank_config)

    result = hourly_df.copy()
    result = result.join(continuous, how="left")
    result = result.join(rolling, how="left")
    result = result.join(effective, how="left", rsuffix="_eff")
    result = result.join(tank_hourly, how="left")
    return result


def compute_annual_maxima_all_boundaries(
    indices_df: pd.DataFrame,
    columns: list[str] | None = None,
) -> dict[str, dict[str, pd.DataFrame]]:
    """3種類の年区切りそれぞれについて、各指標の年最大値を計算する。"""
    columns = columns or INDICATOR_COLUMNS_FOR_ANNUAL_MAXIMA
    result: dict[str, dict[str, pd.DataFrame]] = {}
    for key, boundary in ALL_YEAR_BOUNDARIES.items():
        per_indicator = {}
        for col in columns:
            if col in indices_df.columns:
                per_indicator[col] = calculate_annual_maxima(indices_df[col], boundary)
        result[key] = per_indicator
    return result


def compute_completeness_all_boundaries(
    indices_df: pd.DataFrame,
    completeness_threshold_percent: float = 95.0,
) -> dict[str, list]:
    valid_mask = indices_df["rainfall_raw_mm"].notna()
    state_reset_mask = (
        indices_df["state_reset_due_to_gap"] if "state_reset_due_to_gap" in indices_df.columns else None
    )
    result = {}
    now = pd.Timestamp.now(tz="Asia/Tokyo")
    for key, boundary in ALL_YEAR_BOUNDARIES.items():
        result[key] = calculate_annual_completeness(
            valid_mask,
            boundary,
            state_reset_mask=state_reset_mask,
            completeness_threshold_percent=completeness_threshold_percent,
            now=now,
        )
    return result
