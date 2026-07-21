"""core/examples/benchmark.rs と同一条件（50年分・10分刻み・約262.8万ステップ）で
Python版 run_tank_model_10min の実行時間を計測し、Rust版と直接比較するためのスクリプト。

実行方法:
    .venv/Scripts/python.exe core/examples/benchmark_python.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from amedas_rainfall.config import load_tank_model_config  # noqa: E402
from amedas_rainfall.indices.soil_tank import TankModelConfig, run_tank_model_10min  # noqa: E402


def main() -> None:
    years = 50
    n = years * 365 * 24 * 6
    print(f"n = {n} steps ({years}年分, 10分刻み)")

    rng = np.random.default_rng(2026)
    r = rng.random(n)
    values = np.where(r < 0.75, 0.0, np.where(r < 0.95, rng.uniform(0.1, 2.0, n), rng.uniform(2.0, 15.0, n)))

    index = pd.date_range("2020-01-01", periods=n, freq="10min", tz="Asia/Tokyo")
    series = pd.Series(values, index=index)

    raw = load_tank_model_config()
    config = TankModelConfig.from_dict(raw)

    start = time.perf_counter()
    result = run_tank_model_10min(series, config)
    elapsed = time.perf_counter() - start

    print(f"Python実行時間: {elapsed:.3f}秒")
    print(
        "(検算用) 最終貯留量 "
        f"tank1={result['soil_tank_1_mm'].iloc[-1]:.4f} "
        f"tank2={result['soil_tank_2_mm'].iloc[-1]:.4f} "
        f"tank3={result['soil_tank_3_mm'].iloc[-1]:.4f}"
    )


if __name__ == "__main__":
    main()
