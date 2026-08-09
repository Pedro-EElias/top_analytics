"""Componentes de card reutilizáveis: KPI e moldura de gráfico."""
from dash import html, dcc


def formatar_moeda(valor: float) -> str:
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "§").replace(".", ",").replace("§", ".")
    return f"R$ {texto}"


def formatar_numero(valor: float) -> str:
    if valor >= 1_000_000:
        return f"{valor / 1_000_000:.1f}M".replace(".", ",")
    if valor >= 1_000:
        return f"{valor / 1_000:.1f}K".replace(".", ",")
    return f"{valor:,.0f}".replace(",", ".")


def kpi_card(titulo: str, valor: str, delta: str | None = None, delta_positivo: bool = True,
             icone: str = "bi-graph-up", destaque: bool = False) -> html.Div:
    classes = "kpi-card kpi-card-highlight" if destaque else "kpi-card"
    filhos = [
        html.Div(html.I(className=f"bi {icone}"), className="kpi-icon"),
        html.P(titulo, className="kpi-title"),
        html.H3(valor, className="kpi-value"),
    ]
    if delta:
        cor = "kpi-delta-up" if delta_positivo else "kpi-delta-down"
        seta = "bi-arrow-up-short" if delta_positivo else "bi-arrow-down-short"
        filhos.append(html.Div([html.I(className=f"bi {seta}"), html.Span(delta)], className=f"kpi-delta {cor}"))
    return html.Div(filhos, className=classes)


def chart_card(titulo: str, grafico, subtitulo: str | None = None, altura: str | None = None,
                controles=None, card_id: str | None = None) -> html.Div:
    header_children = [html.H5(titulo, className="chart-card-title")]
    if controles is not None:
        header_children.append(html.Div(controles, className="chart-card-controls"))
    body = [html.Div(header_children, className="chart-card-header")]
    if subtitulo:
        body.append(html.P(subtitulo, className="chart-card-subtitle"))
    body.append(dcc.Graph(figure=grafico, config={"displayModeBar": False}, style={"height": altura or "320px"}))
    kwargs = {"className": "chart-card"}
    if card_id:
        kwargs["id"] = card_id
    return html.Div(body, **kwargs)
