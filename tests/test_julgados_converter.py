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
import julgados_extracao as je  # noqa: E402
import pdf_macos  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "julgados")
B = jc.BASE
CPF = "123.456." + "789-09"  # montado em partes: nenhum CPF literal no repositório


def fixture(nome):
    with open(os.path.join(FIX, nome), "rb") as f:
        return f.read()


def setUpModule():
    # lista positiva sem os dados de dados/ (hermético): só corpo e título do julgado
    je._PESSOAS_PADRAO = je.Pessoas(acusados={}, partes_tc={}, descricoes={})
    conv._LIGACOES_CRSFN, conv._FASES_PAS = {}, {}


def tearDownModule():
    je._PESSOAS_PADRAO = None
    conv._LIGACOES_CRSFN = conv._FASES_PAS = None


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

NOMES_PAGINA = ("alfa", "beta", "gama", "delta")
_PALAVRAS = ("acusação", "defesa", "mérito", "prova", "prazo", "multa", "recurso", "parecer")


def unica(nome, j):
    """Linha de miolo que não se repete entre páginas (a chave troca só os dígitos)."""
    return "Texto %s sobre a %s do processo." % (nome, _PALAVRAS[j])


class PecasTest(unittest.TestCase):
    def test_tirar_repetidas_com_numero_de_pagina(self):
        texto, n = conv.tirar_repetidas([p for p in PAGINAS_PAS if p.strip()])
        self.assertEqual(n, 9)
        self.assertNotIn("COMISSÃO DE VALORES", texto)
        self.assertNotIn("pg. 2", texto)
        self.assertIn("RELATÓRIO", texto)  # cabeçalho de peça fica

    def test_tirar_repetidas_mantem_linha_repetida_no_miolo(self):
        # Fase 3b: termos parecidos no mesmo PDF, data em lista, fecho e subtítulo repetidos no
        # miolo da página são texto da peça; só cabeçalho e rodapé (borda da página) saem
        miolo = ["Cláusula 1ª - O COMPROMITENTE pagará R$ 100.000,00 à CVM.",
                 "Das preliminares",
                 "Rio de Janeiro, 12 de maio de 2018.",
                 "ITR de 30.06.16."]
        paginas = []
        for i, nome in enumerate(NOMES_PAGINA):
            paginas.append("\n".join(
                ["PROCESSO ADMINISTRATIVO SANCIONADOR Nº 19957.000001/2020-01",
                 unica(nome, 0), unica(nome, 1)] + miolo
                + [unica(nome, 2), unica(nome, 3), "Página %d de 4" % (i + 1)]))
        ret = []
        texto, n = conv.tirar_repetidas(paginas, retirado=ret)
        self.assertEqual(n, 8)  # cabeçalho e "Página N de 4" das 4 páginas
        self.assertNotIn("PROCESSO ADMINISTRATIVO SANCIONADOR", texto)
        self.assertNotIn("de 4", texto)
        for linha in miolo:
            self.assertEqual(texto.count(linha), 4, linha)

    def test_tirar_repetidas_borda_so_conta_ocorrencia_na_borda(self):
        # a mesma linha no cabeçalho de 3 páginas e no miolo de outra: só as da borda saem
        cab = "Processo CVM nº 19957.000002/2021-02"
        paginas = ["\n".join([cab] + [unica(nome, j) for j in range(6)])
                   for nome in NOMES_PAGINA[:3]]
        u = [unica(NOMES_PAGINA[3], j) for j in range(8)]
        paginas.append("\n".join(u[:4] + [cab] + u[4:]))
        texto, n = conv.tirar_repetidas(paginas)
        self.assertEqual(n, 3)
        self.assertEqual(texto.count(cab), 1)
        # na borda de 2 páginas só: não sai
        texto, n = conv.tirar_repetidas(paginas[:2] + [paginas[3]])
        self.assertEqual((n, texto.count(cab)), (0, 3))

    def test_tirar_repetidas_mantem_nota_de_rodape_e_titulo_de_cada_peca(self):
        # cvm-pas-19957-003611-2020-91: "12 Doc. 1619945." no pé de várias páginas é nota;
        # cvm-col-20181009-d1183: "TERMO DE COMPROMISSO" no topo de cada termo (páginas não
        # seguidas) é título da peça, não cabeçalho de página
        paginas = []
        for i, nome in enumerate(NOMES_PAGINA * 2):
            topo = ["TERMO DE COMPROMISSO"] if i % 2 == 0 else []
            paginas.append("\n".join(
                topo + [unica(nome, j + i % 2) for j in range(5)]
                + ["%d Doc. %d." % (i + 1, 1619945 + i), "Página %d de 8" % (i + 1)]))
        texto, n = conv.tirar_repetidas(paginas)
        self.assertEqual(n, 8)  # só "Página N de 8"
        self.assertEqual(texto.count("TERMO DE COMPROMISSO"), 4)
        self.assertIn("1 Doc. 1619945.", texto)
        self.assertIn("8 Doc. 1619952.", texto)
        # o fecho do termo no pé de uma página e no topo da seguinte: bordas diferentes, fica
        fecho = "E, assim, por estarem justos e acordados, firmam o presente TERMO,"
        u = [[unica(nome, j) for j in range(6)] for nome in NOMES_PAGINA[:3]]
        paginas = ["\n".join([fecho] + u[0]), "\n".join(u[1] + [fecho]), "\n".join([fecho] + u[2])]
        texto, n = conv.tirar_repetidas(paginas)
        self.assertEqual((n, texto.count(fecho)), (0, 3))

    def test_tirar_repetidas_preserva_bloco_de_interessados(self):
        # cvm-pas-rj2007-4247: o 2º interessado, linha só com o nome, repetido no topo das peças
        paginas = []
        for rot, nome in zip(("Interessados", "Interessados", "Acusados"), NOMES_PAGINA):
            paginas.append("\n".join([
                "PROCESSO ADMINISTRATIVO CVM Nº RJ2007/0001",
                "%s: Auditores Exemplo S/S" % rot,
                "Fulano Beltrano Exemplo",
                "Diretor-Relator: Sicrano"] + [unica(nome, j) for j in range(5)]))
        texto, n = conv.tirar_repetidas(paginas)
        self.assertEqual(n, 3)
        self.assertEqual(texto.count("Fulano Beltrano Exemplo"), 3)
        self.assertEqual(texto.count("PROCESSO ADMINISTRATIVO CVM"), 0)
        self.assertEqual(conv._linhas_de_partes(["Recorrentes: A", "B C", "", "D E"]), {0, 1})
        self.assertEqual(conv._linhas_de_partes(["x", "Indiciados: A", "B C", "Relator: X", "Y"]),
                         {1, 2})
        self.assertEqual(conv._linhas_de_partes(["Interessado: A", "RELATÓRIO", "B"]), {0})

    def test_ocr_paragrafo_lido_como_8(self):
        f = conv.corrigir_ocr
        self.assertEqual(f("nos termos do art. 17, 82°, II, da Lei"),
                         "nos termos do art. 17, §2º, II, da Lei")
        self.assertEqual(f("art. 141, 84º, da LSA"), "art. 141, §4º, da LSA")
        self.assertEqual(f("art.\n141, 85° da LSA"), "art.\n141, §5º da LSA")
        self.assertEqual(f("art. 141, 8 1°, da LSA"), "art. 141, §1º, da LSA")
        self.assertEqual(f("art. 141, 884° e 5° da LSA"), "art. 141, §§4º e 5° da LSA")
        self.assertEqual(f("art. 141, 88°, da LSA"), "art. 141, §8º, da LSA")
        self.assertEqual(f("artigo 141, 84°, I e II"), "artigo 141, §4º, I e II")
        # sem "art." antes, ou sem o grau, fica
        for t in ("multa de 82° graus", "art. 17, 82, II", "Lei 6.385, 82°", "art. 8º, inciso I",
                  "art. 11, 85.000 ações", "o art. 82º da Lei"):
            self.assertEqual(f(t), t)

    def test_ocr_romanos_em_incisos_e_titulos(self):
        f = conv.corrigir_ocr
        for t in ("nos incisos 1 e II, do artigo 7º", "nos incisos I e Il, do artigo 7º",
                  "nos incisos l e 11, do artigo 7º", "nos incisos 1 e lI do artigo 7º"):
            self.assertIn("incisos I e II", f(t), t)
        self.assertEqual(f("inciso 1 e 11"), "inciso I e II")
        self.assertEqual(f("x.\nIl - DA ILEGALIDADE\ntexto"), "x.\nII - DA ILEGALIDADE\ntexto")
        self.assertEqual(f("Il. Nossas Considerações:"), "II. Nossas Considerações:")
        self.assertEqual(f("  lI - Do mérito"), "  II - Do mérito")
        # negativos: o número 11 legítimo e o "Il" no meio da frase ficam
        for t in ("nos termos do art. 11 da Lei", "11 de maio de 2018", "11. Por todo o exposto",
                  "11 - Fatos", "os incisos I e II do § 4º", "incisos 1 e 2 do art. 3º",
                  "Il Sole 24 Ore", "Ilha Grande - RJ", "o Sr. Il - Kim", "11.1 - Das partes"):
            self.assertEqual(f(t), t)

    def test_correcao_de_ocr_so_nas_paginas_por_ocr(self):
        caminho = os.path.join(tempfile.gettempdir(), "nao-existe-ocr.pdf")
        texto = "Pagina com texto: art. 17, 82°, II e incisos 1 e Il, mais texto aqui."
        pm = PdfFalso({"nao-existe-ocr.pdf": texto + "\f "},
                      ocr={"nao-existe-ocr.pdf": "x\f" + texto})
        with mock.patch.object(conv, "_numero_de_paginas", return_value=2):
            pags, nivel, _, _, n_ocr = conv.texto_pdf(caminho, pm)
        self.assertEqual((nivel, n_ocr), ("ocr", 1))
        self.assertIn("82°", pags[0])  # camada de texto: fica
        self.assertIn("art. 17, §2º, II e incisos I e II,", pags[1])

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

    def test_reconversao_preserva_a_extracao(self):
        novo = {c: "" for c in jc.CAMPOS}
        novo.update(id="cvm-col-20250101-d1", orgao="cvm", tipo="decisao-colegiado",
                    data="2025-01-01", ementa="RECURSO", ementa_fonte="titulo")
        extraido = dict(novo, ementa="Recurso contra multa; negado.", ementa_fonte="extracao",
                        tema="processual", tema_fonte="extracao", resultado="nao-provido",
                        relator="SEP")
        caminho = conv.gravar_julgado(extraido, "# X\n", self.raiz)
        conv.gravar_julgado(dict(novo), "# X\n", self.raiz)
        v, _ = je.ler_julgado(caminho)
        self.assertEqual((v["ementa"], v["ementa_fonte"], v["tema"], v["tema_fonte"],
                          v["resultado"], v["relator"]),
                         ("Recurso contra multa; negado.", "extracao", "processual", "extracao",
                          "nao-provido", "SEP"))
        # a ementa que a conversão traz da fonte prevalece sobre a extraída; o resultado já
        # gravado não (não tem _fonte; a reconversão não troca o extraído pelo do conversor)
        conv.gravar_julgado(dict(novo, ementa="Ementa publicada.", ementa_fonte="cvm",
                                 resultado="provido"), "# X\n", self.raiz)
        v, _ = je.ler_julgado(caminho)
        self.assertEqual((v["ementa"], v["ementa_fonte"], v["resultado"]),
                         ("Ementa publicada.", "cvm", "nao-provido"))

    def test_reconversao_so_preenche_resultado_vazio(self):
        novo = {c: "" for c in jc.CAMPOS}
        novo.update(id="cvm-col-20250101-d2", orgao="cvm", tipo="decisao-colegiado",
                    data="2025-01-01", ementa="RECURSO", ementa_fonte="titulo")
        caminho = conv.gravar_julgado(dict(novo), "# X\n", self.raiz)
        conv.gravar_julgado(dict(novo, resultado="indeferido"), "# X\n", self.raiz)
        self.assertEqual(je.ler_julgado(caminho)[0]["resultado"], "indeferido")
        conv.gravar_julgado(dict(novo, resultado="deferido"), "# X\n", self.raiz)
        self.assertEqual(je.ler_julgado(caminho)[0]["resultado"], "indeferido")

    def test_reconversao_mantem_resultado_vazio_da_extracao(self):
        novo = {c: "" for c in jc.CAMPOS}
        novo.update(id="cvm-col-20250101-d3", orgao="cvm", tipo="decisao-colegiado",
                    data="2025-01-01", ementa="RECURSO", ementa_fonte="titulo")
        suspenso = dict(novo, ementa="Recurso. Julgamento suspenso por pedido de vista.",
                        ementa_fonte="extracao")
        caminho = conv.gravar_julgado(suspenso, "# X\n", self.raiz)
        conv.gravar_julgado(dict(novo, resultado="indeferido"), "# X\n", self.raiz)
        self.assertEqual(je.ler_julgado(caminho)[0]["resultado"], "")

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
        self.assertNotIn("Documento assinado eletronicamente", corpo)  # rodapé do SEI sai
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
            "julgados-tc-crsfn", "julgados", "cvm", "colegiado", "2025",
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
        self.assertEqual([f[3] for f in cv._fontes if f[0] == "01-pagina.html"], ["pas"])
        pdf = [c for c in cv.conferencias if c["arquivo"] == "02-pdf.pdf"][0]
        self.assertEqual(pdf["conferencia"], "pypdf")
        self.assertGreater(pdf["cobertura"], 0.6)
        self.gravar_e_validar(valores, corpo)

    def test_pas_com_nome_na_ementa_da_pagina(self):
        pagina = fixture("pas-pagina.html").replace(
            "Ementa: Apurar responsabilidades por".encode(),
            "Ementa: Apurar a responsabilidade de Beltrano Exemplar por".encode())
        montar_cache(self.pasta(PAS), [
            ("pagina", "PAS", PAS["url"], "01-pagina.html", pagina, "text/html; charset=utf-8"),
            ("pdf", "Decisão completa", PDF_PAS, "02-pdf.pdf", b"%PDF-pas", "application/pdf")])
        pm = PdfFalso({"02-pdf.pdf": "\f".join(PAGINAS_PAS) + "\f"})
        lista = je.Pessoas(acusados={}, partes_tc={}, descricoes={
            PAS["id"]: ("pas", "BELTRANO EXEMPLAR Apurar a responsabilidade. Multa.")})
        with mock.patch.object(je, "_PESSOAS_PADRAO", lista), \
                mock.patch.object(conv, "_pypdf_paginas", return_value=["\n".join(PAGINAS_PAS)]):
            valores, corpo, cv = conv.converter_item(PAS, self.pasta(PAS), pm)
        self.assertTrue(valores["ementa"].startswith(
            "Apurar a responsabilidade de [pessoa física] por infração"))
        self.assertEqual(valores["ementa_fonte"], "cvm")
        self.assertIn("nomes de pessoa física omitidos da ementa do frontmatter; ementa integral "
                      "na seção Ementa", valores["incerteza"])
        self.assertEqual([s for s in corpo.splitlines() if s.startswith("## ")],
                         ["## Ementa", "## Extrato", "## Relatório", "## Voto"])
        self.assertIn("## Ementa\n\nApurar a responsabilidade de Beltrano Exemplar por", corpo)
        self.gravar_e_validar(valores, corpo)

    def test_recurso_crsfn_por_ligacao_ou_dados_abertos(self):
        lig = {"rj2019-5673": ["crsfn-10372-100012-2021-00"], "08-2000": ["crsfn-4217"],
               "19957-007543-2019-03": ["crsfn-10372-100012-2021-00", "crsfn-outro"]}
        fases = {"19957000456202451": ("Recurso CRSFN", "2026-09-30"),
                 "19957000999202411": ("Finalizado", "2025-01-02")}
        v = {"processo": "19957.007543/2019-03; RJ2019/5673", "nup": "19957-007543-2019-03"}
        self.assertEqual(conv.recurso_crsfn(v, lig, fases),
                         "recurso ao CRSFN: crsfn-10372-100012-2021-00, crsfn-outro")
        self.assertEqual(conv.recurso_crsfn({"processo": "08/2000", "nup": ""}, lig, fases),
                         "recurso ao CRSFN: crsfn-4217")
        v = {"processo": "19957.000456/2024-51", "nup": "19957-000456-2024-51"}
        self.assertEqual(conv.recurso_crsfn(v, lig, fases),
                         "recurso ao CRSFN em andamento (dados abertos, 2026-09-30)")
        v = {"processo": "19957.000999/2024-11", "nup": "19957-000999-2024-11"}
        self.assertEqual(conv.recurso_crsfn(v, lig, fases), "")
        self.assertEqual(conv.recurso_crsfn(v, {}, {}), "")

    def test_fases_dos_dados_abertos(self):
        cam = os.path.join(self.raiz, "processo_sancionador.csv")
        with open(cam, "w", encoding="latin-1", newline="") as f:
            f.write("NUP;Objeto;Fase_Atual;Subfase_Atual;Data_Ultima_Movimentacao\n"
                    "19957000456202451;Apurar;Recurso CRSFN;Envio dos autos ao CRSFN;2026-09-30\n")
        self.assertEqual(conv.fases_pas(cam), {"19957000456202451": ("Recurso CRSFN", "2026-09-30")})
        self.assertEqual(conv.fases_pas(os.path.join(self.raiz, "nao-existe.csv")), {})
        self.assertEqual(conv.ligacoes_crsfn(os.path.join(self.raiz, "nao-existe.json")), {})

    def test_pas_com_recurso_ao_crsfn_no_incerteza(self):
        montar_cache(self.pasta(PAS), [
            ("pagina", "PAS", PAS["url"], "01-pagina.html", fixture("pas-pagina.html"),
             "text/html; charset=utf-8"),
            ("pdf", "Decisão completa", PDF_PAS, "02-pdf.pdf", b"%PDF-pas", "application/pdf")])
        pm = PdfFalso({"02-pdf.pdf": "\f".join(PAGINAS_PAS) + "\f"})
        with mock.patch.object(conv, "_LIGACOES_CRSFN", {"19957-000456-2024-51": ["crsfn-x"]}), \
                mock.patch.object(conv, "_pypdf_paginas", return_value=["\n".join(PAGINAS_PAS)]):
            valores, corpo, cv = conv.converter_item(PAS, self.pasta(PAS), pm)
        self.assertIn("recurso ao CRSFN: crsfn-x", valores["incerteza"])

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

    def test_pdf_de_duas_paginas_sem_texto_manda_as_duas_ao_ocr(self):
        # PDFKit devolve "\f" (2 páginas vazias): a última não pode sumir antes do OCR
        caminho = os.path.join(self.raiz, "b.pdf")
        pm = PdfFalso({"b.pdf": "\f"}, ocr={"b.pdf": "Página um lida por OCR.\fPágina dois lida por OCR."})
        with mock.patch.object(conv, "_numero_de_paginas", return_value=2):
            pags, nivel, motor, _, n_ocr = conv.texto_pdf(caminho, pm)
        self.assertEqual((motor, nivel, n_ocr, len(pags)), ("pdfkit", "ocr", 2, 2))
        self.assertIn("Página dois", pags[1])

    def test_elemento_vazio_alem_do_numero_de_paginas_sai(self):
        caminho = os.path.join(self.raiz, "c.pdf")
        pm = PdfFalso({"c.pdf": "Texto da única página do documento.\f"})
        with mock.patch.object(conv, "_numero_de_paginas", return_value=1):
            pags, nivel, _, _, n_ocr = conv.texto_pdf(caminho, pm)
        self.assertEqual((len(pags), nivel, n_ocr, pm.ocr_chamado), (1, "pdf-extraido", 0, 0))

    def test_pas_da_noticia_com_extrato_do_sei(self):
        g = "https://www.gov.br/cvm/pt-br/assuntos/noticias"
        item = {"id": "cvm-pas-19957-000444-2025-44", "tipo": "pas", "classe": "",
                "processo": "19957.000444/2025-44", "nup": "19957-000444-2025-44",
                "data": "2025-09-10", "url": g + "/2025/cvm-multa", "titulo": "",
                "origem": "noticia", "noticia": g + "/2025/cvm-multa", "incerteza": []}
        noticia = b"<html><body><h1>CVM multa acusado</h1></body></html>"
        sei = ("<html><body><p>Diário Eletrônico da CVM em 17/09/2025</p>"
               "<p><b>COMISSÃO DE VALORES MOBILIÁRIOS</b></p><p>Extrato de Sessão de Julgamento</p>"
               "<p><b>DO PROCESSO ADMINISTRATIVO SANCIONADOR CVM nº 19957.000444/2025-44</b></p>"
               "<p><b>Data do julgamento:</b> 09/09/2025</p>"
               "<p><b>Relator:</b> Presidente Interino Fulano Exemplo</p>"
               "<p><b>Acusados:</b></p><p>Beltrano Exemplar</p>"
               "<p><b>Ementa:</b> Apurar a responsabilidade por infração ao art. 11 da Resolução "
               "CVM nº 80/2022.<i> Multa.</i></p>"
               "<p><b>Decisão:</b> o Colegiado decidiu pela <b>condenação</b> de Beltrano "
               "Exemplar à multa de R$ 100.000,00.</p>"
               "<p>Presente a Fulana Exemplo, representante da Procuradoria.</p>"
               "<p>Após analisar o caso, o Diretor Sicrano votou pela absolvição de Beltrano "
               "Exemplar.</p></body></html>").encode("iso-8859-1")
        voto = "VOTO\nI. MÉRITO\nEntendo comprovada a infração ao art. 11 da Resolução CVM nº 80."
        rel = ("PROCESSO ADMINISTRATIVO SANCIONADOR CVM Nº 19957.000444/2025-44\n"
               "Acusado: Beltrano Exemplar\nRELATÓRIO\nI. OBJETO E ORIGEM\n1. Trata-se de PAS.")
        montar_cache(self.pasta(item), [
            ("noticia", "", item["url"], "01-noticia.html", noticia, "text/html; charset=utf-8"),
            ("pdf", "relatório", g + "/anexos/2025/relatorio.pdf", "02-pdf.pdf", b"%PDF-rel",
             "application/pdf"),
            ("pdf", "voto", g + "/anexos/2025/voto.pdf", "03-pdf.pdf", b"%PDF-voto",
             "application/pdf"),
            ("sei", "extrato de sessão de julgamento",
             "https://sei.cvm.gov.br/sei/publicacoes/x?id_documento=9", "04-sei.html", sei,
             "text/html; charset=iso-8859-1")])
        with mock.patch.object(conv, "_pypdf_paginas", side_effect=[[rel], [voto]]):
            valores, corpo, cv = conv.converter_item(
                item, self.pasta(item), PdfFalso({"02-pdf.pdf": rel, "03-pdf.pdf": voto}))
        # capa do relatório e o relatório viram uma seção só; o voto vencido não decide
        self.assertEqual([s for s in corpo.splitlines() if s.startswith("## ")],
                         ["## Extrato", "## Relatório", "## Voto"])
        self.assertTrue(corpo.startswith("# PAS CVM nº 19957.000444/2025-44\n"))
        self.assertEqual(valores["ementa"], "Apurar a responsabilidade por infração ao art. 11 "
                                            "da Resolução CVM nº 80/2022. Multa.")
        self.assertEqual(valores["ementa_fonte"], "cvm")
        self.assertEqual((valores["data"], valores["relator"], valores["resultado"]),
                         ("2025-09-09", "Fulano Exemplo", "condenacao"))
        self.assertEqual(valores["fonte_original"], item["url"])
        self.assertEqual(valores["sha256_fonte"], hashlib.sha256(noticia).hexdigest())
        self.gravar_e_validar(valores, corpo)

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

    def test_decisao_antiga_com_ata_de_outro_ano(self):
        # o PDF anual traz atas de anos anteriores; a data é a da primeira reunião do ano do id
        item = {"id": "cvm-dec-1990", "tipo": "decisao-antiga", "classe": "", "processo": "",
                "data": "1990-01-01", "url": B + "/x/d1990.pdf",
                "titulo": "Decisões do Colegiado de 1990", "incerteza": []}
        texto = ("ATA DA REUNIÃO DO COLEGIADO Nº 47 DE 20.12.1990\nPARTICIPANTES:\n"
                 "FULANO EXEMPLO – Presidente\nPEDIDO DE DISPENSA DE REGISTRO\n"
                 "O Colegiado deferiu o pedido.\n"
                 "ATA DA REUNIÃO DO COLEGIADO Nº 05 DE 13.02.1989\nPARTICIPANTES:\n"
                 "FULANO EXEMPLO – Presidente\nRECURSO CONTRA DECISÃO DA SEP\n"
                 "O Colegiado negou provimento.\n"
                 "ATA DA REUNIÃO DO COLEGIADO Nº 02 DE 18.01.1990\nPARTICIPANTES:\n"
                 "FULANO EXEMPLO – Presidente\nCONSULTA SOBRE PRAZO DE PUBLICAÇÃO\n"
                 "O Colegiado respondeu à consulta.\n")
        montar_cache(self.pasta(item), [("documento", "", item["url"], "01-documento.pdf",
                                         b"%PDF-1990", "application/pdf")])
        with mock.patch.object(conv, "_pypdf_paginas", return_value=None):
            valores, corpo, cv = conv.converter_item(item, self.pasta(item),
                                                     PdfFalso({"01-documento.pdf": texto}))
        self.assertEqual(valores["data"], "1990-01-18")
        self.gravar_e_validar(valores, corpo)

    def test_sem_cache_e_erro(self):
        with self.assertRaises(ValueError):
            conv.converter_item(PAS, self.pasta(PAS), PdfFalso({}))


TEL = "(21) 3554-" + "8686"  # telefone da sede da CVM, montado em partes


class TimbreTest(unittest.TestCase):
    def test_endereco_cep_telefone_e_site_da_cvm_saem_antes_do_pii(self):
        texto = ("COMISSÃO DE VALORES MOBILIÁRIOS\n"
                 "Rua Sete de Setembro, 111/2-5º e 23-34º Andares, Centro, Rio de Janeiro/RJ – "
                 "CEP: 20050-901 – Brasil - Tel.: " + TEL + "\n"
                 "Rua Cincinato Braga, 340/2º, 3º e 4º Andares, Bela Vista, São Paulo/SP – CEP: "
                 "01333-010 – Brasil - Tel.: (11) 2146-2000\n"
                 "SCN Q.02 – Bl. A – Ed. Corporate Financial Center, S.404/4º Andar, Brasília/DF – "
                 "CEP: 70712-900 – Brasil -Tel.: (61) 3327-2030/2031\n"
                 "www.cvm.gov.br\n"
                 "O Colegiado aprovou o voto do relator.")
        limpo, n = conv.tirar_timbre(texto)
        self.assertEqual(limpo.strip(), "O Colegiado aprovou o voto do relator.")
        self.assertEqual(n, 5)
        corpo, cortes = conv.pii.limpar_contando(limpo)
        self.assertNotIn(jc.PII, corpo)

    def test_rodape_quebrado_superintendencia_de_sao_paulo_e_sede_antiga(self):
        texto = ("Rua Sete de Setembro, 111/2-5º e 23\n"
                 "Brasil - Tel.: (21) 3554-8686\n"
                 "Superintendência Regional de São Paulo: Rua Formosa, 367 / 20° e 21º andares - "
                 "CEP 01049-000 - Centro - S. Paulo - SP - Brasil - Tel: (11) 2146-2000\n"
                 "Sede: Rua Sete de Setembro, 110 / 2º andar - Centro - Rio de Janeiro - RJ - "
                 "CEP 20159-900 - Brasil - Tel: (21) 3233-8686 - Endereço Internet: "
                 "http://www.cvm.gov.br\n"
                 "O Colegiado aprovou o voto do relator.\n"
                 "A CVM fica na Rua Sete de Setembro, 111, no centro do Rio.")
        limpo, n = conv.tirar_timbre(texto)
        self.assertEqual(limpo.strip(), "O Colegiado aprovou o voto do relator.\n"
                         "A CVM fica na Rua Sete de Setembro, 111, no centro do Rio.")
        self.assertEqual(n, 4)

    def test_rodape_do_sei_em_linhas_quebradas_e_numero_sei_no_texto_fica(self):
        texto = ("Conforme o despacho SEI nº 0284733, o processo segue.\n"
                 "Documento assinado eletronicamente por Fulano Exemplo, Superintendente, em\n"
                 "03/10/2018, às 12:22, com fundamento no art. 6º, § 1º, do Decreto nº 8.539, de 8 de "
                 "outubro de 2015.\n"
                 "A autenticidade deste documento pode ser conferida no site\n"
                 "https://sei.cvm.gov.br/conferir_autenticidade, informando o código verificador "
                 "0594322 e o código CRC 3F2A9B1C.\n"
                 "Referência: Processo nº 19957.001067/2017-47 SEI nº 0594322\n"
                 "Fim do extrato.")
        retirado = []
        limpo, n = conv.tirar_timbre(texto, retirado)
        self.assertIn("SEI nº 0284733", limpo)
        self.assertIn("Fim do extrato.", limpo)
        for fora in ("assinado", "autenticidade", "CRC", "Referência", "Fulano"):
            self.assertNotIn(fora, limpo)
        self.assertEqual(n, 3)
        self.assertTrue(any("Fulano" in r for r in retirado))

    def test_rodape_do_sei_em_markdown(self):
        texto = ("CLÁUSULA FINAL. Vale o acordo.\n\n"
                 "Documento assinado eletronicamente por **Fulano Exemplo**, **Presidente**, em "
                 "10/01/2024, às 18:01, com fundamento no art. 6º, § 1º, do Decreto nº 8.539, de 8 "
                 "de outubro de 2015.\n\n"
                 "A autenticidade do documento pode ser conferida no site "
                 "https://sei.cvm.gov.br/conferir_autenticidade, informando o código verificador "
                 "**1987436** e o código CRC **87D15CC0**.\n\n"
                 "*This document's authenticity can be verified by accessing "
                 "https://sei.cvm.gov.br/conferir_autenticidade, and typing the \"Código "
                 "Verificador\"* ***1987436*** *and the \"Código CRC\"* ***87D15CC0****.*\n")
        limpo, n = conv.tirar_timbre(texto)
        self.assertEqual(limpo.strip(), "CLÁUSULA FINAL. Vale o acordo.")
        self.assertEqual(n, 3)

    def test_impressao_do_sei_e_logotipo_do_ocr(self):
        texto = ("SEI/CVM - 0594322 - Extrato de Sessão de Julgamento "
                 "https://sei.cvm.gov.br/sei/controlador.php?acao=documento_imprimir_web&id=1\n"
                 "1 of 2 03/10/2018 12:22\n"
                 "Extrato de Sessão de Julgamento (0594322) SEI 19957.001067/2017-47 / pg. 1\n"
                 "ÁRIOS\nVALORES\nSSÃO DE\n"
                 "O Diretor VALORES votou.\nCVM")
        limpo, _ = conv.tirar_timbre(texto)
        self.assertEqual(limpo.strip(), "O Diretor VALORES votou.\nCVM")

    def test_pdf_tira_timbre_tambem_sem_regra_de_repetidas(self):
        pasta = tempfile.mkdtemp()
        with open(os.path.join(pasta, "a.pdf"), "wb") as f:
            f.write(b"%PDF")
        cv = conv.Conversao(pasta, PdfFalso({"a.pdf": "Texto da ata.\nwww.cvm.gov.br\n"}))
        with mock.patch.object(conv, "_pypdf_paginas", return_value=None):
            texto = cv.pdf({"arquivo": "a.pdf", "url": "u", "papel": "documento"},
                           limpar_repetidas=False)
        self.assertNotIn("cvm.gov.br", texto)
        self.assertEqual((cv.trechos_timbre, cv.retirado), (1, ["www.cvm.gov.br"]))

    def test_ata_extraordinaria_de_colegiado(self):
        atas = conv.decisoes_antigas(
            "ATA DA REUNIÃO EXTRAORDINÁRIA DE COLEGIADO DE 05.03.1991\nPARTICIPANTES:\n"
            "FULANO EXEMPLO – Presidente\nRECURSO CONTRA DECISÃO DA SEP\nO Colegiado decidiu.\n")
        self.assertEqual(len(atas), 1)
        self.assertEqual(atas[0][1], "1991-03-05")

    def test_ata_com_complemento_antes_da_data(self):
        # 1979: "... DO COLEGIADO COM O SUPERINTENDENTE GERAL DE 17.12.1979" não pode sumir
        atas = conv.decisoes_antigas(
            "Decisões do Colegiado\n1979\n"
            "ATA DA REUNIÃO DO COLEGIADO COM O SUPERINTENDENTE GERAL DE 17.12.1979\nPresentes:\n"
            "PROJETO DE RESOLUÇÃO SOBRE AS BOLSAS\nO projeto será colocado em audiência.\n"
            "ATA DA REUNIÃO DO COLEGIADO DE 17.07.1979\nPresentes:\n"
            "AÇÕES EM TESOURARIA E OUTROS\nO Colegiado aprovou.\n")
        self.assertEqual([a[1] for a in atas], ["1979-12-17", "1979-07-17"])


class CitacoesGuardaTest(unittest.TestCase):
    def test_fora_sem_numero_sai_com_aviso(self):
        falso = mock.MagicMock()
        falso.carregar_ids.return_value = set()
        falso.formatar_normas_citadas.return_value = "fora:lei; fora:lei-9784; lei-6385"
        falso.formatar_dispositivos_citados.return_value = "fora:lei art. 2º; lei-6385 art. 11"
        conv._CITACOES.clear()
        try:
            with mock.patch.dict(sys.modules, {"citacoes": falso}):
                normas, disp, aviso = conv.citacoes("texto")
        finally:
            conv._CITACOES.clear()
        self.assertEqual(normas, "fora:lei-9784; lei-6385")
        self.assertEqual(disp, "lei-6385 art. 11")
        self.assertIn("fora:lei", aviso)


class CoberturaTest(unittest.TestCase):
    def test_pdf_palavra_partida_ou_colada_conta_como_coberta(self):
        m = conv.medir("responsabilidade administrativa", "respon sabilidade adminis-\ntrativa")
        self.assertEqual((m["cobertura"], m["faltam"], m["fragmentos"]), (1.0, [], 2))

    def test_retiradas_e_pii_fora_da_conta(self):
        ref = "decisao colegiado setembro sete telefone fulano beltrano"
        m = conv.medir(ref, "decisao colegiado", retirado="Rua Sete de Setembro telefone",
                       antes_pii="decisao colegiado fulano")
        self.assertEqual((m["retiradas"], m["pii"], m["faltam"]), (3, 1, ["beltrano"]))
        self.assertEqual(m["cobertura"], round(2 / 3, 4))

    def test_html_compara_so_a_regiao_usada(self):
        html = ("<html><nav>Menu Institucional Legislação Ouvidoria</nav>"
                "<article class=\"contentTextoGeral\"><h2>02/12/2025</h2>"
                "<p>O Colegiado deliberou aceitar a proposta.</p>"
                "<div class=\"contentVejaMais\">Consulte anexos relacionados</div></article>"
                "<footer>Rodapé portal governo</footer></html>")
        ref = conv.texto_html_independente(conv.regiao_html(html, "artigo"))
        self.assertNotIn("Menu", ref)
        self.assertNotIn("Consulte", ref)
        self.assertIn("deliberou", ref)
        m = conv.medir(ref, "2025-12-02 O Colegiado deliberou aceitar a proposta.")
        self.assertEqual(m["cobertura"], 1.0)
        pas = conv.regiao_html(fixture("pas-pagina.html").decode("utf-8"), "pas")
        self.assertIn("2025-05-27", pas)
        self.assertNotIn("Data da Sess", pas)


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
