# Análise histórica de custodiantes de fundos da CVM

## Objetivo

Reconstruir, mês a mês, quais custodiantes mantinham quantos fundos de investimento sob custódia, a partir do cadastro histórico oficial da CVM, e responder: quantos custodiantes existem no histórico, quantos estavam ativos em cada data, como os fundos se distribuem entre eles e quem cresceu ou encolheu.

## Fonte dos dados

- Página: <https://dados.cvm.gov.br/dados/FI/CAD/DADOS/>
- ZIP: <https://dados.cvm.gov.br/dados/FI/CAD/DADOS/cad_fi_hist.zip> (o CSV de custodiantes é localizado pelo nome dentro do ZIP).

| Coluna | Descrição |
|---|---|
| `CNPJ_FUNDO` | Identificador do fundo |
| `DT_REG` | Data de registro do fundo (não usada como data de custódia) |
| `CNPJ_CUSTODIANTE` | Identificador do custodiante |
| `CUSTODIANTE` | Nome do custodiante |
| `DT_INI_CUSTODIANTE` | Início da relação de custódia |
| `DT_FIM_CUSTODIANTE` | Fim da relação; vazia = vigente |

## Metodologia

- **Vigência:** intervalo semiaberto `DT_INI_CUSTODIANTE <= data < DT_FIM_CUSTODIANTE`. Fim vazio = vigente até a data da extração (inclusive). Em transferências com fim e início na mesma data, só o novo custodiante conta naquele dia.
- **Frequência:** último dia de cada mês, do mês da primeira relação até a extração, mais a própria data da extração se não for fim de mês.
- **Contagem:** fundos distintos (`CNPJ_FUNDO`) por custodiante (`CNPJ_CUSTODIANTE`) e data. O nome exibido é o mais recente de cada CNPJ (ou o próprio CNPJ, se não houver nome).
- **Custodiante distinto:** CNPJ que aparece em qualquer linha válida do histórico. **Custodiante ativo:** CNPJ com ao menos um fundo com relação vigente na data.
- **Tratamento:** CNPJs lidos como texto; codificação (UTF-8/UTF-8-BOM/CP1252) e delimitador detectados; são descartadas linhas sem CNPJ, sem data de início válida ou com fim anterior ao início; duplicatas exatas são removidas. Todas as contagens ficam em `resultados/qualidade_dados.csv`.

## Estrutura

```
analise_custodiantes_cvm.ipynb   notebook da análise (executar do início ao fim)
graficos.py                      gráfico interativo (seleção de custodiantes, "Outros", filtro de datas)
custodiantes.py                  funções reutilizáveis (download, validação, série histórica)
test_custodiantes.py             testes com dados sintéticos
cad_fi_hist_custodiante.csv      cópia local da base, sobrescrita a cada execução
resultados/
  custodiantes_serie_historica.csv   DATA_REFERENCIA, CNPJ_CUSTODIANTE, CUSTODIANTE, QTD_FUNDOS
  totais_por_data.csv                QTD_CUSTODIANTES_ATIVOS e QTD_FUNDOS_DISTINTOS_TOTAL por data
  concentracao_por_data.csv          participação do top 5 e HHI por data
  variacao_custodiantes.csv          variação em 12 meses e queda desde o pico
  qualidade_dados.csv                resumo de qualidade/descartes
  resumo_indicadores.json            indicadores da última execução
  grafico_fundos_por_custodiante.html, grafico_market_share_custodiantes.html,
  grafico_custodiantes_ativos.html   gráficos interativos
```

## Como executar

Requisitos: Python 3.10+. Crie o ambiente virtual (`.venv`, ignorado pelo git) e instale as dependências:

```
python -m venv .venv
.venv\Scripts\activate        # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
jupyter nbconvert --to notebook --execute --inplace analise_custodiantes_cvm.ipynb
```

(ou abra o notebook e use *Run All*, com o diretório do projeto como diretório de trabalho). Testes: `python test_custodiantes.py`. Se o download falhar, a execução é interrompida com erro; nenhuma cópia antiga é usada. A execução bem-sucedida reescreve `resultados/` e a seção abaixo.

## Gráficos

- **Fundos por custodiante:** HTML interativo em largura total (módulo `graficos.py`). Uma caixa de seleção escolhe os custodiantes exibidos (os 10 maiores por padrão, com busca por nome); os não selecionados são somados na linha tracejada "Outros". Filtro de intervalo de tempo por datas ou atalhos (Tudo, 20, 10, 5 e 1 ano). Exige acesso à internet para carregar o Plotly.js (CDN).
- **Market share:** mesma interface do gráfico anterior (`grafico_market_share_custodiantes.html`), exibindo a participação percentual de cada custodiante no total de vínculos fundo-custodiante da data. "Outros" soma a participação dos não selecionados; um fundo com dois custodiantes simultâneos conta em cada um.
- **Custodiantes ativos:** total mensal de custodiantes com ao menos um fundo sob custódia (gráfico separado, outra grandeza).
- No notebook há ainda um gráfico de concentração (participação do top 5).

## Resultados da última execução

<!-- RESULTADOS:INICIO -->
**Última extração bem-sucedida:** 21/10/2026 (cabeçalho HTTP `Last-Modified`: Wed, 21 Oct 2026 04:17:53 GMT)

| Indicador | Valor |
|---|---|
| Registros brutos / analisados | 73,005 / 72,989 |
| Fundos distintos no histórico | 54,933 |
| Custodiantes distintos no histórico | 118 |
| Série | 1990-08-31 a 2026-10-21 (435 datas) |
| Custodiantes ativos em 21/10/2026 | 95 |
| Fundos distintos sob custódia em 21/10/2026 | 41,349 |
| Pico de custodiantes ativos | 95 (2024-11-30) |

**Maiores custodiantes em 21/10/2026**

| CUSTODIANTE | CNPJ_CUSTODIANTE | QTD_FUNDOS |
|---|---|---|
| ITAU UNIBANCO S.A. | 60.701.190/0001-04 | 10,413 |
| BANCO BTG PACTUAL S/A | 30.306.294/0001-45 | 7,546 |
| BANCO BRADESCO S.A. | 60.746.948/0001-12 | 7,325 |
| S3 CACEIS BRASIL DISTRIBUIDORA DE TITULOS E VALORES MOBILIARIOS S.A | 62.318.407/0001-19 | 3,813 |
| BNY MELLON BANCO S.A. | 42.272.526/0001-70 | 3,509 |
| BANCO SAFRA S/A | 58.160.789/0001-28 | 1,997 |
| BANCO DO BRASIL S.A. | 00.000.000/0001-91 | 1,620 |
| BANCO DAYCOVAL S.A. | 62.232.889/0001-90 | 561 |
| BANCO BNP PARIBAS BRASIL S/A | 01.522.368/0001-82 | 505 |
| QI CORRETORA DE TÍTULOS E VALORES MOBILIÁRIOS S.A. | 62.285.390/0001-40 | 396 |
<!-- RESULTADOS:FIM -->

## Limitações

- Reflete apenas o arquivo da extração; não reconstrói versões anteriores publicadas pela CVM.
- A qualidade depende do cadastro: fundos sem registro de custodiante, datas incorretas ou relações sobrepostas afetam as contagens. Um fundo com dois custodiantes simultâneos conta uma vez em cada, e uma vez no total.
- Fim vazio é assumido como vigente, mesmo que o cadastro esteja desatualizado.
- A data da extração é a do download (data local), não a de publicação pela CVM.
- A última data de início/fim presente no CSV pode ser anterior à data da extração (em 21/10/2026 era 10/12/2025); depois dela a série fica constante porque o cadastro não registra novos eventos, não porque nada mudou no mercado.
- A contagem é de fundos, não de patrimônio.
