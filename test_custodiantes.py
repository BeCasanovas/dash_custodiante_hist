"""Testes com dados sintéticos: python -m pytest test_custodiantes.py (ou python test_custodiantes.py)."""
import pandas as pd

import custodiantes as c

EXT = pd.Timestamp("2024-06-15")


def _df(linhas):
    return pd.DataFrame(linhas, columns=c.COLUNAS)


def _serie(linhas):
    d, log = c.preparar(_df(linhas))
    t, tot = c.serie_historica(d, EXT)
    return d, log, t.set_index(["DATA_REFERENCIA", "CNPJ_CUSTODIANTE"])["QTD_FUNDOS"], tot.set_index("DATA_REFERENCIA")


def L(f, cust, ini, fim, nome=None):
    return [f, "2020-01-01", cust, nome if nome is not None else f"NOME {cust}", ini, fim]


def test_semiaberto_transferencia_mesma_data():
    # A termina e B começa em 2023-03-31: no dia, só B conta.
    _, _, s, tot = _serie([L("F1", "A", "2023-01-10", "2023-03-31"), L("F1", "B", "2023-03-31", "")])
    assert s[(pd.Timestamp("2023-02-28"), "A")] == 1
    assert (pd.Timestamp("2023-03-31"), "A") not in s.index
    assert s[(pd.Timestamp("2023-03-31"), "B")] == 1
    assert tot.loc["2023-03-31", "QTD_FUNDOS_DISTINTOS_TOTAL"] == 1


def test_nao_iniciada_e_encerrada():
    _, _, s, _ = _serie([L("F1", "A", "2023-01-10", "2023-02-10"), L("F2", "A", "2023-04-10", "")])
    assert s[(pd.Timestamp("2023-01-31"), "A")] == 1      # F2 ainda não iniciou
    assert (pd.Timestamp("2023-02-28"), "A") not in s.index  # F1 encerrada, F2 não iniciou
    assert s[(pd.Timestamp("2023-04-30"), "A")] == 1


def test_fim_vazio_vigente_ate_extracao_e_serie_termina_na_extracao():
    d, _, s, tot = _serie([L("F1", "A", "2024-01-01", "")])
    assert tot.index.max() == EXT
    assert s[(EXT, "A")] == 1
    assert tot.index.is_monotonic_increasing and tot.index.is_unique


def test_fundo_distinto_nao_linhas():
    # duas linhas sobrepostas do mesmo fundo/custodiante + duplicata exata -> 1 fundo
    d, log, s, _ = _serie([L("F1", "A", "2023-01-01", ""), L("F1", "A", "2023-02-01", "2023-05-01"),
                           L("F1", "A", "2023-01-01", "")])
    assert s[(pd.Timestamp("2023-03-31"), "A")] == 1
    assert len(d) == 2


def test_custodiante_ativo_exclui_encerrados():
    _, _, s, tot = _serie([L("F1", "A", "2023-01-01", "2023-03-01"), L("F2", "B", "2023-01-01", "")])
    assert tot.loc["2023-06-30", "QTD_CUSTODIANTES_ATIVOS"] == 1
    assert tot.loc["2023-01-31", "QTD_CUSTODIANTES_ATIVOS"] == 2


def test_total_fundos_nao_dupla_conta_fundo_com_dois_custodiantes():
    _, _, s, tot = _serie([L("F1", "A", "2023-01-01", ""), L("F1", "B", "2023-01-01", "")])
    assert tot.loc["2023-06-30", "QTD_FUNDOS_DISTINTOS_TOTAL"] == 1
    assert tot.loc["2023-06-30", "QTD_CUSTODIANTES_ATIVOS"] == 2


def test_qualidade_e_cnpj_string():
    d, log, _, _ = _serie([L("F1", "00.111", "2023-01-01", ""), L("F2", "A", "2023-05-01", "2023-04-01"),
                           L("F3", "A", "xx", ""), L("F4", "A", "2023-01-01", "2023-01-01")])
    assert str(d["CNPJ_CUSTODIANTE"].iloc[0]) == "00.111"
    assert len(d) == 2  # invertida e data inválida descartadas
    assert log.set_index("verificacao").loc["DT_FIM < DT_INI (intervalo invertido)", "linhas"] == 1


def test_nome_ausente_usa_cnpj_e_nome_mais_recente():
    d, _ = c.preparar(_df([L("F1", "A", "2020-01-01", "2021-01-01", nome="ANTIGO"),
                           L("F2", "A", "2022-01-01", "", nome="NOVO"), L("F3", "B", "2020-01-01", "", nome="")]))
    n = c.nomes_exibicao(d)
    assert n["A"] == "NOVO" and n["B"] == "B"


def test_ler_csv_encodings_e_delimitador():
    cab = ";".join(c.COLUNAS)
    linha = "00.000.001/0001-00;2020-01-01;00.111.222/0001-33;BANCO SÃO JOÃO;2020-01-01;"
    for enc in ("utf-8-sig", "cp1252"):
        df, info = c.ler_csv((cab + "\n" + linha + "\n").encode(enc))
        assert df["CUSTODIANTE"].iloc[0] == "BANCO SÃO JOÃO"
        assert df["CNPJ_CUSTODIANTE"].iloc[0].startswith("00.")
        assert info["delimitador"] == ";"


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_"):
            fn()
            print("ok", nome)
