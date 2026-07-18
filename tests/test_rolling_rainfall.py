"""24時間移動雨量のテスト（仕様17.2節）。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from amedas_rainfall.indices.rolling_rainfall import ROLLING_COLUMN, calculate_rolling_rainfall


def _series(values: list[float]) -> pd.Series:
    index = pd.date_range("2020-01-01", periods=len(values), freq="h", tz="Asia/Tokyo")
    return pd.Series(values, index=index, dtype=float)


def test_matches_simple_sum_of_24_hours() -> None:
    values = [1.0] * 30
    s = _series(values)
    result = calculate_rolling_rainfall(s)
    assert result[ROLLING_COLUMN].iloc[23] == 24.0
    assert result[ROLLING_COLUMN].iloc[29] == 24.0


def test_nan_for_first_23_hours() -> None:
    values = [1.0] * 30
    s = _series(values)
    result = calculate_rolling_rainfall(s)
    for i in range(23):
        assert np.isnan(result[ROLLING_COLUMN].iloc[i])


def test_nan_when_gap_within_window() -> None:
    values = [1.0] * 40
    values[10] = np.nan
    s = _series(values)
    result = calculate_rolling_rainfall(s)
    # 欠測を含む窓（10番目を含む23..33番目のインデックス範囲）はNaNとなる
    assert np.isnan(result[ROLLING_COLUMN].iloc[23])
    assert np.isnan(result[ROLLING_COLUMN].iloc[33])
    # 欠測を含まない窓は正しく合計される
    assert result[ROLLING_COLUMN].iloc[34] == 24.0
