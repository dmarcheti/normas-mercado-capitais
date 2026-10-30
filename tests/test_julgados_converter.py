"""Testes da conversão dos julgados: fixtures sintéticas e PDFKit/OCR falsos (sem rede, sem swift)."""
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import julgados_baixar as jb  # noqa: E402
import julgados_comum as jc  # noqa: E402
import julgados_converter as conv  # noqa: E402
import pdf_macos  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "julgados")
B = jc.BASE
CPF = "123.456." + "789-09"  # montado em partes: nenhum CPF literal no repositório


def fixture(nome):
    with open(os.path.join(FIX, nome), "rb") as f:
        return f.read()


class PdfFalso:
    """Substitui pdf_macos: texto por nome de arquivo; OCR opcional."""

    ErroPdfMacos = pdf_macos.ErroPdfMacos

    def __init__(self, textos, ocr=None):
        self.textos, self._ocr = textos, ocr
        self.ocr_chamado = 0

    def texto_pdfkit(self, path):
        return self.textos[os.path.basename(path)]

    def ocr(self, path, detalhe=False):
        self.ocr_chamado += 1
        if self._ocr is None:
            raise pdf_macos.ErroPdfMacos("sem macOS")
        return self._ocr[os.path.basename(path)], [0.91] * 10


def montar_cache(pasta, arquivos):
    """Grava os arquivos e um registro.json como o de julgados_baixar. `arquivos`:
    [(papel, rótulo, url, nome local, bytes, content-type)]."""
    os.makedirs(pasta, exist_ok=True)
    reg = {"arquivos": [], "completo": True}
    for papel, rot, url, nome, dados, ct in arquivos:
        with open(os.path.join(pasta, nome), "wb") as f:
            f.write(dados)
        reg["arquivos"].append({"papel": papel, "rotulo": rot, "url": url, "url_final": url,
                                "arquivo": nome, "tamanho": len(dados),
                                "sha256": hashlib.sha256(dados).hexdigest(),
                                "baixado_em": "2026-10-30", "content_type": ct})
    with open(os.path.join(pasta, "registro.json"), "w", encoding="utf-8") as f:
        json.dump(reg, f)
    return reg


def frontmatter(md):
    bloco = md.split("---\n")[1]
    return dict(x.split(":", 1) if ":" in x else (x, "") for x in bloco.strip().split("\n"))


COL = {"id": "cvm-col-20251202-d3228", "tipo": "termo-compromisso", "classe": "",
       "processo": "19957.000123/2023-45", "nup": "19957-000123-2023-45",
       "data": "2025-12-02", "url": B + "/decisoes/2025/20251202_R1/20251202_D3228.html",
       "titulo": "APRECIAÇÃO DE PROPOSTA DE TERMO DE COMPROMISSO", "incerteza": [],
       "resultado": "aceito"}
PAS = {"id": "cvm-pas-19957-000456-2024-51", "tipo": "pas", "classe": "",
       "processo": "19957.000456/2024-51", "nup": "19957-000456-2024-51", "data": "2025-05-27",
       "url": B + "/sancionadores/sancionador/2025/20250527_PAS.html", "titulo": "PAS",
       "incerteza": []}
PDF_PAS = B + "/export/sites/cvm/sancionadores/sancionador/anexos/2025/SEI_19957000456_2024_51.pdf"

RODAPE = "Relatório DFP (1222196) SEI 19957.000456/2024-51 / pg. %d"
CAB = "COMISSÃO DE VALORES MOBILIÁRIOS\nRelator: Diretor Fulano Exemplo\n"
PAGINAS_PAS = [
    CAB + "EXTRATO DE SESSÃO DE JULGAMENTO\nData do julgamento: 27/05/2025\n"
          "O Colegiado decidiu aplicar multa de R$ 500.000,00 ao acusado.\n" + RODAPE % 1,
    CAB + "RELATÓRIO\nI. OBJETO\nTrata-se de processo sobre deveres fiduciários do administrador "
          "conforme a Resolução CVM nº 62.\n" + RODAPE % 2,
    "   ",
    CAB + "VOTO\nII. MÉRITO\nEntendo comprovada a infração apontada pela acusação.\n" + RODAPE % 4,
]


class PecasTest(unittest.TestCase):
    def test_tirar_repetidas_com_numero_de_pagina(self):
        texto, n = conv.tirar_repetidas([p for p in PAGINAS_PAS if p.strip()])
        self.assertEqual(n, 9)
        self.assertNotIn("COMISSÃO DE VALORES", texto)
        self.assertNotIn("pg. 2", texto)
        self.assertIn("RELATÓRIO", texto)  # cabeçalho de peça fica

    def test_segmentar(self):
        s = conv.segmentar("Preâmbulo da peça\n\nRELATÓRIO\nFatos.\n\n# 1\nVOTO DO DIRETOR X\n"
                           "Mérito.\nDECLARAÇÃO DE VOTO\nConcordo.")
        self.assertEqual([x for x, _ in s], ["Texto", "Relatório", "Voto", "Declaração de voto"])
        self.assertEqual(s[1][1], "Fatos.\n\n\\# 1")  # '#' de PDF escapado
        self.assertTrue(s[2][1].startswith("VOTO DO DIRETOR X"))
        self.assertEqual(conv.segmentar("Sem cabeçalho nenhum."), [("Texto", "Sem cabeçalho nenhum.")])

    def test_resultado_conservador(self):
        self.assertEqual(conv.resultado("decisao-colegiado", "O Colegiado deferiu o pedido.", {}),
                         "deferido")
        self.assertEqual(conv.resultado("decisao-colegiado", "deferiu um e indeferiu outro", {}), "")
        self.assertEqual(conv.resultado("termo-compromisso", "deliberou rejeitar a proposta", {}),
                         "rejeitado")
        pas = "## Extrato\n\nEXTRATO DE SESSÃO\nabsolver o acusado A e aplicar multa ao B\n## Voto"
        self.assertEqual(conv.resultado("pas", pas, {}), "")

    def test_relator_e_rito(self):
        self.assertEqual(conv.relator_do_texto("x\nDiretora Relatora: Beltrana Exemplo.\n"),
                         "Beltrana Exemplo")
        self.assertEqual(conv.rito_do_texto("rito simplificado ... rito ordinário"), "")
        self.assertEqual(conv.rito_do_texto("pelo rito simplificado"), "simplificado")


class ConverterTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.raiz = self.dir.name

    def tearDown(self):
        self.dir.cleanup()

    def pasta(self, item):
        return jb.pasta_do_item(item, os.path.join(self.raiz, "cache"))

    def gravar_e_validar(self, valores, corpo):
        caminho = conv.gravar_julgado(valores, corpo, self.raiz)
        with open(caminho, encoding="utf-8") as f:
            md = f.read()
        try:
            import validar
            self.assertEqual(validar.validar_julgado(caminho), [])
        except ImportError:
            pass
        return caminho, md

    def test_colegiado_com_anexo_termo_sei_e_alheio(self):
        pagina = fixture("colegiado-item.html").replace(b"__CPF__", CPF.encode())
        anexo = B + "/export/sites/cvm/decisoes/anexos/2025/20251202/3228_25.pdf"
        montar_cache(self.pasta(COL), [
            ("pagina", "X", COL["url"], "01-pagina.html", pagina, "text/html; charset=utf-8"),
            ("anexo", "PARECER DO COMITÊ", anexo, "02-anexo.pdf", b"%PDF-1", "application/pdf"),
            ("anexo", "TERMO ADITIVO AO CONVÊNIO", anexo + "x", "03-anexo.pdf", b"%PDF-2",
             "application/pdf"),
            ("termo", "termo de compromisso", "https://sei.cvm.gov.br/sei/publicacoes/x?id=1",
             "04-termo.html", fixture("sei-termo.html"), "text/html"),
        ])
        pm = PdfFalso({"02-anexo.pdf": "Parecer do Comitê de Termo de Compromisso sobre a "
                                       "proposta, que o Comitê recomenda aceitar.",
                       "03-anexo.pdf": "CLÁUSULAS DO CONVÊNIO XYZ entre órgãos públicos."})
        with mock.patch.object(conv, "_pypdf_paginas", return_value=None):
            valores, corpo, cv = conv.converter_item(COL, self.pasta(COL), pm)
        self.assertNotIn(CPF, corpo)
        self.assertIn(jc.PII, corpo)
        self.assertNotIn("CONVÊNIO XYZ", corpo)
        self.assertEqual([s for s in corpo.splitlines() if s.startswith("## ")],
                         ["## Decisão", "## Parecer do Comitê de Termo de Compromisso",
                          "## Termo de compromisso"])
        self.assertTrue(corpo.startswith("# APRECIAÇÃO DE PROPOSTA DE TERMO DE COMPROMISSO – PAS"))
        for fora in ("Rua das Acácias", "Fulana Exemplo", "base64", "Decisão do colegiado de",
                     "Consulte a Ata"):
            self.assertNotIn(fora, corpo)
        self.assertIn("Presidente Exemplo", corpo)  # assinatura de autoridade fica
        self.assertIn("19957.000789/2022-10", corpo)  # célula da tabela do SEI vira texto
        self.assertEqual((valores["relator"], valores["data"], valores["resultado"]),
                         ("SGE", "2025-12-02", "aceito"))
        self.assertEqual((valores["nivel_verificacao"], valores["ementa_fonte"]),
                         ("pdf-extraido", "titulo"))
        self.assertNotIn("Sicrano", valores["ementa"])
        self.assertEqual(valores["fonte_original"], COL["url"])
        self.assertEqual(cv.pii.get("cpf"), 1)
        confs = {c["arquivo"]: c for c in cv.conferencias}
        self.assertGreater(confs["01-pagina.html"]["cobertura"], 0.6)
        self.assertEqual(confs["02-anexo.pdf"]["conferencia"], "sem conferência independente")
        caminho, md = self.gravar_e_validar(valores, corpo)
        self.assertTrue(caminho.endswith(os.path.join(
            "julgados-sancionadores", "julgados", "cvm", "colegiado", "2025",
            "col-20251202-d3228.md")))
        self.assertEqual(list(frontmatter(md)), list(jc.CAMPOS))

    def test_pas_com_cabecalho_rodape_e_ocr(self):
        montar_cache(self.pasta(PAS), [
            ("pagina", "PAS", PAS["url"], "01-pagina.html", fixture("pas-pagina.html"),
             "text/html; charset=utf-8"),
            ("pdf", "Decisão completa", PDF_PAS, "02-pdf.pdf", b"%PDF-pas", "application/pdf"),
        ])
        ocr = "\f\f" + "Página digitalizada lida por reconhecimento óptico de caracteres.\f"
        pm = PdfFalso({"02-pdf.pdf": "\f".join(PAGINAS_PAS) + "\f"}, ocr={"02-pdf.pdf": ocr})
        with mock.patch.object(conv, "_pypdf_paginas",
                               return_value=["\n".join(PAGINAS_PAS)]):
            valores, corpo, cv = conv.converter_item(PAS, self.pasta(PAS), pm)
        self.assertEqual([s for s in corpo.splitlines() if s.startswith("## ")],
                         ["## Extrato", "## Relatório", "## Voto"])
        self.assertTrue(corpo.startswith("# 19957.000456/2024- 51\n"))
        self.assertNotIn("COMISSÃO DE VALORES", corpo)
        self.assertNotIn("pg. 4", corpo)
        self.assertIn("reconhecimento óptico", corpo)
        self.assertEqual((valores["relator"], valores["data"], valores["resultado"]),
                         ("Fulano Exemplo", "2025-05-27", "condenacao"))
        self.assertEqual((valores["nivel_verificacao"], cv.paginas_ocr), ("ocr", 1))
        self.assertTrue(valores["ementa"].startswith("Apurar responsabilidades por infração"))
        self.assertEqual(valores["ementa_fonte"], "cvm")
        self.assertEqual(valores["fonte_original"], PDF_PAS)
        self.assertEqual(valores["sha256_fonte"], hashlib.sha256(b"%PDF-pas").hexdigest())
        self.assertIn("1 página(s) por OCR", valores["incerteza"])
        pdf = [c for c in cv.conferencias if c["arquivo"] == "02-pdf.pdf"][0]
        self.assertEqual(pdf["conferencia"], "pypdf")
        self.assertGreater(pdf["cobertura"], 0.6)
        self.gravar_e_validar(valores, corpo)

    def test_pas_sem_ocr_disponivel(self):
        montar_cache(self.pasta(PAS), [
            ("pdf", "Decisão completa", PDF_PAS, "01-pdf.pdf", b"%PDF-pas", "application/pdf")])
        pm = PdfFalso({"01-pdf.pdf": "\f".join(PAGINAS_PAS)})
        with mock.patch.object(conv, "_pypdf_paginas", return_value=None):
            valores, corpo, cv = conv.converter_item(PAS, self.pasta(PAS), pm)
        self.assertEqual(pm.ocr_chamado, 1)
        self.assertEqual(valores["nivel_verificacao"], "pdf-extraido")
        self.assertTrue(any("sem OCR" in a for a in cv.avisos))
        self.assertEqual(valores["data"], "2025-05-27")

    def test_pdfkit_fora_do_macos_usa_pypdf(self):
        class SemMac(PdfFalso):
            def texto_pdfkit(self, path):
                raise pdf_macos.ErroPdfMacos("fora do macOS")

        pasta = os.path.join(self.raiz, "x")
        os.makedirs(pasta)
        caminho = os.path.join(pasta, "a.pdf")
        with mock.patch.object(conv, "_pypdf_paginas", return_value=["texto da página um"] * 2):
            pags, nivel, motor, _, _ = conv.texto_pdf(caminho, SemMac({}))
        self.assertEqual((motor, nivel, len(pags)), ("pypdf", "pdf-extraido", 2))
        self.assertEqual(conv.conferir("a.pdf", caminho, "pypdf", "x")["conferencia"],
                         "sem conferência independente")
        with mock.patch.object(conv, "_pypdf_paginas", return_value=None):
            with self.assertRaises(pdf_macos.ErroPdfMacos):
                conv.texto_pdf(caminho, SemMac({}))

    def test_tc_avulso_do_sei(self):
        item = {"id": "cvm-tc-19957-000789-2022-10-20230110", "tipo": "termo-compromisso",
                "classe": "", "processo": "19957.000789/2022-10", "data": "2023-01-10",
                "url": "https://sei.cvm.gov.br/sei/publicacoes/x?id=9", "incerteza": [],
                "resultado": "aceito"}
        montar_cache(self.pasta(item), [("sei", "", item["url"], "01-sei.html",
                                         fixture("sei-termo.html"), "text/html")])
        valores, corpo, cv = conv.converter_item(item, self.pasta(item), PdfFalso({}))
        self.assertTrue(corpo.startswith("# Termo de compromisso – 19957.000789/2022-10\n"))
        self.assertIn("## Termo de compromisso", corpo)
        self.assertNotIn("Rua das Acácias", corpo)
        self.assertIn("CLÁUSULA PRIMEIRA", corpo)
        self.assertEqual((valores["nivel_verificacao"], valores["resultado"]),
                         ("html-convertido", "aceito"))
        self.assertIn("título montado", valores["incerteza"])
        self.gravar_e_validar(valores, corpo)

    def test_decisoes_antigas(self):
        item = {"id": "cvm-dec-1990", "tipo": "decisao-antiga", "classe": "", "processo": "",
                "data": "1990-01-01", "url": B + "/x/d1990.pdf",
                "titulo": "Decisões do Colegiado de 1990", "incerteza": []}
        pag1 = ("Rua Sete de Setembro, 111\nSelecione o Dia:\n27/12/1990\n20/12/1990\n"
                "ATA DA REUNIÃO EXTRAORDINÁRIA DO COLEGIADO DE 27.12.1990\nPARTICIPANTES:\n"
                "FULANO EXEMPLO – Presidente\nBELTRANA EXEMPLO – Diretora\n"
                "RECURSO CONTRA DECISÃO DA SEP\nRelator: DNC\nO Colegiado negou provimento.\n")
        pag2 = ("ATA DA REUNIÃO DO COLEGIADO Nº 47 DE 20.12.1990\nPARTICIPANTES:\n"
                "FULANO EXEMPLO – Presidente\nPEDIDO DE DISPENSA DE REGISTRO\nDE OFERTA PÚBLICA\n"
                "O Colegiado deferiu o pedido.\nCONSULTA SOBRE PRAZO DE PUBLICAÇÃO\n"
                "O Colegiado respondeu à consulta.\n")
        montar_cache(self.pasta(item), [("documento", "", item["url"], "01-documento.pdf",
                                         b"%PDF-1990", "application/pdf")])
        pm = PdfFalso({"01-documento.pdf": pag1 + "\f" + pag2})
        with mock.patch.object(conv, "_pypdf_paginas", return_value=None):
            valores, corpo, cv = conv.converter_item(item, self.pasta(item), pm)
        self.assertNotIn("Selecione", corpo)
        h2 = [s for s in corpo.splitlines() if s.startswith("## ")]
        h3 = [s for s in corpo.splitlines() if s.startswith("### ")]
        self.assertEqual(len(h2), 2)
        self.assertEqual(h3, ["### RECURSO CONTRA DECISÃO DA SEP",
                              "### PEDIDO DE DISPENSA DE REGISTRO DE OFERTA PÚBLICA",
                              "### CONSULTA SOBRE PRAZO DE PUBLICAÇÃO"])
        self.assertEqual((valores["data"], valores["resultado"]), ("1990-12-20", ""))
        self.assertIn("heurística", valores["incerteza"])
        caminho, _ = self.gravar_e_validar(valores, corpo)
        self.assertTrue(caminho.endswith(os.path.join("decisoes-antigas", "1990.md")))

    def test_sem_cache_e_erro(self):
        with self.assertRaises(ValueError):
            conv.converter_item(PAS, self.pasta(PAS), PdfFalso({}))


class MainTest(unittest.TestCase):
    def test_lote_com_relatorio(self):
        with tempfile.TemporaryDirectory() as d:
            cache = os.path.join(d, "cache")
            item = dict(PAS)
            montar_cache(jb.pasta_do_item(item, cache), [
                ("pdf", "Decisão completa", PDF_PAS, "01-pdf.pdf", b"%PDF", "application/pdf")])
            outro = dict(PAS, id="cvm-pas-19957-000999-2024-10")
            inv = os.path.join(d, "inv.json")
            with open(inv, "w", encoding="utf-8") as f:
                json.dump({"julgados": [item, outro]}, f)
            pm = PdfFalso({"01-pdf.pdf": "\f".join(PAGINAS_PAS)})
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err), \
                    mock.patch.object(conv, "_pypdf_paginas", return_value=None):
                rc = conv.main(["--inventario", inv, "--cache", cache, "--raiz", d,
                                "--relatorios", os.path.join(d, "rel"), "--tipo", "pas"], pm=pm)
            self.assertEqual(rc, 1)
            (nome,) = os.listdir(os.path.join(d, "rel"))
            with open(os.path.join(d, "rel", nome), encoding="utf-8") as f:
                rel = json.load(f)
            ok, ruim = rel["itens"]
            self.assertEqual(ok["secoes"], ["Extrato", "Relatório", "Voto"])
            self.assertTrue(os.path.exists(os.path.join(d, ok["caminho"])))
            self.assertIn("fonte não baixada", ruim["erro"])


if __name__ == "__main__":
    unittest.main()
