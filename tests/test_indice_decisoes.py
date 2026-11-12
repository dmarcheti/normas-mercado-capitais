"""Testes do índice por decisão das decisões antigas (1978 a 2001): dados fictícios, sem rede."""
import os
import sys
import tempfile
import unittest
from unittest import mock

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))
sys.path.insert(0, AQUI)

import indice  # noqa: E402
import indice_decisoes as idc  # noqa: E402
from test_indice_citacoes import NORMAS  # noqa: E402
from test_validar_julgados import BASE, montar  # noqa: E402

# Nome fictício montado por concatenação (nenhum dado real no repositório).
NOME = "ZEFE" + "RINO QUAR" + "TAMENTE"
PROC = "RJ" + "1999/" + "1234"


# Vocabulário comum em minúsculas (o filtro de nomes só troca palavra que não é vocabulário).
VOCABULARIO = "pedido ressarcimento corretora consulta emissão notas promissórias aumento capital"


def arquivo_anual(ano, atas):
    """atas: [(numero, dd.mm.aaaa, [(titulo, corpo)])]."""
    out = ["# Decisões do Colegiado %d" % ano, ""] + [VOCABULARIO] * 6 + [""]
    for numero, data, decs in atas:
        out += ["## ATA DA REUNIÃO DO COLEGIADO Nº %s DE %s" % (numero, data), ""]
        for titulo, corpo in decs:
            out += ["### " + titulo, "", corpo, ""]
    return "\n".join(out) + "\n"


CORPO = "O Colegiado decidiu, por unanimidade, aprovar o pedido, nos termos do voto do relator."


class TestLerDecisoes(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def gravar(self, ano, texto):
        p = os.path.join(self.d, "%d.md" % ano)
        with open(p, "w", encoding="utf-8") as f:
            f.write(texto)
        return p

    def test_uma_linha_por_decisao_com_data_ata_e_linha(self):
        p = self.gravar(1985, arquivo_anual(1985, [
            ("12", "05.03.1985", [("CONSULTA SOBRE DEBÊNTURES CONVERSÍVEIS", CORPO),
                                  ("EMISSÃO DE NOTAS PROMISSÓRIAS – CIA EXEMPLO", CORPO)]),
            ("13", "19.03.1985", [("AUMENTO DE CAPITAL POR SUBSCRIÇÃO PÚBLICA", CORPO)])]))
        ds, cont = idc.ler_decisoes({1985: p})
        self.assertEqual(cont.decisoes, 3)
        self.assertEqual([(x["data"], x["ata"]) for x in ds],
                         [("1985-03-05", "12"), ("1985-03-05", "12"), ("1985-03-19", "13")])
        self.assertEqual(ds[0]["titulo"], "CONSULTA SOBRE DEBÊNTURES CONVERSÍVEIS")
        self.assertEqual(ds[0]["arquivo"], "cvm/decisoes-antigas/1985.md")
        with open(p, encoding="utf-8") as f:
            linhas = f.read().split("\n")
        for x in ds:
            self.assertTrue(linhas[x["linha"] - 1].startswith("### "))

    def test_nome_de_pessoa_fisica_sai_do_titulo(self):
        p = self.gravar(1990, arquivo_anual(1990, [
            ("5", "10.04.1990", [("RECLAMAÇÃO – " + NOME + " – PEDIDO DE RESSARCIMENTO", CORPO)])]))
        ds, cont = idc.ler_decisoes({1990: p})
        self.assertEqual(len(ds), 1)
        self.assertNotIn("ZEFE" + "RINO", ds[0]["titulo"])
        self.assertNotIn("QUAR" + "TAMENTE", ds[0]["titulo"])
        self.assertIn("[pessoa física]", ds[0]["titulo"])
        self.assertEqual(cont.nomes_trocados, 1)

    def test_empresa_nao_e_trocada(self):
        p = self.gravar(1990, arquivo_anual(1990, [
            ("5", "10.04.1990", [("CONSULTA DA AÇOS EXEMPLO S.A. – REGISTRO DE EMISSÃO", CORPO)])]))
        ds, cont = idc.ler_decisoes({1990: p})
        self.assertIn("EXEMPLO S.A.", ds[0]["titulo"])
        self.assertEqual(cont.nomes_trocados, 0)

    def test_linha_de_participante_e_ruido(self):
        p = self.gravar(1998, arquivo_anual(1998, [
            ("7", "02.02.1998", [("JOSÉ FULANO DA SILVA – Presidente", CORPO),
                                 ("PARTICIPANTES", CORPO),
                                 ("PEDIDO DE DISPENSA DE REGISTRO DE DISTRIBUIÇÃO", CORPO)])]))
        ds, cont = idc.ler_decisoes({1998: p})
        self.assertEqual([x["titulo"] for x in ds], ["PEDIDO DE DISPENSA DE REGISTRO DE DISTRIBUIÇÃO"])
        self.assertEqual(cont.ruido, 2)

    def test_processo_vem_do_texto_da_decisao(self):
        p = self.gravar(1999, arquivo_anual(1999, [
            ("3", "09.03.1999", [("INQUÉRITO ADMINISTRATIVO SOBRE NEGOCIAÇÃO DE AÇÕES",
                                  "Processo CVM " + PROC + "\n" + CORPO)])]))
        ds, _ = idc.ler_decisoes({1999: p})
        self.assertIn("1999-1234", ds[0]["processo"])

    def test_data_na_linha_seguinte_quando_a_ata_quebrou(self):
        texto = ("## ATA DA REUNIÃO DO COLEGIADO Nº 9 DE\n\n04.06.1980\n\n"
                 "### CONSULTA SOBRE AÇÕES ESCRITURAIS\n\n" + CORPO + "\n")
        p = self.gravar(1980, texto)
        ds, _ = idc.ler_decisoes({1980: p})
        self.assertEqual((ds[0]["data"], ds[0]["ata"]), ("1980-06-04", "9"))

    def test_ata_repetida_em_dois_arquivos_conta_uma_vez(self):
        ata = [("20", "28.12.1985", [("CONSULTA SOBRE DEBÊNTURES CONVERSÍVEIS", CORPO)])]
        a = self.gravar(1985, arquivo_anual(1985, ata))
        b = self.gravar(1986, arquivo_anual(1986, ata))
        ds, cont = idc.ler_decisoes({1985: a, 1986: b})
        self.assertEqual(cont.decisoes, 1)
        self.assertEqual(cont.duplicadas, 1)
        self.assertEqual(ds[0]["ano"], 1985)

    def test_titulo_longo_e_cortado_com_reticencias(self):
        longo = " ".join(["CONSULTA"] + ["PALAVRA"] * 40)
        self.assertLessEqual(len(idc._curto(longo)), idc.TITULO_MAX + 1)
        self.assertTrue(idc._curto(longo).endswith("…"))
        self.assertEqual(idc._curto("CURTO"), "CURTO")


class TestIndiceDasDecisoesAntigas(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = os.path.join(self._tmp.name, "julgados")

    def tearDown(self):
        self._tmp.cleanup()

    def anual(self, ano, atas):
        rel = "cvm/decisoes-antigas/%d.md" % ano
        p = os.path.join(self.raiz, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        corpo = arquivo_anual(ano, atas)
        with open(p, "w", encoding="utf-8") as f:
            f.write(montar(dict(BASE, id="cvm-col-%d-antigas" % ano, tipo="decisao-antiga",
                                data="%d-12-31" % ano, ementa="", tema="", tema_fonte="",
                                normas_citadas="", dispositivos_citados=""), corpo))

    def gerar(self):
        return indice.gerar_indice_julgados(self.raiz, NORMAS)[0]

    def test_ano_pequeno_tem_um_subindice_com_uma_linha_por_ficha(self):
        self.anual(1985, [("12", "05.03.1985", [("CONSULTA SOBRE DEBÊNTURES CONVERSÍVEIS", CORPO),
                                                ("AUMENTO DE CAPITAL POR SUBSCRIÇÃO", CORPO)])])
        arqs = self.gerar()
        self.assertIn("indices/decisao-antiga-1985.md", arqs)
        md = arqs["indices/decisao-antiga-1985.md"]
        self.assertIn("| Data da ata | Processo | Título | Id | Ficha |", md)
        self.assertIn("| 1985-03-05 | — | CONSULTA SOBRE DEBÊNTURES CONVERSÍVEIS | cvm-col-1985-antigas-0001 | "
                      "fichas/decisoes-antigas/1985.md |", md)
        self.assertIn("| 1985-03-05 | — | AUMENTO DE CAPITAL POR SUBSCRIÇÃO | cvm-col-1985-antigas-0002 | "
                      "fichas/decisoes-antigas/1985.md |", md)
        self.assertEqual(md.count("fichas/decisoes-antigas/1985.md"), 2)  # uma linha por ficha, não por ano
        self.assertNotIn("julgados/cvm/decisoes-antigas", md)
        self.assertIn("(indices/decisao-antiga-1985.md)", arqs["indice.md"])

    def test_linha_do_indice_acha_a_ficha_em_memoria(self):
        self.anual(1985, [("12", "05.03.1985", [("CONSULTA SOBRE DEBÊNTURES CONVERSÍVEIS", CORPO),
                                                ("AUMENTO DE CAPITAL POR SUBSCRIÇÃO", CORPO)])])
        _f, arquivos, _i = indice.fch.montar(self.raiz)
        por_id = indice.fch.ids_por_arquivo(arquivos)
        md = self.gerar()["indices/decisao-antiga-1985.md"]
        linhas = [l for l in md.split("\n") if l.startswith("| 1985-")]
        self.assertEqual(len(linhas), 2)
        for l in linhas:
            cel = [c.strip() for c in l.strip("|").split("|")]
            self.assertEqual(por_id[cel[3]], cel[4])

    def test_ano_grande_divide_por_semestre_e_cada_parte_tem_link(self):
        self.anual(1999, [("1", "05.02.1999", [("CONSULTA SOBRE DEBÊNTURES CONVERSÍVEIS", CORPO)]),
                          ("2", "05.09.1999", [("AUMENTO DE CAPITAL POR SUBSCRIÇÃO", CORPO)])])
        with mock.patch.object(indice, "LIMITE_SUBINDICE", 150):
            arqs = self.gerar()
        self.assertNotIn("indices/decisao-antiga-1999.md", arqs)
        s1, s2 = arqs["indices/decisao-antiga-1999-s1.md"], arqs["indices/decisao-antiga-1999-s2.md"]
        self.assertIn("1999-02-05 | — | CONSULTA SOBRE DEBÊNTURES CONVERSÍVEIS | cvm-col-1999-antigas-0001 | "
                      "fichas/decisoes-antigas/1999.md", s1)
        self.assertNotIn("1999-09-05", s1)
        self.assertIn("1999-09-05", s2)
        for rel in ("indices/decisao-antiga-1999-s1.md", "indices/decisao-antiga-1999-s2.md"):
            self.assertIn("(%s)" % rel, arqs["indice.md"])

    def test_pessoa_fisica_nao_aparece_em_nenhum_arquivo_gerado(self):
        self.anual(1990, [("5", "10.04.1990", [("RECLAMAÇÃO – " + NOME + " – PEDIDO DE RESSARCIMENTO", CORPO)])])
        for rel, md in self.gerar().items():
            self.assertNotIn("ZEFE" + "RINO", md, rel)
            self.assertNotIn("QUAR" + "TAMENTE", md, rel)

    def test_titulo_e_a_ementa_da_ficha_com_a_marca_de_pessoa_fisica(self):
        self.anual(1990, [("5", "10.04.1990", [("RECLAMAÇÃO – " + NOME + " – PEDIDO DE RESSARCIMENTO", CORPO)])])
        md = self.gerar()["indices/decisao-antiga-1990.md"]
        self.assertIn("| RECLAMAÇÃO – [pessoa física] – PEDIDO DE RESSARCIMENTO |", md)

    def test_titulo_longo_sai_com_ate_140_caracteres_e_reticencias(self):
        longo = "CONSULTA SOBRE " + " ".join(["EMISSÃO"] * 40)
        self.anual(1985, [("12", "05.03.1985", [(longo, CORPO)])])
        md = self.gerar()["indices/decisao-antiga-1985.md"]
        linha = next(l for l in md.split("\n") if l.startswith("| 1985-"))
        titulo = [c.strip() for c in linha.strip("|").split("|")][2]
        self.assertLessEqual(len(titulo), indice.EMENTA_CURTA)
        self.assertTrue(titulo.endswith("…"))

    def test_geracao_e_estavel(self):
        self.anual(1985, [("12", "05.03.1985", [("CONSULTA SOBRE DEBÊNTURES CONVERSÍVEIS", CORPO)])])
        self.assertEqual(self.gerar(), self.gerar())


if __name__ == "__main__":
    unittest.main()
