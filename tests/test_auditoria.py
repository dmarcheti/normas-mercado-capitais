"""Testes da auditoria da Fase 3 (sem rede, sem textutil e sem PDFKit).

O replay roda num repositório Git temporário com três commits sintéticos (texto inicial, uma
alteração e uma segunda alteração que sobrescreve a primeira). Nada aqui lê o acervo real:
as normas de `cmn/` e `bcb/` mudam em paralelo.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))
sys.path.insert(0, AQUI)

import auditoria as A  # noqa: E402
import auditoria_texto as T  # noqa: E402
import auditoria_universo as U  # noqa: E402
from test_converter import NS, par, run  # noqa: E402

try:
    import pypdf  # noqa: F401
    TEM_PYPDF = True
except ImportError:
    TEM_PYPDF = False

FIX = os.path.join(AQUI, "fixtures", "auditoria")


def fixture(nome):
    with open(os.path.join(FIX, nome), encoding="utf-8") as f:
        return f.read()


def gravar(base, rel, texto):
    p = os.path.join(base, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)


NORMA = "cvm/resolucoes/resolucao-cvm-001.md"
ATO = "cvm/alteradoras/resolucao-cvm-100.md"
ATO2 = "cvm/alteradoras/resolucao-cvm-101.md"


def norma(data_base, art1, art2a=None, art3="Texto três."):
    partes = ["---", "tipo: resolucao", "data_base: %s" % data_base, "---", "",
              "# RESOLUÇÃO FICTÍCIA Nº 1", "", "## Art. 1º", "", art1, "", "## Art. 2º", "",
              "Texto dois.", ""]
    if art2a:
        partes += ["## Art. 2º-A", "", art2a, ""]
    partes += ["## Art. 3º", "", art3, ""]
    return "\n".join(partes)


def ato(n, corpo):
    return "---\ntipo: alteradora\nnumero: %d\n---\n\n# RESOLUÇÃO FICTÍCIA Nº %d\n\n%s\n" % (n, n, corpo)


class RepoTemporario(unittest.TestCase):
    """Repo Git com: (1) texto inicial; (2) ato 100: nova redação do art. 1º, inclui o 2º-A,
    revoga o 3º e muda o frontmatter e o índice; (3) ato 101: nova redação do art. 1º de novo."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.repo = os.path.realpath(cls._tmp.name)
        cls.git("init", "-q", "-b", "main")
        base = os.path.join(cls.repo, U.NORMAS)
        gravar(base, NORMA, norma("2020-01-01", "Texto um."))
        gravar(base, "indice.md", "índice v1\n")
        cls.commit("inicial")
        gravar(base, NORMA, norma("2025-01-01", "Texto um alterado.", "Texto incluído.",
                                  "(Revogado pela Resolução Fictícia nº 100, de 2025.)"))
        gravar(base, "indice.md", "índice v2\n")
        gravar(base, ATO, ato(100, "Art. 1º O art. 1º passa a vigorar: “Art. 1º Texto um alterado.”"))
        cls.commit("Res. CVM 100/2025 (DOU 2025-01-01): altera Res. CVM 1")
        gravar(base, NORMA, norma("2026-01-01", "Texto um final.", "Texto incluído.",
                                  "(Revogado pela Resolução Fictícia nº 100, de 2025.)"))
        gravar(base, ATO2, ato(101, "Art. 1º O art. 1º passa a vigorar: “Art. 1º Texto um final.”"))
        cls.commit("Res. CVM 101/2026 (DOU 2026-01-01): altera Res. CVM 1")
        cls.unidades = U.universo_replay(cls.repo, "main")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    @classmethod
    def git(cls, *args):
        subprocess.run(["git", "-C", cls.repo, "-c", "user.name=teste", "-c", "user.email=t@t",
                        "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"] + list(args),
                       check=True, capture_output=True)

    @classmethod
    def commit(cls, msg):
        cls.git("add", "-A")
        cls.git("commit", "-q", "-m", msg)

    def por(self, commit_ordem, loc):
        achou = [u for u in self.unidades if u["ordem_commit"] == commit_ordem and u["localizador"] == loc]
        self.assertEqual(len(achou), 1, (commit_ordem, loc, self.unidades))
        return achou[0]


class TestReplay(RepoTemporario):
    def test_commits_de_replay_em_ordem_cronologica(self):
        msgs = [m for _s, m in U.commits_replay(self.repo, "main")]
        self.assertEqual(len(msgs), 2)
        self.assertIn("Res. CVM 100", msgs[0])

    def test_unidades_e_categorias(self):
        locs = sorted((u["ordem_commit"], u["localizador"], u["categoria"]) for u in self.unidades)
        self.assertEqual(locs, [(0, "Art. 1º", "nova-redacao"), (0, "Art. 2º-A", "inclusao"),
                                (0, "Art. 3º", "revogacao"), (1, "Art. 1º", "nova-redacao")])

    def test_frontmatter_indice_e_alteradoras_ficam_fora(self):
        self.assertTrue(all(u["norma"] == NORMA for u in self.unidades))
        self.assertFalse(any(u["localizador"] == T.PREAMBULO for u in self.unidades))

    def test_sobrescrito(self):
        self.assertTrue(self.por(0, "Art. 1º")["sobrescrito"])
        self.assertFalse(self.por(1, "Art. 1º")["sobrescrito"])
        self.assertFalse(self.por(0, "Art. 2º-A")["sobrescrito"])

    def test_atos_do_commit(self):
        self.assertEqual(self.por(0, "Art. 1º")["atos"], [ATO])
        self.assertEqual(self.por(1, "Art. 1º")["atos"], [ATO2])

    def test_ids_estaveis_e_unicos(self):
        ids = [u["id"] for u in self.unidades]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids, [u["id"] for u in U.universo_replay(self.repo, "main")])

    def test_insumo_do_replay_e_comparador(self):
        u = self.por(0, "Art. 1º")
        with tempfile.TemporaryDirectory() as lote:
            ins, inst, aviso = A.montar_insumo(self.repo, u, lote, lote)
            self.assertIsNone(aviso)
            self.assertEqual(ins, [u["id"] + "-antes.md", u["id"] + "-ato.md"])
            with open(os.path.join(lote, ins[0]), encoding="utf-8") as f:
                antes = f.read()
            with open(os.path.join(lote, ins[1]), encoding="utf-8") as f:
                ato_txt = f.read()
        self.assertIn("Texto um.", antes)
        self.assertNotIn("Art. 2º", antes)
        self.assertIn("Texto um alterado.", ato_txt)
        self.assertNotIn("numero:", ato_txt)
        self.assertIn("«Art. 1º»", inst)
        self.assertEqual(A.comparar_item(self.repo, u, "## Art. 1º\n\nTexto um alterado.\n")["status"], "igual")
        r = A.comparar_item(self.repo, u, "## Art. 1º\n\nTexto um final.\n")
        self.assertEqual(r["status"], "diferente")
        self.assertEqual(r["diffs"][0]["esperado"], "alterado.")

    def test_insumo_de_inclusao_avisa_que_nao_havia_dispositivo(self):
        u = self.por(0, "Art. 2º-A")
        with tempfile.TemporaryDirectory() as lote:
            ins, _inst, _aviso = A.montar_insumo(self.repo, u, lote, lote)
            with open(os.path.join(lote, ins[0]), encoding="utf-8") as f:
                self.assertIn("não existe no texto anterior", f.read())


class TestInsumosSemCaminho(RepoTemporario):
    """Lotes de replay, de página (PDF recortado, simulado) e de HTML: nenhum arquivo do lote
    leva caminho do repo."""

    def test_nenhum_caminho_do_repo_nos_lotes(self):
        base = os.path.join(self.repo, U.NORMAS)
        gravar(base, "leis/lei-1.md", "---\ntipo: lei\n---\n\n## Art. 1º\n\nEsta Lei dispõe sobre %s.\n\n"
               "## Art. 2º\n\nOutro.\n" % self.repo)
        gravar(self.repo, "dados/fontes/lei-1.htm",
               "<html><body><p>Art. 1º Esta Lei dispõe sobre %s.</p><p>Art. 2º Outro.</p></body></html>"
               % self.repo)
        gravar(self.repo, "dados/f/x.pdf", "%PDF-1.4 fictício")
        lei = U.unidade("3", "redacao-incluido", "leis/lei-1.md", "Art. 1º", 4, fonte="dados/fontes/lei-1.htm")
        pag = U.unidade("5", "sumario", "autorregulacao/x.md", "página 2", 2, fonte="dados/f/x.pdf", paginas=[2])
        amostra = {"itens": self.unidades + [lei, pag]}
        recortes = []

        def falso_recorte(origem, paginas, destino):
            recortes.append((origem, paginas))
            with open(destino, "wb") as f:
                f.write(b"%PDF-1.4\n")
            return destino

        with tempfile.TemporaryDirectory() as saida, mock.patch.object(A, "recortar_pdf", falso_recorte):
            feitos = A.insumos(amostra, saida, self.repo, lote_max=2)
            nomes = sorted(os.listdir(saida))
            self.assertEqual(len(feitos), len(nomes))
            arquivos = []
            for n in nomes:
                pasta = os.path.join(saida, n)
                self.assertIn("PROMPT.md", os.listdir(pasta))
                self.assertIn("itens.json", os.listdir(pasta))
                for a in os.listdir(pasta):
                    with open(os.path.join(pasta, a), "rb") as f:
                        arquivos.append((n, a, f.read()))
        self.assertEqual(recortes, [(os.path.join(self.repo, "dados/f/x.pdf"), [2])])
        for n, a, conteudo in arquivos:
            self.assertNotIn(self.repo.encode("utf-8"), conteudo, (n, a))
            self.assertNotIn(b"plugins/normas", conteudo, (n, a))
        self.assertTrue(any(a.endswith("-fonte.html") for _n, a, _c in arquivos))
        self.assertTrue(any(n.endswith("-c5-sumario") for n, _a, _c in arquivos))
        prompt = [c for _n, a, c in arquivos if a == "PROMPT.md"][0].decode("utf-8")
        self.assertIn("sem o parâmetro `pages`", prompt)

    def test_lotes_por_categoria_e_tamanho(self):
        ls = A.lotes(self.unidades, lote_max=1)
        self.assertEqual(len(ls), 4)
        self.assertTrue(all(len(us) == 1 for _n, us in ls))
        self.assertEqual([n for n, _us in ls], sorted(n for n, _us in ls))
        ls = A.lotes(self.unidades, lote_max=10)
        self.assertEqual(sorted(n.split("-", 1)[1] for n, _ in ls),
                         ["c1-inclusao", "c1-nova-redacao", "c1-revogacao"])


# ---------------------------------------------------------------- sorteio

def universo_sintetico():
    us = []
    for k in range(30):
        us.append(U.unidade("1", "inclusao", "n%02d.md" % (k % 10), "Art. %d" % k, k))
        us.append(U.unidade("1", "nova-redacao", "n%02d.md" % (k % 12), "Art. %d" % k, k,
                            commit="c%d" % k, sobrescrito=k % 3 == 0))
    for k in range(5):
        us.append(U.unidade("1", "revogacao", "r%d.md" % k, "Art. 1", k, commit="c"))
    for k in range(9):
        us.append(U.unidade("4", "so-pdf", "bcb/p%d.md" % (k % 3), "página %d" % k, k, paginas=[k + 1]))
    us.append(U.unidade("3", "tabela", "leis/l.md", "Art. 1", 1))
    us.append(U.unidade("4", "tabela", "cmn/a.md", "Art. 1", 1))
    return {"data_base": "2026-10-30", "unidades": us}


class TestSorteio(unittest.TestCase):
    def setUp(self):
        self.uni = universo_sintetico()

    def ids(self, am):
        return [u["id"] for u in am["itens"]]

    def test_deterministico(self):
        a = A.sortear(self.uni, 20261030, hoje="2026-10-30")
        b = A.sortear(json.loads(json.dumps(dict(self.uni, unidades=self.uni["unidades"][::-1]))),
                      20261030, hoje="2026-10-30")
        self.assertEqual(self.ids(a), self.ids(b))
        self.assertEqual(a["universo_sha256"], b["universo_sha256"])
        self.assertNotEqual(self.ids(a), self.ids(A.sortear(self.uni, 20261031)))

    def test_uma_por_norma_enquanto_houver(self):
        am = A.sortear(self.uni, 20261030)
        inc = [u for u in am["itens"] if u["categoria"] == "inclusao"]
        self.assertEqual(len(inc), 12)
        self.assertEqual(len({u["norma"] for u in inc}), 10)

    def test_censo_censo_norma_e_abaixo_do_pedido(self):
        am = A.sortear(self.uni, 20261030)
        self.assertEqual(am["resumo"]["1/revogacao"]["sorteado"], 5)
        so = [u for u in am["itens"] if u["categoria"] == "so-pdf"]
        self.assertEqual(sorted(u["norma"] for u in so), ["bcb/p0.md", "bcb/p1.md", "bcb/p2.md"])
        self.assertTrue(am["resumo"]["4/tabela"]["abaixo_do_pedido"])
        self.assertEqual(am["resumo"]["4/tabela"]["sorteado"], 1)
        self.assertEqual(am["resumo"]["3/tabela"]["sorteado"], 1)
        self.assertFalse(am["resumo"]["3/tabela"]["abaixo_do_pedido"])
        self.assertEqual(am["resumo"]["2/ocr"]["sorteado"], 0)

    def test_metades_do_sobrescrito(self):
        am = A.sortear(self.uni, 20261030)
        nr = [u for u in am["itens"] if u["categoria"] == "nova-redacao"]
        self.assertEqual(sum(1 for u in nr if u["sobrescrito"]), 8)
        self.assertEqual(sum(1 for u in nr if not u["sobrescrito"]), 7)
        self.assertEqual(am["resumo"]["1/nova-redacao"]["por_sobrescrito"]["true"],
                         {"universo": 10, "sorteado": 8})

    def test_reauditoria_exclui_ja_sorteados(self):
        am = A.sortear(self.uni, 20261030)
        ja = set(self.ids(am))
        re_ = A.sortear(self.uni, 20261031, {"1/inclusao"}, ja)
        self.assertEqual(list(re_["resumo"]), ["1/inclusao"])
        self.assertEqual(len(re_["itens"]), 12)
        self.assertFalse(ja & set(self.ids(re_)))
        self.assertEqual(re_["resumo"]["1/inclusao"]["universo"], 18)


# ---------------------------------------------------------------- texto

class TestSecoes(unittest.TestCase):
    TEXTO = ("---\ntipo: x\n---\n\n# TÍTULO\n\n## Art. 1º\n\nUm.\n\n## Art. 2º\n\nDois.\n\n"
             "ANEXO A\n\n## Art. 1º\n\nUm do anexo.\n\nANEXO A\n\nRepetido.\n\n## Notas de rodapé\n\n[1] Nota.\n")

    def test_secoes(self):
        nomes = [n for n, _a, _b in T.secoes(self.TEXTO)]
        self.assertEqual(nomes, ["preambulo", "Art. 1º", "Art. 2º", "ANEXO A", "ANEXO A, Art. 1º",
                                 "ANEXO A (2)", "Notas de rodapé"])
        self.assertEqual(T.texto_secao(self.TEXTO, "Art. 2º"), "## Art. 2º\n\nDois.\n")
        self.assertIsNone(T.texto_secao(self.TEXTO, "Art. 9º"))
        self.assertTrue(T.eh_anexo("ANEXO A, Art. 1º"))
        self.assertTrue(T.eh_anexo("Art. 1º", "cvm/resolucoes/anexo-i.md"))

    def test_secao_da_linha(self):
        secs = T.secoes(self.TEXTO)
        linhas = self.TEXTO.split("\n")
        self.assertEqual(T.secao_da_linha(secs, linhas.index("Dois.")), "Art. 2º")
        self.assertEqual(T.secao_da_linha(secs, linhas.index("Um do anexo.")), "ANEXO A, Art. 1º")


class TestNormalizacaoEComparador(unittest.TestCase):
    def test_normalizar(self):
        self.assertEqual(T.normalizar("## Art. 10. O “prazo” — de 5 dias"), 'art 10 o "prazo" - de 5 dias')
        self.assertEqual(T.normalizar("**Art. 1º** texto"), T.normalizar("Art. 1o texto"))
        self.assertEqual(T.normalizar("§ 3º (Revogado pela Resolução CVM nº 181)"), T.normalizar("§ 3º (Revogado)"))
        self.assertEqual(T.normalizar("| a | b |\n|---|---|\n| 1 | 2 |"), "a b 1 2")
        self.assertEqual(T.normalizar("eﬁciência  ( texto )"), "eficiência (texto)")

    def test_diff_palavras(self):
        self.assertEqual(T.diff_palavras("Art. 1º O prazo é de 30 dias.", "**Art. 1º** O prazo é de 30 dias."), [])
        d = T.diff_palavras("um dois três quatro cinco", "um dois TRES quatro cinco seis")
        self.assertEqual([(x["op"], x["esperado"], x["saida"]) for x in d],
                         [("replace", "três", "tres"), ("insert", "", "seis")])
        self.assertEqual(d[0]["antes"], "um dois")

    def test_janela_acha_o_trecho(self):
        acervo = " ".join("p%d" % i for i in range(500))
        saida = " ".join("p%d" % i for i in range(200, 260))
        txt, i0, i1 = T.janela(acervo, saida)
        self.assertEqual((i0, i1), (200, 260))
        self.assertEqual(txt, saida)
        self.assertEqual(T.janela(acervo, "nada a ver com isso aqui agora"), ("", 0, 0))

    def test_janela_com_diferenca_no_meio(self):
        acervo = " ".join("p%d" % i for i in range(500))
        saida = " ".join("p%d" % i if i != 230 else "ERRO" for i in range(200, 260))
        _txt, i0, i1 = T.janela(acervo, saida)
        self.assertEqual((i0, i1), (200, 260))

    def test_linhas_repetidas_e_cabecalho(self):
        texto = "\n".join(["INFORMAÇÃO PÚBLICA %d" % i if i % 2 else "texto %d único" % i * 3 for i in range(10)])
        rep = T.linhas_repetidas(texto)
        self.assertIn("informação pública #", rep)
        diff = {"esperado": "informação pública 3", "saida": ""}
        self.assertTrue(A._e_cabecalho(diff, rep))
        self.assertFalse(A._e_cabecalho({"esperado": "outra coisa", "saida": ""}, rep))


class TestComparadorPaginas(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = self._tmp.name
        linhas = []
        for p in range(1, 4):
            linhas += ["Palavra%d texto da página %d com conteúdo normativo número %d." % (k, p, k) for k in range(8)]
            linhas += ["CABEÇALHO REPETIDO DA NORMA", "Página %d" % p]
        gravar(os.path.join(self.repo, U.NORMAS), "autorregulacao/n.md", "---\ntipo: x\n---\n\n" + "\n".join(linhas) + "\n")
        self.u = U.unidade("5", "quebra-pagina", "autorregulacao/n.md", "páginas 1-2", 1, paginas=[1, 2])

    def tearDown(self):
        self._tmp.cleanup()

    def test_janela_e_cabecalho(self):
        texto = U.ler(self.repo, U.NORMAS + "/autorregulacao/n.md")
        corpo = [x for x in T.corpo(texto).split("\n") if x.strip()]
        saida = "\n".join(x for x in corpo[:20] if not x.startswith(("CABEÇALHO", "Página")))
        rep = T.linhas_repetidas(texto)
        r = A.comparar_item(self.repo, self.u, saida, rep)
        self.assertEqual(r["status"], "igual-salvo-cabecalho")
        self.assertTrue(all(d["cabecalho_rodape"] for d in r["diffs"]))
        r = A.comparar_item(self.repo, self.u, saida.replace("normativo", "regulatório", 1), rep)
        self.assertEqual(r["status"], "diferente")

    def test_assinaturas(self):
        u = dict(self.u, categoria="assinaturas")
        texto = U.ler(self.repo, U.NORMAS + "/autorregulacao/n.md")
        trecho = "\n".join(T.corpo(texto).strip().split("\n")[:6])
        self.assertEqual(A.comparar_item(self.repo, u, "ASSINATURAS: sim\n" + trecho)["status"], "igual")
        r = A.comparar_item(self.repo, u, "ASSINATURAS: não\n" + trecho)
        self.assertEqual((r["status"], r["assinaturas"]), ("diferente", "não"))


class TestVazamentos(unittest.TestCase):
    def test_leitura_fora_do_lote(self):
        with tempfile.TemporaryDirectory() as lote:
            lote = os.path.realpath(lote)
            eventos = [
                {"type": "system", "cwd": lote},
                {"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Read", "input": {"file_path": os.path.join(lote, "itens.json")}},
                    {"type": "tool_use", "name": "Write", "input": {"file_path": "u1-saida.md"}}]}},
            ]
            with open(os.path.join(lote, "log.jsonl"), "w") as f:
                f.write("\n".join(json.dumps(e) for e in eventos) + "\nlixo\n")
            self.assertEqual(A.vazamentos(lote), [])
            eventos.append({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "../../plugins/x.md"}},
                {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]}})
            with open(os.path.join(lote, "log.jsonl"), "w") as f:
                f.write("\n".join(json.dumps(e) for e in eventos) + "\n")
            vaz = A.vazamentos(lote)
            self.assertEqual([v["ferramenta"] for v in vaz], ["Read", "Bash"])
            os.remove(os.path.join(lote, "log.jsonl"))
            self.assertIsNone(A.vazamentos(lote))


class TestRecorteHtml(unittest.TestCase):
    def test_recorte_com_tachado_e_estilo(self):
        html = fixture("fonte-tachado.html")
        alvo = ("## Art. 2º O prazo é de sessenta dias corridos, contados da comunicação.\n\n"
                "Parágrafo único. O prazo de que trata o caput conta em dias úteis.\n")
        rec, achou = T.recortar_html(html, alvo)
        self.assertTrue(achou)
        self.assertIn("<strike>O prazo é de trinta dias corridos.</strike>", rec)
        self.assertIn("line-through", rec)
        self.assertIn("Art. 1º", rec)       # margem de um bloco antes
        self.assertIn("<table>", rec)       # e um depois (a tabela inteira)
        self.assertNotIn("Art. 3º", rec)
        self.assertNotIn("RESOLUÇÃO FICTÍCIA", rec)

    def test_alvo_ausente(self):
        self.assertEqual(T.recortar_html(fixture("fonte-tachado.html"), "nada disso consta da fonte aqui"),
                         (None, False))

    def test_tabela_e_um_bloco_so(self):
        _e, corpo = T.corpo_html(fixture("fonte-tachado.html"))
        blocos = T.blocos_html(corpo)
        tabelas = [b for b in blocos if "<table>" in b]
        self.assertEqual(len(tabelas), 1)
        self.assertIn("</table>", tabelas[0])
        self.assertEqual(len(blocos), 6)


class TestVigencia(unittest.TestCase):
    def test_datas_por_extenso(self):
        self.assertEqual(T.datas_por_extenso("em 1º de fevereiro de 2021 e 15 de Março de 2022; 2o de maio de 2023"),
                         ["2021-02-01", "2022-03-15", "2023-05-02"])
        self.assertEqual(T.datas_por_extenso("sem data"), [])

    def test_clausulas_com_citacao_e_incisos(self):
        cl = T.clausulas_de_vigor(T.corpo(fixture("ato-vigencia.md")), "2025-03-10")
        self.assertEqual(len(cl), 2)
        self.assertTrue(cl[0]["citacao"])
        self.assertEqual(cl[0]["datas"], ["2030-01-01"])
        self.assertFalse(cl[1]["citacao"])
        self.assertEqual(cl[1]["datas"], ["2025-03-10", "2025-06-02"])

    def test_citacao_fecha_com_nr_e_tabela(self):
        corpo = ("“Art. 5º ....\n| x | y |\n” (NR) |  |  |\n\nArt. 9º Esta Resolução entra em vigor em "
                 "1º de abril de 2025.\n")
        cl = T.clausulas_de_vigor(corpo)
        self.assertEqual([(c["citacao"], c["datas"]) for c in cl], [(False, ["2025-04-01"])])

    def test_censo_e_gate(self):
        with tempfile.TemporaryDirectory() as repo:
            base = os.path.join(repo, U.NORMAS, "cvm", "alteradoras")
            gravar(base, "resolucao-900.md", fixture("ato-vigencia.md"))
            gravar(base, "resolucao-900-retificacao.md", fixture("ato-vigencia.md").replace("2025", "2099"))
            c = U.censo_vigencia(repo, "2026-10-30")
            self.assertEqual(c["total"], 1)
            self.assertEqual(c["atos"][0]["datas"], ["2025-03-10", "2025-06-02"])
            self.assertEqual((c["diferidos"], c["gate_ok"], c["sem_data"]), (1, True, []))
            c = U.censo_vigencia(repo, "2025-05-01")
            self.assertEqual((c["gate_ok"], c["depois_da_data_base"]), (False, ["resolucao-900"]))
            self.assertEqual(U.universo_vigencia(repo, []), ([], []))


# ---------------------------------------------------------------- heurísticas de página

class TestHeuristicasPagina(unittest.TestCase):
    def test_sumario(self):
        pontilhado = "\n".join("Capítulo %d .......... %d" % (i, i * 3) for i in range(1, 8))
        self.assertTrue(U.eh_sumario(pontilhado))
        indice = "SUMÁRIO\n" + "\n".join("Seção %d Disposições %d" % (i, i + 2) for i in range(1, 7))
        self.assertTrue(U.eh_sumario(indice))
        prosa = "Art. 1º O participante deve observar o prazo de 30 dias.\nArt. 2º Outro dever."
        self.assertFalse(U.eh_sumario(prosa))

    def test_tabela(self):
        self.assertTrue(U.eh_tabela("Texto antes\nTabela 3 – Limites\nmais texto"))
        celulas = "\n".join(["Faixa", "Limite", "Prazo"] * 3 + ["10%", "R$ 1.000,00", "20%", "30", "45,5"] * 2)
        self.assertTrue(U.eh_tabela(celulas))
        self.assertFalse(U.eh_tabela("Art. 1º Um parágrafo de prosa normativa comum.\n" * 20))
        self.assertFalse(U.eh_tabela(""))


# ---------------------------------------------------------------- PDF e DOCX

@unittest.skipUnless(TEM_PYPDF, "pypdf não instalado")
class TestRecortePdf(unittest.TestCase):
    def test_so_as_paginas_pedidas(self):
        from pypdf import PdfReader, PdfWriter
        with tempfile.TemporaryDirectory() as d:
            w = PdfWriter()
            for i in range(6):
                w.add_blank_page(width=100 + i, height=200)
            orig, dest = os.path.join(d, "o.pdf"), os.path.join(d, "d.pdf")
            with open(orig, "wb") as f:
                w.write(f)
            A.recortar_pdf(orig, [2, 3], dest)
            larguras = [float(p.mediabox.width) for p in PdfReader(dest).pages]
            self.assertEqual(larguras, [101.0, 102.0])
            with self.assertRaises(ValueError):
                A.recortar_pdf(orig, [1, 2, 3, 4, 5], dest)
            with self.assertRaises(ValueError):
                A.recortar_pdf(orig, [], dest)


def docx(caminho, corpo, notas=None, numeracao=None):
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("word/document.xml", '<?xml version="1.0" encoding="UTF-8"?><w:document %s><w:body>%s'
                   "</w:body></w:document>" % (NS, corpo))
        if notas:
            z.writestr("word/footnotes.xml", '<?xml version="1.0" encoding="UTF-8"?><w:footnotes %s>%s'
                       "</w:footnotes>" % (NS, notas))
        if numeracao:
            z.writestr("word/numbering.xml", '<?xml version="1.0" encoding="UTF-8"?><w:numbering %s>%s'
                       "</w:numbering>" % (NS, numeracao))
    return caminho


class TestDocx(unittest.TestCase):
    def test_fonte_notas(self):
        corpo = (par(run("Art. 1º Texto com nota."), '<w:r><w:footnoteReference w:id="2"/></w:r>')
                 + par(run("Art. 2º Sem nota.")))
        notas = ('<w:footnote w:type="separator" w:id="0"><w:p><w:r><w:t>---</w:t></w:r></w:p></w:footnote>'
                 '<w:footnote w:id="2"><w:p><w:r><w:t>Texto da nota.</w:t></w:r></w:p></w:footnote>')
        with tempfile.TemporaryDirectory() as d:
            txt = A.fonte_notas_docx(docx(os.path.join(d, "a.docx"), corpo, notas))
        self.assertIn("Art. 1º Texto com nota. [nota id=2]", txt)
        self.assertNotIn("Art. 2º", txt)
        self.assertIn("nota id=2: Texto da nota.", txt)
        self.assertNotIn("---", txt.split("NOTAS DE RODAPÉ")[1])

    def test_lista_numerada_pela_conversao(self):
        num = ('<w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:start w:val="1"/>'
               '<w:numFmt w:val="upperRoman"/><w:lvlText w:val="%1 –"/></w:lvl></w:abstractNum>'
               '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>')
        corpo = (par(run("Art. 1º O participante deve:")) + par(run("comunicar;"), num=(1, 0))
                 + par(run("registrar."), num=(1, 0)) + par(run("Art. 2º I – inciso digitado à mão."))
                 + par(run("Art. 3º Texto."), run(" Antigo", tachado=True)))
        with tempfile.TemporaryDirectory() as d:
            arts = U.artigos_com_lista(docx(os.path.join(d, "a.docx"), corpo, numeracao=num), "docx", "consolidado")
        self.assertEqual(arts, {"Art. 1º"})


if __name__ == "__main__":
    unittest.main()
