import dash
from dash import html, dcc, Input, Output, callback
import plotly.graph_objects as go

from components.cards import chart_card, formatar_moeda
from components.header import render_header
from components.theme import SERIES_PALETTE, apply_layout, pad_range, left_align_y_labels
from services import data as ds

dash.register_page(__name__, path="/produtos-regioes", name="Produtos & Regiões", title="Produtos & Regiões")

REGIOES = ["Todas"] + ds.regioes_disponiveis()


def layout():
    return html.Div(
        [
            render_header(
                "Produtos & Regiões",
                "Faturamento do semestre por categoria de produto, cruzado com a região de venda.",
                kicker="MIX DE PRODUTOS",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Região", className="filter-label"),
                            dcc.Dropdown(
                                id="filtro-regiao-produto", options=REGIOES, value="Todas",
                                clearable=False, className="filter-dropdown",
                            ),
                        ],
                        className="filter-group",
                    ),
                ],
                className="filter-bar",
            ),
            html.Div(id="produto-regiao-wrapper", className="chart-card chart-card-full"),
            html.Div(id="ranking-produto-wrapper", className="chart-card chart-card-full"),
        ]
    )


def _fig_barras_empilhadas(df):
    """Faturamento por produto, decomposto por região (barras empilhadas).

    Optei por barras empilhadas em vez de treemap: o treemap do Plotly.js
    não renderizou de forma confiável neste ambiente (nem em um exemplo
    mínimo, isolado do resto da aplicação), então preferi um tipo de
    gráfico com renderização garantida em vez de arriscar uma tela em
    branco em produção.
    """
    top_produtos = (
        df.groupby("produto", as_index=False)["valor_total_vendido"].sum()
        .sort_values("valor_total_vendido", ascending=False).head(10)["produto"]
    )
    dados = df[df["produto"].isin(top_produtos)]
    pivot = dados.pivot_table(index="produto", columns="regiao", values="valor_total_vendido",
                               aggfunc="sum", fill_value=0)
    pivot = pivot.loc[top_produtos.tolist()[::-1]]  # mantém a ordem do ranking, maior no topo

    fig = go.Figure()
    for i, regiao in enumerate(pivot.columns):
        fig.add_trace(
            go.Bar(
                name=regiao, y=pivot.index, x=pivot[regiao], orientation="h",
                marker_color=SERIES_PALETTE[i % len(SERIES_PALETTE)],
                hovertemplate=f"<b>{regiao}</b><br>%{{y}}<br>R$ %{{x:,.2f}}<extra></extra>",
            )
        )
    fig.update_layout(barmode="stack")
    apply_layout(fig, margin=dict(l=10, r=10, t=10, b=10))
    left_align_y_labels(fig, pivot.index)
    return fig


def _fig_ranking(df):
    agrupado = df.groupby("produto", as_index=False).agg(
        quantidade_vendida=("quantidade_vendida", "sum"), valor_total_vendido=("valor_total_vendido", "sum")
    ).sort_values("valor_total_vendido", ascending=True)
    fig = go.Figure(
        go.Bar(
            x=agrupado["valor_total_vendido"], y=agrupado["produto"], orientation="h",
            marker_color=SERIES_PALETTE[3],
            text=[formatar_moeda(v) for v in agrupado["valor_total_vendido"]],
            textposition="outside", textfont=dict(size=11),
        )
    )
    apply_layout(fig, margin=dict(l=10, r=80, t=10, b=10))
    fig.update_xaxes(visible=False)
    pad_range(fig, agrupado["valor_total_vendido"])
    left_align_y_labels(fig, agrupado["produto"])
    return fig


@callback(
    Output("filtro-regiao-produto", "value"),
    Input("botao-limpar-filtros", "n_clicks"),
    prevent_initial_call=True,
)
def limpar_filtro_regiao(n_clicks):
    return "Todas"


@callback(
    Output("produto-regiao-wrapper", "children"),
    Output("ranking-produto-wrapper", "children"),
    Input("filtro-regiao-produto", "value"),
)
def atualizar(regiao):
    df = ds.itens_filtrados("Último semestre", regiao)
    if df.empty:
        vazio = html.Div("Sem dados para esta região.", className="empty-state")
        return vazio, vazio
    grafico_empilhado = chart_card("Faturamento por produto e região (top 10, semestre)", _fig_barras_empilhadas(df), altura="420px")
    ranking = chart_card("Ranking de produtos por faturamento", _fig_ranking(df), altura="360px")
    return grafico_empilhado.children, ranking.children
