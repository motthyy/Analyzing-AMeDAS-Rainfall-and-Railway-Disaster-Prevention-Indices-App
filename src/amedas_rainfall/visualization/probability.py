"""確率雨量グラフの構築（12.4節）。"""

from __future__ import annotations

import math

import numpy as np
import plotly.graph_objects as go

from amedas_rainfall.statistics.bootstrap import BootstrapResult
from amedas_rainfall.statistics.gumbel import GumbelResult, empirical_return_periods
from amedas_rainfall.visualization.styles import PlotStyle


def build_probability_figure(
    annual_maxima: np.ndarray,
    gumbel_result: GumbelResult,
    style: PlotStyle,
    plotting_position: str = "gringorten",
    bootstrap_results: dict[float, BootstrapResult] | None = None,
    show_observed: bool = True,
    show_fit_line: bool = True,
    show_ci: bool = True,
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
        t_max = max(500, (max(gumbel_result.return_periods) if gumbel_result.return_periods else 500))
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

    if show_ci and bootstrap_results:
        items = sorted(bootstrap_results.items())
        xs = [t for t, r in items if not math.isnan(r.lower) and not math.isnan(r.upper)]
        lowers = [r.lower for t, r in items if not math.isnan(r.lower) and not math.isnan(r.upper)]
        uppers = [r.upper for t, r in items if not math.isnan(r.lower) and not math.isnan(r.upper)]
        if xs:
            fig.add_trace(
                go.Scatter(
                    x=xs + xs[::-1],
                    y=uppers + lowers[::-1],
                    fill="toself",
                    fillcolor="rgba(150,150,150,0.25)",
                    line=dict(color="rgba(0,0,0,0)"),
                    name=f"信頼区間({bootstrap_results[xs[0]].confidence_level * 100:.0f}%)",
                    showlegend=True,
                )
            )

    fig.update_xaxes(
        title_text="確率年 [年]",
        type="log" if x_log else "linear",
        showgrid=style.show_grid,
        tickfont=dict(size=style.tick_size),
        title_font=dict(size=style.axis_label_size),
    )
    fig.update_yaxes(
        title_text=f"{indicator_label} [mm]",
        showgrid=style.show_grid,
        tickfont=dict(size=style.tick_size),
        title_font=dict(size=style.axis_label_size),
    )
    fig.update_layout(
        width=style.width_px(),
        height=style.height_px(),
        title=dict(text=style.title, font=dict(size=style.font_size + 4)),
        font=dict(family=style.font_family, size=style.font_size),
        legend=dict(font=dict(size=style.legend_size)),
        plot_bgcolor=style.background_color,
        paper_bgcolor=style.background_color,
        margin=dict(
            t=style.margin_top, b=style.margin_bottom, l=style.margin_left, r=style.margin_right
        ),
    )
    if style.x_range:
        fig.update_xaxes(range=list(style.x_range))
    if style.y_range:
        fig.update_yaxes(range=list(style.y_range))
    return fig
