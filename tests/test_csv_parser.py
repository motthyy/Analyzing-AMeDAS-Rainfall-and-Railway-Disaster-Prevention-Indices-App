"""気象庁CSVパーサーのテスト（仕様17.8節）。"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from amedas_rainfall.jma.csv_parser import (
    JmaCsvFormatError,
    classify_quality,
    parse_jma_hourly_precipitation_csv,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


def test_parses_cp932_encoded_file() -> None:
    raw = _load("sample_normal_cp932.csv")
    parsed = parse_jma_hourly_precipitation_csv(raw)
    assert parsed.station_name == "豊田"


def test_multirow_header_is_skipped_and_only_data_rows_remain() -> None:
    raw = _load("sample_normal_cp932.csv")
    parsed = parse_jma_hourly_precipitation_csv(raw)
    assert len(parsed.frame) == 24


def test_hour_24_normalized_to_next_day_00() -> None:
    raw = _load("sample_normal_cp932.csv")
    parsed = parse_jma_hourly_precipitation_csv(raw)
    last_ts = parsed.frame.index.max()
    assert last_ts == pd.Timestamp("2024-01-02 00:00", tz="Asia/Tokyo")


def test_missing_value_is_nan_not_zero() -> None:
    raw = _load("sample_normal_cp932.csv")
    parsed = parse_jma_hourly_precipitation_csv(raw)
    ts = pd.Timestamp("2024-01-01 04:00", tz="Asia/Tokyo")
    value = parsed.frame.loc[ts, "rainfall_raw_mm"]
    assert math.isnan(value)
    assert parsed.frame.loc[ts, "quality_code"] == "1"


def test_quality_info_values_preserved() -> None:
    raw = _load("sample_normal_cp932.csv")
    parsed = parse_jma_hourly_precipitation_csv(raw)
    ts_normal = pd.Timestamp("2024-01-01 01:00", tz="Asia/Tokyo")
    ts_quasi = pd.Timestamp("2024-01-01 08:00", tz="Asia/Tokyo")
    assert parsed.frame.loc[ts_normal, "quality_code"] == "8"
    assert parsed.frame.loc[ts_quasi, "quality_code"] == "5"
    assert classify_quality(parsed.frame.loc[ts_normal, "quality_code"]) == "正常"
    assert classify_quality(parsed.frame.loc[ts_quasi, "quality_code"]) == "準正常"
    assert classify_quality("1") == "欠測"
    assert classify_quality("0") == "欠測"


def test_numeric_conversion_handles_decimals() -> None:
    raw = _load("sample_normal_cp932.csv")
    parsed = parse_jma_hourly_precipitation_csv(raw)
    ts = pd.Timestamp("2024-01-01 03:00", tz="Asia/Tokyo")
    assert parsed.frame.loc[ts, "rainfall_raw_mm"] == pytest.approx(1.2)


def test_duplicate_timestamps_across_two_files_can_be_detected() -> None:
    raw1 = _load("sample_normal_cp932.csv")
    raw2 = _load("sample_overlap_cp932.csv")
    parsed1 = parse_jma_hourly_precipitation_csv(raw1)
    parsed2 = parse_jma_hourly_precipitation_csv(raw2)
    overlap_ts = pd.Timestamp("2024-01-01 23:00", tz="Asia/Tokyo")
    assert overlap_ts in parsed1.frame.index
    assert overlap_ts in parsed2.frame.index
    # 同一時刻・同一品質だが値が異なる（統合処理での競合検出対象）
    assert parsed1.frame.loc[overlap_ts, "rainfall_raw_mm"] != parsed2.frame.loc[overlap_ts, "rainfall_raw_mm"]


def test_raises_on_empty_input() -> None:
    with pytest.raises(JmaCsvFormatError):
        parse_jma_hourly_precipitation_csv(b"")
