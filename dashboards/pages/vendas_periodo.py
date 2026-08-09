import dash
from dash import html, dcc, Input, Output, callback
import plotly.graph_objects as go

from components.cards import chart_card, kpi_card, formatar_moeda, formatar_numero
from components.header import render_header
from components.theme import COLORS, SERIES_PALETTE, apply_layout, pad_range, left_align_y_labels
from services import data as ds

dash.register_page(__name__, path="/vendas-por-periodo", name="Vendas por Período", title="Vendas por Período")

PERIODOS = ds.periodos_disponiveis()
REGIOES = ["Todas"] + ds.regioes_disponiveis()


def layout():
    return html.Div(
        [
            render_header(
                "Vendas por Período",
                "Explore transações, quantidade e faturamento em cada janela de tempo do semestre.",
                kicker="ANÁLISE TEMPORAL",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Período", className="filter-label"),
                            dcc.Dropdown(
                                id="filtro-periodo", options=PERIODOS, value="Último semestre",
                                clearable=False, className="filter-dropdown",
                            ),
                        ],
                        className="filter-group",
                    ),
                    html.Div(
                        [
                            html.Label("Região", className="filter-label"),
                            dcc.Dropdown(
                                id="filtro-regiao-periodo", options=REGIOES, value="Todas",
                                clearable=False, className="filter-dropdown",
                            ),
                        ],
                        className="filter-group",
                    ),
                ],
                className="filter-bar",
            ),
            html.Div(id="kpis-periodo", className="kpi-row"),
            html.Div(
                [
                    html.Div(id="grafico-produto-periodo-wrapper", className="chart-card"),
                    html.Div(id="grafico-regiao-periodo-wrapper", className="chart-card"),
                ],
                className="grid-2",
            ),
        ]
    )


def _kpis(df):
    """Retorna a LISTA de cards (não uma Div envolvendo-os), para que o
    grid CSS de .kpi-row atue diretamente sobre cada card."""
    faturamento = df["valor_total_vendido"].sum()
    transacoes = df["transacoes"].sum()
    quantidade = df["quantidade_vendida"].sum()
    ticket = faturamento / transacoes if transacoes else 0
    return [
        kpi_card("Faturamento no período", formatar_moeda(faturamento), icone="bi-currency-dollar", destaque=True),
        kpi_card("Transações", formatar_numero(transacoes), icone="bi-receipt"),
        kpi_card("Itens vendidos", formatar_numero(quantidade), icone="bi-box-seam"),
        kpi_card("Ticket médio", formatar_moeda(ticket), icone="bi-graph-up-arrow"),
    ]


def _fig_produto(df):
    top = df.groupby("produto", as_index=False)["valor_total_vendido"].sum().sort_values(
        "valor_total_vendido", ascending=True
    ).tail(10)
    fig = go.Figure(
        go.Bar(
            x=top["valor_total_vendido"], y=top["produto"], orientation="h",
            marker_color=SERIES_PALETTE[0],
            text=[formatar_moeda(v) for v in top["valor_total_vendido"]],
            textposition="outside", textfont=dict(size=11),
        )
    )
    apply_layout(fig, margin=dict(l=10, r=70, t=10, b=10))
    fig.update_xaxes(visible=False)
    pad_range(fig, top["valor_total_vendido"])
    left_align_y_labels(fig, top["produto"])
    return fig


def _fig_regiao(df):
    agrupado = df.groupby("regiao", as_index=False)["valor_total_vendido"].sum().sort_values("valor_total_vendido")
    fig = go.Figure(
        go.Bar(
            x=agrupado["regiao"], y=agrupado["valor_total_vendido"],
            marker_color=SERIES_PALETTE[1],
            text=[formatar_moeda(v) for v in agrupado["valor_total_vendido"]],
            textposition="outside", textfont=dict(size=11),
        )
    )
    apply_layout(fig, margin=dict(l=10, r=10, t=20, b=10))
    fig.update_yaxes(visible=False)
    pad_range(fig, agrupado["valor_total_vendido"], axis="y", factor=1.22)
    return fig


@callback(
    Output("filtro-periodo", "value"),
    Output("filtro-regiao-periodo", "value"),
    Input("botao-limpar-filtros", "n_clicks"),
    prevent_initial_call=True,
)
def limpar_filtros(n_clicks):
    return "Último semestre", "Todas"


@callback(
    Output("kpis-periodo", "children"),
    Output("grafico-produto-periodo-wrapper", "children"),
    Output("grafico-regiao-periodo-wrapper", "children"),
    Input("filtro-periodo", "value"),
    Input("filtro-regiao-periodo", "value"),
)
def atualizar(periodo, regiao):
    df = ds.itens_filtrados(periodo, regiao)
    if df.empty:
        vazio = html.Div("Sem dados para esta combinação de filtros.", className="empty-state")
        return [], vazio, vazio

    grafico_produto = chart_card("Faturamento por produto (top 10)", _fig_produto(df), altura="360px")
    grafico_regiao = chart_card(
        "Faturamento por região" if regiao == "Todas" else f"Detalhe — {regiao}",
        _fig_regiao(df), altura="360px",
    )
    return _kpis(df), grafico_produto.children, grafico_regiao.children
