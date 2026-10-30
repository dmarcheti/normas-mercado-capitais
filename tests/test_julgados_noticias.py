"""Testes da fonte de PAS fora da listagem: notícias do resultado (gov.br/cvm) e extratos de
sessão de julgamento do SEI. HTML sintético, sem rede, sem nomes reais."""
import hashlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import julgados_noticias as jn  # noqa: E402

G = "https://www.gov.br/cvm/pt-br/assuntos/noticias"
N1 = "19957.000111/2025-11"
N2 = "19957.000222/2024-22"
N_ANTIGO = "19957.008807/2021-52"


def busca(itens):
    lis = "".join(
        '<li>\n<div class="conteudo">\n<div class="subtitulo-noticia">%s</div>\n'
        '<h2 class="titulo"> <a href="%s">%s</a></h2>\n'
        '<span class="data"> %s</span></div></li>' % i for i in itens)
    return "<html><ul>%s</ul><a href='?b_start:int=30'>2</a></html>" % lis


def artigo(url, sub, titulo, publicado, corpo):
    return ('<html><head><meta property="og:url" content="%s" /></head><body>'
            '<p class="nitfSubtitle">%s</p><h1 class="documentFirstHeading">%s</h1>'
            '<span class="documentPublished"><span>Publicado em</span>'
            '<span class="value">%s 16h10</span></span>'
            '<div id="parent-fieldname-text">%s</div>'
            '<div id="viewlet-below-content"><a href="%s/anexos/2020/alheio.pdf">alheio</a></div>'
            '</body></html>' % (url, sub, titulo, publicado, corpo, G))


def linha_sei(id_doc, protocolo, serie, data_pub, resumo):
    return ('<tr class="infraTrClara"><td><input type="checkbox"/></td><td>%s</td><td>%s</td>'
            '<td>Diário Eletrônico da CVM</td><td>%s</td><td>GCP</td><td>x</td>'
            '<td><a href="controlador_publicacoes.php?acao=publicacao_visualizar&amp;id_documento=%s'
            '&amp;id_orgao_publicacao=0">%s</a></td></tr>'
            % (protocolo, serie, data_pub, id_doc, resumo))


class LeituraTest(unittest.TestCase):
    def test_busca_e_filtro_de_resultado(self):
        h = busca([("ATIVIDADE SANCIONADORA", G + "/2025/cvm-multa-ex-diretor", "CVM multa ex-diretor",
                    "08/07/2025"),
                   ("AGENDA", G + "/2025/sessao-de-julgamento-em-8-7", "Sessão de Julgamento em 8/7",
                    "07/07/2025"),
                   ("ATIVIDADE SANCIONADORA", G + "/2025/inicia", "CVM inicia julgamento de processo",
                    "01/07/2025"),
                   ("ATIVIDADE SANCIONADORA", G + "/2025/tc", "CVM rejeita Termo de Compromisso",
                    "01/07/2025"),
                   ("JULGAMENTO", G + "/2022/absolve", "CVM absolve acusados", "01/02/2022")])
        itens = jn.ler_busca(h)
        self.assertEqual(len(itens), 5)
        self.assertEqual(itens[0]["data"], "2025-07-08")
        self.assertEqual([i["url"] for i in itens if jn.e_resultado(i)],
                         [G + "/2025/cvm-multa-ex-diretor", G + "/2022/absolve"])
        self.assertEqual(jn.proximo_inicio(h, 0), 30)

    def test_artigo_com_nups_e_pecas(self):
        corpo = ('<p>O Colegiado julgou o PAS CVM %s e o PAS CVM %s.</p>'
                 '<a href="%s/anexos/2025/20250708-pas-cvm-19957-000111-2025-11-voto.pdf">voto</a>'
                 '<a href="%s/anexos/2025/20250707_PAS_CVM_19957_000222_2024_22_relatorio.pdf">'
                 'relatório</a>'
                 '<a href="%s/anexos/2025/manifestacao.pdf">manifestação de voto</a>'
                 % (N1, N2, G, G, G))
        a = jn.ler_artigo(artigo(G + "/2025/x", "ATIVIDADE SANCIONADORA", "CVM multa",
                                 "08/07/2025", corpo))
        self.assertEqual(a["url"], G + "/2025/x")
        self.assertEqual(a["data"], "2025-07-08")
        self.assertEqual(a["nups"], [N1, N2])
        self.assertEqual(len(a["pecas"]), 3)  # o PDF fora do corpo da notícia não entra
        por = jn.pecas_por_nup(a)
        self.assertEqual([r for _, r in por[N1]], ["voto", "manifestação de voto"])
        self.assertEqual([r for _, r in por[N2]], ["relatório", "manifestação de voto"])

    def test_numero_curto_no_nome_do_pdf(self):
        a = {"nups": [N_ANTIGO, N1], "pecas": [(G + "/anexos/2022/SEI_19957_08807_2021_52.pdf",
                                                "voto")]}
        self.assertEqual(list(jn.pecas_por_nup(a)[N_ANTIGO]), a["pecas"])
        self.assertEqual(jn.pecas_por_nup(a)[N1], [])

    def test_busca_do_sei(self):
        h = "<table>%s%s</table>" % (
            linha_sei("3000001", "2800001", "Extrato de Sessão de Julgamento 700", "17/09/2025",
                      "PAS CVM nº %s - Apurar a responsabilidade por infração. Multa." % N1),
            linha_sei("3000002", "2800002", "Extrato de Sessão de Julgamento 701", "18/09/2025",
                      "PAS CVM nº %s - Advertência." % N2))
        rs = jn.ler_busca_sei(h)
        self.assertEqual([r["id_documento"] for r in rs], ["3000001", "3000002"])
        self.assertEqual(rs[0]["data_pub"], "2025-09-17")
        self.assertEqual(rs[0]["nups"], [N1])
        self.assertIn("id_documento=3000001", rs[0]["url"])


class IndiceTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.pasta = self.dir.name

    def tearDown(self):
        self.dir.cleanup()

    def gravar(self, nome, texto, cod="utf-8"):
        with open(os.path.join(self.pasta, nome), "w", encoding=cod) as f:
            f.write(texto)

    def test_carregar_e_indice_por_nup(self):
        u1, u2 = G + "/2025/cvm-multa", G + "/2025/sessao-de-julgamento-em-3-11"
        self.gravar("busca-0000.html", busca([
            ("ATIVIDADE SANCIONADORA", u1, "CVM multa acusados", "08/07/2025"),
            ("AGENDA", u2, "Sessão de Julgamento em 3/11", "30/10/2026")]))
        corpo = ('<p>PAS CVM %s</p><a href="%s/anexos/2025/20250708-pas-cvm-19957-000111-2025-11'
                 '-voto.pdf">voto</a>' % (N1, G))
        self.gravar(jn.nome_artigo(u1), artigo(u1, "ATIVIDADE SANCIONADORA", "CVM multa acusados",
                                               "08/07/2025", corpo))
        os.makedirs(os.path.join(self.pasta, "sei"))
        self.gravar(os.path.join("sei", "o0.html"), "<table>%s%s</table>" % (
            linha_sei("3000001", "2800001", "Extrato de Sessão de Julgamento 700", "17/09/2025",
                      "PAS CVM nº %s - Multa." % N1),
            linha_sei("3000002", "2800002", "Extrato de Sessão de Julgamento 701", "18/09/2025",
                      "PAS CVM nº %s - Advertência." % N2)), cod="latin-1")
        fonte = jn.carregar(self.pasta, os.path.join(self.pasta, "sei"))
        self.assertEqual(fonte["faltam"], [])  # a pauta não precisa de artigo
        idx = jn.indice(fonte)
        self.assertEqual(sorted(idx), [N1, N2])
        self.assertEqual(idx[N1]["noticia"], u1)
        self.assertEqual(idx[N1]["data"], "2025-07-08")
        self.assertEqual(idx[N1]["data_fonte"], "noticia")
        self.assertEqual(len(idx[N1]["pecas"]), 1)
        self.assertEqual(idx[N1]["extratos"][0]["data_pub"], "2025-09-17")
        self.assertEqual(idx[N2]["noticia"], "")
        self.assertEqual(idx[N2]["data"], "2025-09-18")
        self.assertEqual(idx[N2]["data_fonte"], "extrato")

    def test_pecas_de_duas_noticias_do_mesmo_nup(self):
        rel = (G + "/anexos/2022/20220131_PAS_CVM_19957_000111_2025_11_relatorio.pdf", "relatório")
        voto = (G + "/anexos/2022/20220201_PAS_CVM_19957_000111_2025_11_voto.pdf", "voto")
        fonte = {"extratos": [], "noticias": [
            {"url": G + "/2022/sessao", "titulo": "Sessão de Julgamento da CVM em 1/2",
             "data": "2022-02-01", "nups": [N1], "pecas": [rel]},
            {"url": G + "/2022/caso", "titulo": "CVM adverte acusados", "data": "2022-02-01",
             "nups": [N1], "pecas": [voto]}]}
        e = jn.indice(fonte)[N1]
        self.assertEqual(e["noticia"], G + "/2022/caso")
        self.assertEqual(e["outras_noticias"], [G + "/2022/sessao"])
        self.assertEqual(e["pecas"], [voto, rel])

    def test_artigo_que_falta_fica_listado(self):
        u1 = G + "/2025/cvm-multa"
        self.gravar("busca-0000.html", busca([("JULGAMENTO", u1, "CVM multa", "08/07/2025")]))
        fonte = jn.carregar(self.pasta, os.path.join(self.pasta, "sei"))
        self.assertEqual(fonte["faltam"], [u1])
        self.assertEqual(jn.nome_artigo(u1), "artigo-%s.html" % hashlib.md5(
            u1.encode()).hexdigest()[:8])


class BaixarTest(unittest.TestCase):
    def test_baixa_so_o_que_falta(self):
        u1 = G + "/2025/cvm-multa"

        class Cli:
            n = 0
            gets, posts = [], []

            def get(self, url):
                self.gets.append(url)
                if "form.submitted" in url:
                    b = busca([("JULGAMENTO", u1, "CVM multa", "08/07/2025")]) if "b_start" not in url \
                        else busca([])
                else:
                    b = artigo(u1, "JULGAMENTO", "CVM multa", "08/07/2025", "<p>%s</p>" % N1)
                return b.encode("utf-8"), {"content-type": "text/html; charset=utf-8"}, url

            def post(self, url, campos):
                self.posts.append(dict(campos))
                linhas = linha_sei("3000001", "2800001", "Extrato de Sessão de Julgamento 700",
                                   "17/09/2025", "PAS CVM nº %s" % N1) \
                    if campos["hdnInicio"] == "0" else ""
                return ("<table>%s</table>" % linhas).encode("latin-1"), {}, url

        with tempfile.TemporaryDirectory() as d:
            sei = os.path.join(d, "sei")
            cli = Cli()
            jn.baixar(d, sei, cli, "01/06/2025", "30/10/2026", maximo=20)
            self.assertEqual(len(cli.posts), 1)
            self.assertEqual(cli.posts[0]["selSerie"], "919")
            idx = jn.indice(jn.carregar(d, sei))
            self.assertEqual(idx[N1]["noticia"], u1)
            n = len(cli.gets)
            jn.baixar(d, sei, cli, "01/06/2025", "30/10/2026", maximo=20, refazer_busca=False)
            self.assertEqual(len(cli.gets), n)  # tudo no cache: nenhuma requisição nova
            self.assertEqual(len(cli.posts), 1)


if __name__ == "__main__":
    unittest.main()
