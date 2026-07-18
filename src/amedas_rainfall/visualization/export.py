"""グラフ画像出力（PNG/SVG/PDF）とグラフ設定JSONの保存・読込（14節）。"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import plotly.graph_objects as go

from amedas_rainfall.visualization.styles import PlotStyle

BASE_CSS_DPI = 96.0
SUPPORTED_FORMATS = ("png", "svg", "pdf")


def _sanitize_filename_part(text: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]", "_", text)


def build_export_filename(
    station_name: str,
    chart_type: str,
    detail: str,
    start: dt.date | dt.datetime,
    end: dt.date | dt.datetime,
    ext: str,
) -> str:
    """例: 豊田_時系列_実効雨量6h_20260618-20260718.png"""
    parts = [
        _sanitize_filename_part(station_name),
        _sanitize_filename_part(chart_type),
        _sanitize_filename_part(detail),
        f"{start:%Y%m%d}-{end:%Y%m%d}",
    ]
    return "_".join(parts) + f".{ext}"


def export_figure(
    fig: go.Figure,
    output_path: Path,
    fmt: str,
    width_px: float,
    height_px: float,
    dpi: int = 300,
) -> Path:
    """Plotly図をPNG/SVG/PDFとして書き出す（Kaleidoを使用、サーバー側で再生成）。"""
    fmt = fmt.lower()
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"未対応の出力形式です: {fmt}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "png":
        scale = dpi / BASE_CSS_DPI
        fig.write_image(str(output_path), format="png", width=width_px, height=height_px, scale=scale)
    else:
        fig.write_image(str(output_path), format=fmt, width=width_px, height=height_px)
    return output_path


def save_plot_settings(style: PlotStyle, extra: dict, path: Path) -> None:
    """グラフ設定（スタイル＋選択指標等）をJSONとして保存する。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"style": style.to_dict(), "extra": extra}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)


def load_plot_settings(path: Path) -> tuple[PlotStyle, dict]:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    style = PlotStyle.from_dict(payload.get("style", {}))
    extra = payload.get("extra", {})
    return style, extra
