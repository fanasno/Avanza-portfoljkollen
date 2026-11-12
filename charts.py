"""Existing Plotly charts with the Avanza prototype palette."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from engine import format_sek
from brand import THEME, BRAND_COLORS


def build_current_allocation_chart(df: pd.DataFrame) -> go.Figure:
    fig = px.pie(
        df,
        values="value_sek",
        names="category",
        hole=0.62,
        color_discrete_sequence=BRAND_COLORS,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=10),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(font=dict(family="DM Sans, Arial, sans-serif", color=THEME["ink"]), separators=", ", height=360)
    fig.update_traces(textinfo="percent", hovertemplate="%{label}<br>%{value:,.0f} kr · %{percent}<extra></extra>")
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center", font=dict(size=10)))
    fig.add_annotation(text="Din portfölj", x=0.5, y=0.5, showarrow=False, font=dict(size=14))
    return fig



def build_comparison_chart(df: pd.DataFrame) -> go.Figure:
    comparison = df[["name", "current_weight_pct", "target_weight_pct"]].melt(
        id_vars="name",
        value_vars=["current_weight_pct", "target_weight_pct"],
        var_name="scenario",
        value_name="weight_pct",
    )
    comparison["scenario"] = comparison["scenario"].map(
        {
            "current_weight_pct": "Nuvarande",
            "target_weight_pct": "Föreslagen",
        }
    )
    fig = px.bar(
        comparison,
        x="name",
        y="weight_pct",
        color="scenario",
        barmode="group",
        color_discrete_map={
            "Nuvarande": "#C8D8D0",
            "Föreslagen": THEME["accent_blue"],
        },
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="",
        yaxis_title="Vikt (%)",
        legend_title="",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(font=dict(family="DM Sans, Arial, sans-serif", color=THEME["ink"]), separators=", ", height=360)
    fig.update_xaxes(tickvals=df["name"].tolist(), ticktext=df["category"].tolist(), tickangle=0)
    return fig



def build_contribution_chart(df: pd.DataFrame) -> go.Figure:
    comparison = df[["name", "weight_after_cash_pct", "target_weight_pct"]].melt(
        id_vars="name",
        value_vars=["weight_after_cash_pct", "target_weight_pct"],
        var_name="scenario",
        value_name="weight_pct",
    )
    comparison["scenario"] = comparison["scenario"].map(
        {
            "weight_after_cash_pct": "Efter insättning",
            "target_weight_pct": "Målvikt",
        }
    )
    fig = px.bar(
        comparison,
        x="name",
        y="weight_pct",
        color="scenario",
        barmode="group",
        color_discrete_map={
            "Efter insättning": "#77BE9A",
            "Målvikt": THEME["accent_blue"],
        },
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="",
        yaxis_title="Vikt (%)",
        legend_title="",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(font=dict(family="DM Sans, Arial, sans-serif", color=THEME["ink"]), separators=", ", height=360)
    fig.update_xaxes(tickvals=df["name"].tolist(), ticktext=df["category"].tolist(), tickangle=0)
    return fig



def build_mock_backtest_chart(history_series: pd.Series, invested_amount: float) -> go.Figure:
    chart_df = pd.DataFrame({"date": history_series.index, "value": history_series.values})
    fig = px.area(chart_df, x="date", y="value")
    fig.update_traces(
        line=dict(color=THEME["accent_blue"], width=3),
        fillcolor="rgba(0, 133, 104, 0.12)",
    )
    fig.add_hline(
        y=invested_amount,
        line_dash="dot",
        line_color=THEME["ink_soft"],
        annotation_text="Startbelopp",
        annotation_position="top left",
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="",
        yaxis_title="Värde (kr)",
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(font=dict(family="DM Sans, Arial, sans-serif", color=THEME["ink"]), separators=", ", height=360)
    return fig



def build_mock_future_chart(path_df: pd.DataFrame, start_value: float) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=path_df["date"],
            y=path_df["p90"],
            mode="lines",
            line=dict(color="rgba(0,133,104,0)"),
            hoverinfo="skip",
            showlegend=False,
            name="Övre spann (P90)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=path_df["date"],
            y=path_df["p10"],
            mode="lines",
            line=dict(color="rgba(0,133,104,0)"),
            fill="tonexty",
            fillcolor="rgba(0,133,104,0.16)",
            name="Sannolikhetsband (P10-P90)",
            hovertemplate="%{y:,.0f} kr<extra>Nedre spann</extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=path_df["date"],
            y=path_df["median"],
            mode="lines",
            line=dict(color=THEME["accent_blue"], width=3),
            name="Median (P50)",
            hovertemplate="%{y:,.0f} kr<extra>Median</extra>",
        )
    )
    fig.add_hline(
        y=start_value,
        line_dash="dot",
        line_color=THEME["ink_soft"],
        annotation_text="Investerat belopp",
        annotation_position="top left",
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="",
        yaxis_title="Möjligt värde (kr)",
        legend_title="",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(font=dict(family="DM Sans, Arial, sans-serif", color=THEME["ink"]), separators=", ", height=360)
    fig.update_layout(legend=dict(orientation="h", y=1.13, x=0, font=dict(size=10)), margin=dict(l=10, r=10, t=40, b=25))
    return fig



