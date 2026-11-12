"""Testes do índice reverso de citações (normas) e dos índices dos julgados (SPEC v0.5.0), sem rede."""
import io
import os
import sys
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stdout

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))
sys.path.insert(0, AQUI)

import indice  # noqa: E402
from test_indice import SEM_ACERVO, SEM_VIGENCIA, VALORES  # noqa: E402
from test_validar_julgados import BASE, montar  # noqa: E402
from validar import CAMPOS  # noqa: E402

TEXTO_OC = """# Ofício-Circular

25. Nos termos do art. 2º, inciso XII, alínea "d", do Anexo Normativo II à Resolução CVM nº 175, as cotas.
18. O gestor fica sujeito ao art. 90 da Parte Geral da Resolução CVM nº 175 e ao art. 3º da ICVM 358.
Repetido: art. 90 da Resolução CVM nº 175.
"""


def gravar(raiz, rel, corpo="## Art. 1º\n\nTexto.", **mudancas):
    v = dict(VALORES)
    v.update(mudancas)
    caminho = os.path.join(raiz, *rel.split("/"))
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    linhas = ["---"] + ["%s: %s" % (c, v[c]) if v[c] else "%s:" % c for c in CAMPOS] + ["---", "", corpo]
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")


def silencioso(fn, *a):
    with redirect_stdout(io.StringIO()):
        return fn(*a)


class TestCitacoesDoAcervo(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = self._tmp.name
        gravar(self.raiz, "cvm/resolucoes/0175.md", id="cvm-res-175", numero="175", data="2022-12-23",
               corpo="## Art. 1º\n\nConforme o art. 2º desta Resolução e o art. 5º da Resolução CVM nº 175.")
        gravar(self.raiz, "cvm/oficios-circulares/sse1/oc-sse-0825.md", id="cvm-oc-sse-0825",
               tipo="oficio-circular", numero="8", data="2025-11-17", corpo=TEXTO_OC, **SEM_VIGENCIA)

    def tearDown(self):
        self._tmp.cleanup()

    def test_subindice_por_norma_citada(self):
        arqs, _ = indice.gerar_indice(self.raiz, SEM_ACERVO)
        self.assertEqual(sorted(k for k in arqs if "citacoes" in k),
                         ["indices/citacoes.md", "indices/citacoes/cvm-res-175.md"])
        md = arqs["indices/citacoes/cvm-res-175.md"]
        self.assertIn("## art. 90", md)
        self.assertIn("## Anexo II, art. 2º", md)
        self.assertLess(md.index("## art. 90"), md.index("## Anexo II, art. 2º"))  # parte geral primeiro
        linha = next(l for l in md.split("\n") if l.startswith("| Anexo II art. 2º"))
        self.assertIn("| Anexo II art. 2º, inciso XII, alínea d | ", linha)
        self.assertIn("| oficio-circular | 2025-11-17 | cvm/oficios-circulares/sse1/oc-sse-0825.md |", linha)
        trecho = linha.rstrip(" |").rsplit(" | ", 1)[1]
        self.assertLessEqual(len(trecho), 160)
        self.assertEqual(md.count("| art. 90 |"), 1)  # (documento, dispositivo) sem repetir
        self.assertNotIn("icvm", md)
        self.assertIn("Material não oficial", md)

    def test_so_documentos_de_interpretacao_e_sem_autocitacao(self):
        arqs, _ = indice.gerar_indice(self.raiz, SEM_ACERVO)
        md = arqs["indices/citacoes/cvm-res-175.md"]
        self.assertNotIn("art. 5º", md)  # a própria 175 não é documento de interpretação
        self.assertIn("[cvm-res-175](citacoes/cvm-res-175.md)", arqs["indices/citacoes.md"])
        self.assertIn("| 1 | 2 |", arqs["indices/citacoes.md"])  # 1 documento, 2 citações

    def test_resumo_aponta_citacoes_e_julgados(self):
        arqs, _ = indice.gerar_indice(self.raiz, SEM_ACERVO)
        self.assertIn("(indices/citacoes.md)", arqs["indice.md"])
        self.assertIn("(../julgados/indice.md)", arqs["indice.md"])
        self.assertNotIn("julgados-*", arqs["indice.md"])

    def test_sem_citacao_nao_gera(self):
        with tempfile.TemporaryDirectory() as r:
            gravar(r, "cvm/resolucoes/0017.md", id="cvm-res-17", numero="17")
            arqs, _ = indice.gerar_indice(r, SEM_ACERVO)
            self.assertFalse([k for k in arqs if "citacoes" in k])
            self.assertNotIn("indices/citacoes.md", arqs["indice.md"])

    def test_subindice_grande_vira_pasta(self):
        orig = indice.LIMITE_SUBINDICE
        indice.LIMITE_SUBINDICE = 500
        try:
            arqs, _ = indice.gerar_indice(self.raiz, SEM_ACERVO)
        finally:
            indice.LIMITE_SUBINDICE = orig
        base = "indices/citacoes/cvm-res-175"
        self.assertEqual(sorted(k for k in arqs if "citacoes/" in k),
                         [base + "/anexo-ii-art-0002.md", base + "/art-0090.md", base + "/index.md"])
        self.assertNotIn(base + ".md", arqs)
        idx = arqs[base + "/index.md"]
        self.assertIn("| parte geral | 90 | 1 | [art-0090.md](art-0090.md) |", idx)
        self.assertIn("| Anexo II | 2º | 1 | [anexo-ii-art-0002.md](anexo-ii-art-0002.md) |", idx)
        self.assertLess(idx.index("art-0090"), idx.index("anexo-ii"))
        self.assertIn("## Anexo II, art. 2º", arqs[base + "/anexo-ii-art-0002.md"])
        self.assertNotIn("## art. 90", arqs[base + "/anexo-ii-art-0002.md"])
        self.assertIn("(citacoes/cvm-res-175/index.md)", arqs["indices/citacoes.md"])

    def test_nome_do_arquivo_de_artigo(self):
        self.assertEqual(indice._nome_artigo("", "155"), "art-0155")
        self.assertEqual(indice._nome_artigo("Anexo II", "2º"), "anexo-ii-art-0002")
        self.assertEqual(indice._nome_artigo("", "1.368-C"), "art-1368-c")
        self.assertEqual(indice._nome_artigo("Suplemento A", "9º"), "suplemento-a-art-0009")

    def test_verificar_cobre_a_pasta_e_a_troca_de_formato(self):
        args = ["indice.py", self.raiz, "--acervo", SEM_ACERVO]
        orig = indice.LIMITE_SUBINDICE
        indice.LIMITE_SUBINDICE = 500
        try:
            self.assertEqual(silencioso(indice.main, args), 0)
            self.assertEqual(silencioso(indice.main, args + ["--verificar"]), 0)
            pasta = os.path.join(self.raiz, "indices", "citacoes", "cvm-res-175")
            sobra = os.path.join(pasta, "art-0999.md")
            with open(sobra, "w", encoding="utf-8") as f:
                f.write("velho\n")
            self.assertEqual(silencioso(indice.main, args + ["--verificar"]), 1)
            self.assertEqual(silencioso(indice.main, args), 0)
            self.assertFalse(os.path.exists(sobra))
        finally:
            indice.LIMITE_SUBINDICE = orig
        # de volta abaixo do limite: a pasta sobra (falha) até gravar, que a apaga
        self.assertEqual(silencioso(indice.main, args + ["--verificar"]), 1)
        self.assertEqual(silencioso(indice.main, args), 0)
        self.assertFalse(os.path.exists(pasta))
        self.assertTrue(os.path.exists(pasta + ".md"))
        self.assertEqual(silencioso(indice.main, args + ["--verificar"]), 0)

    def test_verificar_acusa_sobra_em_citacoes(self):
        args = ["indice.py", self.raiz, "--acervo", SEM_ACERVO]
        self.assertEqual(silencioso(indice.main, args), 0)
        self.assertEqual(silencioso(indice.main, args + ["--verificar"]), 0)
        sobra = os.path.join(self.raiz, "indices", "citacoes", "cvm-res-1.md")
        with open(sobra, "w", encoding="utf-8") as f:
            f.write("velho\n")
        self.assertEqual(silencioso(indice.main, args + ["--verificar"]), 1)
        self.assertEqual(silencioso(indice.main, args), 0)
        self.assertFalse(os.path.exists(sobra))


NORMAS = {"lei-6404": {"id": "lei-6404", "titulo": "Lei nº 6.404/1976", "caminho": "leis/lei-06404/index.md"}}


class TestIndicesDosJulgados(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = os.path.join(self._tmp.name, "julgados")  # texto dos julgados (raiz do repositório)
        self.saida = os.path.join(self._tmp.name, "saida")  # onde os índices são gravados
        self.gravar("cvm/pas/2025/19957-011607-2024-20.md", BASE, "# PAS CVM nº 19957.011607/2024-20 - "
                    "FULANO DE TAL\n\n## Relatório\n\nx\n")
        tc = dict(BASE, id="cvm-col-20240603-d100", tipo="termo-compromisso", data="2024-06-03",
                  resultado="aceito", tema="", tema_fonte="", normas_citadas="lei-6404",
                  dispositivos_citados="", ementa="Proposta de termo de compromisso.")
        self.gravar("cvm/colegiado/2024/col-20240603-d100.md", tc)

    def tearDown(self):
        self._tmp.cleanup()

    def gravar(self, rel, valores, corpo="# Título\n\n## Texto\n\nx\n"):
        p = os.path.join(self.raiz, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(montar(valores, corpo))

    def test_arquivos_gerados(self):
        arqs, n = indice.gerar_indice_julgados(self.raiz, NORMAS)
        self.assertEqual(n, 2)
        self.assertEqual(sorted(arqs), [
            "indice.md", "indices/norma-fora-outras-icvm.md", "indices/norma-lei-6404.md",
            "indices/normas-citadas.md", "indices/pas-2025.md", "indices/processo-2024.md", "indices/tema-deveres-administradores.md",
            "indices/termo-compromisso-2024.md"])

    def test_resumo_com_aviso_perimetro_e_contagem(self):
        md = indice.gerar_indice_julgados(self.raiz, NORMAS)[0]["indice.md"]
        self.assertIn("Julgado não é norma", md)
        self.assertIn("Julgados da CVM (processos administrativos sancionadores", md)
        self.assertIn("acórdãos do CRSFN", md)
        self.assertIn("| [2025](indices/pas-2025.md) | 1 |", md)
        self.assertIn("## Por processo", md)
        self.assertIn("[2024](indices/processo-2024.md)", md)
        self.assertIn("(indices/tema-deveres-administradores.md)", md)
        self.assertIn("[indices/normas-citadas.md](indices/normas-citadas.md) (2 normas citadas)", md)
        self.assertIn("Processos Administrativos Sancionadores (PAS), 1", md)

    def test_linha_usa_ementa_e_nunca_o_titulo(self):
        arqs = indice.gerar_indice_julgados(self.raiz, NORMAS)[0]
        for rel, md in arqs.items():
            self.assertNotIn("FULANO", md, rel)
        pas = arqs["indices/pas-2025.md"]
        self.assertIn("Dever de diligência de administradores", pas)
        self.assertIn("| 19957.011607/2024-20 | 2025-05-27 | condenacao | deveres-administradores |", pas)
        self.assertIn("| ../../../../../julgados/cvm/pas/2025/19957-011607-2024-20.md |", pas)

    def test_indice_reverso_por_norma(self):
        arqs = indice.gerar_indice_julgados(self.raiz, NORMAS)[0]
        md = arqs["indices/norma-lei-6404.md"]
        self.assertIn("[leis/lei-06404/index.md](../../normas/leis/lei-06404/index.md)", md)
        self.assertIn("texto vigente hoje; o julgado aplicou a redação da época", md)
        self.assertIn("## art. 155", md)
        self.assertIn("| § 1º | pas |", md.replace("art. 155, § 1º", "§ 1º"))
        self.assertIn("## Citada sem dispositivo identificado", md)  # o TC cita só a norma
        self.assertIn("col-20240603-d100.md", md)
        # fora do acervo com menos de FORA_MIN_PROPRIO julgados: arquivo da família, seção por norma
        fora = arqs["indices/norma-fora-outras-icvm.md"]
        self.assertIn("fora do acervo", fora)
        self.assertIn("## icvm-358", fora)
        self.assertIn("### art. 3º", fora)
        # a tabela das normas fica no subíndice normas-citadas.md (o indice.md só aponta para ele)
        lista = arqs["indices/normas-citadas.md"]
        self.assertIn("[Fora do acervo, família icvm: 1 normas com menos de 10 julgados cada]"
                      "(norma-fora-outras-icvm.md)", lista)
        self.assertIn("[Lei nº 6.404/1976](norma-lei-6404.md) | 2 |", lista)
        self.assertNotIn("norma-lei-6404", arqs["indice.md"])

    def test_fora_do_acervo_muito_citada_tem_arquivo_proprio(self):
        with mock.patch.object(indice, "FORA_MIN_PROPRIO", 1):
            arqs = indice.gerar_indice_julgados(self.raiz, NORMAS)[0]
        self.assertIn("indices/norma-fora-icvm-358.md", arqs)
        self.assertNotIn("indices/norma-fora-outras-icvm.md", arqs)
        self.assertIn("## art. 3º", arqs["indices/norma-fora-icvm-358.md"])

    def test_familia_da_norma_fora(self):
        self.assertEqual([indice.familia_fora(r) for r in
                          ("icvm-358", "res-cmn-4656", "decreto-lei-2848", "lei-6385", "mp-2158-35")],
                         ["icvm", "res-cmn", "decreto-lei", "lei", "mp"])

    def test_sem_julgados_gerar_devolve_vazio_mas_o_script_falha(self):
        with tempfile.TemporaryDirectory() as r:
            vazio = os.path.join(r, "julgados")
            os.makedirs(vazio)
            self.assertEqual(indice.gerar_indice_julgados(vazio, NORMAS), ({}, 0))
            saida = os.path.join(r, "saida")
            args = ["indice.py", vazio, "--saida-julgados", saida]
            # sem nenhum julgado o índice não pode ficar em dia nem ser gravado em silêncio
            self.assertEqual(silencioso(indice.main, args + ["--verificar"]), 2)
            self.assertEqual(silencioso(indice.main, args), 2)
            self.assertFalse(os.path.exists(saida))

    def test_pasta_de_julgados_ausente_falha(self):
        with tempfile.TemporaryDirectory() as r:
            with mock.patch.object(indice, "JULGADOS_PADRAO", os.path.join(r, "julgados")):
                self.assertEqual(silencioso(indice.main, ["indice.py", "--saida-julgados", os.path.join(r, "s"),
                                                          "--verificar"]), 2)
                self.assertEqual(silencioso(indice.main, ["indice.py", "--saida-julgados", os.path.join(r, "s")]), 2)
                self.assertFalse(os.path.exists(os.path.join(r, "s")))

    def test_main_grava_e_verifica_raiz_de_julgados(self):
        args = ["indice.py", self.raiz, "--saida-julgados", self.saida]
        self.assertEqual(silencioso(indice.main, args + ["--verificar"]), 1)
        self.assertEqual(silencioso(indice.main, args), 0)
        self.assertEqual(silencioso(indice.main, args + ["--verificar"]), 0)
        self.assertTrue(os.path.exists(os.path.join(self.saida, "indice.md")))
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "indice.md")))  # nada gravado junto do texto
        os.remove(os.path.join(self.raiz, "cvm", "colegiado", "2024", "col-20240603-d100.md"))
        self.assertEqual(silencioso(indice.main, args + ["--verificar"]), 1)  # sobra termo-compromisso-2024
        self.assertEqual(silencioso(indice.main, args), 0)
        self.assertFalse(os.path.exists(os.path.join(self.saida, "indices", "termo-compromisso-2024.md")))

    def test_conjunto_unico_para_cvm_e_crsfn(self):
        cr = dict(BASE, id="crsfn-19957-000009-2020-01", orgao="crsfn", tipo="acordao-crsfn",
                  data="2021-05-05", processo="19957.000009/2020-01", normas_citadas="", dispositivos_citados="",
                  tema="", tema_fonte="", ementa="Recurso contra decisão da CVM.")
        self.gravar("crsfn/2021/19957-000009-2020-01.md", cr)
        col = dict(BASE, id="cvm-col-20250101-d1", tipo="decisao-colegiado", data="2025-01-01",
                   processo="RJ2025/1", normas_citadas="", dispositivos_citados="", tema="", tema_fonte="",
                   ementa="Consulta respondida.")
        self.gravar("cvm/colegiado/2025/col-20250101-d1.md", col)
        arqs, n = indice.gerar_indice_julgados(self.raiz, NORMAS)
        self.assertEqual(n, 4)
        md = arqs["indice.md"]
        for rotulo in ("Processos Administrativos Sancionadores (PAS)", "Termos de compromisso",
                       "Decisões do Colegiado", "Acórdãos do CRSFN"):
            self.assertIn(rotulo, md)
        self.assertEqual(md.count("# Índice dos julgados"), 1)
        self.assertIn("../../../../../julgados/crsfn/2021/19957-000009-2020-01.md",
                      arqs["indices/acordao-crsfn-2021.md"])
        # índice por processo: PAS, termo de compromisso e acórdão do CRSFN; a decisão do Colegiado fica fora
        self.assertIn("19957-000009-2020-01", arqs["indices/processo-2020.md"])
        self.assertNotIn("col-20250101-d1", "".join(v for k, v in arqs.items() if k.startswith("indices/processo-")))

    def test_alvo_do_link_vem_de_uma_funcao_so(self):
        v = {"_caminho": "cvm/pas/2025/x.md"}
        self.assertEqual(indice.alvo_link(v), "../../../../../julgados/cvm/pas/2025/x.md")
        self.assertEqual(indice.alvo_link(v, prefixo="p/"), "p/cvm/pas/2025/x.md")
        # trocar a função muda o alvo em todas as tabelas (índice por tipo, tema, norma, processo)
        with mock.patch.object(indice, "alvo_link", lambda v: "FICHA/" + v["_caminho"]):
            arqs = indice.gerar_indice_julgados(self.raiz, NORMAS)[0]
        for rel in ("indices/pas-2025.md", "indices/tema-deveres-administradores.md",
                    "indices/norma-lei-6404.md", "indices/processo-2024.md"):
            self.assertIn("FICHA/cvm/pas/2025/19957-011607-2024-20.md", arqs[rel], rel)
            self.assertNotIn("../julgados/", arqs[rel], rel)

    def test_prefixo_leva_da_pasta_do_indice_ao_julgados_da_raiz(self):
        pasta = os.path.join(indice.SKILL_NORMAS, "julgados")
        self.assertEqual(os.path.normpath(os.path.join(pasta, indice.PREFIXO_ALVO)),
                         os.path.join(indice.REPO, "julgados"))
        self.assertEqual(os.path.normpath(os.path.join(pasta, "indices", indice.LINK_NORMAS_PADRAO)),
                         os.path.join(indice.SKILL_NORMAS, "normas"))
        self.assertEqual(indice.SAIDA_JULGADOS_PADRAO, pasta)

    def test_indice_md_abaixo_de_25_kb_ou_falha(self):
        arqs = indice.gerar_indice_julgados(self.raiz, NORMAS)[0]
        self.assertLess(len(arqs["indice.md"].encode("utf-8")), 25 * 1024)
        self.assertEqual(indice.LIMITE_INDICE_MD, 25 * 1024)
        with mock.patch.object(indice, "LIMITE_INDICE_MD", 500):
            with self.assertRaises(ValueError):
                indice.gerar_indice_julgados(self.raiz, NORMAS)

    def test_slug_do_tema(self):
        self.assertEqual(indice.slug_tema("Ofertas públicas: dispensa"), "ofertas-publicas-dispensa")


if __name__ == "__main__":
    unittest.main()
