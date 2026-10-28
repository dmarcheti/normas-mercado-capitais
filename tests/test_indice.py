"""Testes do índice (sem rede): resumo em indice.md, subíndices em indices/ e normas.json."""
import json
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import indice  # noqa: E402
from validar import CAMPOS  # noqa: E402

ACERVO = os.path.join(AQUI, "fixtures", "v030-acervo.json")
SEM_ACERVO = os.path.join(AQUI, "fixtures", "v030-nao-existe.json")

VALORES = {
    "id": "cvm-res-9", "orgao": "cvm", "tipo": "resolucao", "numero": "9",
    "data": "2020-05-04", "publicacao_dou": "2020-05-05",
    "ementa": "Dispõe sobre assunto de fixture | com barra.", "situacao": "vigente",
    "versao_texto": "consolidado", "vigente_ate_ato": "12",
    "aguarda_consolidado_oficial": "false", "historico_parcial": "false",
    "fonte_original": "https://exemplo.invalid/o", "fonte_consolidada": "https://exemplo.invalid/c",
    "sha256_fonte": "b" * 64, "baixado_em": "2026-10-28", "verificado_em": "2026-10-28",
    "incerteza": "",
}
LEI = dict(orgao="federal", tipo="lei", vigente_ate_ato="", historico_parcial="true")
SEM_VIGENCIA = dict(situacao="nao-informada", vigente_ate_ato="", versao_texto="original")


def gravar(raiz, rel, **mudancas):
    v = dict(VALORES)
    v.update(mudancas)
    caminho = os.path.join(raiz, *rel.split("/"))
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    linhas = ["---"] + ["%s: %s" % (c, v[c]) if v[c] else "%s:" % c for c in CAMPOS] + ["---", "", "## Art. 1º", "", "Texto."]
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")


def ler(raiz, rel):
    with open(os.path.join(raiz, *rel.split("/")), encoding="utf-8") as f:
        return f.read()


class TestIndice(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = self._tmp.name
        gravar(self.raiz, "cvm/resolucoes/0009.md")
        gravar(self.raiz, "cvm/resolucoes/0003.md", id="cvm-res-3", numero="3", vigente_ate_ato="")
        gravar(self.raiz, "cvm/alteradoras/0012.md", id="cvm-res-12", numero="12", versao_texto="original")

    def tearDown(self):
        self._tmp.cleanup()

    def test_caminho_relativo_e_campos(self):
        _arqs, itens = indice.gerar_indice(self.raiz)
        item = next(i for i in itens if i["id"] == "cvm-res-9")
        self.assertEqual(item["caminho"], "cvm/resolucoes/0009.md")
        self.assertEqual(item["titulo"], "Resolução CVM nº 9/2020")
        self.assertEqual(item["tipo"], "resolucao")
        self.assertEqual(item["situacao"], "vigente")
        self.assertEqual(item["vigente_ate_ato"], "12")
        self.assertIn("fixture", item["ementa"])
        self.assertNotIn("grupo", item)  # sem acervo.json, sem grupo

    def test_ordem_por_numero_e_sem_alteradoras_no_json(self):
        _arqs, itens = indice.gerar_indice(self.raiz)
        self.assertEqual([i["id"] for i in itens], ["cvm-res-3", "cvm-res-9"])

    def test_subindices_listam_normas_e_atos(self):
        arqs, _itens = indice.gerar_indice(self.raiz)
        resol = arqs["indices/resolucoes.md"]
        self.assertIn("cvm/resolucoes/0009.md", resol)
        self.assertIn("redação original", resol)
        self.assertIn("fixture \\| com barra", resol)  # a barra da ementa é escapada
        self.assertIn("cvm/alteradoras/0012.md", arqs["indices/alteradoras.md"])
        self.assertIn("Material não oficial", resol)

    def test_resumo_curto_com_contagem_e_links(self):
        arqs, _itens = indice.gerar_indice(self.raiz)
        md = arqs["indice.md"]
        self.assertIn("Material não oficial", md)
        self.assertIn("(indices/resolucoes.md)", md)
        self.assertIn("(indices/alteradoras.md)", md)
        self.assertNotIn("cvm/resolucoes/0009.md", md)  # os detalhes ficam nos subíndices
        linha = next(l for l in md.split("\n") if "indices/resolucoes.md" in l)
        self.assertIn("| 2 |", linha)

    def test_subindice_vazio_nao_e_gerado(self):
        arqs, _itens = indice.gerar_indice(self.raiz)
        self.assertEqual(sorted(arqs), ["indice.md", "indices/alteradoras.md",
                                        "indices/resolucoes.md", "normas.json"])
        self.assertNotIn("indices/leis.md", arqs["indice.md"])

    def test_verificar_detecta_indice_desatualizado(self):
        args = ["indice.py", self.raiz, "--acervo", SEM_ACERVO]
        self.assertEqual(indice.main(args + ["--verificar"]), 1)
        self.assertEqual(indice.main(args), 0)
        self.assertEqual(indice.main(args + ["--verificar"]), 0)
        with open(os.path.join(self.raiz, "normas.json"), encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)), 2)
        gravar(self.raiz, "cvm/resolucoes/0020.md", id="cvm-res-20", numero="20")
        self.assertEqual(indice.main(args + ["--verificar"]), 1)

    def test_verificar_acusa_subindice_que_sobrou(self):
        args = ["indice.py", self.raiz, "--acervo", SEM_ACERVO]
        gravar(self.raiz, "cvm/instrucoes/0489.md", id="cvm-instr-489", tipo="instrucao", numero="489")
        self.assertEqual(indice.main(args), 0)
        self.assertTrue(os.path.exists(os.path.join(self.raiz, "indices", "instrucoes.md")))
        os.remove(os.path.join(self.raiz, "cvm", "instrucoes", "0489.md"))
        self.assertEqual(indice.main(args + ["--verificar"]), 1)
        # gerar de novo apaga o subíndice que sobrou
        self.assertEqual(indice.main(args), 0)
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "indices", "instrucoes.md")))
        self.assertEqual(indice.main(args + ["--verificar"]), 0)

    def test_saida_deterministica(self):
        a, _ = indice.gerar_indice(self.raiz, ACERVO)
        b, _ = indice.gerar_indice(self.raiz, ACERVO)
        self.assertEqual(a, b)


class TestIndiceLeisEPartes(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.raiz = self._tmp.name
        gravar(self.raiz, "cvm/resolucoes/0017.md", id="cvm-res-17", numero="17")
        gravar(self.raiz, "cvm/resolucoes/0175/index.md", id="cvm-res-175", numero="175", data="2022-12-23")
        with open(os.path.join(self.raiz, "cvm", "resolucoes", "0175", "anexo-01.md"), "w", encoding="utf-8") as f:
            f.write("# Anexo\n\n## Art. 1º\n\nTexto.\n")
        lei = dict(LEI, id="lei-6404", numero="6404", data="1976-12-15",
                   ementa="Dispõe sobre as sociedades por ações.")
        gravar(self.raiz, "leis/lei-06404/index.md", **lei)
        gravar(self.raiz, "leis/lei-06385.md", **dict(lei, id="lei-6385", numero="6385", data="1976-12-07"))
        gravar(self.raiz, "leis/decreto-11415.md", **dict(lei, id="decreto-11415", tipo="decreto",
                                                          numero="11415", data="2023-02-15"))
        gravar(self.raiz, "leis/lcp-105.md", **dict(lei, id="lcp-105", tipo="lei-complementar",
                                                   numero="105", data="2001-01-10"))

    def test_norma_em_partes_aponta_para_o_index(self):
        _arqs, itens = indice.gerar_indice(self.raiz)
        item = next(i for i in itens if i["id"] == "cvm-res-175")
        self.assertEqual(item["caminho"], "cvm/resolucoes/0175/index.md")
        self.assertNotIn("anexo-01.md", [os.path.basename(i["caminho"]) for i in itens])

    def test_leis_decretos_e_lcp_no_subindice_de_leis(self):
        arqs, itens = indice.gerar_indice(self.raiz)
        ids = [i["id"] for i in itens]
        self.assertEqual(ids, ["cvm-res-17", "cvm-res-175", "lei-6385", "lei-6404", "lcp-105", "decreto-11415"])
        leis = arqs["indices/leis.md"]
        self.assertIn("Lei nº 6.385/1976", leis)
        self.assertLess(leis.index("6.385"), leis.index("6.404"))
        self.assertIn("leis/lei-06404/index.md", leis)
        self.assertIn("Lei Complementar nº 105/2001", leis)
        self.assertIn("Decreto nº 11.415/2023", leis)
        self.assertNotIn("lei-06385", arqs["indices/resolucoes.md"])
        self.assertIn("2026-10-28", leis)  # data-base
        self.assertEqual(next(i for i in itens if i["id"] == "lei-6385")["baixado_em"], "2026-10-28")
        linha = next(l for l in arqs["indice.md"].split("\n") if "indices/leis.md" in l)
        self.assertIn("| 4 |", linha)

    def test_verificar_com_leis_e_partes(self):
        args = ["indice.py", self.raiz, "--acervo", SEM_ACERVO]
        self.assertEqual(indice.main(args), 0)
        self.assertEqual(indice.main(args + ["--verificar"]), 0)


class TestIndiceV030(unittest.TestCase):
    """Grupos do Estoque Regulatório, instruções, pareceres e ofícios (com verbetes)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        r = self.raiz = self._tmp.name
        gravar(r, "cvm/resolucoes/0009.md", ementa="Aprova o Pronunciamento Técnico CPC 00.")
        gravar(r, "cvm/resolucoes/0017.md", id="cvm-res-17", numero="17")
        gravar(r, "cvm/resolucoes/0080.md", id="cvm-res-80", numero="80", data="2022-03-29")
        gravar(r, "cvm/resolucoes/0030.md", id="cvm-res-30", numero="30")
        gravar(r, "cvm/resolucoes/0003.md", id="cvm-res-3", numero="3")
        gravar(r, "cvm/instrucoes/0489.md", id="cvm-instr-489", tipo="instrucao", numero="489", data="2011-01-14")
        gravar(r, "cvm/pareceres-orientacao/0035.md", id="cvm-po-35", tipo="parecer-orientacao",
               numero="35", data="2008-09-01", **SEM_VIGENCIA)
        gravar(r, "cvm/oficios-circulares/sse1/oc-sse-0326.md", id="cvm-oc-sse-0326",
               tipo="oficio-circular", numero="3", data="2026-05-10",
               ementa="Orientações sobre securitização (texto).", **SEM_VIGENCIA)
        gravar(r, "cvm/oficios-circulares/sin/oc-sin-0122.md", id="cvm-oc-sin-0122",
               tipo="oficio-circular", numero="1", data="2022-01-20",
               ementa="Ofício da SIN fora do acervo.json.", **SEM_VIGENCIA)
        self.arqs, self.itens = indice.gerar_indice(r, ACERVO)

    def item(self, id_):
        return next(i for i in self.itens if i["id"] == id_)

    def test_tipo_e_grupo_no_json(self):
        self.assertEqual(self.item("cvm-res-17")["grupo"], "Agente fiduciário")
        self.assertEqual(self.item("cvm-res-9")["grupo"], "Normas contábeis")
        self.assertNotIn("grupo", self.item("cvm-res-3"))
        self.assertEqual(self.item("cvm-instr-489")["tipo"], "instrucao")
        self.assertEqual(self.item("cvm-oc-sse-0326")["tipo"], "oficio-circular")
        ids = [i["id"] for i in self.itens]
        self.assertEqual(ids, ["cvm-res-3", "cvm-res-9", "cvm-res-17", "cvm-res-30", "cvm-res-80",
                               "cvm-instr-489", "cvm-po-35", "cvm-oc-sin-0122", "cvm-oc-sse-0326"])

    def test_resolucoes_por_grupo_com_contabeis_por_ultimo(self):
        md = self.arqs["indices/resolucoes.md"]
        titulos = [l[3:] for l in md.split("\n") if l.startswith("## ")]
        self.assertEqual(titulos, ["Agente fiduciário", "Intermediação | adequação",
                                   "Sem grupo no Estoque Regulatório", "Normas contábeis"])
        agente = md.split("## Agente fiduciário")[1].split("\n## ")[0]
        self.assertLess(agente.index("0017.md"), agente.index("0080.md"))
        self.assertIn("0009.md", md.split("## Normas contábeis")[1])

    def test_sem_chave_grupos_todas_sem_grupo(self):
        arqs, itens = indice.gerar_indice(self.raiz, SEM_ACERVO)
        titulos = [l[3:] for l in arqs["indices/resolucoes.md"].split("\n") if l.startswith("## ")]
        self.assertEqual(titulos, ["Sem grupo no Estoque Regulatório"])
        self.assertFalse(any("grupo" in i for i in itens))

    def test_titulos_e_situacao_nao_informada(self):
        self.assertEqual(self.item("cvm-instr-489")["titulo"], "Instrução CVM nº 489/2011")
        self.assertEqual(self.item("cvm-po-35")["titulo"], "Parecer de Orientação CVM nº 35/2008")
        self.assertEqual(self.item("cvm-oc-sse-0326")["titulo"], "Ofício Circular nº 3/2026/CVM/SSE")
        self.assertEqual(self.item("cvm-po-35")["situacao"], "nao-informada")
        self.assertIn("não informada pela CVM", self.arqs["indices/pareceres-orientacao.md"])
        self.assertIn("não informada pela CVM", self.arqs["indices/oficios-circulares.md"])
        self.assertIn("cvm/instrucoes/0489.md", self.arqs["indices/instrucoes.md"])

    def test_oficios_por_pasta_com_verbetes(self):
        md = self.arqs["indices/oficios-circulares.md"]
        sse = md.split("`sse1`")[1].split("\n## ")[0]
        sin = md.split("`sin`")[1].split("\n## ")[0]
        # data decrescente; o que tem arquivo não se repete como verbete
        self.assertLess(sse.index("cvm/oficios-circulares/sse1/oc-sse-0326.md"), sse.index("Ofício Circular nº 1/2025"))
        self.assertEqual(md.count("oc-sse-0326"), 1)
        verbete = next(l for l in sse.split("\n") if "1/2025" in l)
        self.assertIn("só verbete; texto não incluído", verbete)
        self.assertIn("oc-sse-0125.pdf", verbete)
        self.assertIn("Verbete sem texto \\| com barra.", verbete)
        self.assertIn("2025-02-03", verbete)
        antigo = next(l for l in sin.split("\n") if "2/1999" in l)
        self.assertIn("oc-sin-0299.html", antigo)  # sem PDF: link da página
        self.assertLess(sin.index("oc-sin-0122.md"), sin.index("2/1999"))
        linha = next(l for l in self.arqs["indice.md"].split("\n") if "indices/oficios-circulares.md" in l)
        self.assertIn("| 2 |", linha)
        self.assertIn("2 só verbete", linha)

    def test_verbetes_nao_entram_no_json(self):
        self.assertFalse(any("0125" in i["id"] for i in self.itens))


class TestIndiceSlugDoAcervo(unittest.TestCase):
    """O verbete casa com o arquivo pelo `slug` do acervo, não pelo nome da url_pagina."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        r = self.raiz = self._tmp.name
        gravar(r, "cvm/resolucoes/0009.md")
        gravar(r, "cvm/oficios-circulares/sse1/oficio-circular-cvmsse0122.md",
               id="cvm-oficio-circular-cvmsse0122", tipo="oficio-circular", numero="1",
               data="2022-06-21", ementa="Texto do SSE 01/22.", **SEM_VIGENCIA)
        gravar(r, "cvm/oficios-circulares/sin/oc-sin-0623-sin.md", id="cvm-oc-sin-0623-sin",
               tipo="oficio-circular", numero="6", data="2023-09-27", ementa="SIN 06/23.", **SEM_VIGENCIA)
        url = "https://x/legislacao/oficios-circulares/%s/%s.html"
        oficios = [
            {"titulo": "Ofício Circular CVM/SSE 01/22", "data": "2022-06-21", "superintendencia": "sse1",
             "slug": "oficio-circular-cvmsse0122", "slug_cvm": "OficioCircularCVMSSE0122",
             "descricao": "SSE 01/22", "url_pagina": url % ("sse1", "OficioCircularCVMSSE0122")},
            {"titulo": "Ofício Circular CVM/SIN 06/23", "data": "2023-09-27", "superintendencia": "sin",
             "slug": "oc-sin-0623-sin", "slug_cvm": "oc-sin-0623",
             "descricao": "SIN 06/23", "url_pagina": url % ("sin", "oc-sin-0623")},
            {"titulo": "Ofício Circular CVM/SSE 06/23", "data": "2023-07-05", "superintendencia": "sse1",
             "slug": "oc-sin-0623", "slug_cvm": "oc-sin-0623",
             "descricao": "SSE 06/23 sem texto", "url_pagina": url % ("sse1", "oc-sin-0623")},
            # acervo antigo, sem o campo slug: casa pelo nome da url_pagina
            {"titulo": "Ofício Circular CVM/SEP 01/99", "data": "1999-01-01", "superintendencia": "sep",
             "descricao": "Antigo", "url_pagina": url % ("sep", "oc-sep-0199")},
        ]
        self.acervo = os.path.join(r, "acervo.json")
        with open(self.acervo, "w", encoding="utf-8") as f:
            json.dump({"oficios_circulares": oficios}, f)
        self.arqs, self.itens = indice.gerar_indice(r, self.acervo)

    def test_titulo_vem_do_acervo_pelo_slug(self):
        titulos = {i["id"]: i["titulo"] for i in self.itens}
        self.assertEqual(titulos["cvm-oficio-circular-cvmsse0122"], "Ofício Circular CVM/SSE 01/22")
        self.assertEqual(titulos["cvm-oc-sin-0623-sin"], "Ofício Circular CVM/SIN 06/23")

    def test_com_arquivo_nao_vira_verbete(self):
        md = self.arqs["indices/oficios-circulares.md"]
        self.assertNotIn("SSE 01/22 |", md.replace("Ofício Circular CVM/SSE 01/22 |", ""))
        self.assertEqual(md.count("Ofício Circular CVM/SIN 06/23"), 1)
        verbete = next(l for l in md.split("\n") if "SSE 06/23 sem texto" in l)
        self.assertIn("só verbete", verbete)
        self.assertIn("Antigo", md)
        self.assertIn("2 só verbete", next(l for l in self.arqs["indice.md"].split("\n")
                                           if "indices/oficios-circulares.md" in l))


if __name__ == "__main__":
    unittest.main()
