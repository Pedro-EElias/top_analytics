"""Header da área de conteúdo: título da página + ações rápidas."""
from dash import html


def render_header(titulo: str, subtitulo: str, kicker: str = "PAINEL") -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.Span(kicker, className="page-kicker"),
                    html.H1(
                        [html.Span(titulo.split(" ")[0] + " ", className="page-title-strong"),
                         html.Span(" ".join(titulo.split(" ")[1:]), className="page-title-light")],
                        className="page-title",
                    ),
                    html.P(subtitulo, className="page-subtitle"),
                ],
                className="header-text",
            ),
            html.Div(
                [
                    html.Button(html.I(className="bi bi-info-circle"), className="icon-button", title="Sobre este painel"),
                    html.Button(
                        [html.I(className="bi bi-arrow-counterclockwise me-2"), "Limpar filtros"],
                        id="botao-limpar-filtros",
                        className="reset-button",
                    ),
                ],
                className="header-actions",
            ),
        ],
        className="content-header",
    )
