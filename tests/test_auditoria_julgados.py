"""Testes da auditoria dos julgados (Fase 3b), sem rede e sem as ferramentas do macOS.

Tudo roda num repositório-raiz temporário: julgados, índices, cache da fonte, inventário, classificação do
CRSFN e RESULTADOS.md sintéticos. PDF e HTML são gerados aqui (o .gitignore ignora *.pdf). O runner
só é testado com subprocess falso: nenhuma sessão `claude -p` roda.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import auditoria_julgados as A  # noqa: E402

try:
    import pypdf  # noqa: F401
    TEM_PYPDF = True
except ImportError:
    TEM_PYPDF = False


def pdf_bytes(paginas):
    """PDF mínimo com texto (Helvetica), uma lista de linhas por página. Só ASCII."""
    objs = {1: b"<< /Type /Catalog /Pages 2 0 R >>",
            3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"}
    kids = []
    n = 4
    for linhas in paginas:
        txt = "BT /F1 10 Tf 12 TL 40 800 Td " + " ".join(
            "(%s) Tj T*" % ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            for ln in linhas) + " ET"
        s = txt.encode("latin-1")
        objs[n + 1] = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(s), s)
        objs[n] = (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources "
                   b"<< /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % (n + 1))
        kids.append(n)
        n += 2
    objs[2] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
        b" ".join(b"%d 0 R" % k for k in kids), len(kids))
    out = bytearray(b"%PDF-1.4\n")
    pos = {}
    for k in sorted(objs):
        pos[k] = len(out)
        out += b"%d 0 obj\n%s\nendobj\n" % (k, objs[k])
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for k in sorted(objs):
        out += b"%010d 00000 n \n" % pos[k]
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


def gravar(base, rel, conteudo):
    p = os.path.join(base, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb" if isinstance(conteudo, bytes) else "w") as f:
        f.write(conteudo)
    return p


def julgado(valores, corpo):
    fm = "\n".join("%s: %s" % kv for kv in valores.items())
    return "---\n%s\n---\n\n%s\n" % (fm, corpo)


def pagina_html(paragrafos):
    return ("<html><head><title>x</title></head><body><nav>menu</nav>"
            '<article class="contentTextoGeral">%s</article></body></html>'
            % "".join("<p>%s</p>" % p for p in paragrafos))


# Página do termo de compromisso (com qualificação pessoal) e o que ficou no acervo.
TC_LINHAS = [
    "TERMO DE COMPROMISSO que celebram a Comissao de Valores Mobiliarios e Fulano Beltrano,",
    "brasileiro, casado, administrador, portador do CPF " + "123.456." + "789-00, residente na Rua das",
    "Flores 10, compromete-se a pagar a quantia de cem mil reais nos termos do art. 11 da Lei",
    "6.385, de 7 de dezembro de 1976, em parcela unica no prazo de dez dias contados da",
    "publicacao do extrato do presente termo no sitio eletronico da autarquia federal, sendo",
    "certo que o descumprimento da obrigacao ensejara a retomada do processo sancionador",
    "e a cobranca dos valores pelos meios proprios previstos na regulamentacao em vigor.",
]
TC_CORPO = (
    "# Termo de compromisso\n\n"
    "TERMO DE COMPROMISSO que celebram a Comissao de Valores Mobiliarios e Fulano Beltrano, "
    "[dado pessoal retirado], compromete-se a pagar a quantia de cem mil reais nos termos do "
    "art. 11 da Lei 6.385, de 7 de dezembro de 1976, em parcela unica no prazo de dez dias "
    "contados da publicacao do extrato do presente termo no sitio eletronico da autarquia "
    "federal, sendo certo que o descumprimento da obrigacao ensejara a retomada do processo "
    "sancionador e a cobranca dos valores pelos meios proprios previstos na regulamentacao em "
    "vigor.\n")
COL_PARS = [
    "Reg. 1234/2020 - Consulta sobre a interpretacao do regulamento de emissores apresentada "
    "pela companhia aberta interessada ao Colegiado da autarquia.",
    "O Colegiado, acompanhando o entendimento da area tecnica, deliberou responder a consulta "
    "nos termos do memorando juntado aos autos, que conclui pela possibilidade da operacao desde "
    "que observadas as condicoes de divulgacao e de tratamento equitativo dos acionistas "
    "minoritarios previstas na regulamentacao aplicavel.",
    "Participaram da reuniao o Presidente e os Diretores do Colegiado.",
]


def montar_repo(raiz):
    """Repo-raiz sintético: 1 TC (PDF), 1 decisão do Colegiado (HTML), 1 acórdão do CRSFN (HTML)."""
    p = "julgados/"  # texto dos julgados na raiz do repositório
    ind = "plugins/normas/skills/consultar-normas/julgados/"  # índices, dentro da skill
    tc = {"id": "cvm-tc-20150101-a", "orgao": "cvm", "tipo": "termo-compromisso", "classe": "",
          "processo": "19957.000001/2015-01", "data": "2015-01-01", "relator": "SGE",
          "resultado": "aceito", "ementa": "Proposta de termo de compromisso aceita.",
          "ementa_fonte": "extracao", "tema": "outros", "dispositivos_citados": "lei-6385 art. 11",
          "nivel_verificacao": "pdf-extraido"}
    gravar(raiz, p + "cvm/tc/2015/tc-20150101-a.md", julgado(tc, TC_CORPO))
    col = {"id": "cvm-col-20200101-d1", "orgao": "cvm", "tipo": "decisao-colegiado",
           "classe": "consulta", "processo": "RJ2020/1234", "data": "2020-01-01",
           "relator": "SEP", "resultado": "deferido", "ementa": "Consulta respondida.",
           "ementa_fonte": "oficial", "tema": "outros", "dispositivos_citados": "",
           "nivel_verificacao": "html-convertido"}
    gravar(raiz, p + "cvm/colegiado/2020/col-20200101-d1.md", julgado(col, "\n\n".join(COL_PARS)))
    cr = {"id": "crsfn-19957-000009-2020-01", "orgao": "crsfn", "tipo": "acordao-crsfn",
          "classe": "", "processo": "19957.000009/2020-01", "data": "2021-05-05",
          "relator": "Conselheiro Fulano", "resultado": "condenacao", "ementa": "",
          "ementa_fonte": "", "tema": "outros", "dispositivos_citados": "",
          "nivel_verificacao": "html-convertido"}
    gravar(raiz, p + "crsfn/2021/crsfn-19957-000009-2020-01.md",
           julgado(cr, "Recurso contra decisao da CVM. Recurso conhecido e nao provido."))
    gravar(raiz, ind + "indice.md", "# Indice\n")
    gravar(raiz, ind + "indices/termo-compromisso.md",
           "| Processo | Data | Resultado | Tema | Ementa | Arquivo |\n|---|---|---|---|---|---|\n"
           "| 19957.000001/2015-01 | 2015-01-01 | aceito | outros | Acordo de Fulano Beltrano | "
           "../../../../../julgados/cvm/tc/2015/tc-20150101-a.md |\n")
    c = "dados/fase-2d/cache/"
    d = c + "termo-compromisso/2015/cvm-tc-20150101-a/"
    gravar(raiz, d + "01-pagina.html", pagina_html(["Termo de compromisso. Ver anexo."]))
    gravar(raiz, d + "02-anexo.pdf", pdf_bytes([TC_LINHAS, ["Pagina dois sem nada."]]))
    gravar(raiz, d + "registro.json", json.dumps({"id": "cvm-tc-20150101-a", "arquivos": [
        {"papel": "pagina", "arquivo": "01-pagina.html", "content_type": "text/html"},
        {"papel": "anexo", "arquivo": "02-anexo.pdf", "content_type": "application/pdf"}]}))
    d = c + "decisao-colegiado/2020/cvm-col-20200101-d1/"
    gravar(raiz, d + "01-pagina.html", pagina_html(COL_PARS))
    gravar(raiz, d + "registro.json", json.dumps({"id": "cvm-col-20200101-d1", "arquivos": [
        {"papel": "pagina", "arquivo": "01-pagina.html", "content_type": "text/html"}]}))
    gravar(raiz, c + "crsfn/acordao-9.html", "<html><body><p>Recurso contra decisao da CVM. "
           "Recurso conhecido e nao provido.</p></body></html>")
    gravar(raiz, c + "crsfn/acordao-bcb.pdf", pdf_bytes([[
        "CONSELHO DE RECURSOS DO SISTEMA FINANCEIRO NACIONAL", "Recorrente: Banco X S.A.",
        "Recorrido: Banco Central do Brasil", "Ementa: Recurso. Ver tambem Comissao de "
        "Valores Mobiliarios."]]))
    gravar(raiz, "dados/fase-2d/crsfn-classificacao.json", json.dumps({
        "gerado": "2026-10-30", "erros": {"crsfn-erro-1": "sem fonte"},
        "itens": {"crsfn-19957-000009-2020-01": {"orgao": "CVM", "criterio": "nup",
                                                  "cache": "acordao-9.html"},
                  "crsfn-bcb-1": {"orgao": "BCB", "criterio": "titulo", "cache": "acordao-bcb.pdf"},
                  "crsfn-ind-1": {"orgao": "INDETERMINADO", "criterio": "conflito",
                                  "cache": ""}}}))
    gravar(raiz, "fontes/julgados-inventario.json", json.dumps([
        {"id": "cvm-tc-20150101-a"}, {"id": "cvm-col-20200101-d1"},
        {"id": "cvm-col-20250408-d3248"}, {"id": "cvm-col-20990101-d9"}]))
    gravar(raiz, "fontes/RESULTADOS.md", "## Exceções\n\n- `cvm-col-20250408-d3248` (HTTP 410).\n")


class Base(unittest.TestCase):
    def setUp(self):
        self.raiz = os.path.realpath(tempfile.mkdtemp())
        montar_repo(self.raiz)
        A._PDF.clear()

    def tearDown(self):
        shutil.rmtree(self.raiz, ignore_errors=True)

    def univ(self):
        return A.universo(self.raiz, preambulos={
            "crsfn-bcb-1": {"cvm_preambulo": False, "cvm_inicio": True, "orgao": "BCB"},
            "crsfn-ind-1": {"cvm_preambulo": False, "cvm_inicio": False}}, log=lambda *a: 0)


def disp_falso(t):
    return ["lei-6385 art. 11"] if "art. 11" in t else []


@unittest.skipUnless(TEM_PYPDF, "pypdf ausente")
class TestUniversoESorteio(Base):
    def test_estratos(self):
        u = self.univ()
        n = {"%s/%s" % (e["bloco"], e["estrato"]): e["ids"] for e in u["estratos"]}
        self.assertEqual(n["A/tc-pdf"], ["cvm-tc-20150101-a"])
        self.assertEqual(n["A/colegiado-html"], ["cvm-col-20200101-d1"])
        self.assertEqual(n["A/crsfn-html"], ["crsfn-19957-000009-2020-01"])
        self.assertEqual(n["B/tc"], ["cvm-tc-20150101-a"])
        self.assertEqual(n["C/resultado-colegiado"], ["cvm-col-20200101-d1"])
        self.assertEqual(n["C/ementa-tema"], ["cvm-tc-20150101-a"])
        self.assertEqual(n["D/citacoes"], ["cvm-tc-20150101-a"])
        self.assertEqual(n["E/qualificacao"], ["cvm-tc-20150101-a"])
        self.assertEqual(n["F/crsfn-cvm-preambulo"], ["crsfn-bcb-1"])
        f = [e for e in u["estratos"] if e["bloco"] == "F"][0]
        self.assertIn("2 primeiras páginas", f["criterio"])
        self.assertEqual(u["extra"]["F/crsfn-indeterminado"], 1)
        self.assertEqual(u["extra"]["F/inventario-cvm"], 4)
        self.assertIn("<-- difere >5%", A.resumo_universo(u))

    def sortear(self, semente=A.SEMENTE, **kw):
        with mock.patch.object(A, "dispositivos_do_trecho", disp_falso):
            return A.sortear(self.univ(), semente, raiz=self.raiz, log=lambda *a: 0, **kw)

    def test_sorteio_deterministico_e_localizadores(self):
        a, b = self.sortear(), self.sortear()
        self.assertEqual(a["itens"], b["itens"])
        por = {(u["bloco"], u["estrato"]): u for u in a["itens"]}
        tc = por[("A", "tc-pdf")]
        self.assertEqual((tc["paginas"], tc["ancora"]), ([1], "fonte"))
        self.assertTrue(tc["fonte"].endswith("02-anexo.pdf"))
        self.assertIn("blocos", por[("A", "colegiado-html")])
        self.assertEqual(por[("B", "crsfn")]["pecas"][0]["fonte"],
                         "dados/fase-2d/cache/crsfn/acordao-9.html")
        self.assertEqual(por[("D", "citacoes")]["paginas"], [1])
        self.assertEqual(por[("E", "qualificacao")]["paginas"], [1])
        self.assertEqual(por[("F", "crsfn-cvm-preambulo")]["pecas"][0]["paginas"], [1])
        self.assertTrue(all(u["uid"][0] == u["bloco"] for u in a["itens"]))
        self.assertEqual(len({u["uid"] for u in a["itens"]}), len(a["itens"]))
        # amostra sem texto: nada além de ids, caminhos e localizadores
        chaves = set().union(*(u.keys() for u in a["itens"]))
        self.assertLessEqual(chaves, {"uid", "bloco", "estrato", "id", "tipo", "arquivo", "fonte",
                                      "paginas", "blocos", "papel", "ancora", "pecas",
                                      "marcador"})
        self.assertIn({"estrato": "A/pas-pdf", "pedido": 20, "sorteado": 0}, a["faltas"])

    def test_reauditoria_exclui_e_filtra_estratos(self):
        r = self.sortear(A.SEMENTE_REAUDITORIA, estratos=["A/tc-pdf", "B/tc"],
                         excluir={"cvm-tc-20150101-a"})
        self.assertEqual(r["itens"], [])
        r = self.sortear(A.SEMENTE_REAUDITORIA, estratos=["B/colegiado"])
        self.assertEqual([u["uid"] for u in r["itens"]], ["RB001"])

    def test_insumos_cegos_sem_caminho(self):
        am = self.sortear()
        saida = os.path.join(self.raiz, "..", os.path.basename(self.raiz) + "-insumos")
        saida = os.path.realpath(saida)
        self.addCleanup(shutil.rmtree, saida, True)
        with mock.patch.object(A, "dispositivos_do_trecho", disp_falso):
            feitos = A.insumos(am, saida, raiz=self.raiz, log=lambda *a: 0)
        self.assertTrue(all(not x["avisos"] for x in feitos), feitos)
        modelos = {(x["bloco"], x["estrato"]): x["modelo"] for x in feitos}
        self.assertEqual(modelos[("A", "tc-pdf")], "opus")
        self.assertEqual(modelos[("A", "colegiado-html")], "sonnet")
        self.assertEqual(modelos[("B", "tc")], "sonnet")
        self.assertTrue(os.path.exists(os.path.join(saida, "lotes.json")))
        for x in feitos:
            pasta = os.path.join(saida, x["lote"])
            nomes = os.listdir(pasta)
            self.assertIn("PROMPT.md", nomes)
            self.assertIn("itens.json", nomes)
            self.assertNotIn("lotes.json", nomes)
            for n in nomes:
                with open(os.path.join(pasta, n), "rb") as f:
                    dados = f.read()
                self.assertNotIn(self.raiz.encode(), dados, n)
                if n in ("itens.json", "PROMPT.md"):
                    self.assertNotIn(b"cvm-tc-20150101-a", dados)
                    self.assertNotIn(b"cvm-col-20200101-d1", dados)
        uid_b = [u["uid"] for u in am["itens"] if u["estrato"] == "tc" and u["bloco"] == "B"][0]
        lote_b = [x["lote"] for x in feitos if x["bloco"] == "B" and x["estrato"] == "tc"][0]
        with open(os.path.join(saida, lote_b, "itens.json")) as f:
            itens = json.load(f)
        self.assertEqual(itens[0]["id"], uid_b)
        self.assertNotIn("19957.000001/2015-01", json.dumps(itens))
        self.assertEqual(itens[0]["saida"], uid_b + "-saida.json")
        # recorte de PDF com uma página só
        lote_a = [x["lote"] for x in feitos if x["estrato"] == "tc-pdf"][0]
        from pypdf import PdfReader
        pdfs = [n for n in os.listdir(os.path.join(saida, lote_a)) if n.endswith(".pdf")]
        self.assertEqual(len(PdfReader(os.path.join(saida, lote_a, pdfs[0])).pages), 1)
        # bloco E: trecho do acervo com a marca; bloco D: lista numerada
        lote_e = [x["lote"] for x in feitos if x["bloco"] == "E"][0]
        acervo = [n for n in os.listdir(os.path.join(saida, lote_e)) if n.endswith("-acervo.md")]
        with open(os.path.join(saida, lote_e, acervo[0])) as f:
            self.assertIn("[dado pessoal retirado]", f.read())
        lote_d = [x["lote"] for x in feitos if x["bloco"] == "D"][0]
        with open(os.path.join(saida, lote_d, "itens.json")) as f:
            self.assertEqual(json.load(f)[0]["dispositivos"],
                             [{"n": 1, "dispositivo": "lei-6385 art. 11"}])
        # C ementa-tema mostra ementa e tema; prompt traz os temas
        lote_c = [x["lote"] for x in feitos if x["estrato"] == "ementa-tema"][0]
        with open(os.path.join(saida, lote_c, "itens.json")) as f:
            c = json.load(f)[0]
        self.assertEqual((c["ementa"], c["tema"]), ("Proposta de termo de compromisso aceita.",
                                                    "outros"))

    def test_comparar_ponta_a_ponta(self):
        am = self.sortear()
        saidas = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, saidas, True)
        lote = os.path.join(saidas, "01")
        os.makedirs(lote)
        por = {(u["bloco"], u["estrato"]): u["uid"] for u in am["itens"]}
        gravar(lote, por[("A", "tc-pdf")] + "-saida.md", "\n".join(TC_LINHAS))
        gravar(lote, por[("B", "colegiado")] + "-saida.json", json.dumps({
            "data": "01/01/2020", "processo": "RJ2020/1234", "relator": "SEP",
            "tipo": "decisao-colegiado", "classe": "consulta", "resultado": "deferido"}))
        gravar(lote, por[("B", "tc")] + "-saida.json", json.dumps({
            "data": "2015-01-02", "processo": "19957.000001/2015-01", "relator": "SGE",
            "tipo": "termo-compromisso", "classe": "", "resultado": "aceito"}))
        gravar(lote, por[("F", "crsfn-cvm-preambulo")] + "-saida.json",
               json.dumps({"orgao_de_origem": "BCB", "trecho": "Recorrido: Banco Central"}))
        with mock.patch.object(A, "dispositivos_do_trecho", disp_falso):
            comp = A.comparar(am, saidas, raiz=self.raiz)
        it = {r["uid"]: r for r in comp["itens"]}
        self.assertEqual(it[por[("A", "tc-pdf")]]["status"], "pii")
        self.assertFalse(it[por[("A", "tc-pdf")]]["erro"])
        self.assertEqual(it[por[("B", "colegiado")]]["status"], "igual")
        self.assertEqual(list(it[por[("B", "tc")]]["campos"]), ["data"])
        self.assertEqual(comp["resumo"]["B/tc"]["erros"], 1)
        self.assertEqual(comp["resumo"]["F/crsfn-cvm-preambulo"]["frase"],
                         "taxa abaixo de 3/1 (300%) com 95% de confiança")
        self.assertEqual(it[por[("D", "citacoes")]]["status"], "sem-saida")
        self.assertIn("B/tc", A.resumo_comparacao(comp))


class TestComparador(unittest.TestCase):
    def test_texto_igual_hifenizacao_e_diferente(self):
        corpo = ("O Colegiado deliberou aprovar a proposta de termo de compromisso apresentada "
                 "pelos proponentes, com a obrigacao de pagar a quantia de cem mil reais a CVM.")
        r = A.compara_texto(corpo, "", corpo)
        self.assertEqual(r["status"], "igual")
        r = A.compara_texto(corpo, "", corpo.replace("obrigacao", "obri- gacao"))
        self.assertEqual(r["status"], "igual-salvo-ressalvas")
        self.assertEqual({d["classe"] for d in r["diffs"]}, {"hifenizacao"})
        r = A.compara_texto(corpo, "", corpo.replace("cem mil", "duzentos mil"))
        self.assertEqual(r["status"], "diferente")
        r = A.compara_texto(corpo, "", corpo.replace("1º", "1o"))
        self.assertEqual(r["status"], "igual")
        r = A.compara_texto(corpo, "", "texto que nao tem nada a ver com o acervo daqui")
        self.assertEqual(r["status"], "sem-esperado")

    def test_campos(self):
        self.assertTrue(A.compara_campo("data", "2020-01-05", "05/01/2020")[0])
        self.assertFalse(A.compara_campo("data", "2020-01-05", "2020-01-06")[0])
        self.assertTrue(A.compara_campo("processo", "19957.001770/2022-12; RJ2015/1",
                                        "19957.001770/2022-12")[0])
        self.assertTrue(A.compara_campo("relator", "Diretor Otto Lobo", "Otto Lobo")[0])
        self.assertTrue(A.compara_campo("relator", "João Pedro Nascimento",
                                        "Diretor Joao Pedro Nascimento")[0])
        self.assertFalse(A.compara_campo("relator", "SGE", "SEP")[0])
        self.assertTrue(A.compara_campo("tipo", "pas", " PAS ")[0])

    def test_citacoes_precisao_e_recall(self):
        u = {"uid": "D001", "bloco": "D", "estrato": "citacoes", "id": "x", "arquivo": ""}
        with mock.patch.object(A, "ancora", return_value="t"), \
                mock.patch.object(A, "dispositivos_do_trecho", return_value=["a", "b", "c"]):
            r = A.comparar_item("/x", u, json.dumps({
                "dispositivos": [{"n": 1, "certo": "sim"}, {"n": 2, "certo": "nao"},
                                 {"n": 3, "certo": "sim"}], "faltam": ["d"]}))
        self.assertEqual((r["listados"], r["certos"], r["errados"], r["faltam"]),
                         (3, 2, ["b"], ["d"]))
        self.assertTrue(r["erro"])

    def test_ementa_tema_e_pii(self):
        with tempfile.TemporaryDirectory() as raiz:
            gravar(raiz, "j.md", julgado({"id": "x", "ementa": "e", "tema": "outros"}, "c"))
            u = {"uid": "C001", "bloco": "C", "estrato": "ementa-tema", "id": "x", "arquivo": "j.md"}
            r = A.comparar_item(raiz, u, json.dumps({
                "afirma_sem_suporte": "nao", "omite_decisao": "sim", "nome_pessoa_fisica": "não",
                "tema_defensavel": "nao"}))
            self.assertEqual((r["erro_ementa"], r["erro_tema"]), (["omite_decisao"], True))
            u = dict(u, bloco="E", estrato="qualificacao")
            r = A.comparar_item(raiz, u, json.dumps({"dado_pessoal_restante": ["CPF, 2o par."],
                                                     "corte_indevido": []}))
            self.assertTrue(r["erro"])
            r = A.comparar_item(raiz, u, "isto não é json")
            self.assertEqual(r["status"], "saida-invalida")

    def test_frase(self):
        self.assertEqual(A.frase(40, 0), "taxa abaixo de 3/40 (7,5%) com 95% de confiança")
        self.assertEqual(A.frase(20, 1), "1 erro(s) em 20 (5%)")
        self.assertEqual(A.frase(0, 0), "sem item conferido")

    def test_vazamento_marca_o_item(self):
        with tempfile.TemporaryDirectory() as raiz, tempfile.TemporaryDirectory() as saidas:
            lote = os.path.join(os.path.realpath(saidas), "01")
            os.makedirs(lote)
            gravar(raiz, "j.md", julgado({"id": "x"}, "c"))
            gravar(lote, "F001-saida.json", json.dumps({"orgao_de_origem": "BCB"}))
            with open(os.path.join(lote, "log.jsonl"), "w") as f:
                f.write(json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Read",
                     "input": {"file_path": "/Users/x/cerebro/plugins/a.md"}}]}}) + "\n")
            am = {"itens": [{"uid": "F001", "bloco": "F", "estrato": "crsfn-cvm-preambulo",
                             "id": "crsfn-1", "arquivo": ""}]}
            comp = A.comparar(am, saidas, raiz=raiz)
            self.assertEqual(comp["itens"][0]["status"], "vazou")
            self.assertEqual(comp["resumo"]["F/crsfn-cvm-preambulo"]["vazou"], 1)


class TestCensos(Base):
    def test_censos(self):
        class Pessoas:
            def do_julgado(self, valores, corpo):
                return ["Fulano Beltrano"] if valores["id"] == "cvm-tc-20150101-a" else []

        pre = {"crsfn-bcb-1": {"orgao": "BCB", "criterio": "titulo", "cache": "acordao-bcb.pdf",
                               "texto": True, "cvm_preambulo": True, "cvm_inicio": True},
               "crsfn-ind-1": {"orgao": "INDETERMINADO", "criterio": "conflito", "cache": "",
                               "texto": False, "cvm_preambulo": False, "cvm_inicio": False}}
        c = A.censos(self.raiz, pessoas=Pessoas(), preambulos=pre, log=lambda *a: 0)
        cvm = c["completude"]["cvm"]
        self.assertEqual(cvm["faltam_nas_excecoes"], ["cvm-col-20250408-d3248"])
        self.assertEqual(cvm["faltam_sem_excecao"], ["cvm-col-20990101-d9"])
        self.assertEqual(cvm["sobram"], [])
        cr = c["completude"]["crsfn"]
        self.assertEqual((cr["cvm"], cr["publicados"], cr["faltam_sem_excecao"]), (1, 1, []))
        self.assertEqual(cr["erros_classificacao"], ["crsfn-erro-1"])
        achados = {(x["campo"], x["trecho"]) for x in c["nomes"]["achados"]}
        self.assertEqual(achados, {("indice", "Fulano Beltrano")})
        self.assertEqual(c["nomes"]["linhas_sem_julgado"], 0)
        self.assertEqual([x["id"] for x in c["crsfn"]["cvm_no_preambulo"]], ["crsfn-bcb-1"])
        self.assertEqual([x["id"] for x in c["crsfn"]["indeterminado"]], ["crsfn-ind-1"])
        self.assertIn("(d) CRSFN indeterminado: 1", A.resumo_censos(c))

    def test_duplicatas_e_suspensas(self):
        def j(id_, sha, corpo, tipo="acordao-crsfn", resultado="", data="2022-01-01"):
            return {"id": id_, "tipo": tipo, "sha256_fonte": sha, "corpo": corpo, "data": data,
                    "resultado": resultado, "arquivo": id_ + ".md"}
        ac = "ACÓRDÃO CRSFN** 173/2022\n\nRecurso nao provido."
        pubs = [j("crsfn-1", "s1", ac), j("crsfn-1-2", "s1", ac + " "),
                j("crsfn-2", "s2", "ACÓRDÃO CRSFN 34/2022 primeiro"),
                j("crsfn-2-2", "s2", "ACÓRDÃO CRSFN 35/2022 segundo"),
                j("crsfn-3", "s3", "ACÓRDÃO CRSFN nº 181/2021 a"),
                j("crsfn-3-2", "s4", "ACÓRDÃO CRSFN nº 181/2021 b"),
                j("cvm-col-1", "s5", "## Decisão\n\nO Diretor X solicitou vista do processo."
                  "\n\n## Voto\n\nVoto pelo indeferimento. Deliberou-se.",
                  "decisao-colegiado", "indeferido"),
                j("cvm-col-2", "s6", "## Decisão\n\nO Colegiado, por unanimidade, deliberou "
                  "indeferir o pedido, que estava suspenso.", "decisao-colegiado", "indeferido"),
                j("cvm-col-3", "s7", "## Decisão\n\nAdiado.", "decisao-colegiado", ""),
                j("cvm-col-4", "s8", "## Decisão\n\n(PEDIDO DE VISTA DO PTE) Retomada; registro "
                  "suspenso por decisão anterior.", "decisao-colegiado", "deferido"),
                j("cvm-col-5", "s9", "## Decisão\n\nO Colegiado deu continuidade, tendo ficado "
                  "adiada sua decisão.", "decisao-colegiado", "outro")]
        d = A.censo_duplicatas(self.raiz, pubs)
        self.assertEqual([(g["ids"], g["classe"]) for g in d["grupos_sha"]],
                         [(["crsfn-1", "crsfn-1-2"], "duplicata"),
                          (["crsfn-2", "crsfn-2-2"], "acordaos-distintos")])
        self.assertEqual(d["arquivos_sha"], 4)
        self.assertEqual([(g["acordao"], g["ids"], g["corpo_identico"])
                          for g in d["mesmo_numero_sha_diferente"]],
                         [("181/2021", ["crsfn-3", "crsfn-3-2"], False)])
        self.assertEqual([x["id"] for x in A.censo_suspensas(self.raiz, pubs)],
                         ["cvm-col-1", "cvm-col-5"])

    def test_nome_no_id(self):
        self.assertEqual(A._nome_em_slug("cvm-pas-fulano-beltrano-2019", ["Fulano de Beltrano"]),
                         "Fulano Beltrano")
        self.assertEqual(A._nome_em_slug("cvm-pas-19957-000001-2019-01", ["Fulano Beltrano"]), "")

    @unittest.skipUnless(TEM_PYPDF, "pypdf ausente")
    def test_preambulo_do_pdf(self):
        pre = A.censo_preambulos(self.raiz, log=lambda *a: 0)
        self.assertEqual(set(pre), {"crsfn-bcb-1", "crsfn-ind-1"})
        self.assertTrue(pre["crsfn-bcb-1"]["cvm_inicio"])
        self.assertTrue(pre["crsfn-bcb-1"]["texto"])
        self.assertEqual(pre["crsfn-ind-1"]["cache"], "")
        self.assertTrue(os.path.exists(A.caminhos(self.raiz)["preambulos"]))


class TestRodar(unittest.TestCase):
    def setUp(self):
        self.pasta = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.pasta, True)
        lotes = []
        for k in range(6):
            nome = "%02d-b-tc" % (k + 1)
            gravar(self.pasta, nome + "/itens.json",
                   json.dumps([{"id": "B%03d" % k, "saida": "B%03d-saida.json" % k}]))
            gravar(self.pasta, nome + "/PROMPT.md", "x")
            lotes.append({"lote": nome, "modelo": "opus" if k == 0 else "sonnet"})
        gravar(self.pasta, "01-b-tc/B000-saida.json", "{}")  # lote 01 já completo
        gravar(self.pasta, "lotes.json", json.dumps(lotes))
        self.chamadas, self.ativos, self.pico = [], 0, 0
        self.trava = threading.Lock()

    def run_falso(self, cmd, input=None, cwd=None, stdout=None, stderr=None, **kw):
        with self.trava:
            self.chamadas.append((cmd, cwd, input))
            self.ativos += 1
            self.pico = max(self.pico, self.ativos)
        time.sleep(0.05)
        with open(os.path.join(cwd, "itens.json")) as f:
            itens = json.load(f)
        for i in itens:
            gravar(cwd, i["saida"], "{}")
        stdout.write(json.dumps({"type": "result", "total_cost_usd": 0.5}) + "\n")
        with self.trava:
            self.ativos -= 1
        return subprocess.CompletedProcess(cmd, 0)

    def test_roda_pendentes_com_teto(self):
        res = A.rodar(self.pasta, paralelo=8, run=self.run_falso, log=lambda *a: 0)
        self.assertEqual(sorted(res), ["%02d-b-tc" % k for k in range(2, 7)])
        self.assertLessEqual(self.pico, 4)
        cmd, cwd, entrada = self.chamadas[0]
        self.assertEqual(cmd[:4], ["claude", "-p", "--model", "sonnet"])
        self.assertIn("--strict-mcp-config", cmd)
        self.assertEqual(cmd[cmd.index("--tools") + 1], "Read,Write")
        self.assertEqual(cmd[cmd.index("--output-format") + 1], "stream-json")
        self.assertIn("PROMPT.md", entrada)
        self.assertTrue(cwd.startswith(self.pasta))
        self.assertTrue(all(r["completo"] for r in res.values()))
        with open(os.path.join(self.pasta, "02-b-tc", "execucao.json")) as f:
            self.assertEqual(json.load(f)["total_cost_usd"], 0.5)
        self.assertTrue(os.path.exists(os.path.join(self.pasta, "02-b-tc", "log.jsonl")))
        # retomada: tudo completo, nada roda
        self.chamadas = []
        self.assertEqual(A.rodar(self.pasta, run=self.run_falso, log=lambda *a: 0), {})
        self.assertEqual(self.chamadas, [])

    def test_recusa_pasta_no_repo(self):
        with self.assertRaises(SystemExit):
            A.rodar(os.path.join(A.RAIZ, "dados", "fase-3b", "insumos"), run=self.run_falso)
        self.assertEqual(self.chamadas, [])


class TestLotes(unittest.TestCase):
    def test_lotes_e_modelo(self):
        itens = [{"uid": "A%03d" % i, "bloco": "A", "estrato": "tc-pdf"} for i in range(23)]
        itens += [{"uid": "B001", "bloco": "B", "estrato": "tc"}]
        ls = A.lotes(itens)
        self.assertEqual([(n, len(us)) for n, us in ls],
                         [("01-a-tc-pdf", 10), ("02-a-tc-pdf", 10), ("03-a-tc-pdf", 3),
                          ("04-b-tc", 1)])
        self.assertEqual(A.modelo_do_lote("A", "pas-ocr"), "opus")
        self.assertEqual(A.modelo_do_lote("A", "crsfn-html"), "sonnet")
        self.assertEqual(A.modelo_do_lote("D", "citacoes"), "sonnet")

    def test_trecho_acervo(self):
        corpo = "Primeiro paragrafo qualquer.\n\nSegundo com o alvo procurado aqui dentro mesmo " \
                "agora sim.\n\nTerceiro paragrafo.\n\nQuarto."
        t = A.trecho_acervo(corpo, "Segundo com o alvo procurado aqui dentro mesmo agora sim.",
                            margem=0)
        self.assertEqual(t, "Segundo com o alvo procurado aqui dentro mesmo agora sim.")
        self.assertEqual(A.trecho_acervo(corpo, "nada a ver com isso tudo de jeito nenhum"), "")


if __name__ == "__main__":
    unittest.main()
