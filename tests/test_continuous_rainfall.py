"""12時間無降雨リセット連続雨量のテスト（仕様17.1節）。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from amedas_rainfall.indices.continuous_rainfall import (
    CONTINUOUS_COLUMN,
    DRY_HOURS_COLUMN,
    EVENT_ID_COLUMN,
    RESET_DUE_TO_GAP_COLUMN,
    WARMUP_COLUMN,
    calculate_continuous_rainfall,
)
from amedas_rainfall.processing.normalization import apply_no_rain_threshold


def _series(values: list[float | None]) -> pd.Series:
    index = pd.date_range("2020-01-01", periods=len(values), freq="h", tz="Asia/Tokyo")
    return pd.Series(values, index=index, dtype=float)


def test_accumulates_during_rain() -> None:
    s = _series([1.0, 2.0, 3.0])
    result = calculate_continuous_rainfall(s)
    assert result[CONTINUOUS_COLUMN].tolist() == [1.0, 3.0, 6.0]


def test_holds_value_during_short_dry_spell_up_to_11_hours() -> None:
    values = [5.0] + [0.0] * 11 + [2.0]
    s = _series(values)
    result = calculate_continuous_rainfall(s)
    # 無降雨1〜11時間目は直前の値を保持する
    for i in range(1, 12):
        assert result[CONTINUOUS_COLUMN].iloc[i] == 5.0
        assert result[DRY_HOURS_COLUMN].iloc[i] == i
    # 12時間目の降雨で同一イベントとして継続、累積される
    assert result[CONTINUOUS_COLUMN].iloc[12] == 7.0
    assert result[EVENT_ID_COLUMN].iloc[0] == result[EVENT_ID_COLUMN].iloc[12]


def test_resets_to_zero_after_12_dry_hours() -> None:
    values = [5.0] + [0.0] * 12
    s = _series(values)
    result = calculate_continuous_rainfall(s)
    assert result[DRY_HOURS_COLUMN].iloc[12] == 12
    assert result[CONTINUOUS_COLUMN].iloc[12] == 0.0


def test_new_event_starts_after_reset() -> None:
    values = [5.0] + [0.0] * 12 + [3.0]
    s = _series(values)
    result = calculate_continuous_rainfall(s)
    assert result[CONTINUOUS_COLUMN].iloc[13] == 3.0
    assert result[EVENT_ID_COLUMN].iloc[13] != result[EVENT_ID_COLUMN].iloc[0]


def test_threshold_0_3_is_no_rain_0_4_is_rain() -> None:
    raw = pd.Series([0.0, 0.1, 0.2, 0.3, 0.4], dtype=float)
    used = apply_no_rain_threshold(raw)
    assert used.tolist() == [0.0, 0.0, 0.0, 0.0, 0.4]


def test_missing_values_are_not_zeroed_by_threshold() -> None:
    raw = pd.Series([0.5, np.nan, 1.0], dtype=float)
    used = apply_no_rain_threshold(raw)
    assert used.iloc[1] != used.iloc[1]  # NaN check
    assert np.isnan(used.iloc[1])


def test_gap_resets_state_with_flags() -> None:
    values = [5.0, 5.0, np.nan, np.nan, 2.0]
    s = _series(values)
    result = calculate_continuous_rainfall(s)
    assert result[WARMUP_COLUMN].iloc[4]
    assert result[RESET_DUE_TO_GAP_COLUMN].iloc[4]
    assert result[CONTINUOUS_COLUMN].iloc[4] == 2.0
    assert np.isnan(result[CONTINUOUS_COLUMN].iloc[2])
