"""Importa Excel, padroniza campos e publica um SQLite auditável."""
import argparse
import sqlite3

import pandas as pd

from qualidade import auditoria_pendencias, marcar_pendencias, padronizar


def _processar_aba(
    aba: str, caminho_origem: str, conexao: sqlite3.Connection,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lê uma aba do Excel, padroniza, audita pendências e publica no SQLite.

    Devolve (auditoria_resumida, detalhes_pendentes) dessa aba, para serem
    concatenados com as demais abas depois.
    """
    dados = padronizar(pd.read_excel(caminho_origem, sheet_name=aba))
    auditoria = auditoria_pendencias(aba, dados)
    dados, pendentes = marcar_pendencias(aba, dados)
    if "data" in dados:
        dados["data"] = dados["data"].dt.strftime("%Y-%m-%d")
    dados.to_sql(aba, conexao, if_exists="replace", index=False)
    return auditoria, pendentes


def main() -> None:
    """CLI: --origem (Excel) -> --destino (SQLite padronizado e auditado)."""
    parser = argparse.ArgumentParser(description="Transforma planilha Excel em SQLite padronizado.")
    parser.add_argument("--origem", required=True, help="Arquivo Excel (.xlsx)")
    parser.add_argument("--destino", required=True, help="Banco SQLite de destino (.db)")
    args = parser.parse_args()

    auditorias, detalhes = [], []
    with sqlite3.connect(args.destino) as conexao:
        for aba in pd.ExcelFile(args.origem).sheet_names:
            auditoria, pendentes = _processar_aba(aba, args.origem, conexao)
            auditorias.append(auditoria)
            detalhes.append(pendentes)

        pd.concat(auditorias, ignore_index=True).to_sql(
            "Qualidade_Dados_Pendentes", conexao, if_exists="replace", index=False
        )
        pd.concat(detalhes, ignore_index=True).to_sql(
            "Dados_Pendentes", conexao, if_exists="replace", index=False
        )

    print(f"Banco padronizado criado: {args.destino}")


if __name__ == "__main__":
    main()
