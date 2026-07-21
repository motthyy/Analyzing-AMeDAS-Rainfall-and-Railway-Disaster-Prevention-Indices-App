"""Phase 0: 既存Python実装の入出力を「正解データ（ゴールデンフィクスチャ）」としてJSONへ書き出す。

移行計画（docs/language_migration_plan.md）のPhase 0に対応する。
ここで書き出したJSONは、Rust移植後の実装が同じ入力に対して同じ出力（許容誤差1e-9程度）を
返すことを確認するための「唯一の正解」として使う。

実行方法:
    .venv/Scripts/python.exe tests/fixtures/golden/generate.py

出力先:
    tests/fixtures/golden/*.json
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from amedas_rainfall.config import load_tank_model_config  # noqa: E402
from amedas_rainfall.indices.continuous_rainfall import calculate_continuous_rainfall  # noqa: E402
from amedas_rainfall.indices.effective_rainfall import calculate_effective_rainfall  # noqa: E402
from amedas_rainfall.indices.rolling_rainfall import calculate_rolling_rainfall  # noqa: E402
from amedas_rainfall.indices.soil_tank import (  # noqa: E402
    TankModelConfig,
    disaggregate_hourly_to_10min,
    run_tank_model_10min,
)
from amedas_rainfall.processing.normalization import apply_no_rain_threshold  # noqa: E402
from amedas_rainfall.statistics.annual_maxima import (  # noqa: E402
    CALENDAR_YEAR,
    FISCAL_YEAR,
    JUNE_START_YEAR,
    calculate_annual_completeness,
    calculate_annual_maxima,
    year_window,
)
from amedas_rainfall.statistics.bootstrap import bootstrap_return_period_ci  # noqa: E402
from amedas_rainfall.statistics.gumbel import (  # noqa: E402
    STANDARD_RETURN_PERIODS,
    analyze_gumbel,
    fit_gumbel_mle,
    fit_gumbel_moments,
    return_period_value,
)

OUT_DIR = Path(__file__).resolve().parent


def _clean(obj):
    """NaN/NaT/numpy型/Timestampを、JSON化可能かつ言語非依存な形へ変換する。"""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (pd.Timestamp,)):
        if pd.isna(obj):
            return None
        return obj.isoformat()
    if obj is pd.NaT:
        return None
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return None if math.isnan(f) else f
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, str):
        return obj
    if obj is None:
        return None
    return obj


def _series_to_records(index: pd.DatetimeIndex, columns: dict[str, pd.Series | np.ndarray]) -> list[dict]:
    records = []
    for i, ts in enumerate(index):
        rec = {"t": ts.isoformat()}
        for name, col in columns.items():
            values = col.to_numpy() if isinstance(col, pd.Series) else col
            rec[name] = _clean(values[i])
        records.append(rec)
    return records


def _write(name: str, payload: dict) -> None:
    path = OUT_DIR / f"{name}.json"
    path.write_text(json.dumps(_clean(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


def _hourly_index(n: int, start: str = "2020-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="h", tz="Asia/Tokyo")


# ---------------------------------------------------------------------------
# 1. 閾値処理 (normalization.apply_no_rain_threshold)
# ---------------------------------------------------------------------------

def gen_threshold() -> None:
    raw = [0.0, 0.1, 0.2, 0.3, 0.4, 1.0, float("nan"), 5.0]
    used = apply_no_rain_threshold(pd.Series(raw, dtype=float))
    _write(
        "threshold",
        {
            "input_raw_mm": _clean(raw),
            "output_used_mm": _clean(used.tolist()),
        },
    )


# ---------------------------------------------------------------------------
# 2. 12時間無降雨リセット連続雨量
# ---------------------------------------------------------------------------

def gen_continuous_rainfall() -> None:
    cases = {
        "accumulates_during_rain": [1.0, 2.0, 3.0],
        "holds_then_resets_then_new_event": [5.0] + [0.0] * 12 + [3.0],
        "gap_resets_with_flags": [5.0, 5.0, float("nan"), float("nan"), 2.0],
    }
    out = {}
    for case_name, values in cases.items():
        s = pd.Series(values, index=_hourly_index(len(values)), dtype=float)
        result = calculate_continuous_rainfall(s)
        out[case_name] = {
            "input": _clean(values),
            "continuous_rainfall_12h_mm": _clean(result["continuous_rainfall_12h_mm"].tolist()),
            "dry_hours": _clean(result["dry_hours"].tolist()),
            "rain_event_id": _clean(result["rain_event_id"].tolist()),
            "state_reset_due_to_gap": _clean(result["state_reset_due_to_gap"].tolist()),
            "warmup_flag": _clean(result["warmup_flag"].tolist()),
        }
    _write("continuous_rainfall", out)


# ---------------------------------------------------------------------------
# 3. 24時間移動雨量
# ---------------------------------------------------------------------------

def gen_rolling_rainfall() -> None:
    values = [1.0] * 40
    values[10] = float("nan")
    s = pd.Series(values, index=_hourly_index(len(values)), dtype=float)
    result = calculate_rolling_rainfall(s)
    _write(
        "rolling_rainfall",
        {
            "input": _clean(values),
            "rolling_24h_mm": _clean(result["rolling_rainfall_24h_mm"].tolist()),
        },
    )


# ---------------------------------------------------------------------------
# 4. 実効雨量
# ---------------------------------------------------------------------------

def gen_effective_rainfall() -> None:
    values = [10.0, 5.0, float("nan"), float("nan"), 3.0] + [0.0] * 20
    s = pd.Series(values, index=_hourly_index(len(values)), dtype=float)
    out = {"input": _clean(values), "half_lives": {}}
    for hl in (1.5, 6.0, 24.0):
        result = calculate_effective_rainfall(s, half_life_hours=hl, column_name="e")
        out["half_lives"][str(hl)] = {
            "e": _clean(result["e"].tolist()),
            "state_reset_due_to_gap": _clean(result["state_reset_due_to_gap"].tolist()),
            "warmup_flag": _clean(result["warmup_flag"].tolist()),
        }
    _write("effective_rainfall", out)


# ---------------------------------------------------------------------------
# 5. 推定10分雨量・3段タンクモデル（最重要: 性能ボトルネック箇所）
# ---------------------------------------------------------------------------

def gen_soil_tank() -> None:
    raw = load_tank_model_config()
    config = TankModelConfig.from_dict(raw)

    # 5a. 手計算で検証可能な単一ステップケース
    single_index = pd.date_range("2020-01-01", periods=1, freq="10min", tz="Asia/Tokyo")
    single = pd.Series([10.0], index=single_index)
    single_result = run_tank_model_10min(single, config)

    # 5b. 10分雨量への均等分配（disaggregate）の確認用ケース
    hourly = pd.Series([0.3, 0.4, 12.0, float("nan"), 3.6], index=_hourly_index(5), dtype=float)
    disaggregated = disaggregate_hourly_to_10min(hourly)

    # 5c. 中規模の乱数系列（正確性の突合とベンチマークの両方に使う）
    rng = np.random.default_rng(2026)
    n = 4320  # 30日分 x 144(10分/日)
    ten_min_index = pd.date_range("2020-01-01", periods=n, freq="10min", tz="Asia/Tokyo")
    ten_min_values = rng.choice(
        [0.0, 0.0, 0.0, 0.0, 0.5, 2.0, 5.0, 15.0], size=n, p=[0.55, 0.1, 0.05, 0.05, 0.1, 0.08, 0.05, 0.02]
    )
    # 欠測区間を1箇所混入させ、状態再初期化ロジックも突合対象に含める
    ten_min_values[1000:1010] = np.nan
    ten_min_series = pd.Series(ten_min_values, index=ten_min_index)
    medium_result = run_tank_model_10min(ten_min_series, config)

    _write(
        "soil_tank",
        {
            "tank_model_config": raw,
            "single_step": {
                "input_10min_mm": [10.0],
                "tank1_mm": _clean(single_result["soil_tank_1_mm"].tolist()),
                "tank2_mm": _clean(single_result["soil_tank_2_mm"].tolist()),
                "tank3_mm": _clean(single_result["soil_tank_3_mm"].tolist()),
            },
            "disaggregate": {
                "input_hourly_mm": _clean(hourly.tolist()),
                "output_10min_mm": _clean(disaggregated.tolist()),
            },
            "medium_series": {
                "input_10min_mm": _clean(ten_min_values.tolist()),
                "tank1_mm": _clean(medium_result["soil_tank_1_mm"].tolist()),
                "tank2_mm": _clean(medium_result["soil_tank_2_mm"].tolist()),
                "tank3_mm": _clean(medium_result["soil_tank_3_mm"].tolist()),
                "tank1_outflow_mm": _clean(medium_result["tank1_outflow_mm"].tolist()),
                "tank2_outflow_mm": _clean(medium_result["tank2_outflow_mm"].tolist()),
                "tank3_outflow_mm": _clean(medium_result["tank3_outflow_mm"].tolist()),
                "tank1_infiltration_mm": _clean(medium_result["tank1_infiltration_mm"].tolist()),
                "tank2_infiltration_mm": _clean(medium_result["tank2_infiltration_mm"].tolist()),
                "tank3_infiltration_mm": _clean(medium_result["tank3_infiltration_mm"].tolist()),
            },
        },
    )


# ---------------------------------------------------------------------------
# 6. 年最大値・年区切り・完全性
# ---------------------------------------------------------------------------

def gen_annual_maxima() -> None:
    windows = {}
    for name, boundary in (("calendar", CALENDAR_YEAR), ("fiscal", FISCAL_YEAR), ("june_start", JUNE_START_YEAR)):
        start, end = year_window(2025, boundary)
        windows[name] = {"start": start.isoformat(), "end": end.isoformat()}

    idx = pd.date_range("2020-01-01", periods=24 * 400, freq="h", tz="Asia/Tokyo")
    rng = np.random.default_rng(7)
    values = pd.Series(rng.uniform(0, 50, size=len(idx)), index=idx)
    maxima = calculate_annual_maxima(values, CALENDAR_YEAR)

    valid = pd.Series(True, index=idx)
    valid.iloc[24:48] = False  # 1日分欠測
    completeness = calculate_annual_completeness(
        valid,
        CALENDAR_YEAR,
        data_start=idx[0],
        data_end=idx[-1],
        now=pd.Timestamp("2030-01-01", tz="Asia/Tokyo"),
    )

    _write(
        "annual_maxima",
        {
            "year_windows_2025": windows,
            "maxima_input_seed": 7,
            "maxima_input_n_hours": len(idx),
            "maxima": [
                {
                    "year_label": r["year_label"],
                    "start_year": r["start_year"],
                    "max_value": _clean(r["max_value"]),
                    "max_datetime": _clean(r["max_datetime"]),
                }
                for r in maxima.to_dict("records")
            ],
            "completeness": [
                {
                    "year_label": c.year_label,
                    "expected_hours": c.expected_hours,
                    "valid_hours": c.valid_hours,
                    "missing_hours": c.missing_hours,
                    "completeness_percent": c.completeness_percent,
                    "is_eligible_default": c.is_eligible_default,
                    "exclusion_reasons": c.exclusion_reasons,
                }
                for c in completeness
            ],
        },
    )


# ---------------------------------------------------------------------------
# 7. ガンベル分布・確率雨量
# ---------------------------------------------------------------------------

def gen_gumbel() -> None:
    sample = [120.5, 98.2, 145.0, 110.3, 88.7, 200.1, 132.4, 99.9, 155.6, 121.0, 175.3, 105.8]
    data = np.array(sample)

    mle = fit_gumbel_mle(data)
    moments = fit_gumbel_moments(data)

    return_values = {
        str(t): return_period_value(mle.loc_mu, mle.scale_beta, t)
        for t in [1, 2, 5, 10, 20, 50, 100, 200, 500]
    }

    mle_analysis = analyze_gumbel(data, method="mle", plotting_position="gringorten")
    moments_analysis = analyze_gumbel(data, method="moments", plotting_position="weibull")

    _write(
        "gumbel",
        {
            "sample_data": sample,
            "mle": {"loc_mu": mle.loc_mu, "scale_beta": mle.scale_beta},
            "moments": {"loc_mu": moments.loc_mu, "scale_beta": moments.scale_beta},
            "return_period_values_from_mle": _clean(return_values),
            "standard_return_periods": STANDARD_RETURN_PERIODS,
            "analysis_mle_gringorten": {
                "loc_mu": mle_analysis.parameters.loc_mu,
                "scale_beta": mle_analysis.parameters.scale_beta,
                "return_periods": mle_analysis.return_periods,
                "estimates_mm": _clean(mle_analysis.estimates_mm),
                "aic": mle_analysis.goodness_of_fit.aic,
                "ks_statistic": mle_analysis.goodness_of_fit.ks_statistic,
                "rmse": mle_analysis.goodness_of_fit.rmse,
                "correlation": mle_analysis.goodness_of_fit.correlation,
            },
            "analysis_moments_weibull": {
                "loc_mu": moments_analysis.parameters.loc_mu,
                "scale_beta": moments_analysis.parameters.scale_beta,
                "return_periods": moments_analysis.return_periods,
                "estimates_mm": _clean(moments_analysis.estimates_mm),
                "aic": moments_analysis.goodness_of_fit.aic,
                "ks_statistic": moments_analysis.goodness_of_fit.ks_statistic,
                "rmse": moments_analysis.goodness_of_fit.rmse,
                "correlation": moments_analysis.goodness_of_fit.correlation,
            },
        },
    )


# ---------------------------------------------------------------------------
# 8. ブートストラップ信頼区間（再現性の突合が主目的。同一乱数アルゴリズムの
#    移植が前提で難易度が高いため、Rust側でNumPy PCG64と同一アルゴリズムの
#    乱数生成器を用意できない場合は、この項目は「アルゴリズム置換」を許容し、
#    数値一致ではなく統計的性質（分布形状・単調性）の検証に切り替えてよい。
# ---------------------------------------------------------------------------

def gen_bootstrap() -> None:
    sample = [120.5, 98.2, 145.0, 110.3, 88.7, 200.1, 132.4, 99.9, 155.6, 121.0, 175.3, 105.8]
    data = np.array(sample)
    result = bootstrap_return_period_ci(data, [10, 100], n_iterations=500, random_seed=42)
    _write(
        "bootstrap",
        {
            "note": "NumPy PCG64乱数系列に依存するため、Rust側はアルゴリズム互換が困難な場合は"
            "統計的性質の検証に切り替えてよい（詳細はこのファイル内のコメント参照）。",
            "sample_data": sample,
            "n_iterations": 500,
            "random_seed": 42,
            "results": {
                str(t): {
                    "lower": r.lower,
                    "upper": r.upper,
                    "median": r.median,
                }
                for t, r in result.items()
            },
        },
    )


def main() -> None:
    gen_threshold()
    gen_continuous_rainfall()
    gen_rolling_rainfall()
    gen_effective_rainfall()
    gen_soil_tank()
    gen_annual_maxima()
    gen_gumbel()
    gen_bootstrap()
    print("done.")


if __name__ == "__main__":
    main()
