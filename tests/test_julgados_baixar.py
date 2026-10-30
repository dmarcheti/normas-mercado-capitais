"""Testes do download das fontes dos julgados, com cliente falso e páginas sintéticas."""
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import julgados_baixar as jb  # noqa: E402
import julgados_comum as jc  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "julgados")
B = jc.BASE


def fixture(nome):
    with open(os.path.join(FIX, nome), "rb") as f:
        return f.read()


class Falso:
    """Cliente falso: mapa URL -> bytes; registra GET e HEAD; `tamanhos` muda o HEAD."""

    def __init__(self, mapa, tamanhos=None, falhar=()):
        self.mapa, self.tamanhos, self.falhar = mapa, tamanhos or {}, set(falhar)
        self.gets, self.heads, self.n = [], [], 0

    def get(self, url):
        self.gets.append(url)
        self.n += 1
        if url in self.falhar or url not in self.mapa:
            raise OSError("404 " + url)
        ct = "application/pdf" if url.endswith(".pdf") else "text/html; charset=utf-8"
        return self.mapa[url], {"content-type": ct}, url

    def head(self, url):
        self.heads.append(url)
        self.n += 1
        tam = self.tamanhos.get(url, len(self.mapa.get(url, b"")))
        return {"content-length": str(tam)} if tam is not None else {}


COL = {"id": "cvm-col-20251202-d3228", "tipo": "termo-compromisso", "data": "2025-12-02",
       "url": B + "/decisoes/2025/20251202_R1/20251202_D3228.html", "titulo": "X",
       "termo_urls": ["/export/sites/cvm/termos_compromisso/anexos/2025/termo.pdf"]}
PAS = {"id": "cvm-pas-19957-000456-2024-51", "tipo": "pas", "data": "2025-05-27",
       "url": B + "/sancionadores/sancionador/2025/20250527_PAS.html", "titulo": "Y"}
ANEXO = B + "/export/sites/cvm/decisoes/anexos/2025/20251202/3228_25.pdf"
TERMO = B + "/export/sites/cvm/termos_compromisso/anexos/2025/termo.pdf"
PDF_PAS = B + "/export/sites/cvm/sancionadores/sancionador/anexos/2025/SEI_19957000456_2024_51.pdf"


class LinksTest(unittest.TestCase):
    def test_colegiado(self):
        links = jb.links_da_pagina(fixture("colegiado-item.html").decode("utf-8"))
        self.assertEqual([u for u, _ in links],
                         [ANEXO, ANEXO.replace(".pdf", "_conv.pdf")])
        self.assertEqual(links[0][1], "PARECER DO COMITÊ")  # rótulo mais longo vence o vazio

    def test_pas(self):
        links = jb.links_da_pagina(fixture("pas-pagina.html").decode("utf-8"))
        self.assertEqual(links, [(PDF_PAS, "Decisão completa")])

    def test_sei_e_nome_local(self):
        h = '<article class="contentTextoGeral"><a href="https://sei.cvm.gov.br/sei/publicacoes/' \
            'controlador_publicacoes.php?acao=x&amp;id=1">termo</a></article>'
        (u, _), = jb.links_da_pagina(h)
        self.assertIn("acao=x&id=1", u)
        self.assertEqual(jb._nome_local("termo", 3, u, "text/html"), "03-termo.html")
        self.assertEqual(jb._nome_local("pdf", 1, PDF_PAS), "01-pdf.pdf")
        # slug de notícia terminado em "-s.a" não vira extensão
        self.assertEqual(jb._nome_local("noticia", 1, "https://www.gov.br/cvm/2025/multa-x-s.a",
                                        "text/html;charset=utf-8"), "01-noticia.html")


class BaixarItemTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.raiz = self.dir.name
        self.mapa = {COL["url"]: fixture("colegiado-item.html"), ANEXO: b"%PDF-anexo",
                     TERMO: b"%PDF-termo", PAS["url"]: fixture("pas-pagina.html"),
                     PDF_PAS: b"%PDF-pas"}

    def tearDown(self):
        self.dir.cleanup()

    def baixar(self, item, cli, **kw):
        return jb.baixar_item(item, cli, self.raiz, log=lambda *a: None, **kw)

    def test_colegiado_com_anexo_termo_e_alheio(self):
        cli = Falso(self.mapa)
        reg = self.baixar(COL, cli)
        self.assertTrue(reg["completo"])
        self.assertEqual([a["papel"] for a in reg["arquivos"]], ["pagina", "anexo", "termo"])
        self.assertEqual(reg["ignorados"][0]["motivo"], "anexo alheio")
        pasta = jb.pasta_do_item(COL, self.raiz)
        self.assertTrue(pasta.endswith(os.path.join("termo-compromisso", "2025",
                                                    "cvm-col-20251202-d3228")))
        a = reg["arquivos"][1]
        self.assertEqual(a["sha256"], hashlib.sha256(b"%PDF-anexo").hexdigest())
        self.assertEqual((a["tamanho"], a["url"], a["rotulo"]), (10, ANEXO, "PARECER DO COMITÊ"))
        for k in ("baixado_em", "content_type", "arquivo"):
            self.assertTrue(a[k])
        with open(os.path.join(pasta, "registro.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["arquivos"], reg["arquivos"])
        self.assertFalse([n for n in os.listdir(pasta) if n.endswith(".parcial")])

    def test_retoma_com_head_e_rebaixa_se_mudou(self):
        self.baixar(PAS, Falso(self.mapa))
        cli = Falso(self.mapa)
        reg = self.baixar(PAS, cli)
        self.assertEqual(cli.gets, [])
        self.assertEqual(cli.heads, [PAS["url"], PDF_PAS])
        self.assertTrue(reg["completo"])
        cli2 = Falso(dict(self.mapa, **{PDF_PAS: b"%PDF-pas-v2"}))
        reg2 = self.baixar(PAS, cli2)
        self.assertEqual(cli2.gets, [PDF_PAS])
        self.assertTrue(any("tamanho mudou" in x for x in reg2["avisos"]))
        self.assertEqual(reg2["arquivos"][1]["tamanho"], 11)

    def test_sem_content_length_vale_o_cache_e_sem_head(self):
        self.baixar(PAS, Falso(self.mapa))
        cli = Falso(self.mapa, tamanhos={PAS["url"]: None, PDF_PAS: None})
        self.baixar(PAS, cli)
        self.assertEqual(cli.gets, [])
        cli2 = Falso(self.mapa)
        self.baixar(PAS, cli2, verificar=False)
        self.assertEqual((cli2.gets, cli2.heads), ([], []))

    def test_cache_corrompido_rebaixa(self):
        self.baixar(PAS, Falso(self.mapa))
        pasta = jb.pasta_do_item(PAS, self.raiz)
        with open(os.path.join(pasta, "02-pdf.pdf"), "wb") as f:
            f.write(b"%PDF-xxx")
        cli = Falso(self.mapa)
        self.baixar(PAS, cli)
        self.assertEqual(cli.gets, [PDF_PAS])

    def test_extensao_invalida_no_cache_rebaixa(self):
        self.baixar(PAS, Falso(self.mapa))
        pasta = jb.pasta_do_item(PAS, self.raiz)
        p = os.path.join(pasta, "registro.json")
        with open(p, encoding="utf-8") as f:
            reg = json.load(f)
        os.rename(os.path.join(pasta, "01-pagina.html"), os.path.join(pasta, "01-pagina.a"))
        reg["arquivos"][0]["arquivo"] = "01-pagina.a"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(reg, f)
        cli = Falso(self.mapa)
        reg2 = self.baixar(PAS, cli)
        self.assertEqual(cli.gets, [PAS["url"]])
        self.assertEqual(reg2["arquivos"][0]["arquivo"], "01-pagina.html")

    def test_erro_de_rede_deixa_incompleto_e_retoma(self):
        reg = self.baixar(COL, Falso(self.mapa, falhar=[TERMO]))
        self.assertFalse(reg["completo"])
        self.assertEqual(reg["erros"][0]["url"], TERMO)
        cli = Falso(self.mapa)
        reg2 = self.baixar(COL, cli)
        self.assertTrue(reg2["completo"])
        self.assertEqual(cli.gets, [TERMO])

    def test_pdf_direto_sem_duplicar_termo(self):
        tc = {"id": "cvm-tc-rj1996-4025-19980603", "tipo": "termo-compromisso",
              "data": "1998-06-03", "url": TERMO, "termo_urls": [TERMO]}
        cli = Falso(self.mapa)
        reg = self.baixar(tc, cli)
        self.assertEqual([a["papel"] for a in reg["arquivos"]], ["documento"])
        self.assertEqual(cli.gets, [TERMO])

    def test_noticia_baixa_pecas_e_extrato_sem_seguir_links(self):
        g = "https://www.gov.br/cvm/pt-br/assuntos/noticias"
        noticia, voto = g + "/2025/cvm-multa", g + "/anexos/2025/voto.pdf"
        sei = "https://sei.cvm.gov.br/sei/publicacoes/controlador_publicacoes.php?id_documento=9"
        outro = g + "/anexos/2025/outro.pdf"
        html = ('<article class="contentTextoGeral"><a href="%s">outro caso</a></article>'
                % outro).encode()
        it = {"id": "cvm-pas-19957-000444-2025-44", "tipo": "pas", "data": "2025-12-09",
              "url": noticia, "titulo": "", "origem": "noticia", "noticia": noticia,
              "pecas": [{"url": voto, "rotulo": "voto"}], "sei_urls": [sei]}
        cli = Falso({noticia: html, voto: b"%PDF-voto", sei: b"<html>extrato</html>"})
        reg = self.baixar(it, cli)
        self.assertTrue(reg["completo"])
        self.assertEqual([(a["papel"], a["rotulo"]) for a in reg["arquivos"]],
                         [("noticia", ""), ("pdf", "voto"), ("sei", "extrato de sessão de julgamento")])
        self.assertNotIn(outro, cli.gets)
        # sem notícia, o extrato é a fonte principal
        it2 = dict(it, id="cvm-pas-19957-000333-2025-33", url=sei, noticia="", pecas=[])
        reg2 = self.baixar(it2, Falso({sei: b"<html>extrato</html>"}))
        self.assertEqual([a["papel"] for a in reg2["arquivos"]], ["sei"])


class MainTest(unittest.TestCase):
    def test_selecao_e_pendente(self):
        with tempfile.TemporaryDirectory() as d:
            inv = os.path.join(d, "inv.json")
            itens = [PAS, COL, {"id": "cvm-pas-x", "tipo": "pas", "data": "2024-01-01",
                                "url": ""}]
            with open(inv, "w", encoding="utf-8") as f:
                json.dump({"julgados": itens}, f)
            mapa = {PAS["url"]: fixture("pas-pagina.html"), PDF_PAS: b"%PDF"}
            out = io.StringIO()
            with redirect_stdout(out):
                rc = jb.main(["--inventario", inv, "--cache", os.path.join(d, "c"),
                              "--ids", "%s,cvm-pas-x" % PAS["id"]], cliente=Falso(mapa))
            self.assertEqual(rc, 0)
            resumo = json.loads(out.getvalue().strip().splitlines()[-1])
            self.assertEqual((resumo["itens"], resumo["completos"], resumo["sem_url"]),
                             (2, 1, ["cvm-pas-x"]))
            out = io.StringIO()
            with redirect_stdout(out):
                jb.main(["--inventario", inv, "--cache", os.path.join(d, "c"), "--onda", "1",
                         "--tipo", "pas", "--limite", "1"], cliente=Falso(mapa))
            self.assertEqual(json.loads(out.getvalue().strip().splitlines()[-1])["itens"], 1)


if __name__ == "__main__":
    unittest.main()
