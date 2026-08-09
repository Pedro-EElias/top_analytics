"""Gera uma camada analítica SQLite para vendas de eletrônicos.

Lê o banco bruto (tabelas Lojas/Vendedores/Produtos/Vendas), padroniza e
audita qualidade (ver `qualidade.py`), e publica tabelas analíticas prontas
para consumo (dashboard, Power BI, etc.) num segundo banco SQLite.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

import pandas as pd

from qualidade import auditoria_pendencias, marcar_pendencias, padronizar
from schemas import VendasSchema, VendedoresSchema

JANELAS = {
    "2026-01": ("2026-01-01", "2026-01-31"),
    "2026-02": ("2026-02-01", "2026-02-28"),
    "2026-03": ("2026-03-01", "2026-03-31"),
    "2026-04": ("2026-04-01", "2026-04-30"),
    "2026-05": ("2026-05-01", "2026-05-31"),
    "2026-06": ("2026-06-01", "2026-06-30"),
    "Último trimestre": ("2026-04-01", "2026-06-30"),
    "Último semestre": ("2026-01-01", "2026-06-30"),
}


# ---------------------------------------------------------------------------
# percentual() — mantida MATEMATICAMENTE IDÊNTICA à versão original; a
# única mudança aqui é dar nome a cada etapa (agregar -> totais de
# referência -> percentuais + arredondamento). Nenhuma fórmula, ordem de
# operação ou arredondamento foi alterado — ver tests/test_analise.py, que
# trava os valores exatos com casos escolhidos a dedo para não fechar em
# números redondos.
# ---------------------------------------------------------------------------

def _agregar(df: pd.DataFrame, grupo: list[str]) -> pd.DataFrame:
    """Agrega transações (contagem única de venda_id), quantidade (soma) e
    faturamento (soma). Se `grupo` for vazio, agrega o `df` inteiro em uma
    única linha; senão, agrupa por `grupo`."""
    agregacoes = dict(transacoes=("venda_id", "nunique"),
                       quantidade_vendida=("quantidade", "sum"),
                       valor_total_vendido=("valor_total", "sum"))
    if grupo:
        return df.groupby(grupo, as_index=False).agg(**agregacoes)
    return pd.DataFrame([{nome: df[coluna].nunique() if func == "nunique" else df[coluna].sum()
                           for nome, (coluna, func) in agregacoes.items()}])


def _totais_de_referencia(df: pd.DataFrame, referencia: pd.DataFrame | None) -> dict:
    """Totais usados como denominador dos percentuais. Por padrão
    (`referencia=None`), são os totais do próprio `df` — os percentuais
    somam 100% entre os grupos. Passar uma `referencia` diferente (ex.: o
    semestre inteiro) permite calcular "que fração do total geral este
    mês representa", como em `por_periodo`."""
    base = df if referencia is None else referencia
    return {"transacoes": base["venda_id"].nunique(),
            "quantidade_vendida": base["quantidade"].sum(),
            "valor_total_vendido": base["valor_total"].sum()}


def _adicionar_percentuais(resultado: pd.DataFrame, totais: dict) -> pd.DataFrame:
    """Calcula pct_transacoes / pct_quantidade / pct_faturamento a partir
    dos totais de referência, e arredonda os valores para exibição."""
    resultado["pct_transacoes"] = resultado["transacoes"].div(totais["transacoes"]).mul(100)
    resultado["pct_quantidade"] = resultado["quantidade_vendida"].div(totais["quantidade_vendida"]).mul(100)
    resultado["pct_faturamento"] = resultado["valor_total_vendido"].div(totais["valor_total_vendido"]).mul(100)
    return resultado.round({"valor_total_vendido": 2, "pct_transacoes": 2,
                             "pct_quantidade": 2, "pct_faturamento": 2})


def percentual(df: pd.DataFrame, grupo: list[str], referencia: pd.DataFrame | None = None) -> pd.DataFrame:
    """Agrupa vendas e calcula participações por quantidade e faturamento.

    `grupo`: colunas para agrupar (ex.: ["regiao"]); lista vazia agrega
    tudo em uma única linha.
    `referencia`: DataFrame usado para calcular o total (denominador dos
    percentuais) — ver `_totais_de_referencia`.
    """
    resultado = _agregar(df, grupo)
    totais = _totais_de_referencia(df, referencia)
    return _adicionar_percentuais(resultado, totais)


def por_periodo(vendas: pd.DataFrame, dimensoes: list[str], referencia: pd.DataFrame | None = None) -> pd.DataFrame:
    """Roda `percentual()` uma vez por janela de tempo (ver `JANELAS`) e
    empilha o resultado, com o nome/início/fim do período nas 3 primeiras
    colunas."""
    partes = []
    for periodo, (inicio, fim) in JANELAS.items():
        fatia = vendas.loc[vendas["data"].between(inicio, fim)].copy()
        tabela = percentual(fatia, dimensoes, referencia)
        tabela.insert(0, "periodo", periodo)
        tabela.insert(1, "inicio_periodo", pd.Timestamp(inicio))
        tabela.insert(2, "fim_periodo", pd.Timestamp(fim))
        partes.append(tabela)
    return pd.concat(partes, ignore_index=True)


# ---------------------------------------------------------------------------
# main() — dividida em etapas nomeadas, na mesma ordem exata da versão
# original (isso importa: a auditoria de "nome_vendedor" só faz sentido
# DEPOIS do merge, por exemplo). Ver tests/test_regressao_pipeline.py, que
# roda main() de ponta a ponta e compara com o baseline congelado.
# ---------------------------------------------------------------------------

def _copiar_banco_bruto(origem: Path, destino: Path) -> None:
    """O banco analítico começa como uma cópia do bruto (Lojas, Produtos,
    etc. ficam disponíveis nele sem precisar reprocessar); as tabelas
    analíticas são adicionadas por cima depois, em `_salvar_tabelas`."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origem, destino)


def _carregar_e_padronizar(origem: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lê Vendas e Vendedores do banco bruto e aplica `padronizar()` (ver qualidade.py)."""
    with sqlite3.connect(origem) as conexao:
        vendas = padronizar(pd.read_sql_query("SELECT * FROM Vendas", conexao))
        vendedores = padronizar(pd.read_sql_query("SELECT * FROM Vendedores", conexao))
    return vendas, vendedores


def _validar_schemas(vendas: pd.DataFrame, vendedores: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Valida tipos/domínios com Pandera (ver schemas.py); lança exceção
    se algo estiver fora do esperado (ex.: quantidade negativa)."""
    vendas = VendasSchema.validate(vendas)
    vendedores = VendedoresSchema.validate(vendedores)
    return vendas, vendedores


def _auditar_e_enriquecer(vendas: pd.DataFrame, vendedores: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Audita pendências de Vendas e Vendedores separadamente, traz o nome
    do vendedor para dentro de Vendas (merge), e audita de novo só o
    campo novo (`nome_vendedor`) — um vendedor_id "órfão" (sem
    correspondência em Vendedores) vira uma pendência aqui, mesmo que a
    linha de Vendas original estivesse completa."""
    pendencias = pd.concat([
        auditoria_pendencias("Vendas", vendas),
        auditoria_pendencias("Vendedores", vendedores),
    ], ignore_index=True)

    vendas = vendas.merge(vendedores[["vendedor_id", "nome_vendedor"]], on="vendedor_id",
                           how="left", validate="many_to_one")

    pendencias = pd.concat([
        pendencias,
        auditoria_pendencias("Vendas", vendas, ["nome_vendedor"]),
    ], ignore_index=True)

    return vendas, pendencias


def _resumo_geral(vendas: pd.DataFrame) -> pd.DataFrame:
    """Uma linha com os totais gerais do período inteiro (sem filtro de
    data nem agrupamento) — usada nos cards de KPI do dashboard."""
    return pd.DataFrame([{
        "data_inicial": vendas["data"].min(),
        "data_final": vendas["data"].max(),
        "transacoes": vendas["venda_id"].nunique(),
        "quantidade_vendida": vendas["quantidade"].sum(),
        "valor_total_vendido": vendas["valor_total"].sum(),
        "ticket_medio": vendas["valor_total"].sum() / vendas["venda_id"].nunique(),
    }])


def _montar_tabelas_finais(vendas: pd.DataFrame, vendedores: pd.DataFrame, pendencias: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Monta o dicionário {nome_da_tabela: DataFrame} que será publicado
    no banco analítico — inclui as agregações (`percentual`/`por_periodo`)
    e as tabelas de auditoria (`marcar_pendencias`)."""
    vendas_padronizadas, detalhes_vendas = marcar_pendencias("Vendas", vendas)
    vendedores_padronizados, detalhes_vendedores = marcar_pendencias("Vendedores", vendedores)
    detalhes_pendentes = pd.concat([detalhes_vendas, detalhes_vendedores], ignore_index=True)

    return {
        "eda_resumo_geral": _resumo_geral(vendas),
        "percentual_vendas_regiao": percentual(vendas, ["regiao"]),
        "percentual_vendas_funcionario": percentual(vendas, ["vendedor_id", "nome_vendedor", "regiao"]),
        "percentual_vendas_data": por_periodo(vendas, [], referencia=vendas),
        "itens_por_regiao_data": por_periodo(vendas, ["regiao", "produto_id", "produto"]),
        "qualidade_dados_pendentes": pendencias,
        "dados_pendentes": detalhes_pendentes,
        "vendas_padronizadas": vendas_padronizadas,
        "vendedores_padronizados": vendedores_padronizados,
    }


def _salvar_tabelas(tabelas: dict[str, pd.DataFrame], destino: Path) -> None:
    """Publica cada tabela no banco analítico e cria os índices usados
    pelos filtros mais comuns do dashboard (período+região, região)."""
    with sqlite3.connect(destino) as conexao:
        for nome, tabela in tabelas.items():
            tabela.to_sql(nome, conexao, if_exists="replace", index=False)
        conexao.execute("CREATE INDEX IF NOT EXISTS idx_itens_periodo ON itens_por_regiao_data(periodo, regiao)")
        conexao.execute("CREATE INDEX IF NOT EXISTS idx_funcionario_regiao ON percentual_vendas_funcionario(regiao)")


def main(origem: Path, destino: Path) -> None:
    """Roda o pipeline completo: origem (banco bruto) -> destino (banco analítico)."""
    _copiar_banco_bruto(origem, destino)

    vendas, vendedores = _carregar_e_padronizar(origem)
    vendas, vendedores = _validar_schemas(vendas, vendedores)
    vendas, pendencias = _auditar_e_enriquecer(vendas, vendedores)

    tabelas = _montar_tabelas_finais(vendas, vendedores, pendencias)
    _salvar_tabelas(tabelas, destino)

    print(f"Análise concluída: {destino}")
    print(f"{vendas['venda_id'].nunique()} transações | R$ {vendas['valor_total'].sum():,.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--origem", type=Path, required=True, help="Banco SQLite de origem")
    parser.add_argument("--destino", type=Path, required=True, help="Banco SQLite analítico")
    args = parser.parse_args()
    try:
        main(args.origem, args.destino)
    except Exception as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        raise
