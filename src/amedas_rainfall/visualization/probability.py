"""確率雨量グラフの構築（12.4節）。"""

from __future__ import annotations

import math

import numpy as np
import plotly.graph_objects as go

from amedas_rainfall.statistics.gumbel import GumbelResult, empirical_return_periods
from amedas_rainfall.visualization.styles import PlotStyle


def build_probability_figure(
    annual_maxima: np.ndarray,
    gumbel_result: GumbelResult,
    style: PlotStyle,
    plotting_position: str = "gringorten",
    show_observed: bool = True,
    show_fit_line: bool = True,
    x_log: bool = True,
    indicator_label: str = "指標",
) -> go.Figure:
    """年最大値のプロッティングポジションとガンベル適合曲線を描画する。"""
    fig = go.Figure()
    cycle = style.style_cycle()

    data = np.sort(np.asarray(annual_maxima, dtype=float))
    data = data[~np.isnan(data)]
    n = len(data)

    if show_observed and n > 0:
        t_m = empirical_return_periods(n, method=plotting_position)
        fig.add_trace(
            go.Scatter(
                x=t_m,
                y=data,
                mode="markers",
                name="年最大値観測点",
                marker=dict(color=cycle[0]["color"], size=style.marker_size, symbol=cycle[0]["symbol"]),
            )
        )

    if show_fit_line:
        t_min = 1.05
        t_max = max(gumbel_result.return_periods) if gumbel_result.return_periods else 100
        t_line = np.geomspace(t_min, t_max, 200) if x_log else np.linspace(t_min, t_max, 200)
        mu, beta = gumbel_result.parameters.loc_mu, gumbel_result.parameters.scale_beta
        y_line = [mu - beta * math.log(-math.log(1 - 1 / t)) for t in t_line]
        fig.add_trace(
            go.Scatter(
                x=t_line,
                y=y_line,
                mode="lines",
                name=f"ガンベル適合曲線（{gumbel_result.parameters.method}）",
                line=dict(color=cycle[1]["color"], dash=cycle[1]["dash"], width=style.line_width),
            )
        )

    fig.update_xaxes(
        title_text="確率年 [年]",
        type="log" if x_log else "linear",
        showgrid=style.show_grid,
        gridcolor="#e0e0e0",
        tickfont=dict(size=style.tick_size, color=style.font_color),
        title_font=dict(size=style.axis_label_size, color=style.font_color),
        showline=style.show_frame,
        linecolor=style.font_color,
        mirror=style.show_frame,
        ticks="outside",
        showspikes=style.show_crosshair,
        spikemode="across",
        spikesnap="cursor",
        spikedash="dot",
        spikethickness=1,
        spikecolor="#666666",
    )
    fig.update_yaxes(
        title_text=f"{indicator_label} [mm]",
        showgrid=style.show_grid,
        gridcolor="#e0e0e0",
        tickfont=dict(size=style.tick_size, color=style.font_color),
        title_font=dict(size=style.axis_label_size, color=style.font_color),
        showline=style.show_frame,
        linecolor=style.font_color,
        mirror=style.show_frame,
        ticks="outside",
        showspikes=style.show_crosshair,
        spikemode="across",
        spikesnap="cursor",
        spikedash="dot",
        spikethickness=1,
        spikecolor="#666666",
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
        hovermode="x unified",
        hoverlabel=dict(font=dict(color=style.font_color)),
    )
    if style.x_range:
        fig.update_xaxes(range=list(style.x_range))
    if style.y_range:
        fig.update_yaxes(range=list(style.y_range))
    return fig
