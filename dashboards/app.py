"""Ponto de entrada do dashboard executivo de vendas de eletrônicos.

Este arquivo só monta o "shell" da aplicação (sidebar + área de conteúdo).
A lógica de cada página vive em pages/, os componentes visuais reutilizáveis
em components/, e o acesso aos dados (lidos do SQLite gerado pelo pipeline
existente em src/) fica isolado em services/data.py.
"""
import dash
from dash import Dash, html, dcc, page_container, Input, Output, State, ALL, callback

from components.sidebar import render_sidebar

app = Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css",
    ],
    title="Painel de Vendas · Eletrônicos",
    update_title=None,
    suppress_callback_exceptions=True,  # cada página registra ids próprios (ex.: filtros),
                                         # que não existem nas demais páginas ao carregar
)
server = app.server  # exposto para deploy (gunicorn, etc.)

app.layout = html.Div(
    [
        dcc.Location(id="url", refresh=False),
        render_sidebar(),
        html.Div(page_container, className="content-area"),
    ],
    className="app-shell",
)


@callback(
    Output({"type": "nav-link", "index": ALL}, "className"),
    Input("url", "pathname"),
    State({"type": "nav-link", "index": ALL}, "id"),
)
def marcar_link_ativo(caminho_atual, ids):
    """Destaca na sidebar o item correspondente à página aberta."""
    return [
        "nav-link-wrapper active" if item["index"] == caminho_atual else "nav-link-wrapper"
        for item in ids
    ]


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
