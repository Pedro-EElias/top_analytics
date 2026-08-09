"""Testes unitários de src/qualidade.py (Testes 2, 3 e 4 do plano de testes).

Cobrem casos-limite, formatos numéricos equivalentes e cenários de dados
faltantes — isolados da execução do pipeline inteiro, então rodam em
milissegundos e apontam exatamente qual função quebrou.
"""
import pandas as pd
import pytest

from qualidade import _data, _numero, _texto, auditoria_pendencias, marcar_pendencias, padronizar


# ---------------------------------------------------------------------------
# _texto
# ---------------------------------------------------------------------------

class TestTexto:
    def test_remove_espacos_duplicados_e_das_pontas(self):
        resultado = _texto(pd.Series(["  São   Paulo  "]))
        assert resultado.iloc[0] == "São Paulo"

    def test_string_vazia_vira_nulo(self):
        resultado = _texto(pd.Series(["", "   ", "ok"]))
        assert resultado.iloc[0] is pd.NA
        assert resultado.iloc[1] is pd.NA
        assert resultado.iloc[2] == "ok"

    def test_title_capitaliza_cada_palavra(self):
        resultado = _texto(pd.Series(["são paulo"]), title=True)
        assert resultado.iloc[0] == "São Paulo"

    def test_nulo_permanece_nulo(self):
        resultado = _texto(pd.Series([None, pd.NA]))
        assert resultado.isna().all()


# ---------------------------------------------------------------------------
# _numero — Teste 3: formatos equivalentes devem convergir pro mesmo valor
# ---------------------------------------------------------------------------

class TestNumero:
    @pytest.mark.parametrize("texto_entrada", ["1234.56", "1.234,56", "R$ 1.234,56", " 1234.56 ", "R$1.234,56"])
    def test_formatos_equivalentes_geram_mesmo_valor(self, texto_entrada):
        resultado = _numero(pd.Series([texto_entrada]))
        assert resultado.iloc[0] == pytest.approx(1234.56)

    def test_valor_zero(self):
        resultado = _numero(pd.Series(["0", "0.00", "R$ 0,00"]))
        assert (resultado == 0).all()

    def test_numero_apenas_com_virgula_decimal(self):
        # "1234,56" sem separador de milhar: a vírgula só pode ser decimal.
        resultado = _numero(pd.Series(["1234,56"]))
        assert resultado.iloc[0] == pytest.approx(1234.56)

    def test_texto_nao_numerico_vira_nulo(self):
        resultado = _numero(pd.Series(["abc", "", None]))
        assert resultado.isna().all()

    def test_negativo(self):
        resultado = _numero(pd.Series(["-1.234,56"]))
        assert resultado.iloc[0] == pytest.approx(-1234.56)


# ---------------------------------------------------------------------------
# _data — cobre especificamente o bug de dia/mês trocado (dayfirst=True
# aplicado sem checar o formato de origem)
# ---------------------------------------------------------------------------

class TestData:
    @pytest.mark.parametrize("texto_entrada,esperado", [
        ("2026-06-12", "2026-06-12"),   # ISO, formato "de fábrica"
        ("2026-01-02", "2026-01-02"),   # ISO com dia <= 12 — o caso que quebrava antes
        ("12/06/2026", "2026-06-12"),   # bagunçado dia-primeiro (barra)
        ("12-06-2026", "2026-06-12"),   # bagunçado dia-primeiro (traço)
        ("2026/06/12", "2026-06-12"),   # bagunçado ano-primeiro (barra)
        ("12.06.2026", "2026-06-12"),   # bagunçado dia-primeiro (ponto)
    ])
    def test_formatos_conhecidos_nao_trocam_dia_e_mes(self, texto_entrada, esperado):
        resultado = _data(pd.Series([texto_entrada]))
        assert resultado.iloc[0] == pd.Timestamp(esperado)

    def test_lote_com_formatos_misturados(self):
        """Regressão direta do bug: quando vários formatos aparecem juntos
        na mesma coluna, a inferência vetorizada do pandas pode se
        confundir mais do que quando cada valor é testado sozinho."""
        entrada = pd.Series(["2026-06-12", "12/06/2026", "2026/06/12", "12.06.2026", None])
        resultado = _data(entrada)
        assert (resultado.dropna() == pd.Timestamp("2026-06-12")).all()
        assert resultado.isna().sum() == 1

    def test_formato_desconhecido_vira_nulo_em_vez_de_data_errada(self):
        """Preferimos um nulo explícito (fácil de auditar) a uma data
        silenciosamente incorreta."""
        resultado = _data(pd.Series(["31 de junho de 2026", "não é uma data"]))
        assert resultado.isna().all()

    def test_dia_maior_que_12_no_formato_iso_nao_vira_nulo(self):
        """Antes da correção, QUALQUER data ISO com dia > 12 virava NaT
        (63% das vendas do banco de exemplo)."""
        resultado = _data(pd.Series(["2026-06-25", "2026-12-31"]))
        assert resultado.notna().all()
        assert resultado.iloc[0] == pd.Timestamp("2026-06-25")
        assert resultado.iloc[1] == pd.Timestamp("2026-12-31")


# ---------------------------------------------------------------------------
# padronizar — casos-limite de ponta a ponta na função pública
# ---------------------------------------------------------------------------

class TestPadronizar:
    def test_dataframe_vazio_nao_quebra(self):
        vazio = pd.DataFrame(columns=["venda_id", "data", "quantidade", "valor_total"])
        resultado = padronizar(vazio)
        assert len(resultado) == 0

    def test_registro_unico(self):
        df = pd.DataFrame([{"venda_id": " vd001 ", "data": "2026-06-12", "quantidade": "3", "valor_total": "R$ 99,90"}])
        resultado = padronizar(df)
        assert resultado.loc[0, "venda_id"] == "VD001"
        assert resultado.loc[0, "data"] == pd.Timestamp("2026-06-12")
        assert resultado.loc[0, "quantidade"] == 3
        assert resultado.loc[0, "valor_total"] == pytest.approx(99.90)

    def test_quantidade_zero_preservada(self):
        df = pd.DataFrame([{"quantidade": "0"}])
        resultado = padronizar(df)
        assert resultado.loc[0, "quantidade"] == 0

    def test_valor_financeiro_arredonda_para_duas_casas(self):
        df = pd.DataFrame([{"valor_total": "10,005"}])
        resultado = padronizar(df)
        assert resultado.loc[0, "valor_total"] == round(10.005, 2)

    def test_percentual_arredonda_para_quatro_casas(self):
        df = pd.DataFrame([{"margem_%": "0,123456"}])
        resultado = padronizar(df)
        assert resultado.loc[0, "margem_%"] == round(0.123456, 4)

    def test_quantidade_nao_inteira_vira_nulo_em_vez_de_truncar(self):
        """Preserva o comportamento original: um valor tipo '3.5' não é
        um Int64 válido, então fica nulo em vez de virar 3 silenciosamente."""
        df = pd.DataFrame([{"quantidade": "3.5"}])
        resultado = padronizar(df)
        assert pd.isna(resultado.loc[0, "quantidade"])


# ---------------------------------------------------------------------------
# auditoria_pendencias / marcar_pendencias — Teste 4 (dados faltantes)
# ---------------------------------------------------------------------------

class TestPendencias:
    def test_dataframe_vazio(self):
        vazio = pd.DataFrame(columns=["venda_id", "data"])
        resultado = auditoria_pendencias("Vendas", vazio)
        assert resultado.empty
        assert list(resultado.columns) == ["tabela_origem", "campo", "valores_pendentes", "pct_pendente"]

    def test_nenhum_campo_faltando(self):
        completo = pd.DataFrame([{"venda_id": "VD001", "data": pd.Timestamp("2026-01-01")}])
        resultado = auditoria_pendencias("Vendas", completo)
        assert resultado.empty

    def test_conta_pendencias_por_campo(self):
        df = pd.DataFrame([
            {"venda_id": "VD001", "regiao": "Sul"},
            {"venda_id": "VD002", "regiao": None},
            {"venda_id": None, "regiao": None},
        ])
        resultado = auditoria_pendencias("Vendas", df)
        pendentes = dict(zip(resultado["campo"], resultado["valores_pendentes"]))
        assert pendentes["regiao"] == 2
        assert pendentes["venda_id"] == 1

    def test_marcar_pendencias_registro_completo(self):
        df = pd.DataFrame([{"venda_id": "VD001", "regiao": "Sul"}])
        marcado, detalhes = marcar_pendencias("Vendas", df)
        assert marcado.loc[0, "status_pendencia"] == "Completo"
        assert detalhes.empty

    def test_marcar_pendencias_registro_com_varios_campos_faltando(self):
        df = pd.DataFrame([{"venda_id": "VD001", "regiao": None, "produto": None}])
        marcado, detalhes = marcar_pendencias("Vendas", df)
        assert marcado.loc[0, "status_pendencia"] == "Pendente"
        assert set(detalhes["campo_pendente"]) == {"regiao", "produto"}
        assert (detalhes["registro_id"] == "VD001").all()

    def test_marcar_pendencias_sem_identificador_usa_numero_da_linha(self):
        """Quando nem venda_id/vendedor_id/produto_id/loja_id existem
        (ex.: tabela genérica), cai para o índice da linha (1-based)."""
        df = pd.DataFrame([{"campo_qualquer": None}, {"campo_qualquer": "ok"}])
        _marcado, detalhes = marcar_pendencias("Genérica", df)
        assert detalhes["registro_id"].iloc[0] == "1"

    def test_venda_id_duplicado_nao_quebra_a_auditoria(self):
        df = pd.DataFrame([
            {"venda_id": "VD001", "regiao": None},
            {"venda_id": "VD001", "regiao": "Sul"},
        ])
        marcado, detalhes = marcar_pendencias("Vendas", df)
        assert len(marcado) == 2  # não deduplica silenciosamente
        assert len(detalhes) == 1
