"""Esquemas Pandera aplicados depois da padronização (ver qualidade.py::padronizar).

Cada schema é "estrito" (não aceita colunas extras) e "coerce" (converte
tipos compatíveis automaticamente); os campos são todos `nullable=True`
porque a validação de completude é feita separadamente, em
qualidade.py::marcar_pendencias — aqui só validamos TIPO e DOMÍNIO
(ex.: quantidade não pode ser negativa), não presença.
"""
import pandera.pandas as pa
from pandera.typing import Series


class VendasSchema(pa.DataFrameModel):
    """Uma linha de venda, já padronizada por qualidade.py::padronizar."""
    venda_id: Series[str] = pa.Field(nullable=True)
    data: Series[pa.DateTime] = pa.Field(nullable=True)
    vendedor_id: Series[str] = pa.Field(nullable=True)
    loja_id: Series[str] = pa.Field(nullable=True)
    regiao: Series[str] = pa.Field(nullable=True)
    produto_id: Series[str] = pa.Field(nullable=True)
    produto: Series[str] = pa.Field(nullable=True)
    quantidade: Series[int] = pa.Field(nullable=True, ge=0)
    preco_unitario: Series[float] = pa.Field(nullable=True, ge=0)
    valor_total: Series[float] = pa.Field(nullable=True, ge=0)
    custo_unitario: Series[float] = pa.Field(nullable=True, ge=0)
    custo_total: Series[float] = pa.Field(nullable=True, ge=0)

    class Config:
        """Estrito (sem colunas extras) e com coerção automática de tipo."""
        strict = True
        coerce = True


class VendedoresSchema(pa.DataFrameModel):
    """Cadastro de vendedores, já padronizado por qualidade.py::padronizar."""
    vendedor_id: Series[str] = pa.Field(nullable=True)
    nome_vendedor: Series[str] = pa.Field(nullable=True)
    loja_id: Series[str] = pa.Field(nullable=True)
    nome_loja: Series[str] = pa.Field(nullable=True)
    regiao: Series[str] = pa.Field(nullable=True)

    class Config:
        """Estrito (sem colunas extras) e com coerção automática de tipo."""
        strict = True
        coerce = True


class LojasSchema(pa.DataFrameModel):
    """Cadastro de lojas, já padronizado por qualidade.py::padronizar."""
    loja_id: Series[str] = pa.Field(nullable=True)
    nome_loja: Series[str] = pa.Field(nullable=True)
    cidade: Series[str] = pa.Field(nullable=True)
    estado: Series[str] = pa.Field(nullable=True, str_matches=r"^[A-Z]{2}$")
    regiao: Series[str] = pa.Field(nullable=True)

    class Config:
        """Estrito (sem colunas extras) e com coerção automática de tipo."""
        strict = True
        coerce = True


class ProdutosSchema(pa.DataFrameModel):
    """Catálogo de produtos, já padronizado por qualidade.py::padronizar."""
    produto_id: Series[str] = pa.Field(nullable=True)
    categoria: Series[str] = pa.Field(nullable=True)
    modelo: Series[str] = pa.Field(nullable=True)
    preco_unitario: Series[float] = pa.Field(nullable=True, ge=0)
    custo_unitario: Series[float] = pa.Field(nullable=True, ge=0)
    margem_unitaria: Series[float] = pa.Field(nullable=True)
    margem_percentual: Series[float] = pa.Field(alias="margem_%", nullable=True)

    class Config:
        """Estrito (sem colunas extras) e com coerção automática de tipo."""
        strict = True
        coerce = True
