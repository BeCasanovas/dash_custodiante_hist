"""Gráfico interativo de linhas por custodiante (HTML autocontido com Plotly.js).

Os controles (seleção de custodiantes, intervalo de datas) rodam no navegador; os custodiantes
fora da seleção são somados na linha "Outros".
"""
from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd

PLOTLY_JS = "https://cdn.plot.ly/plotly-2.35.2.min.js"

_TEMPLATE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITULO__</title>
<script src="__PLOTLY_JS__"></script>
<style>
  html, body { margin: 0; height: 100%; font-family: system-ui, sans-serif; color: #222; background: #fff; }
  #app { display: flex; flex-direction: column; height: 100vh; min-height: 520px; }
  #controls { display: flex; flex-wrap: wrap; gap: 16px 28px; padding: 10px 16px; border-bottom: 1px solid #ddd; font-size: 13px; }
  fieldset { border: 1px solid #ccc; border-radius: 6px; margin: 0; padding: 6px 10px 8px; }
  legend { font-weight: 600; padding: 0 4px; }
  #lista { width: 380px; max-width: 80vw; height: 92px; overflow-y: auto; border: 1px solid #ddd; margin-top: 6px; padding: 2px 6px; }
  #lista label { display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; cursor: pointer; }
  button, input { font: inherit; }
  button { margin: 2px 4px 2px 0; padding: 2px 8px; cursor: pointer; }
  #busca { width: 160px; }
  #chart { flex: 1; min-height: 0; width: 100%; }
</style></head>
<body><div id="app">
  <div id="controls">
    <fieldset><legend>Custodiantes (os demais viram "Outros")</legend>
      <input id="busca" type="search" placeholder="Buscar nome...">
      <button id="top10">Top 10</button><button id="todos">Todos</button><button id="nenhum">Nenhum</button>
      <span id="contagem"></span>
      <div id="lista"></div>
    </fieldset>
    <fieldset><legend>Intervalo de tempo</legend>
      <label>De <input id="de" type="date"></label> <label>até <input id="ate" type="date"></label><br>
      <button data-anos="0">Tudo</button><button data-anos="20">20 anos</button>
      <button data-anos="10">10 anos</button><button data-anos="5">5 anos</button><button data-anos="1">1 ano</button>
    </fieldset>
  </div>
  <div id="chart"></div>
</div>
<script>
const D = __DADOS__;
const PAL = ["#1f77b4","#ff7f0e","#2ca02c","#d62728","#9467bd","#8c564b","#e377c2","#17becf","#bcbd22","#393b79",
              "#e6550d","#31a354","#756bb1","#636363","#843c39","#7b4173"];
const $ = id => document.getElementById(id);
const sel = new Set(D.padrao);
const dates = D.dates;
const total = dates.map((_, t) => D.series.reduce((s, x) => s + x.v[t], 0));

function montarLista(filtro) {
  const f = (filtro || "").toLowerCase();
  $("lista").innerHTML = "";
  D.series.forEach((s, i) => {
    if (f && !s.nome.toLowerCase().includes(f)) return;
    const l = document.createElement("label");
    const c = document.createElement("input");
    c.type = "checkbox"; c.checked = sel.has(i);
    c.onchange = () => { c.checked ? sel.add(i) : sel.delete(i); desenhar(); };
    l.append(c, " " + s.nome); l.title = s.nome;
    $("lista").append(l);
  });
}

function intervalo() {
  const de = $("de").value || dates[0], ate = $("ate").value || dates[dates.length - 1];
  return de <= ate ? [de, ate] : [ate, de];
}

function desenhar() {
  const idx = [...sel].sort((a, b) => a - b);
  const traces = idx.map((i, k) => ({
    type: "scatter", mode: "lines", x: dates, y: D.series[i].v, name: D.series[i].nome,
    line: { color: PAL[k % PAL.length], width: 2 },
    hovertemplate: "<b>%{fullData.name}</b><br>%{x|%d/%m/%Y}: %{y" + D.hoverY + "}<extra></extra>"
  }));
  if (idx.length < D.series.length) {
    const outros = dates.map((_, t) => Math.max(0, total[t] - idx.reduce((s, i) => s + D.series[i].v[t], 0)));
    traces.push({ type: "scatter", mode: "lines", x: dates, y: outros, name: "Outros",
      line: { color: "#888", width: 2, dash: "dash" },
      hovertemplate: "<b>Outros</b><br>%{x|%d/%m/%Y}: %{y" + D.hoverY + "}<extra></extra>" });
  }
  $("contagem").textContent = idx.length + " de " + D.series.length + " selecionados";
  Plotly.react("chart", traces, {
    title: { text: D.titulo }, margin: { l: 70, r: 20, t: 50, b: 60 },
    xaxis: { title: "Data de referência", range: intervalo(), tickformat: "%b/%Y" },
    yaxis: { title: D.eixoY, rangemode: "tozero", autorange: true, ticksuffix: D.sufixo },
    hovermode: "closest", legend: { orientation: "h", y: -0.12, yanchor: "top" }
  }, { responsive: true, displaylogo: false });
}

function recortar(anos) {
  const fim = dates[dates.length - 1];
  if (!anos) { $("de").value = dates[0]; $("ate").value = fim; }
  else {
    const d = new Date(fim); d.setFullYear(d.getFullYear() - anos);
    const ini = d.toISOString().slice(0, 10);
    $("de").value = ini < dates[0] ? dates[0] : ini; $("ate").value = fim;
  }
  desenhar();
}

$("de").min = $("ate").min = dates[0];
$("de").max = $("ate").max = dates[dates.length - 1];
$("de").onchange = $("ate").onchange = desenhar;
document.querySelectorAll("button[data-anos]").forEach(b => b.onclick = () => recortar(+b.dataset.anos));
$("busca").oninput = e => montarLista(e.target.value);
$("top10").onclick = () => { sel.clear(); D.padrao.forEach(i => sel.add(i)); montarLista($("busca").value); desenhar(); };
$("todos").onclick = () => { D.series.forEach((_, i) => sel.add(i)); montarLista($("busca").value); desenhar(); };
$("nenhum").onclick = () => { sel.clear(); montarLista($("busca").value); desenhar(); };
$("de").value = dates[0]; $("ate").value = dates[dates.length - 1];
montarLista(); desenhar();
</script></body></html>
"""


def _rotulos(nomes: pd.Series, cnpjs) -> list[str]:
    """Nome de exibição; só acrescenta o CNPJ quando dois custodiantes têm o mesmo nome."""
    lista = [nomes[c] for c in cnpjs]
    repetidos = {n for n in lista if lista.count(n) > 1}
    return [f"{n} ({c})" if n in repetidos else n for n, c in zip(lista, cnpjs)]


def montar_dados(serie: pd.DataFrame, nomes: pd.Series, titulo: str, eixo_y: str, top_n: int = 10) -> dict:
    """Matriz data x custodiante (valores em QTD_FUNDOS), ordenada pelo pico de cada custodiante."""
    piv = serie.pivot_table(index="DATA_REFERENCIA", columns="CNPJ_CUSTODIANTE", values="QTD_FUNDOS", fill_value=0)
    ordem = piv.max().sort_values(ascending=False).index
    piv = piv[ordem]
    return {
        "titulo": titulo, "eixoY": eixo_y, "hoverY": ":,", "sufixo": "",
        "dates": [d.strftime("%Y-%m-%d") for d in piv.index],
        "series": [{"nome": n, "v": piv[c].astype(float).round(4).tolist()}
                   for n, c in zip(_rotulos(nomes, ordem), ordem)],
        "padrao": list(range(min(top_n, len(ordem)))),
    }


def gerar_html(dados: dict) -> str:
    return (_TEMPLATE.replace("__TITULO__", html.escape(dados["titulo"]))
            .replace("__PLOTLY_JS__", PLOTLY_JS)
            .replace("__DADOS__", json.dumps(dados, ensure_ascii=False)))


def salvar(dados: dict, caminho: Path) -> str:
    doc = gerar_html(dados)
    caminho.write_text(doc, encoding="utf-8")
    return doc


def iframe(doc: str, altura: int = 900) -> str:
    """HTML para exibir o documento dentro do notebook, ocupando toda a largura."""
    return (f'<iframe srcdoc="{html.escape(doc, quote=True)}" width="100%" height="{altura}" '
            'style="border:0"></iframe>')
