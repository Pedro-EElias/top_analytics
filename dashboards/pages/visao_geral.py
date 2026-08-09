import dash
from dash import html
import plotly.graph_objects as go

from components.cards import kpi_card, chart_card, formatar_moeda, formatar_numero
from components.header import render_header
from components.theme import COLORS, SERIES_PALETTE, apply_layout, pad_range, left_align_y_labels
from services import data as ds

dash.register_page(__name__, path="/", name="Visão Geral", title="Visão Geral · Vendas de Eletrônicos")


def _grafico_regiao(df):
    df = df.sort_values("valor_total_vendido", ascending=True)
    fig = go.Figure(
        go.Bar(
            x=df["valor_total_vendido"], y=df["regiao"], orientation="h",
            marker_color=SERIES_PALETTE[0],
            text=[formatar_moeda(v) for v in df["valor_total_vendido"]],
            textposition="outside", textfont=dict(color=COLORS["text_dark"], size=12),
            hovertemplate="<b>%{y}</b><br>Faturamento: %{text}<extra></extra>",
        )
    )
    apply_layout(fig, margin=dict(l=10, r=60, t=10, b=10))
    fig.update_xaxes(visible=False)
    pad_range(fig, df["valor_total_vendido"])
    left_align_y_labels(fig, df["regiao"])
    return fig


def _grafico_donut_regiao(df):
    fig = go.Figure(
        go.Pie(
            labels=df["regiao"], values=df["pct_faturamento"], hole=0.62,
            marker=dict(colors=SERIES_PALETTE, line=dict(color="white", width=2)),
            textinfo="label+percent", textfont=dict(size=12),
        )
    )
    apply_layout(fig, showlegend=False)
    return fig


def _grafico_evolucao(df):
    labels = [ds.mes_abreviado(p) for p in df["periodo"].astype(str)]
    fig = go.Figure(
        go.Scatter(
            x=labels, y=df["valor_total_vendido"], mode="lines+markers",
            line=dict(color=COLORS["accent"], width=3, shape="spline"),
            marker=dict(size=8, color=COLORS["accent"]),
            fill="tozeroy", fillcolor="rgba(236,72,153,0.10)",
            hovertemplate="%{x}<br>Faturamento: R$ %{y:,.2f}<extra></extra>",
        )
    )
    apply_layout(fig)
    return fig


def _grafico_top_vendedores(df):
    df = df.sort_values("valor_total_vendido", ascending=True).tail(8)
    fig = go.Figure(
        go.Bar(
            x=df["valor_total_vendido"], y=df["nome_vendedor"], orientation="h",
            marker_color=SERIES_PALETTE[2],
            text=[formatar_moeda(v) for v in df["valor_total_vendido"]],
            textposition="outside", textfont=dict(size=11),
            hovertemplate="<b>%{y}</b><br>%{text}<extra></extra>",
        )
    )
    apply_layout(fig, margin=dict(l=10, r=70, t=10, b=10))
    fig.update_xaxes(visible=False)
    pad_range(fig, df["valor_total_vendido"])
    left_align_y_labels(fig, df["nome_vendedor"])
    return fig


def layout():
    kpis = ds.kpis_gerais()
    regiao = ds.vendas_por_regiao()
    evolucao = ds.evolucao_mensal()
    top_vend = ds.top_vendedores()

    cards_kpi = html.Div(
        [
            kpi_card("Faturamento total", formatar_moeda(kpis["faturamento_total"]), icone="bi-currency-dollar", destaque=True),
            kpi_card("Transações", formatar_numero(kpis["transacoes"]), icone="bi-receipt"),
            kpi_card("Itens vendidos", formatar_numero(kpis["quantidade_vendida"]), icone="bi-box-seam"),
            kpi_card("Ticket médio", formatar_moeda(kpis["ticket_medio"]), icone="bi-graph-up-arrow"),
        ],
        className="kpi-row",
    )

    return html.Div(
        [
            render_header(
                "Visão Geral de Vendas",
                f"Período analisado: {str(kpis['data_inicial'])[:10]} a {str(kpis['data_final'])[:10]}",
                kicker="RESUMO EXECUTIVO",
            ),
            cards_kpi,
            html.Div(
                [
                    chart_card("Faturamento por região", _grafico_regiao(regiao), altura="280px"),
                    chart_card("Participação no faturamento", _grafico_donut_regiao(regiao), altura="280px"),
                ],
                className="grid-2",
            ),
            html.Div(
                [
                    chart_card("Evolução mensal do faturamento", _grafico_evolucao(evolucao), altura="300px"),
                    chart_card("Top vendedores", _grafico_top_vendedores(top_vend), altura="300px"),
                ],
                className="grid-2",
            ),
        ]
    )
