"""Testes unitários de src/analise.py (Teste 1 do plano: regressão exata
de entrada->resultado, sem depender do pipeline Excel -> SQLite inteiro).

Os números de exemplo abaixo foram escolhidos para dar frações "feias"
(1/3, 23,08%...) de propósito — são justamente esses casos que expõem
erros de arredondamento ou de ordem de operações numa futura refatoração.
"""
import pandas as pd
import pytest

from analise import JANELAS, percentual, por_periodo


def _vendas_exemplo() -> pd.DataFrame:
    """4 linhas / 3 vendas (venda_id V1 aparece 2x, simulando 2 itens na
    mesma venda) espalhadas em duas regiões, com totais que não fecham em
    números redondos ao calcular percentuais."""
    return pd.DataFrame({
        "venda_id": ["V1", "V1", "V2", "V3"],
        "regiao": ["Sul", "Sul", "Nordeste", "Nordeste"],
        "quantidade": [1, 2, 3, 4],
        "valor_total": [100.0, 50.0, 200.0, 300.0],
        "data": pd.to_datetime(["2026-01-15", "2026-01-15", "2026-03-10", "2026-06-30"]),
    })


class TestPercentual:
    def test_agrupado_por_regiao(self):
        resultado = percentual(_vendas_exemplo(), ["regiao"]).set_index("regiao")

        # Sul: transacoes=nunique(V1,V1)=1, quantidade=1+2=3, valor=100+50=150
        assert resultado.loc["Sul", "transacoes"] == 1
        assert resultado.loc["Sul", "quantidade_vendida"] == 3
        assert resultado.loc["Sul", "valor_total_vendido"] == pytest.approx(150.0)
        assert resultado.loc["Sul", "pct_transacoes"] == pytest.approx(33.33)   # 1/3 * 100
        assert resultado.loc["Sul", "pct_quantidade"] == pytest.approx(30.0)    # 3/10 * 100
        assert resultado.loc["Sul", "pct_faturamento"] == pytest.approx(23.08)  # 150/650 * 100

        # Nordeste: transacoes=nunique(V2,V3)=2, quantidade=3+4=7, valor=200+300=500
        assert resultado.loc["Nordeste", "transacoes"] == 2
        assert resultado.loc["Nordeste", "quantidade_vendida"] == 7
        assert resultado.loc["Nordeste", "valor_total_vendido"] == pytest.approx(500.0)
        assert resultado.loc["Nordeste", "pct_transacoes"] == pytest.approx(66.67)  # 2/3 * 100
        assert resultado.loc["Nordeste", "pct_quantidade"] == pytest.approx(70.0)
        assert resultado.loc["Nordeste", "pct_faturamento"] == pytest.approx(76.92)  # 500/650 * 100

    def test_percentuais_dos_grupos_somam_cem(self):
        resultado = percentual(_vendas_exemplo(), ["regiao"])
        # tolerância pequena só por causa do arredondamento pra 2 casas
        # aplicado a CADA grupo separadamente (não é tolerância de fórmula)
        assert resultado["pct_quantidade"].sum() == pytest.approx(100.0, abs=0.01)
        assert resultado["pct_faturamento"].sum() == pytest.approx(100.0, abs=0.02)

    def test_grupo_vazio_agrega_tudo_em_uma_linha(self):
        resultado = percentual(_vendas_exemplo(), [])
        assert len(resultado) == 1
        assert resultado.loc[0, "transacoes"] == 3       # V1, V2, V3
        assert resultado.loc[0, "quantidade_vendida"] == 10
        assert resultado.loc[0, "valor_total_vendido"] == pytest.approx(650.0)
        # sem grupo e sem referência separada, o total é 100% de si mesmo
        assert resultado.loc[0, "pct_transacoes"] == pytest.approx(100.0)
        assert resultado.loc[0, "pct_quantidade"] == pytest.approx(100.0)
        assert resultado.loc[0, "pct_faturamento"] == pytest.approx(100.0)

    def test_referencia_diferente_da_fatia(self):
        """Uso real: por_periodo() calcula o % de UM mês em relação ao
        TOTAL do semestre, não ao total do próprio mês (referência
        explícita != fatia agregada)."""
        completo = _vendas_exemplo()
        so_sul = completo[completo["regiao"] == "Sul"]

        resultado = percentual(so_sul, [], referencia=completo)

        assert resultado.loc[0, "transacoes"] == 1        # só V1, dentro da fatia "Sul"
        assert resultado.loc[0, "valor_total_vendido"] == pytest.approx(150.0)
        # mas o percentual é relativo ao TOTAL (650), não aos 150 da fatia
        assert resultado.loc[0, "pct_transacoes"] == pytest.approx(33.33)   # 1 / 3 (total geral)
        assert resultado.loc[0, "pct_quantidade"] == pytest.approx(30.0)    # 3 / 10
        assert resultado.loc[0, "pct_faturamento"] == pytest.approx(23.08)  # 150 / 650

    def test_valor_total_vendido_arredonda_para_duas_casas(self):
        df = pd.DataFrame({
            "venda_id": ["V1"], "regiao": ["Sul"],
            "quantidade": [1], "valor_total": [10.005],
        })
        resultado = percentual(df, ["regiao"])
        assert resultado.loc[0, "valor_total_vendido"] == round(10.005, 2)

    def test_registro_unico(self):
        df = pd.DataFrame({"venda_id": ["V1"], "regiao": ["Sul"], "quantidade": [5], "valor_total": [99.9]})
        resultado = percentual(df, ["regiao"])
        assert len(resultado) == 1
        assert resultado.loc[0, "pct_faturamento"] == pytest.approx(100.0)


class TestPorPeriodo:
    def test_gera_uma_linha_por_janela(self):
        resultado = por_periodo(_vendas_exemplo(), [])
        assert len(resultado) == len(JANELAS)
        assert set(resultado["periodo"]) == set(JANELAS.keys())

    def test_filtra_vendas_pela_janela_de_data(self):
        resultado = por_periodo(_vendas_exemplo(), []).set_index("periodo")

        # só a venda de 2026-01-15 (V1, 2 linhas) cai na janela "2026-01"
        assert resultado.loc["2026-01", "transacoes"] == 1
        assert resultado.loc["2026-01", "valor_total_vendido"] == pytest.approx(150.0)

        # só a venda de 2026-03-10 (V2) cai em "2026-03"
        assert resultado.loc["2026-03", "transacoes"] == 1
        assert resultado.loc["2026-03", "valor_total_vendido"] == pytest.approx(200.0)

        # nenhuma venda em fevereiro no exemplo
        assert resultado.loc["2026-02", "transacoes"] == 0

        # "Último semestre" cobre as 3 vendas inteiras
        assert resultado.loc["Último semestre", "transacoes"] == 3
        assert resultado.loc["Último semestre", "valor_total_vendido"] == pytest.approx(650.0)

    def test_colunas_de_periodo_inseridas_corretamente(self):
        resultado = por_periodo(_vendas_exemplo(), [])
        linha_junho = resultado[resultado["periodo"] == "2026-06"].iloc[0]
        assert linha_junho["inicio_periodo"] == pd.Timestamp("2026-06-01")
        assert linha_junho["fim_periodo"] == pd.Timestamp("2026-06-30")

    def test_janela_sem_vendas_nao_quebra(self):
        """Uma janela em que nenhuma venda cai (ex.: 2026-02 no exemplo)
        precisa retornar uma linha com zeros, não lançar erro nem sumir."""
        resultado = por_periodo(_vendas_exemplo(), []).set_index("periodo")
        linha = resultado.loc["2026-02"]
        assert linha["transacoes"] == 0
        assert linha["quantidade_vendida"] == 0
        assert linha["valor_total_vendido"] == 0
