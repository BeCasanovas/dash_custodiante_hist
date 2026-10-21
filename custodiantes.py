"""Funções da análise histórica de custodiantes de fundos da CVM.

Usadas por analise_custodiantes_cvm.ipynb e testadas em test_custodiantes.py.
"""
from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

URL_ZIP = "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/cad_fi_hist.zip"
COLUNAS = ["CNPJ_FUNDO", "DT_REG", "CNPJ_CUSTODIANTE", "CUSTODIANTE",
           "DT_INI_CUSTODIANTE", "DT_FIM_CUSTODIANTE"]
COLUNAS_DATA = ["DT_REG", "DT_INI_CUSTODIANTE", "DT_FIM_CUSTODIANTE"]
ENCODINGS = ("utf-8-sig", "cp1252")


class DadosIndisponiveisError(RuntimeError):
    """Não foi possível obter ou validar a base oficial da CVM."""


# --------------------------------------------------------------------------
# Obtenção
# --------------------------------------------------------------------------
def baixar_zip(url: str = URL_ZIP, timeout: int = 120) -> tuple[bytes, dict]:
    """Baixa o ZIP e valida status HTTP, tamanho e integridade. Retorna (bytes, metadados)."""
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise DadosIndisponiveisError(f"Falha ao baixar {url}: {exc}") from exc
    conteudo = resp.content
    if not conteudo:
        raise DadosIndisponiveisError("Download retornou conteúdo vazio.")
    esperado = resp.headers.get("Content-Length")
    if esperado and esperado.isdigit() and int(esperado) != len(conteudo) \
            and not resp.headers.get("Content-Encoding"):
        raise DadosIndisponiveisError(
            f"Download incompleto: {len(conteudo)} bytes de {esperado}.")
    try:
        with zipfile.ZipFile(io.BytesIO(conteudo)) as zf:
            corrompido = zf.testzip()
    except zipfile.BadZipFile as exc:
        raise DadosIndisponiveisError(f"Arquivo ZIP inválido: {exc}") from exc
    if corrompido:
        raise DadosIndisponiveisError(f"ZIP corrompido (membro {corrompido}).")
    meta = {"url": url, "bytes": len(conteudo), "last_modified": resp.headers.get("Last-Modified")}
    return conteudo, meta


def localizar_csv_custodiante(zf: zipfile.ZipFile) -> str:
    """Localiza no ZIP o CSV de custodiantes, sem presumir o caminho interno."""
    candidatos = [n for n in zf.namelist()
                  if n.lower().endswith(".csv") and "custodiante" in Path(n).name.lower()]
    if len(candidatos) != 1:
        raise DadosIndisponiveisError(
            f"Esperava exatamente 1 CSV de custodiante no ZIP; encontrados: {candidatos}")
    return candidatos[0]


def ler_csv(dados: bytes) -> tuple[pd.DataFrame, dict]:
    """Lê o CSV detectando codificação e delimitador; CNPJs e demais campos como string."""
    texto, enc_usada = None, None
    for enc in ENCODINGS:
        try:
            texto, enc_usada = dados.decode(enc), enc
            break
        except UnicodeDecodeError:
            continue
    if texto is None:
        raise DadosIndisponiveisError("Não foi possível decodificar o CSV.")
    cabecalho = texto.split("\n", 1)[0]
    try:
        delim = csv.Sniffer().sniff(cabecalho, delimiters=";,\t|").delimiter
    except csv.Error as exc:
        raise DadosIndisponiveisError("Delimitador do CSV não identificado.") from exc
    df = pd.read_csv(io.StringIO(texto), sep=delim, dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    faltantes = [c for c in COLUNAS if c not in df.columns]
    if faltantes:
        raise DadosIndisponiveisError(f"Colunas ausentes no CSV: {faltantes}")
    if df.empty:
        raise DadosIndisponiveisError("CSV sem linhas.")
    return df[COLUNAS], {"encoding": enc_usada, "delimitador": delim}


def atualizar_base(destino: Path, url: str = URL_ZIP) -> tuple[pd.DataFrame, dict]:
    """Baixa a base oficial, atualiza a cópia local em `destino` e devolve (df bruto, metadados).

    Falhas levantam DadosIndisponiveisError; a cópia local antiga nunca é usada em silêncio.
    """
    conteudo, meta = baixar_zip(url)
    with zipfile.ZipFile(io.BytesIO(conteudo)) as zf:
        nome = localizar_csv_custodiante(zf)
        bruto = zf.read(nome)
    df, info = ler_csv(bruto)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(bruto)
    meta.update(info, csv_no_zip=nome,
                data_extracao=pd.Timestamp.now().normalize())
    return df, meta


# --------------------------------------------------------------------------
# Preparação
# --------------------------------------------------------------------------
def preparar(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Converte tipos e remove registros inutilizáveis. Retorna (df limpo, log de qualidade)."""
    d = df.copy()
    for c in COLUNAS:
        d[c] = d[c].astype("string").str.strip()
    d = d.replace({"": pd.NA})
    log = []

    def registrar(regra, n, tratamento):
        log.append({"verificacao": regra, "linhas": int(n), "tratamento": tratamento})

    registrar("Linhas lidas", len(d), "—")
    for c in COLUNAS_DATA:
        orig = d[c]
        d[c] = pd.to_datetime(orig, format="%Y-%m-%d", errors="coerce")
        registrar(f"{c}: valor preenchido porém inválido", (orig.notna() & d[c].isna()).sum(),
                  "tratada como ausente (descartada se for DT_INI_CUSTODIANTE)"
                  if c == "DT_INI_CUSTODIANTE" else "tratada como ausente")
    registrar("DT_FIM_CUSTODIANTE vazia (relação vigente)", d["DT_FIM_CUSTODIANTE"].isna().sum(),
              "mantida; vigente até a data de extração")

    for c in ("CNPJ_FUNDO", "CNPJ_CUSTODIANTE"):
        m = d[c].isna()
        registrar(f"{c} ausente", m.sum(), "linha descartada")
        d = d[~m]
    m = d["DT_INI_CUSTODIANTE"].isna()
    registrar("DT_INI_CUSTODIANTE ausente/inválida", m.sum(), "linha descartada (vigência indeterminável)")
    d = d[~m]
    m = d["DT_FIM_CUSTODIANTE"].notna() & (d["DT_FIM_CUSTODIANTE"] < d["DT_INI_CUSTODIANTE"])
    registrar("DT_FIM < DT_INI (intervalo invertido)", m.sum(), "linha descartada")
    d = d[~m]
    m = d["DT_FIM_CUSTODIANTE"].notna() & (d["DT_FIM_CUSTODIANTE"] == d["DT_INI_CUSTODIANTE"])
    registrar("DT_FIM = DT_INI (vigência de duração zero)", m.sum(),
              "mantida; nunca é contada no intervalo semiaberto")
    m = d.duplicated()
    registrar("Duplicatas exatas", m.sum(), "removidas (mantida 1 ocorrência)")
    d = d[~m]
    registrar("Linhas finais analisadas", len(d), "—")
    return d.reset_index(drop=True), pd.DataFrame(log)


def nomes_exibicao(d: pd.DataFrame) -> pd.Series:
    """Nome mais recente (por DT_INI) não vazio de cada CNPJ_CUSTODIANTE; fallback = o CNPJ."""
    com_nome = d.dropna(subset=["CUSTODIANTE"]).sort_values("DT_INI_CUSTODIANTE")
    nomes = com_nome.groupby("CNPJ_CUSTODIANTE")["CUSTODIANTE"].last()
    todos = pd.Index(d["CNPJ_CUSTODIANTE"].unique(), name="CNPJ_CUSTODIANTE")
    return pd.Series(todos, index=todos).where(~todos.isin(nomes.index), nomes.reindex(todos)).rename("CUSTODIANTE")


# --------------------------------------------------------------------------
# Série histórica
# --------------------------------------------------------------------------
def intervalos(d: pd.DataFrame, data_extracao: pd.Timestamp) -> pd.DataFrame:
    """Intervalos semiabertos [INI, FIM). Vigente sem fim -> FIM = extração + 1 dia."""
    out = d[["CNPJ_FUNDO", "CNPJ_CUSTODIANTE", "DT_INI_CUSTODIANTE", "DT_FIM_CUSTODIANTE"]].copy()
    out.columns = ["fundo", "cust", "ini", "fim"]
    out["fim"] = out["fim"].fillna(data_extracao + pd.Timedelta(days=1))
    return out


def unir_intervalos(iv: pd.DataFrame, chaves: list[str]) -> pd.DataFrame:
    """Une intervalos sobrepostos/contíguos por chave, para contar cada chave no máximo uma vez."""
    iv = iv.sort_values(chaves + ["ini", "fim"]).reset_index(drop=True)
    fim_acum = iv.groupby(chaves)["fim"].cummax()
    fim_ant = fim_acum.groupby([iv[c] for c in chaves]).shift()
    novo_bloco = fim_ant.isna() | (iv["ini"] > fim_ant)
    bloco = novo_bloco.cumsum()
    return iv.groupby(bloco).agg(**{c: (c, "first") for c in chaves},
                                 ini=("ini", "min"), fim=("fim", "max")).reset_index(drop=True)


def datas_referencia(d: pd.DataFrame, data_extracao: pd.Timestamp) -> pd.DatetimeIndex:
    """Fins de mês desde o mês da primeira relação até a extração, mais a própria extração."""
    inicio = d["DT_INI_CUSTODIANTE"].min() + pd.offsets.MonthEnd(0)
    datas = pd.date_range(inicio, data_extracao, freq="ME")
    if len(datas) == 0 or datas[-1] != data_extracao:
        datas = datas.append(pd.DatetimeIndex([data_extracao]))
    return datas


def serie_historica(d: pd.DataFrame, data_extracao: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retorna (tabela longa DATA x CUSTODIANTE com QTD_FUNDOS, totais por data)."""
    iv = intervalos(d, data_extracao)
    por_cust = unir_intervalos(iv, ["cust", "fundo"])
    por_fundo = unir_intervalos(iv, ["fundo"])
    nomes = nomes_exibicao(d)
    longo, totais = [], []
    for ref in datas_referencia(d, data_extracao):
        v = por_cust[(por_cust["ini"] <= ref) & (ref < por_cust["fim"])]
        cont = v.groupby("cust").size()
        longo.append(pd.DataFrame({"DATA_REFERENCIA": ref, "CNPJ_CUSTODIANTE": cont.index,
                                   "QTD_FUNDOS": cont.to_numpy()}))
        n_fundos = int(((por_fundo["ini"] <= ref) & (ref < por_fundo["fim"])).sum())
        totais.append({"DATA_REFERENCIA": ref, "QTD_CUSTODIANTES_ATIVOS": len(cont),
                       "QTD_FUNDOS_DISTINTOS_TOTAL": n_fundos})
    tabela = pd.concat(longo, ignore_index=True)
    tabela["CUSTODIANTE"] = tabela["CNPJ_CUSTODIANTE"].map(nomes)
    tabela = tabela[["DATA_REFERENCIA", "CNPJ_CUSTODIANTE", "CUSTODIANTE", "QTD_FUNDOS"]]
    return tabela, pd.DataFrame(totais)
