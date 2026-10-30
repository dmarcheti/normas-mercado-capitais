"""Testes do índice reverso de citações (normas) e dos índices dos julgados (SPEC v0.5.0), sem rede."""
import io
import os
import sys
import tempfile
import unittest
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
        self.assertIn("plugins `julgados-*`", arqs["indice.md"])

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
        self.raiz = os.path.join(self._tmp.name, "plugins", "julgados-sancionadores", "julgados")
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
            "indice.md", "indices/norma-fora-icvm-358.md", "indices/norma-lei-6404.md",
            "indices/pas-2025.md", "indices/tema-deveres-administradores.md",
            "indices/termo-compromisso-2024.md"])

    def test_resumo_com_aviso_perimetro_e_contagem(self):
        md = indice.gerar_indice_julgados(self.raiz, NORMAS)[0]["indice.md"]
        self.assertIn("Julgado não é norma", md)
        self.assertIn("PAS, termos de compromisso e acórdãos do CRSFN", md)
        self.assertIn("[indices/pas-2025.md](indices/pas-2025.md)", md)
        self.assertIn("[indices/tema-deveres-administradores.md]", md)
        self.assertIn("[indices/norma-lei-6404.md]", md)
        self.assertIn("Processos Administrativos Sancionadores (PAS), 1", md)

    def test_linha_usa_ementa_e_nunca_o_titulo(self):
        arqs = indice.gerar_indice_julgados(self.raiz, NORMAS)[0]
        for rel, md in arqs.items():
            self.assertNotIn("FULANO", md, rel)
        pas = arqs["indices/pas-2025.md"]
        self.assertIn("Dever de diligência de administradores", pas)
        self.assertIn("| 19957.011607/2024-20 | 2025-05-27 | condenacao | deveres-administradores |", pas)
        self.assertIn("cvm/pas/2025/19957-011607-2024-20.md", pas)

    def test_indice_reverso_por_norma(self):
        arqs = indice.gerar_indice_julgados(self.raiz, NORMAS)[0]
        md = arqs["indices/norma-lei-6404.md"]
        self.assertIn("[leis/lei-06404/index.md](../../../normas/normas/leis/lei-06404/index.md)", md)
        self.assertIn("texto vigente hoje; o julgado aplicou a redação da época", md)
        self.assertIn("## art. 155", md)
        self.assertIn("| § 1º | pas |", md.replace("art. 155, § 1º", "§ 1º"))
        self.assertIn("## Citada sem dispositivo identificado", md)  # o TC cita só a norma
        self.assertIn("col-20240603-d100.md", md)
        fora = arqs["indices/norma-fora-icvm-358.md"]
        self.assertIn("fora do acervo", fora)
        self.assertIn("## art. 3º", fora)

    def test_sem_julgados_nada_e_gerado(self):
        with tempfile.TemporaryDirectory() as r:
            vazio = os.path.join(r, "julgados")
            os.makedirs(vazio)
            self.assertEqual(indice.gerar_indice_julgados(vazio, NORMAS), ({}, 0))
            self.assertEqual(silencioso(indice.main, ["indice.py", vazio, "--verificar"]), 0)

    def test_main_grava_e_verifica_raiz_de_julgados(self):
        args = ["indice.py", self.raiz]
        self.assertEqual(silencioso(indice.main, args + ["--verificar"]), 1)
        self.assertEqual(silencioso(indice.main, args), 0)
        self.assertEqual(silencioso(indice.main, args + ["--verificar"]), 0)
        os.remove(os.path.join(self.raiz, "cvm", "colegiado", "2024", "col-20240603-d100.md"))
        self.assertEqual(silencioso(indice.main, args + ["--verificar"]), 1)  # sobra termo-compromisso-2024
        self.assertEqual(silencioso(indice.main, args), 0)
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "indices", "termo-compromisso-2024.md")))

    def test_slug_do_tema(self):
        self.assertEqual(indice.slug_tema("Ofertas públicas: dispensa"), "ofertas-publicas-dispensa")


if __name__ == "__main__":
    unittest.main()
