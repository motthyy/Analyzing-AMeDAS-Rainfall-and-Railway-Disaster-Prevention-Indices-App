"""アメダス長期雨量・鉄道防災指標解析アプリ エントリーポイント。

起動方法:
    streamlit run app.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import streamlit as st  # noqa: E402

from amedas_rainfall.config import get_default_config  # noqa: E402
from amedas_rainfall.ui.export_page import render_export_page  # noqa: E402
from amedas_rainfall.ui.probability_page import render_probability_page  # noqa: E402
from amedas_rainfall.ui.quality_page import render_quality_page  # noqa: E402
from amedas_rainfall.ui.station_page import render_station_page  # noqa: E402
from amedas_rainfall.ui.timeseries_page import render_timeseries_page  # noqa: E402


def _setup_logging(config) -> None:
    logs_dir = config.resolved_path("paths.logs_dir")
    logs_dir.mkdir(parents=True, exist_ok=True)
    import datetime as dt

    log_path = logs_dir / f"app_{dt.date.today():%Y%m%d}.log"
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        root_logger.setLevel(logging.INFO)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root_logger.addHandler(file_handler)


def main() -> None:
    st.set_page_config(
        page_title="アメダス長期雨量・鉄道防災指標解析アプリ",
        layout="wide",
    )
    config = get_default_config()
    _setup_logging(config)

    st.title("アメダス長期雨量・鉄道防災指標解析アプリ")
    st.caption(
        "気象庁「過去の気象データ・ダウンロード」を用いた時別降水量の取得、"
        "鉄道防災用雨量指標・推定土壌雨量指数・ガンベル分布による確率雨量の解析ツールです。"
    )

    tabs = st.tabs(["地点選択・ダウンロード", "データ品質", "時系列グラフ", "確率雨量グラフ", "データ出力"])
    with tabs[0]:
        render_station_page(config)
    with tabs[1]:
        render_quality_page(config)
    with tabs[2]:
        render_timeseries_page(config)
    with tabs[3]:
        render_probability_page(config)
    with tabs[4]:
        render_export_page(config)


if __name__ == "__main__":
    main()
