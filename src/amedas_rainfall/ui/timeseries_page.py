"""時系列グラフ画面（12.3節）。"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from amedas_rainfall.config import AppConfig
from amedas_rainfall.pipeline import compute_all_indices, load_normalized_hourly, normalized_hourly_path
from amedas_rainfall.visualization.export import build_export_filename, export_figure, save_plot_settings
from amedas_rainfall.visualization.styles import PlotStyle
from amedas_rainfall.visualization.timeseries import INDICATOR_LABELS, build_timeseries_figure

PERIOD_PRESETS = ["最新31日", "今月", "前月", "任意期間"]


def _resolve_period(preset: str, max_ts: pd.Timestamp) -> tuple[dt.date, dt.date]:
    today = max_ts.date()
    if preset == "最新31日":
        return today - dt.timedelta(days=31), today
    if preset == "今月":
        start = today.replace(day=1)
        return start, today
    if preset == "前月":
        first_this_month = today.replace(day=1)
        last_month_end = first_this_month - dt.timedelta(days=1)
        return last_month_end.replace(day=1), last_month_end
    return today - dt.timedelta(days=31), today


def render_timeseries_page(config: AppConfig) -> None:
    st.header("時系列グラフ")

    station = st.session_state.get("selected_station")
    if not station:
        st.info("「地点選択・ダウンロード」タブで地点を選択してください。")
        return
    station_code = station["station_code"]
    station_name = station["station_name"]

    if not normalized_hourly_path(config, station_code).exists():
        st.warning("正規化済みデータがありません。先にダウンロードと正規化データの再構築を行ってください。")
        return

    cache_key = f"indices_df_{station_code}"
    if cache_key not in st.session_state:
        with st.spinner("指標を計算しています..."):
            hourly = load_normalized_hourly(config, station_code)
            st.session_state[cache_key] = compute_all_indices(config, hourly)
    indices_df = st.session_state[cache_key]

    if st.button("指標を再計算する", key="ts_recompute_button"):
        hourly = load_normalized_hourly(config, station_code)
        st.session_state[cache_key] = compute_all_indices(config, hourly)
        st.rerun()

    st.subheader("表示期間")
    preset = st.radio("期間プリセット", PERIOD_PRESETS, horizontal=True, key="ts_period_preset")
    max_ts = indices_df.index.max()
    default_start, default_end = _resolve_period(preset, max_ts)
    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input(
            "開始日時", value=default_start, disabled=(preset != "任意期間"), key="ts_start_date"
        )
    with c2:
        end_date = st.date_input(
            "終了日時", value=default_end, disabled=(preset != "任意期間"), key="ts_end_date"
        )

    mask = (indices_df.index.date >= start_date) & (indices_df.index.date <= end_date)
    view = indices_df.loc[mask]

    st.subheader("表示項目")
    bar_column = st.radio(
        "上段（棒グラフ）", ["rainfall_raw_mm", "rainfall_used_mm"], format_func=lambda c: {
            "rainfall_raw_mm": "原時雨量", "rainfall_used_mm": "閾値処理後時雨量"
        }[c], horizontal=True, key="ts_bar_column",
    )
    indicator_options = list(INDICATOR_LABELS.keys())
    selected_indicators = st.multiselect(
        "下段（折れ線グラフ、複数選択可）",
        indicator_options,
        default=["effective_rainfall_6h_mm"],
        format_func=lambda c: INDICATOR_LABELS.get(c, c),
        key="ts_selected_indicators",
    )

    with st.expander("グラフ調整"):
        style_key = f"ts_style_{station_code}"
        if style_key not in st.session_state:
            st.session_state[style_key] = PlotStyle(title=f"{station_name} 時系列")
        style: PlotStyle = st.session_state[style_key]

        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            style.size_unit = st.radio(
                "単位", ["px", "mm"], index=0 if style.size_unit == "px" else 1, key="ts_size_unit"
            )
            style.width = st.number_input("図幅", value=float(style.width), key="ts_fig_width")
            style.height = st.number_input("図高", value=float(style.height), key="ts_fig_height")
        with cc2:
            style.dpi = st.selectbox(
                "DPI(PNG用)", [300, 600, 1200],
                index=[300, 600, 1200].index(style.dpi) if style.dpi in (300, 600, 1200) else 0,
                key="ts_fig_dpi",
            )
            style.font_size = st.number_input("基本フォントサイズ", value=style.font_size, key="ts_font_size")
            style.line_width = st.number_input("線幅", value=float(style.line_width), key="ts_line_width")
        with cc3:
            style.grayscale = st.checkbox("白黒モード", value=style.grayscale, key="ts_grayscale")
            style.show_grid = st.checkbox("グリッド表示", value=style.show_grid, key="ts_show_grid")
            style.show_missing_markers = st.checkbox(
                "欠測箇所を表示", value=style.show_missing_markers, key="ts_show_missing_markers"
            )

        style.title = st.text_input("タイトル", value=style.title, key="ts_title")
        style.subtitle = st.text_input("サブタイトル", value=style.subtitle, key="ts_subtitle")
        style.note = st.text_area("注記", value=style.note, key="ts_note")

    missing_mask = view["is_missing"] if "is_missing" in view.columns else None
    fig = build_timeseries_figure(view, bar_column, selected_indicators, style, missing_mask=missing_mask)
    st.plotly_chart(fig, use_container_width=True, theme=None)

    st.subheader("画像出力")
    fmt = st.selectbox("形式", ["png", "svg", "pdf"], key="ts_fmt")
    detail = "_".join(selected_indicators) if selected_indicators else "指標未選択"
    if st.button("画像を生成してダウンロード用に保存", key="ts_export_button"):
        filename = build_export_filename(station_name, "時系列", detail, start_date, end_date, fmt)
        out_dir = config.resolved_path("paths.output_dir") / "figures"
        out_path = out_dir / filename
        export_figure(fig, out_path, fmt, style.width_px(), style.height_px(), dpi=style.dpi)
        st.success(f"保存しました: {out_path}")
        with open(out_path, "rb") as f:
            st.download_button("ダウンロード", f.read(), file_name=filename, key="ts_dl")

    if st.button("グラフ設定を保存(JSON)", key="ts_save_settings_button"):
        settings_path = (
            config.resolved_path("paths.output_dir")
            / "plot_settings"
            / f"{station_code}_timeseries_settings.json"
        )
        save_plot_settings(
            style,
            {"bar_column": bar_column, "indicators": selected_indicators, "preset": preset},
            settings_path,
        )
        st.success(f"保存しました: {settings_path}")
