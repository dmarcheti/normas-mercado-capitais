"""Testes de pdf_macos (PDFKit e Vision via swift) e conferir_pdf. As funções Python rodam com o
subprocess substituído (o CI é Ubuntu, sem swift); o teste real gera um PDF pelo próprio swift e
só roda no macOS com swift instalado."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import conferir_pdf as cp  # noqa: E402
import pdf_macos as pm  # noqa: E402


def _r(stdout="", stderr="", code=0):
    return subprocess.CompletedProcess([], code, stdout=stdout, stderr=stderr)


class Comando(unittest.TestCase):
    def test_fora_do_macos_erro_claro(self):
        with mock.patch.object(pm.sys, "platform", "linux"):
            with self.assertRaisesRegex(pm.ErroPdfMacos, "só funciona no macOS"):
                pm.texto_pdfkit("x.pdf")

    def test_compila_quando_falta_binario(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(pm.sys, "platform", "darwin"), \
                mock.patch.object(pm, "BINARIO", os.path.join(d, "bin", "pdf_macos")), \
                mock.patch.object(pm.shutil, "which", return_value="/usr/bin/swiftc"), \
                mock.patch.object(pm.subprocess, "run", return_value=_r()) as run:
            self.assertEqual(pm._comando(), [pm.BINARIO])
            self.assertEqual(run.call_args[0][0][:3], ["swiftc", "-O", pm.FONTE])

    def test_reusa_binario_novo(self):
        with tempfile.NamedTemporaryFile() as b, \
                mock.patch.object(pm.sys, "platform", "darwin"), \
                mock.patch.object(pm, "BINARIO", b.name), \
                mock.patch.object(pm.os.path, "getmtime", side_effect=lambda p: 2 if p == b.name else 1), \
                mock.patch.object(pm.subprocess, "run") as run:
            self.assertEqual(pm._comando(), [b.name])
            run.assert_not_called()

    def test_sem_swiftc_cai_para_swift(self):
        with mock.patch.object(pm.sys, "platform", "darwin"), \
                mock.patch.object(pm, "BINARIO", "/nao/existe"), \
                mock.patch.object(pm.shutil, "which", side_effect=lambda c: "/usr/bin/swift" if c == "swift" else None):
            self.assertEqual(pm._comando(), ["swift", pm.FONTE])

    def test_falha_de_compilacao(self):
        with mock.patch.object(pm.sys, "platform", "darwin"), \
                mock.patch.object(pm, "BINARIO", "/nao/existe/pdf_macos"), \
                mock.patch.object(pm.os, "makedirs"), \
                mock.patch.object(pm.shutil, "which", return_value="/usr/bin/swiftc"), \
                mock.patch.object(pm.subprocess, "run", return_value=_r(stderr="erro x", code=1)):
            with self.assertRaisesRegex(pm.ErroPdfMacos, "swiftc falhou"):
                pm._comando()


class Funcoes(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(pm, "_comando", return_value=["bin"])
        p.start()
        self.addCleanup(p.stop)

    def test_texto_pdfkit(self):
        with mock.patch.object(pm.subprocess, "run", return_value=_r("pág. 1\fpág. 2\n")) as run:
            self.assertEqual(pm.texto_pdfkit("a.pdf"), "pág. 1\fpág. 2")
        cmd = run.call_args[0][0]
        self.assertEqual(cmd[:2], ["bin", "texto"])
        self.assertTrue(os.path.isabs(cmd[2]))
        self.assertEqual(run.call_args[1]["timeout"], pm.TIMEOUT_TEXTO)

    def test_ocr_confiancas(self):
        err = "CONF\t1\t0.9800\t12\t1\naviso qualquer\nCONF\t2\t0.5000\t3\t0\n"
        with mock.patch.object(pm.subprocess, "run", return_value=_r("a\fb\n", err)):
            self.assertEqual(pm.ocr("a.pdf"), ("a\fb", [0.98, 0.5]))
            self.assertEqual(pm.ocr("a.pdf", detalhe=True)[1], [(0.98, 12, 1), (0.5, 3, 0)])

    def test_erro_do_swift(self):
        with mock.patch.object(pm.subprocess, "run", return_value=_r(stderr="não abriu", code=2)):
            with self.assertRaisesRegex(pm.ErroPdfMacos, "código 2: não abriu"):
                pm.texto_pdfkit("a.pdf")

    def test_timeout(self):
        with mock.patch.object(pm.subprocess, "run", side_effect=subprocess.TimeoutExpired("x", 5)):
            with self.assertRaisesRegex(pm.ErroPdfMacos, "tempo esgotado"):
                pm.ocr("a.pdf", timeout=5)

    def test_ocr_sem_texto(self):
        with tempfile.TemporaryDirectory() as d:
            rel = os.path.join(d, "camada.json")
            with open(rel, "w") as f:
                json.dump([{"id": "a", "resultado": "ok"}, {"id": "b", "resultado": "sem-texto"},
                           {"id": "c", "resultado": "sem-texto"}], f)
            fontes = os.path.join(d, "fontes")
            os.makedirs(fontes)
            open(os.path.join(fontes, "b.pdf"), "w").close()
            txt = "Ofício-Circular nº 2/2025\n1. O presente ofício trata de fundos.\fpágina dois"

            def extrair(pdf, detalhe=False):
                return txt, [(0.9, 10, 1), (0.7, 4, 0)]

            res = pm.ocr_sem_texto(rel, fontes, os.path.join(d, "ocr"), extrair=extrair)
            self.assertEqual([i["id"] for i in res], ["b", "c"])
            self.assertIn("fonte ausente", res[1]["erro"])
            b = res[0]
            self.assertEqual((b["paginas"], b["confianca_media"], b["confianca_minima"],
                              b["trechos_extras"]), (2, 0.8, 0.7, 1))
            self.assertGreater(b["palavras"], 10)
            with open(os.path.join(d, "ocr", "b.txt"), encoding="utf-8") as f:
                self.assertEqual(f.read(), txt)
            with open(os.path.join(d, "ocr", "relatorio.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f), res)


NORMA = """---
id: %s
nivel_verificacao: %s
---

%s
"""


class Conferencia(unittest.TestCase):
    def _acervo(self, d):
        pasta = os.path.join(d, "normas", "cvm", "oficios-circulares")
        os.makedirs(pasta)
        for nome, id_, nivel, corpo in [
                ("a.md", "cvm-oc-a", "pdf-extraido", "A ﬁscalização dos fundos de investimento."),
                ("b.md", "cvm-oc-b", "ato-convertido", "Outro texto."),
                ("c.md", "cvm-oc-c", "pdf-extraido", "Texto sem fonte.")]:
            with open(os.path.join(pasta, nome), "w", encoding="utf-8") as f:
                f.write(NORMA % (id_, nivel, corpo))
        fontes = os.path.join(d, "fontes")
        os.makedirs(fontes)
        open(os.path.join(fontes, "cvm-oc-a.pdf"), "w").close()
        return os.path.join(d, "normas"), fontes

    def test_separar(self):
        campos, corpo = cp.separar(NORMA % ("x", "pdf-extraido", "Corpo."))
        self.assertEqual(campos["nivel_verificacao"], "pdf-extraido")
        self.assertEqual(corpo.strip(), "Corpo.")

    def test_conferir(self):
        with tempfile.TemporaryDirectory() as d:
            normas, fontes = self._acervo(d)
            lidas = cp.normas_pdf(normas)
            self.assertEqual([n[0] for n in lidas], ["cvm-oc-a", "cvm-oc-c"])
            itens = cp.conferir(lidas, fontes,
                                extrair=lambda p: "A fiscalização dos fundos de investimento.")
            a, c = itens
            self.assertEqual(c["resultado"], "fonte-ausente")
            # a norma traz a ligadura "ﬁ": a cobertura crua perde "fiscalização", a ajustada não
            self.assertEqual((a["cobertura"], a["cobertura_ajustada"]), (0.8333, 1.0))
            self.assertEqual((a["palavras_pdfkit"], a["palavras_norma"]), (6, 6))
            self.assertEqual(a["palavras_faltando"], 0)
            r = cp.resumo(itens)
            self.assertIn("conferidas: 1", r)
            self.assertIn("cvm-oc-c: fonte-ausente", r)
            self.assertIn("cvm-oc-a  83.33%  ajustada 100.00%", r)

    def test_ajuste_do_sublinhado(self):
        fonte = "controlador.php?acao=documento\n_\nimprimir"
        corpo = "controlador.php?acao=documento_imprimir"
        # a cobertura do texto_vigente já trata "_" como separador; o ajuste não muda o resultado
        self.assertEqual(cp.cobertura(fonte, corpo), 1.0)
        self.assertEqual(cp.cobertura(cp.ajustar(fonte), cp.ajustar(corpo)), 1.0)

    def test_main_grava_json(self):
        with tempfile.TemporaryDirectory() as d:
            normas, fontes = self._acervo(d)
            saida = os.path.join(d, "conf.json")
            with mock.patch.object(cp.pdf_macos, "texto_pdfkit", return_value="A fiscalização"), \
                    mock.patch("sys.stdout"):
                cp.main(["--normas", normas, "--fontes", fontes, "--saida", saida])
            with open(saida, encoding="utf-8") as f:
                self.assertEqual(len(json.load(f)), 2)


TEM_SWIFT = sys.platform == "darwin" and (shutil.which("swiftc") or shutil.which("swift"))


@unittest.skipUnless(TEM_SWIFT, "precisa do macOS com swift (PDFKit e Vision)")
class Real(unittest.TestCase):
    def test_texto_e_ocr_de_pdf_gerado(self):
        with tempfile.TemporaryDirectory() as d:
            txt = os.path.join(d, "t.txt")
            with open(txt, "w", encoding="utf-8") as f:
                f.write("Ofício-Circular nº 9/2026/CVM/SSE\n\n1. Esta comunicação trata da "
                        "distribuição de rendimentos.\n\f2. Segunda página com ação e coração.\n")
            pdf = pm.pdf_teste(os.path.join(d, "t.pdf"), txt)
            texto = pm.texto_pdfkit(pdf)
            self.assertEqual(texto.count("\f"), 1)
            self.assertIn("distribuição de rendimentos", texto)
            self.assertIn("ação e coração", texto)
            ocr, conf = pm.ocr(pdf)
            self.assertEqual(len(conf), 2)
            self.assertTrue(all(c > 0.5 for c in conf), conf)
            self.assertIn("distribuição de rendimentos", ocr)
            self.assertIn("coração", ocr.split("\f")[1])
            self.assertGreaterEqual(cp.cobertura(texto, ocr), 0.8)


if __name__ == "__main__":
    unittest.main()
