# Análise de vendas de eletrônicos — 1º semestre de 2026
Projeto de EDA com **Pandas**, validação de dados com **Pandera** e publicação dos resultados em **SQLite**.

## Indicadores entregues
- Participação percentual de vendas por região;
- Participação percentual por funcionário/vendedor;
- Participação por data: janeiro a junho, **Último trimestre** (abr–jun) e **Último semestre** (jan–jun);
- Quantidade e faturamento de cada item por região e período.

As colunas `pct_transacoes`, `pct_quantidade` e `pct_faturamento` mostram participações percentuais. Nas tabelas por região e funcionário, a base é o semestre inteiro. Em `percentual_vendas_data`, cada mês e janela é comparado ao total do semestre; portanto, os seis meses somam 100%. Em `itens_por_regiao_data`, a base é o próprio período. "Vendas" são tratadas como transações (`venda_id`); a quantidade física está em `quantidade_vendida`.

# Padronização e qualidade de dados
O módulo `src/qualidade.py` é a única fonte das regras de padronização usadas na importação Excel→SQLite e na EDA.

- IDs: remove espaços e converte para maiúsculas;
- textos: remove espaços duplicados e aplica Title Case;
- UF: remove espaços e converte para duas letras maiúsculas; o esquema Pandera bloqueia valores fora de `^[A-Z]{2}$`;
- valores financeiros: conversão tolerante a formatos brasileiro/internacional e arredondamento em 2 casas;
- quantidades: valores não inteiros viram pendência, sem truncamento silencioso;
- `margem_%`: decimal com 4 casas.

`Qualidade_Dados_Pendentes` (na importação) e `qualidade_dados_pendentes` (na análise) listam tabela, campo, número e percentual de valores ausentes após a limpeza. Assim, o Power BI pode exibir e filtrar problemas de qualidade sem interromper a atualização inteira.

Além disso, cada tabela importada recebe `status_pendencia` (`Completo` ou `Pendente`) e `campos_pendentes`. A tabela `Dados_Pendentes` (importação) / `dados_pendentes` (análise) contém exclusivamente registros com problema, uma linha por campo faltante: `tabela_origem`, `linha_origem`, `registro_id`, `campo_pendente` e `status_pendencia`.

# Gerador não interativo para GitHub Actions
Por padrão, execute:
```bash
python src/gerar_planilha.py --mes 6 --ano 2026 --destino data/raw
```

O comando sempre gera dois arquivos determinísticos:
1. `vendas_202606_completo_padronizado.xlsx`: sem dados ausentes ou erros de formato;
2. `vendas_202606_aleatorio_com_erro.xlsx`: contém campos ausentes e textos, moedas e datas propositalmente mal formatados.

Use `--interativo` apenas para o modo manual legado. O workflow em `.github/workflows/gerar-planilhas.yml` executa o modo não interativo e publica os dois arquivos como artefato do Actions.

## Execução
```powershell
# 1. Instale as dependências necessárias
python -m pip install -r requirements.txt

# 2. Transforme a planilha Excel original em um banco de dados SQLite (.db)
python src/transform_xlsx_to_db.py --origem "C:\caminho\sua_planilha_original.xlsx" --destino "C:\caminho\vendas_eletronicos_1S2026.db"

# 3. Execute a análise de dados e gere o banco com os resultados finais
python src/analise.py --origem "C:\caminho\vendas_eletronicos_1S2026.db" --destino "data\resultados\analise_vendas_1S2026.sqlite"
```

## Tabelas geradas no SQLite

| Tabela | Conteúdo |
|---|---|
| `eda_resumo_geral` | Período, transações, itens, faturamento e ticket médio |
| `percentual_vendas_regiao` | Participação de cada região no semestre |
| `percentual_vendas_funcionario` | Participação de cada vendedor no semestre |
| `percentual_vendas_data` | Todos os meses, último trimestre e último semestre |
| `itens_por_regiao_data` | Produtos por região em cada período solicitado |

O script preserva as tabelas do banco de origem ao copiar o arquivo antes de acrescentar a camada analítica.

# Dashboard executivo (Dash)
Além dos dados publicados em SQLite, o projeto inclui um dashboard visual em `dashboards/` — feito com **Dash + Plotly + dash-bootstrap-components** —, que lê diretamente o banco gerado por `src/analise.py` e apresenta os indicadores acima (participação por região, por vendedor, evolução mensal, mix de produtos e as pendências de qualidade) em uma interface web, sem precisar do Power BI.

Ele não reprocessa nada: é só uma camada de visualização por cima do que o pipeline já produz.

## Como rodar o dashboard
```bash
cd dashboards
pip install -r requirements.txt
python app.py
```
Depois acesse `http://localhost:8050` no navegador.

O dashboard acha o banco de dados automaticamente: como ele está dentro desta pasta do projeto, ele lê o `.sqlite` mais recente em `data/resultados/` sozinho — não importa o nome que você deu em `--destino` ao rodar `src/analise.py`. Ou seja, depois de rodar os passos da seção **Execução** acima, é só rodar `python dashboards/app.py` que os números já aparecem atualizados.

Se quiser apontar para um banco em outro lugar, defina a variável de ambiente `DASHBOARD_DB_PATH` antes de rodar `app.py`. Mais detalhes de arquitetura estão em `dashboards/README.md`.

# Testes automatizados

O projeto tem uma suíte de testes em `tests/` (pytest) que funciona como rede de segurança para qualquer mudança futura no pipeline — principalmente refatorações que não devem alterar nenhum resultado numérico.

## Como rodar
```bash
pip install -r requirements.txt
python -m pytest tests/
```

## O que cada arquivo cobre
- **`test_analise.py`** — testa `percentual()` e `por_periodo()` isoladamente, com números pequenos e verificáveis à mão (sem depender do pipeline Excel → SQLite inteiro).
- **`test_qualidade.py`** — testa `_texto`, `_numero`, `_data`, `padronizar`, `auditoria_pendencias` e `marcar_pendencias` com casos-limite (registro único, dados vazios, valores nulos, `venda_id` duplicado, formatos numéricos equivalentes como `1234.56` / `1.234,56` / `R$ 1.234,56`).
- **`test_regressao_pipeline.py`** — roda o pipeline completo contra `data/raw/vendas_eletronicos_1S2026.db` e compara, tabela por tabela e sem tolerância numérica, com o resultado congelado em `tests/fixtures/baseline_analise.sqlite`.

## Se um resultado mudar de propósito

Se uma mudança de comportamento for intencional (uma correção de bug, uma nova regra de negócio), o `tests/fixtures/baseline_analise.sqlite` precisa ser deliberadamente regenerado — nunca "consertado" só para o teste voltar a passar. Para regenerar:
```bash
cd src
python analise.py --origem ../data/raw/vendas_eletronicos_1S2026.db --destino ../tests/fixtures/baseline_analise.sqlite
```

## Resultado (radon + pylint)

| Função | Complexidade antes | Complexidade depois |
|---|---:|---:|
| `salvar_excel` | 10 | 2 (dividida em 5 funções, a maior com complexidade 4) |
| `padronizar` | 8 | 1 (dividida em 7 funções, cada uma complexidade 2) |
| `aplicar_erros_formatacao` | 7 | 4 |
| `verificar_qualidade` | 6 | 1 (dividida em 3 funções) |
| `auditoria_pendencias` | 6 | 5 |
| `marcar_pendencias` | 6 | 3 (dividida em 3 funções) |

Índice de manutenibilidade (radon mi): `analise.py` 46,94 → 71,87; `qualidade.py` 55,31 → 61,46; `gerar_planilha.py` 38,19 → 42,02 — todos os 5 arquivos de `src/` classificados **A**. As categorias de estilo `missing-function-docstring` e `multiple-statements`, antes recorrentes, foram zeradas.