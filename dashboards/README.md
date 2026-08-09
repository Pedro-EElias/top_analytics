# Painel de Vendas · Eletrônicos (TOP Analytics)

Dashboard executivo em **Dash + Plotly + dash-bootstrap-components**, construído
sobre o pipeline de dados já existente em `src/` (Excel → SQLite → tabelas
analíticas). O pipeline **não foi alterado** — este projeto só lê o resultado
dele (`data/resultados/banco_analise.sqlite`) e apresenta em um dashboard
visual inspirado no layout de referência (sidebar escura, cards de KPI,
paleta azul/rosa/roxo).

## Como rodar

Este projeto pode viver de dois jeitos:

**A) Dentro da pasta do projeto original** (`analise_treino/dashboard_vendas/`)
— é o jeito recomendado, porque o dashboard já acha sozinho o banco gerado
pelo pipeline, sem nenhuma configuração:

```bash
cd analise_treino/dashboard_vendas
pip install -r requirements.txt
python app.py
```

**B) Standalone**, em qualquer outro lugar — usa a cópia de banco incluída
neste zip (`data/resultados/banco_analise.sqlite`) só para você conseguir
ver o dashboard funcionando antes de conectar ao seu banco real:

```bash
pip install -r requirements.txt
python app.py
```

Em ambos os casos, acesse `http://localhost:8050`.

> Os ícones (Bootstrap Icons) e a fonte "Sora" são carregados via CDN
> (`cdn.jsdelivr.net` e `fonts.googleapis.com`). Isso exige acesso normal à
> internet no navegador — não depende de nada além disso.

## Como conectar ao seu pipeline real

O dashboard resolve o caminho do banco automaticamente, nesta ordem:

1. Variável de ambiente `DASHBOARD_DB_PATH`, se você definir uma (tem
   prioridade sobre tudo);
2. `<pasta do projeto>/data/resultados/*.sqlite` — usado quando
   `dashboard_vendas/` está dentro de `analise_treino/` (opção A acima).
   Não precisa ser exatamente `banco_analise.sqlite`: se houver mais de um
   `.sqlite` ali, o dashboard pega o mais recente — então funciona com
   qualquer nome que você tenha passado em `--destino` no `analise.py`;
3. `dashboard_vendas/data/resultados/*.sqlite` — a cópia local incluída
   neste zip, usada só no modo standalone (opção B).

Ou seja: se você colocar esta pasta dentro do projeto e rodar o pipeline
normalmente —

```bash
python src/transform_xlsx_to_db.py --origem sua_planilha.xlsx --destino data/raw/vendas.db
python src/analise.py --origem data/raw/vendas.db --destino data/resultados/analise_vendas_1S2026.sqlite
```

— o dashboard já vai ler esse arquivo automaticamente na próxima vez que
você rodar `python dashboard_vendas/app.py`, sem precisar mexer em nada.
Se quiser forçar um caminho específico mesmo assim:

```bash
export DASHBOARD_DB_PATH=/caminho/para/outro/banco.sqlite
python app.py
```

## Arquitetura

```
app.py                     # shell: sidebar fixa + roteamento entre páginas
services/
  data.py                  # única porta de entrada ao banco_analise.sqlite
components/
  theme.py                 # cores, tipografia, layout padrão dos gráficos Plotly
  sidebar.py                # navegação (destaca a página ativa via callback)
  header.py                 # título da página + botão "Limpar filtros"
  cards.py                  # kpi_card() e chart_card() reutilizáveis
pages/
  visao_geral.py             # "/"                    — KPIs gerais, região, evolução mensal, top vendedores
  vendas_periodo.py          # "/vendas-por-periodo"  — filtros de período + região
  produtos_regioes.py        # "/produtos-regioes"    — mix de produtos por região
  qualidade_dados.py         # "/qualidade-dos-dados" — expõe as pendências do src/qualidade.py
assets/
  style.css                  # sidebar escura, cards arredondados, grid responsivo
```

### Por que essa estrutura

- **`services/data.py` isola o SQL.** Nenhuma página faz `sqlite3.connect`
  diretamente — todas chamam funções como `ds.kpis_gerais()` ou
  `ds.itens_filtrados(periodo, regiao)`. Se amanhã o pipeline passar a gravar
  em Postgres em vez de SQLite, só esse arquivo muda.
- **Páginas via `dash.register_page`.** Cada página é um módulo independente
  com sua própria `layout()` e seus próprios `@callback`s — dá pra adicionar
  uma 5ª página sem tocar nas outras.
- **Componentes (`kpi_card`, `chart_card`) são funções puras**, não classes —
  mais fácil de testar isoladamente e de reaproveitar entre páginas.

## Decisão de design: Treemap → barras empilhadas

A primeira versão de "Produtos & Regiões" usava um `go.Treemap` para cruzar
produto × região. Em testes (inclusive um exemplo mínimo, isolado de todo o
resto da aplicação), o Treemap do Plotly.js não renderizou nenhuma "fatia"
neste ambiente — tela em branco, sem erro no console. Como não quis arriscar
essa mesma falha silenciosa no seu ambiente, troquei por um gráfico de
barras horizontais empilhadas (uma cor por região), que é mais previsível e,
neste caso, ficou até mais legível para comparar as regiões dentro de cada
produto. Se quiser retomar o Treemap depois, teste primeiro numa página
isolada antes de reintroduzir.

## Qualidade de dados

A página "Qualidade dos Dados" lê as tabelas `qualidade_dados_pendentes` e
`dados_pendentes`, geradas pelo seu `src/qualidade.py`. No banco de exemplo
usado para testar este dashboard essas tabelas não existiam (versão mais
antiga do pipeline) — o dashboard trata isso graciosamente (mostra "nenhuma
pendência encontrada" em vez de quebrar). Assim que você rodar o pipeline
atualizado, essa página passa a mostrar os números reais automaticamente.

## Próximos passos sugeridos (evoluções futuras)

1. **Cache do banco**: hoje cada requisição HTTP relê o SQLite inteiro. Para
   um volume maior de dados, cacheie os DataFrames com `flask_caching` e
   invalide o cache quando o pipeline gerar um novo banco.
2. **Deploy**: `server = app.server` já está exposto em `app.py` para rodar
   com `gunicorn app:server`.
3. **Filtro de data livre** (não só os períodos pré-calculados): exigiria
   trazer a tabela `Vendas` bruta para o dashboard em vez de só as tabelas
   agregadas — hoje as agregações vêm prontas do `analise.py`.
4. **Autenticação**: `dash-auth` ou um proxy reverso com login, se o painel
   for exposto fora da rede interna.
