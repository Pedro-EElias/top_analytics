import dash
from dash import html, dash_table
import plotly.graph_objects as go

from components.cards import chart_card, kpi_card, formatar_numero
from components.header import render_header
from components.theme import COLORS, SERIES_PALETTE, apply_layout, pad_range
from services import data as ds

dash.register_page(__name__, path="/qualidade-dos-dados", name="Qualidade dos Dados", title="Qualidade dos Dados")


def _fig_por_tabela(df):
    df = df.sort_values("valores_pendentes", ascending=True)
    fig = go.Figure(
        go.Bar(
            x=df["valores_pendentes"], y=df["tabela_origem"], orientation="h",
            marker_color=SERIES_PALETTE[1],
            text=df["valores_pendentes"], textposition="outside", textfont=dict(size=11),
        )
    )
    apply_layout(fig, margin=dict(l=10, r=40, t=10, b=10))
    fig.update_xaxes(visible=False)
    pad_range(fig, df["valores_pendentes"])
    return fig


def _cards_kpi(resumo, detalhes):
    """3 cards de KPI: valores pendentes, tabelas afetadas, registros com pendência."""
    total_pendencias = int(resumo["valores_pendentes"].sum()) if not resumo.empty else 0
    tabelas_afetadas = resumo["tabela_origem"].nunique() if not resumo.empty else 0
    registros_pendentes = detalhes["linha_origem"].nunique() if not detalhes.empty else 0

    return html.Div(
        [
            kpi_card("Valores pendentes", formatar_numero(total_pendencias), icone="bi-exclamation-triangle",
                     destaque=total_pendencias > 0),
            kpi_card("Tabelas afetadas", str(tabelas_afetadas), icone="bi-table"),
            kpi_card("Registros com pendência", formatar_numero(registros_pendentes), icone="bi-list-check"),
        ],
        className="kpi-row kpi-row-3",
    )


def _bloco_grafico(resumo):
    """Gráfico de pendências por tabela, ou uma mensagem de sucesso quando
    não há nenhuma pendência."""
    if resumo.empty:
        return html.Div(
            "Nenhuma pendência de qualidade encontrada — base 100% padronizada.",
            className="empty-state empty-state-success",
        )
    return chart_card("Pendências por tabela de origem", _fig_por_tabela(resumo), altura="260px")


def _colunas_tabela_detalhe():
    """Definição das colunas da tabela de detalhes (nome de exibição + id)."""
    campos = ["tabela_origem", "linha_origem", "registro_id", "campo_pendente", "status_pendencia"]
    return [{"name": campo.replace("_", " ").title(), "id": campo} for campo in campos]


def _tabela_detalhe(detalhes):
    """Tabela paginada com uma linha por (registro, campo pendente), ou
    uma mensagem quando não há nenhum registro pendente."""
    if detalhes.empty:
        conteudo = html.P("Sem registros pendentes. 🎉", className="empty-state-text")
    else:
        conteudo = dash_table.DataTable(
            data=detalhes.to_dict("records"),
            columns=_colunas_tabela_detalhe(),
            page_size=10,
            style_table={"overflowX": "auto"},
            style_header={"backgroundColor": COLORS["page_bg"], "fontWeight": "600", "border": "none",
                           "color": COLORS["muted"], "textTransform": "uppercase", "fontSize": "11px"},
            style_cell={"padding": "10px 14px", "fontFamily": "Inter, sans-serif", "fontSize": "13px",
                        "border": "none", "borderBottom": f"1px solid {COLORS['border']}"},
            style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#FAFBFD"}],
        )
    return html.Div(
        [html.H5("Detalhe de campos pendentes", className="chart-card-title"), conteudo],
        className="chart-card chart-card-full",
    )


def layout():
    """Página "Qualidade dos Dados": KPIs + gráfico por tabela + detalhe
    linha a linha das pendências geradas por src/qualidade.py."""
    resumo = ds.resumo_qualidade_por_tabela()
    detalhes = ds.dados_pendentes()

    return html.Div(
        [
            render_header(
                "Qualidade dos Dados",
                "Auditoria automática gerada por src/qualidade.py a cada execução do pipeline.",
                kicker="GOVERNANÇA",
            ),
            _cards_kpi(resumo, detalhes),
            _bloco_grafico(resumo),
            _tabela_detalhe(detalhes),
        ]
    )
