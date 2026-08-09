"""Teste de regressão de ponta a ponta (Teste 1 e Teste 5 do plano de testes).

Roda o pipeline completo (`analise.main`) contra o mesmo banco de origem
já versionado no repositório e compara, TABELA POR TABELA e SEM
TOLERÂNCIA NUMÉRICA, com o resultado congelado em
`tests/fixtures/baseline_analise.sqlite`.

Esse baseline foi gerado already com a correção do bug de datas em
`qualidade.py::_data` (ver commit que introduziu esses testes) — ou seja,
ele representa o comportamento CORRETO e validado, não um "estado antigo
qualquer". Qualquer refatoração futura (conservadora ou não) só pode ser
considerada seguro se este teste continuar passando.

Se um dia uma mudança de comportamento for intencional (uma correção de
bug, uma nova regra de negócio), este baseline precisa ser
deliberadamente regenerado — nunca "consertado" só para o teste passar.
"""
import sqlite3

import pandas as pd
import pytest

import analise
from conftest import BASELINE_ANALISE, DADOS_ORIGEM

TABELAS_ANALITICAS = [
    "eda_resumo_geral",
    "percentual_vendas_regiao",
    "percentual_vendas_funcionario",
    "percentual_vendas_data",
    "itens_por_regiao_data",
    "qualidade_dados_pendentes",
    "dados_pendentes",
    "vendas_padronizadas",
    "vendedores_padronizados",
]


@pytest.fixture(scope="module")
def banco_gerado(tmp_path_factory):
    """Roda o pipeline uma única vez para todos os testes deste arquivo."""
    if not DADOS_ORIGEM.exists():
        pytest.skip(f"Banco de origem não encontrado em {DADOS_ORIGEM}")
    destino = tmp_path_factory.mktemp("regressao") / "saida.sqlite"
    analise.main(DADOS_ORIGEM, destino)
    return destino


def _ler_tabela(caminho_banco, tabela) -> pd.DataFrame:
    with sqlite3.connect(caminho_banco) as conexao:
        return pd.read_sql_query(f"SELECT * FROM {tabela}", conexao)


@pytest.mark.parametrize("tabela", TABELAS_ANALITICAS)
def test_tabela_identica_ao_baseline(banco_gerado, tabela):
    if not BASELINE_ANALISE.exists():
        pytest.skip(f"Baseline não encontrado em {BASELINE_ANALISE}")

    atual = _ler_tabela(banco_gerado, tabela)
    esperado = _ler_tabela(BASELINE_ANALISE, tabela)

    assert list(atual.columns) == list(esperado.columns), (
        f"Colunas de '{tabela}' mudaram.\nAtual: {list(atual.columns)}\n"
        f"Esperado: {list(esperado.columns)}"
    )
    assert len(atual) == len(esperado), (
        f"'{tabela}' tem {len(atual)} linhas, esperado {len(esperado)} "
        f"(baseline: {BASELINE_ANALISE.name})"
    )
    # dtypes podem divergir de forma inofensiva ao ir e voltar do SQLite
    # (ex.: Int64 nullable vira int64/float64 conforme haja nulos ou não);
    # comparamos os valores já alinhados a um dtype comum por coluna.
    pd.testing.assert_frame_equal(
        atual.reset_index(drop=True),
        esperado.reset_index(drop=True),
        check_dtype=False,
        check_exact=True,
    )


def test_totais_gerais_consistentes(banco_gerado):
    """Sanity check independente do baseline: o resumo geral bate com a
    soma dos períodos mensais — se um dia voltar a haver perda de linhas
    por data mal interpretada, esse teste falha mesmo sem depender do
    arquivo de baseline."""
    resumo = _ler_tabela(banco_gerado, "eda_resumo_geral").iloc[0]
    mensal = _ler_tabela(banco_gerado, "percentual_vendas_data")
    meses = mensal[mensal["periodo"].str.match(r"^\d{4}-\d{2}$")]

    assert meses["transacoes"].sum() == resumo["transacoes"]
    assert meses["quantidade_vendida"].sum() == resumo["quantidade_vendida"]
    assert meses["valor_total_vendido"].sum() == pytest.approx(resumo["valor_total_vendido"])


def test_nenhuma_data_de_venda_perdida(banco_gerado):
    """Sanity check dedicado ao bug corrigido: nenhuma venda deve ficar
    sem data depois da padronização, já que o banco de origem sempre
    preenche esse campo."""
    vendas = _ler_tabela(banco_gerado, "vendas_padronizadas")
    assert vendas["data"].notna().all(), (
        f"{vendas['data'].isna().sum()} vendas ficaram sem data após padronizar() "
        "— isso é sintoma do bug de dayfirst= corrigido em qualidade.py::_data."
    )
