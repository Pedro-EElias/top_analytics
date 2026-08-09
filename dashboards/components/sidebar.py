"""Sidebar fixa e escura, com navegação entre páginas registradas via dash.register_page."""
from dash import html, dcc
import dash

NAV_ICONS = {
    "Visão Geral": "bi-grid-1x2-fill",
    "Vendas por Período": "bi-calendar3",
    "Produtos & Regiões": "bi-box-seam",
    "Qualidade dos Dados": "bi-shield-check",
}


def render_sidebar() -> html.Div:
    links = []
    for page in dash.page_registry.values():
        nome = page["name"]
        icone = NAV_ICONS.get(nome, "bi-circle")
        links.append(
            dcc.Link(
                html.Div(
                    [
                        html.I(className=f"bi {icone} nav-icon"),
                        html.Span(nome, className="nav-label"),
                    ],
                    className="nav-item",
                ),
                href=page["path"],
                id={"type": "nav-link", "index": page["path"]},
                className="nav-link-wrapper",
            )
        )

    return html.Div(
        [
            html.Div(
                [
                    html.Div(className="brand-mark"),
                    html.Div(
                        [
                            html.Span("TOP", className="brand-title"),
                            html.Span("ANALYTICS", className="brand-subtitle"),
                        ],
                        className="brand-text",
                    ),
                ],
                className="brand-block",
            ),
            html.Div(links, className="nav-block"),
            html.Div(
                [
                    html.I(className="bi bi-cpu sidebar-illustration"),
                    html.P("Vendas de Eletrônicos", className="sidebar-footnote-title"),
                    html.P("1º Semestre · 2026", className="sidebar-footnote-sub"),
                ],
                className="sidebar-footnote",
            ),
        ],
        className="sidebar",
    )
