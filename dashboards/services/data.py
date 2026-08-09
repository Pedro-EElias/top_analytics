"""Camada de acesso a dados do dashboard.

Este módulo é a ÚNICA porta de entrada para o banco analítico gerado pelo
pipeline existente (src/transform_xlsx_to_db.py -> src/analise.py). Ele não
recalcula nada: apenas lê as tabelas já publicadas em um `.sqlite` gerado
por `src/analise.py` e devolve DataFrames prontos para as páginas /
componentes do Dash consumirem.

RESOLUÇÃO DO CAMINHO DO BANCO (nessa ordem de prioridade):
1. Variável de ambiente DASHBOARD_DB_PATH, se definida (caminho exato);
2. <raiz do projeto>/data/resultados/*.sqlite — usado quando esta pasta
   (`dashboard_vendas/`) está DENTRO do projeto `analise_treino/`, lendo o
   banco de dados real que o pipeline gera ali;
3. <dashboard_vendas>/data/resultados/*.sqlite — cópia local, usada quando
   o dashboard roda de forma independente/standalone (fora do projeto).

Como o nome do arquivo `.sqlite` de destino é escolhido livremente por quem
roda `src/analise.py --destino ...`, não fixamos um nome: se houver mais de
um `.sqlite` na pasta candidata, pegamos o mais recente.

Se um dia o pipeline mudar de lugar ou de nome, só este arquivo precisa ser
ajustado — o resto da aplicação não sabe (nem precisa saber) que os dados
vêm de um SQLite.
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent  # pasta dashboard_vendas/


def _mais_recente(pasta: Path) -> Path | None:
    if not pasta.is_dir():
        return None
    candidatos = sorted(pasta.glob("*.sqlite"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidatos[0] if candidatos else None


def _resolver_db_path() -> Path:
    variavel_ambiente = os.environ.get("DASHBOARD_DB_PATH")
    if variavel_ambiente:
        return Path(variavel_ambiente)

    # Caso 1: dashboard_vendas/ está dentro da pasta raiz do projeto
    # (ex.: analise_treino/dashboard_vendas/) — lê o banco real do pipeline,
    # um nível acima.
    projeto_pai = _mais_recente(BASE_DIR.parent / "data" / "resultados")
    if projeto_pai:
        return projeto_pai

    # Caso 2: uso standalone, com a cópia local empacotada junto do dashboard.
    copia_local = _mais_recente(BASE_DIR / "data" / "resultados")
    if copia_local:
        return copia_local

    # Nenhum banco encontrado: devolve o caminho "esperado" só para a
    # mensagem de erro em _ler() ficar clara sobre onde ele deveria estar.
    return BASE_DIR.parent / "data" / "resultados" / "banco_analise.sqlite"


DB_PATH = _resolver_db_path()

# Meses considerados "período mensal" (exclui as janelas agregadas de
# trimestre/semestre definidas em src/analise.py::JANELAS). Não fixamos
# quais meses existem: eles são detectados dinamicamente em
# meses_disponiveis(), então o dashboard se adapta sozinho se o pipeline
# gerar um único mês, um trimestre, o semestre inteiro ou o ano todo.
_PADRAO_PERIODO_MENSAL = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
JANELAS_AGREGADAS = ["Último trimestre", "Último semestre"]

MESES_PT_ABREV = {
    1: "jan.", 2: "fev.", 3: "mar.", 4: "abr.", 5: "maio", 6: "jun.",
    7: "jul.", 8: "ago.", 9: "set.", 10: "out.", 11: "nov.", 12: "dez.",
}


def mes_abreviado(periodo_aaaa_mm: str) -> str:
    """Converte um período 'AAAA-MM' na abreviação em português do mês
    ('jan.', 'fev.', ..., 'dez.'). Se o valor não for um período mensal
    reconhecível (ex.: "Último semestre"), devolve o valor original."""
    try:
        _ano, mes = str(periodo_aaaa_mm).split("-")
        return MESES_PT_ABREV[int(mes)]
    except (ValueError, KeyError):
        return str(periodo_aaaa_mm)


def _ler(tabela: str) -> pd.DataFrame:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Banco analítico não encontrado em {DB_PATH}. "
            "Rode o pipeline (transform_xlsx_to_db.py -> analise.py) primeiro, "
            "ou aponte DASHBOARD_DB_PATH para o arquivo .sqlite correto."
        )
    try:
        with sqlite3.connect(DB_PATH) as conexao:
            return pd.read_sql_query(f"SELECT * FROM {tabela}", conexao)
    except (sqlite3.OperationalError, pd.errors.DatabaseError):
        # Tabela ainda não existe nesta versão do banco (ex.: pipeline mais
        # antigo, ou tabela de pendências que só é criada quando há
        # pendências). O dashboard deve degradar graciosamente, não quebrar.
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Leitores "crus" (uma tabela = uma função). Cacheados em processo porque o
# banco é regenerado por um job externo (pipeline / GitHub Actions), não a
# cada clique do usuário.
# ---------------------------------------------------------------------------

def resumo_geral() -> pd.DataFrame:
    return _ler("eda_resumo_geral")


def vendas_por_regiao() -> pd.DataFrame:
    return _ler("percentual_vendas_regiao")


def vendas_por_funcionario() -> pd.DataFrame:
    return _ler("percentual_vendas_funcionario")


def vendas_por_data() -> pd.DataFrame:
    df = _ler("percentual_vendas_data")
    df["inicio_periodo"] = pd.to_datetime(df["inicio_periodo"])
    df["fim_periodo"] = pd.to_datetime(df["fim_periodo"])
    return df


def itens_por_regiao_data() -> pd.DataFrame:
    df = _ler("itens_por_regiao_data")
    df["inicio_periodo"] = pd.to_datetime(df["inicio_periodo"])
    df["fim_periodo"] = pd.to_datetime(df["fim_periodo"])
    return df


def qualidade_pendencias() -> pd.DataFrame:
    return _ler("qualidade_dados_pendentes")


def dados_pendentes() -> pd.DataFrame:
    return _ler("dados_pendentes")


# ---------------------------------------------------------------------------
# Leitores "de negócio": já vêm no formato que os gráficos consomem.
# Mantêm as páginas livres de lógica de agregação/SQL.
# ---------------------------------------------------------------------------

def kpis_gerais() -> dict:
    linha = resumo_geral().iloc[0]
    total_pendencias = int(qualidade_pendencias()["valores_pendentes"].sum()) if not qualidade_pendencias().empty else 0
    return {
        "faturamento_total": float(linha["valor_total_vendido"]),
        "transacoes": int(linha["transacoes"]),
        "quantidade_vendida": int(linha["quantidade_vendida"]),
        "ticket_medio": float(linha["ticket_medio"]),
        "data_inicial": linha["data_inicial"],
        "data_final": linha["data_final"],
        "total_pendencias": total_pendencias,
    }


def evolucao_mensal() -> pd.DataFrame:
    """Série mensal (exclui trimestre/semestre) ordenada cronologicamente.

    Os meses presentes são detectados a partir dos próprios dados (não são
    fixos), então funciona igual para um pipeline mensal, trimestral,
    semestral ou anual.
    """
    meses = meses_disponiveis()
    df = vendas_por_data()
    mensal = df[df["periodo"].isin(meses)].copy()
    mensal["periodo"] = pd.Categorical(mensal["periodo"], categories=meses, ordered=True)
    return mensal.sort_values("periodo")


def meses_disponiveis() -> list[str]:
    """Períodos mensais (formato 'AAAA-MM') presentes em percentual_vendas_data,
    ordenados cronologicamente — descobertos a partir dos dados, não fixos."""
    df = vendas_por_data()
    if df.empty:
        return []
    return sorted(p for p in df["periodo"].astype(str).unique() if _PADRAO_PERIODO_MENSAL.match(p))


def regioes_disponiveis() -> list[str]:
    return sorted(vendas_por_regiao()["regiao"].dropna().unique().tolist())


def periodos_disponiveis() -> list[str]:
    return meses_disponiveis() + JANELAS_AGREGADAS


def top_vendedores(n: int = 8) -> pd.DataFrame:
    return vendas_por_funcionario().sort_values("valor_total_vendido", ascending=False).head(n)


def itens_filtrados(periodo: str, regiao: str | None = None) -> pd.DataFrame:
    df = itens_por_regiao_data()
    df = df[df["periodo"] == periodo]
    if regiao and regiao != "Todas":
        df = df[df["regiao"] == regiao]
    return df.sort_values("valor_total_vendido", ascending=False)


def resumo_qualidade_por_tabela() -> pd.DataFrame:
    df = qualidade_pendencias()
    if df.empty:
        return df
    return df.groupby("tabela_origem", as_index=False).agg(
        valores_pendentes=("valores_pendentes", "sum"),
        campos_afetados=("campo", "nunique"),
    ).sort_values("valores_pendentes", ascending=False)
