"""Tokens visuais compartilhados entre assets/style.css e os gráficos Plotly.

Manter cor/tipografia num único lugar evita que os gráficos "destoem" do
resto da interface quando a paleta mudar.
"""

COLORS = {
    "sidebar_from": "#0B1E3F",
    "sidebar_to": "#132A55",
    "page_bg": "#EEF1F7",
    "card_bg": "#FFFFFF",
    "primary": "#1E3A8A",      # azul principal
    "primary_light": "#3B5FCB",
    "accent": "#EC4899",       # rosa de destaque
    "accent_purple": "#7C5CFC",
    "muted": "#5B6B8C",        # cinza-azulado para textos secundários
    "border": "#E2E6F0",
    "success": "#16A34A",
    "warning": "#F59E0B",
    "text_dark": "#111827",
    "text_light": "#FFFFFF",
}

# Paleta categórica usada em séries de gráficos (regiões, produtos, etc.)
SERIES_PALETTE = ["#1E3A8A", "#EC4899", "#7C5CFC", "#22B8CF", "#F59E0B", "#16A34A", "#EF4444"]

FONT_FAMILY = "'Sora', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif"

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family=FONT_FAMILY, color=COLORS["text_dark"], size=13),
    margin=dict(l=10, r=10, t=10, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=12)),
    hoverlabel=dict(bgcolor="white", font_size=12, font_family=FONT_FAMILY, bordercolor=COLORS["border"]),
)


def apply_layout(fig, **overrides):
    """Aplica o layout padrão do dashboard a uma figura Plotly."""
    layout = {**PLOTLY_LAYOUT, **overrides}
    fig.update_layout(**layout)
    fig.update_xaxes(showgrid=False, zeroline=False, showline=True, linecolor=COLORS["border"])
    fig.update_yaxes(showgrid=True, gridcolor=COLORS["border"], zeroline=False)
    return fig


def pad_range(fig, values, axis="x", factor=1.30):
    """Estende o range de um eixo para que rótulos 'outside' não sejam cortados.

    Usado em barras horizontais com texto fora da barra: sem isso, o Plotly
    corta o texto quando ele ultrapassa a área de plotagem.
    """
    maximo = max(values) if len(values) else 0
    novo_limite = maximo * factor if maximo > 0 else 1
    if axis == "x":
        fig.update_xaxes(range=[0, novo_limite])
    else:
        fig.update_yaxes(range=[0, novo_limite])
    fig.update_traces(cliponaxis=False)
    return fig


def left_align_y_labels(fig, categorias, font_size=12.5):
    """Alinha os rótulos do eixo Y (nomes/produtos) à esquerda da margem.

    Por padrão, o Plotly "cola" o rótulo do eixo Y rente à barra (alinhado
    à direita) — então nomes curtos ficam soltos, longe da margem, e nomes
    longos ficam grudados na barra. Isso substitui os tick labels nativos
    por anotações fixas na borda esquerda da figura, todas começando na
    mesma posição, independentemente do tamanho do texto.

    Detalhe técnico: coordenadas `xref="paper"` no Plotly são relativas à
    ÁREA DE PLOTAGEM (dentro dos eixos), não à figura inteira — ou seja,
    x=0 cai exatamente na borda esquerda do eixo, não na borda esquerda da
    margem. Por isso usamos `xshift` (deslocamento em PIXELS, que não
    depende do tamanho responsivo do gráfico) para empurrar o texto para
    dentro da margem reservada por `margin.l`.
    """
    categorias = list(categorias)
    fig.update_yaxes(showticklabels=False, ticks="")

    # Margem esquerda proporcional ao maior nome, com folga generosa: a
    # largura real do texto depende da fonte que o navegador efetivamente
    # carrega (com fallback, pode ser mais larga que o esperado), então é
    # mais seguro superestimar do que arriscar o texto invadir a barra.
    maior_nome = max((len(str(c)) for c in categorias), default=10)
    margem_esquerda = min(max(maior_nome * 8.0 + 28, 110), 260)
    fig.update_layout(margin=dict(l=int(margem_esquerda)))

    anotacoes_existentes = list(fig.layout.annotations) if fig.layout.annotations else []
    novas_anotacoes = [
        dict(
            xref="paper", x=0, xanchor="left", xshift=-(margem_esquerda - 18),
            yref="y", y=categoria, yanchor="middle",
            text=str(categoria), showarrow=False, align="left",
            font=dict(size=font_size, color=COLORS["text_dark"]),
        )
        for categoria in categorias
    ]
    fig.update_layout(annotations=anotacoes_existentes + novas_anotacoes)
    return fig
