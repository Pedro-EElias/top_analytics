"""Padronização e auditoria de qualidade dos dados de vendas.

Este módulo tem duas responsabilidades:
1. `padronizar()` — normaliza tipos e formatos de um DataFrame bruto
   (IDs, textos, valores financeiros, percentuais, inteiros, datas).
2. `auditoria_pendencias()` / `marcar_pendencias()` — identificam campos
   obrigatórios ausentes, sem alterar os dados em si.
"""
from collections.abc import Iterable

import pandas as pd

IDS = {"loja_id", "vendedor_id", "produto_id", "venda_id"}
TEXTOS = {"nome_loja", "cidade", "regiao", "nome_vendedor", "categoria", "modelo", "produto"}
FINANCEIROS = {
    "preco_unitario", "custo_unitario", "valor_total", "custo_total",
    "margem_unitaria", "valor_total_vendido", "ticket_medio",
    "custo_total_alocacao", "lucro_total",
}
INTEIROS = {"quantidade", "numero_de_vendas", "quantidade_vendida"}
PERCENTUAIS = {"margem_%"}

_FORMATOS_DATA_CONHECIDOS = (
    "%Y-%m-%d",  # formato "de fábrica" do pipeline (ISO, ano primeiro) — sem ambiguidade
    "%Y/%m/%d",  # variante bagunçada, mas ainda ano primeiro — sem ambiguidade
    "%d/%m/%Y",  # variante bagunçada, dia primeiro
    "%d-%m-%Y",  # variante bagunçada, dia primeiro
    "%d.%m.%Y",  # variante bagunçada, dia primeiro
)


# ---------------------------------------------------------------------------
# Conversores de baixo nível (texto -> texto limpo / número / data)
# ---------------------------------------------------------------------------

def _texto(serie: pd.Series, title: bool = False) -> pd.Series:
    """Normaliza texto: colapsa espaços repetidos, tira espaço das pontas
    e transforma string vazia em nulo. Se `title=True`, também aplica
    Title Case (usado em nomes, categorias, etc.)."""
    resultado = serie.astype("string").str.replace(r"\s+", " ", regex=True).str.strip()
    resultado = resultado.mask(resultado.eq(""), pd.NA)
    return resultado.str.title() if title else resultado


def _numero(serie: pd.Series) -> pd.Series:
    """Converte texto para número, aceitando formatos BR e US misturados
    (ex.: "1234.56", "1.234,56", "R$ 1.234,56"). Quando o texto tem tanto
    "," quanto ".", o símbolo que aparece por último é tratado como
    separador decimal; o outro é tratado como separador de milhar."""
    texto = _texto(serie).str.replace(r"[^0-9,.-]", "", regex=True)
    tem_ambos = texto.str.contains(",", na=False) & texto.str.contains(r"\.", na=False)
    virgula_e_decimal = tem_ambos & texto.str.rfind(",").gt(texto.str.rfind("."))

    texto = texto.where(
        ~virgula_e_decimal,
        texto.str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
    )
    texto = texto.where(
        ~(tem_ambos & ~virgula_e_decimal),
        texto.str.replace(",", "", regex=False),
    )
    texto = texto.where(
        ~(~tem_ambos & texto.str.contains(",", na=False)),
        texto.str.replace(",", ".", regex=False),
    )
    return pd.to_numeric(texto, errors="coerce")


def _data(serie: pd.Series) -> pd.Series:
    """Converte texto para data, sem ambiguidade de dia/mês.

    Em vez de deixar o pandas "adivinhar" o formato (via dayfirst=True ou
    inferência automática), testamos explicitamente, em ordem, cada um dos
    formatos que realmente aparecem no pipeline: o formato ISO "de fábrica"
    (AAAA-MM-DD) e as quatro variantes bagunçadas que
    gerar_planilha.py::_bagunca_data produz de propósito para testar o
    cenário de erro de formatação. Um valor só fica nulo se não bater com
    NENHUM desses formatos conhecidos.

    Bug histórico corrigido aqui: `pd.to_datetime(..., dayfirst=True)` —
    mesmo aplicado a uma data já em formato ISO ("2026-06-12") ou
    ano-primeiro ("2026/06/12") — trocava dia e mês (ou zerava a data)
    porque o pandas aplica esse parâmetro nos dois últimos componentes da
    string, mesmo quando o primeiro componente já deixa claro que é o ano.
    Isso corrompia ou apagava a data em ~97% das vendas no banco de exemplo.
    """
    texto = _texto(serie)
    resultado = pd.Series(pd.NaT, index=texto.index, dtype="datetime64[ns]")
    pendente = texto.notna()
    for formato in _FORMATOS_DATA_CONHECIDOS:
        if not pendente.any():
            break
        tentativa = pd.to_datetime(texto[pendente], format=formato, errors="coerce")
        acertou = tentativa.notna()
        resultado.loc[tentativa.index[acertou]] = tentativa[acertou]
        pendente.loc[tentativa.index[acertou]] = False
    return resultado


# ---------------------------------------------------------------------------
# padronizar() — cada etapa isolada em uma função nomeada, na mesma ordem
# da versão original. Nenhuma fórmula ou ordem de operação foi alterada
# aqui: é puramente uma reorganização estrutural (ver tests/test_qualidade.py
# e tests/test_regressao_pipeline.py, que travam esse comportamento).
# ---------------------------------------------------------------------------

def _padronizar_identificadores(df: pd.DataFrame) -> pd.DataFrame:
    """Uppercase nos IDs (loja_id, vendedor_id, produto_id, venda_id)."""
    for coluna in set(df.columns) & IDS:
        df[coluna] = _texto(df[coluna]).str.upper()
    return df


def _padronizar_textos(df: pd.DataFrame) -> pd.DataFrame:
    """Title Case nos campos de texto livre (nome, cidade, categoria...)."""
    for coluna in set(df.columns) & TEXTOS:
        df[coluna] = _texto(df[coluna], title=True)
    return df


def _padronizar_estado(df: pd.DataFrame) -> pd.DataFrame:
    """Uppercase na sigla do estado (ex.: "sp" -> "SP")."""
    if "estado" in df:
        df["estado"] = _texto(df["estado"]).str.upper()
    return df


def _padronizar_financeiros(df: pd.DataFrame) -> pd.DataFrame:
    """Converte valores monetários e arredonda para 2 casas decimais."""
    for coluna in set(df.columns) & FINANCEIROS:
        df[coluna] = _numero(df[coluna]).round(2)
    return df


def _padronizar_percentuais(df: pd.DataFrame) -> pd.DataFrame:
    """Converte percentuais e arredonda para 4 casas decimais."""
    for coluna in set(df.columns) & PERCENTUAIS:
        df[coluna] = _numero(df[coluna]).round(4)
    return df


def _padronizar_inteiros(df: pd.DataFrame) -> pd.DataFrame:
    """Converte para inteiro (Int64); valores não inteiros (ex.: "3.5")
    viram nulo em vez de serem truncados silenciosamente."""
    for coluna in set(df.columns) & INTEIROS:
        numero = _numero(df[coluna])
        df[coluna] = numero.where(numero.isna() | numero.mod(1).eq(0)).astype("Int64")
    return df


def _padronizar_data(df: pd.DataFrame) -> pd.DataFrame:
    """Converte a coluna 'data', quando presente (ver `_data`)."""
    if "data" in df:
        df["data"] = _data(df["data"])
    return df


def padronizar(df: pd.DataFrame) -> pd.DataFrame:
    """Padroniza tipos e formatos de um DataFrame bruto de vendas/cadastro.

    Aplica, nesta ordem exata:
    1. Uppercase nos identificadores (IDs)
    2. Title Case nos textos livres
    3. Uppercase na sigla do estado
    4. Valores financeiros, arredondados para 2 casas
    5. Percentuais, arredondados para 4 casas
    6. Inteiros (Int64, nulo se não for um inteiro exato)
    7. Data (ver `_data`)

    Colunas que não existem em `df` são simplesmente ignoradas em cada
    etapa — a função funciona tanto para a tabela de Vendas quanto para
    Vendedores, Produtos, etc., cada uma com seu próprio subconjunto de
    colunas.
    """
    resultado = df.copy()
    resultado = _padronizar_identificadores(resultado)
    resultado = _padronizar_textos(resultado)
    resultado = _padronizar_estado(resultado)
    resultado = _padronizar_financeiros(resultado)
    resultado = _padronizar_percentuais(resultado)
    resultado = _padronizar_inteiros(resultado)
    resultado = _padronizar_data(resultado)
    return resultado


# ---------------------------------------------------------------------------
# Auditoria de pendências (campos obrigatórios ausentes)
# ---------------------------------------------------------------------------

def _pendencia_de_campo(tabela: str, campo: str, serie: pd.Series, total_linhas: int) -> dict | None:
    """Calcula a pendência de UM campo; devolve None se não há pendência
    nenhuma (para o campo não aparecer no relatório)."""
    pendentes = int(serie.isna().sum())
    if not pendentes:
        return None
    pct_pendente = round(pendentes / total_linhas * 100, 2) if total_linhas else 0.0
    return {
        "tabela_origem": tabela,
        "campo": campo,
        "valores_pendentes": pendentes,
        "pct_pendente": pct_pendente,
    }


def auditoria_pendencias(tabela: str, df: pd.DataFrame, obrigatorias: Iterable[str] | None = None) -> pd.DataFrame:
    """Conta quantos valores estão faltando em cada campo obrigatório.

    Por padrão (`obrigatorias=None`), audita TODAS as colunas de `df`.
    Devolve uma linha por campo com pendência — campos sem nenhum valor
    faltando não aparecem no resultado.
    """
    campos = list(obrigatorias) if obrigatorias else list(df.columns)
    linhas = []
    for campo in campos:
        if campo not in df:
            continue
        pendencia = _pendencia_de_campo(tabela, campo, df[campo], len(df))
        if pendencia is not None:
            linhas.append(pendencia)
    colunas = ["tabela_origem", "campo", "valores_pendentes", "pct_pendente"]
    return pd.DataFrame(linhas, columns=colunas)


def _identificador_de_registro(df: pd.DataFrame) -> pd.Series:
    """Identificador de cada linha para uso no relatório de pendências.

    Usa o primeiro ID disponível (venda_id, vendedor_id, produto_id,
    loja_id, nessa ordem de prioridade) e cai para o número da linha
    (1-based) quando nenhum identificador está preenchido naquela linha."""
    identificadores = [campo for campo in ("venda_id", "vendedor_id", "produto_id", "loja_id") if campo in df]
    if identificadores:
        registro = df[identificadores].bfill(axis=1).iloc[:, 0]
    else:
        registro = pd.Series(pd.NA, index=df.index)
    numero_da_linha = pd.Series((df.index + 1).astype(str), index=df.index)
    return registro.fillna(numero_da_linha).astype("string")


def _construir_detalhes(tabela: str, linha_origem: pd.Series, registro_id: pd.Series, faltas: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por (registro, campo faltando) — formato longo, pronto
    para virar tabela/gráfico de auditoria."""
    detalhes = (
        faltas.assign(linha_origem=linha_origem, registro_id=registro_id)
        .melt(id_vars=["linha_origem", "registro_id"], var_name="campo_pendente", value_name="pendente")
        .query("pendente")
        .drop(columns="pendente")
    )
    detalhes.insert(0, "tabela_origem", tabela)
    detalhes["status_pendencia"] = "Pendente"
    return detalhes[["tabela_origem", "linha_origem", "registro_id", "campo_pendente", "status_pendencia"]]


def marcar_pendencias(tabela: str, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cria sinalização por registro e uma tabela detalhada de campos ausentes.

    Não substitui nulos por texto em campos numéricos/datas; isso preserva
    seus tipos para análise e identifica o problema só nas colunas de
    controle (`campos_pendentes`, `status_pendencia`) e na tabela de
    detalhes devolvida junto.

    Devolve (df_marcado, detalhes):
    - df_marcado: o `df` original + linha_origem, campos_pendentes, status_pendencia
    - detalhes: uma linha por (registro, campo faltando)
    """
    resultado = df.copy().reset_index(drop=True)
    registro = _identificador_de_registro(resultado)

    colunas_de_controle = {"linha_origem", "status_pendencia", "campos_pendentes"}
    campos_auditaveis = [coluna for coluna in resultado.columns if coluna not in colunas_de_controle]
    faltas = resultado[campos_auditaveis].isna()

    resultado.insert(0, "linha_origem", resultado.index + 1)
    resultado["campos_pendentes"] = (
        faltas.apply(lambda linha: ", ".join(linha.index[linha]), axis=1)
        .mask(~faltas.any(axis=1), pd.NA)
    )
    resultado["status_pendencia"] = resultado["campos_pendentes"].notna().map({True: "Pendente", False: "Completo"})

    detalhes = _construir_detalhes(tabela, resultado["linha_origem"], registro, faltas)
    return resultado, detalhes
