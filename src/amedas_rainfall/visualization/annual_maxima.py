"""年最大値時系列（棒グラフ）の構築。Excel r_max_c(manual ver.).xlsmのrp_inシートに
埋め込まれた棒グラフ（各指標の年最大値を年ごとに表示）と同等の図を作る。
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from amedas_rainfall.visualization.styles import PlotStyle


def build_annual_maxima_figure(
    maxima_df: pd.DataFrame,
    style: PlotStyle,
    y_axis_label: str = "年最大値 [mm]",
) -> go.Figure:
    """年最大値データフレーム（year_label, start_year, max_value, max_datetime列）から棒グラフを作る。"""
    fig = go.Figure()
    bar_color = style.style_cycle()[0]["color"]

    fig.add_trace(
        go.Bar(
            x=maxima_df["year_label"],
            y=maxima_df["max_value"],
            name=y_axis_label,
            marker_color=bar_color,
        )
    )

    fig.update_xaxes(
        title_text="年",
        type="category",
        showgrid=style.show_grid,
        gridcolor="#e0e0e0",
        tickfont=dict(size=style.tick_size, color=style.font_color),
        title_font=dict(size=style.axis_label_size, color=style.font_color),
        showline=style.show_frame,
        linecolor=style.font_color,
        mirror=style.show_frame,
        ticks="outside",
    )
    fig.update_yaxes(
        title_text=y_axis_label,
        showgrid=style.show_grid,
        gridcolor="#e0e0e0",
        tickfont=dict(size=style.tick_size, color=style.font_color),
        title_font=dict(size=style.axis_label_size, color=style.font_color),
        showline=style.show_frame,
        linecolor=style.font_color,
        mirror=style.show_frame,
        ticks="outside",
    )
    fig.update_layout(
        width=style.width_px(),
        height=style.height_px(),
        title=dict(text=style.title, font=dict(size=style.font_size + 4, color=style.font_color)),
        font=dict(family=style.font_family, size=style.font_size, color=style.font_color),
        legend=dict(
            font=dict(size=style.legend_size, color=style.font_color),
            bgcolor=style.background_color,
            bordercolor="#cccccc",
            borderwidth=1,
        ),
        plot_bgcolor=style.background_color,
        paper_bgcolor=style.background_color,
        margin=dict(
            t=style.margin_top, b=style.margin_bottom, l=style.margin_left, r=style.margin_right
        ),
        showlegend=False,
        hovermode="x unified",
        hoverlabel=dict(font=dict(color=style.font_color)),
    )
    if style.subtitle:
        fig.add_annotation(
            text=style.subtitle,
            xref="paper",
            yref="paper",
            x=0.5,
            y=1.06,
            showarrow=False,
            font=dict(size=style.font_size, color=style.font_color),
        )
    if style.note:
        fig.add_annotation(
            text=style.note,
            xref="paper",
            yref="paper",
            x=0.0,
            y=-0.22,
            showarrow=False,
            font=dict(size=max(style.font_size - 2, 8), color=style.font_color),
            align="left",
        )
    if style.y_range:
        fig.update_yaxes(range=list(style.y_range))
    return fig
