"""Testes do validar_plugin.py (limites do plugin, fichas e índices dos julgados), em pastas temporárias."""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import fichas as F  # noqa: E402
import validar_plugin as VP  # noqa: E402

ID = "cvm-pas-1"
REL = "cvm/pas/2025/1.md"


def gravar(base, rel, texto):
    p = os.path.join(base, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(texto)


def ficha(id_=ID, rel=REL):
    return "## %s\n- id: %s\n- texto_integral: %s%s\n- trecho: x\n" % (id_, id_, F.BASE_URL, rel)


def indice_md(linhas):
    return ("# Índice\n\n| Processo | Data | Resultado | Id | Ficha |\n|---|---|---|---|---|\n"
            + "".join("| 1 | 2025-01-01 | condenacao | %s | %s |\n" % (i, f) for i, f in linhas))


class Base(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.skill = os.path.join(self.repo, VP.SKILL_JULGADOS)
        gravar(self.repo, "julgados/" + REL, "texto\n")
        gravar(self.skill, "fichas/pas/2025.md", "# PAS 2025\n\n" + ficha())
        gravar(self.skill, "indice.md", "# Índice\n")
        gravar(self.skill, "indices/pas-2025.md", indice_md([(ID, "fichas/pas/2025.md")]))

    def validar(self):
        return VP.validar(self.repo)


class TestOk(Base):
    def test_pasta_consistente_nao_tem_violacao(self):
        self.assertEqual(self.validar(), [])

    def test_main_devolve_zero_e_um(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(VP.main(["--repo", self.repo]), 0)
        self.assertIn("0 violação", out.getvalue())
        os.remove(os.path.join(self.skill, "fichas", "pas", "2025.md"))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(VP.main(["--repo", self.repo]), 1)

    def test_limites_sao_os_da_tarefa(self):
        self.assertEqual((VP.LIMITE_MB, VP.LIMITE_ARQUIVOS, VP.LIMITE_FICHA, VP.LIMITE_INDICE_MD),
                         (170, 4500, 24000, 25 * 1024))
        self.assertEqual(VP.LIMITE_FICHA, F.LIMITE_ARQUIVO)


class TestTamanho(Base):
    def test_plugin_acima_de_mb_falha(self):
        gravar(self.repo, "plugins/normas/grande.bin", "x" * 2048)
        self.assertEqual(VP.erros_tamanho(self.repo, limite_mb=1), [])
        e = VP.erros_tamanho(self.repo, limite_mb=0.001)
        self.assertEqual(len(e), 1)
        self.assertIn("MB, acima de 0.001 MB", e[0])

    def test_plugin_acima_de_arquivos_falha(self):
        e = VP.erros_tamanho(self.repo, limite_arquivos=2)
        self.assertEqual(len(e), 1)
        self.assertIn("arquivos, acima de 2", e[0])
        self.assertEqual(VP.erros_tamanho(self.repo, limite_arquivos=4500), [])

    def test_plugin_ausente_e_falha(self):
        shutil.rmtree(os.path.join(self.repo, "plugins"))
        self.assertTrue(any("pasta não existe" in e for e in self.validar()))


class TestLimitesDaSkill(Base):
    def test_ficha_acima_de_24000_bytes_falha(self):
        gravar(self.skill, "fichas/pas/2025-02.md", "x" * 24001)
        e = [x for x in self.validar() if "24000" in x]
        self.assertEqual(len(e), 1)
        self.assertIn("2025-02.md", e[0])

    def test_ficha_de_exatos_24000_bytes_passa(self):
        gravar(self.skill, "fichas/pas/2025-02.md", "x" * 24000)
        self.assertEqual([x for x in self.validar() if "24000" in x], [])

    def test_indice_md_acima_de_25_kb_falha(self):
        gravar(self.skill, "indice.md", "x" * (25 * 1024 + 1))
        self.assertTrue(any("indice.md" in x and "acima de %d" % (25 * 1024) in x for x in self.validar()))

    def test_sem_fichas_ou_sem_indice_md_e_falha(self):
        shutil.rmtree(os.path.join(self.skill, "fichas"))
        self.assertTrue(any("sem fichas" in e for e in self.validar()))
        os.remove(os.path.join(self.skill, "indice.md"))
        self.assertTrue(any("indice.md: não existe" in e for e in self.validar()))


class TestTextoIntegral(Base):
    def test_url_para_arquivo_inexistente_falha(self):
        gravar(self.skill, "fichas/pas/2025.md", "# x\n\n" + ficha(rel="cvm/pas/2025/nao-existe.md"))
        self.assertTrue(any("não existe" in e and "nao-existe.md" in e for e in self.validar()))

    def test_url_fora_da_base_falha(self):
        gravar(self.skill, "fichas/pas/2025.md", "# x\n\n## cvm-pas-1\n- texto_integral: https://exemplo.com/a.md\n")
        self.assertTrue(any("fora da base" in e for e in self.validar()))

    def test_url_com_percent_encoding_vira_caminho(self):
        gravar(self.repo, "julgados/cvm/pas/2025/a b.md", "texto\n")
        self.assertEqual(VP.alvo_do_texto(F.url_texto("cvm/pas/2025/a b.md")), "cvm/pas/2025/a b.md")
        self.assertIsNone(VP.alvo_do_texto("https://exemplo.com/x.md"))
        gravar(self.skill, "fichas/pas/2025.md", "# x\n\n" + ficha() + "\n" + ficha("cvm-pas-2", "cvm/pas/2025/a b.md").replace(
            "a b.md", "a%20b.md"))
        self.assertEqual(self.validar(), [])

    def test_pasta_julgados_da_raiz_ausente_e_falha(self):
        shutil.rmtree(os.path.join(self.repo, "julgados"))
        self.assertTrue(any(e == "julgados: pasta não existe" for e in self.validar()))


class TestIndices(Base):
    def test_ficha_inexistente_no_indice_falha(self):
        gravar(self.skill, "indices/pas-2025.md", indice_md([(ID, "fichas/pas/2026.md")]))
        self.assertTrue(any("ficha não existe: fichas/pas/2026.md" in e for e in self.validar()))

    def test_id_que_nao_esta_no_arquivo_da_ficha_falha(self):
        gravar(self.skill, "indices/pas-2025.md", indice_md([("cvm-pas-9", "fichas/pas/2025.md")]))
        self.assertTrue(any("não tem `## cvm-pas-9`" in e for e in self.validar()))

    def test_id_que_e_so_prefixo_de_outro_nao_vale(self):
        gravar(self.skill, "indices/pas-2025.md", indice_md([("cvm-pas", "fichas/pas/2025.md")]))
        self.assertTrue(any("não tem `## cvm-pas`" in e for e in self.validar()))

    def test_indice_sem_nenhuma_linha_com_id_e_ficha_falha(self):
        os.remove(os.path.join(self.skill, "indices", "pas-2025.md"))
        gravar(self.skill, "indices/outro.md", "# vazio\n")
        self.assertTrue(any("nenhuma linha com Id e Ficha" in e for e in self.validar()))

    def test_pares_dos_indices_le_so_tabelas_com_id_e_ficha(self):
        md = ("| Tipo | Ano |\n|---|---|\n| pas | 2025 |\n\n"
              "| Data da ata | Processo | Id | Ficha |\n|---|---|---|---|\n"
              "| 1990-01-01 | — | cvm-dec-1990-0001 | fichas/decisoes-antigas/1990.md |\n")
        self.assertEqual(VP.pares_dos_indices(md), [("fichas/decisoes-antigas/1990.md", "cvm-dec-1990-0001")])

    def test_arquivos_de_ficha_nao_sao_lidos_como_indice(self):
        # a ficha cita "| Id | Ficha |" no texto de um trecho: não conta como tabela de índice
        gravar(self.skill, "fichas/pas/2025.md", "# x\n\n" + ficha() + "| Id | Ficha |\n| a | b |\n")
        self.assertEqual(self.validar(), [])


class TestJulgadoSemFicha(Base):
    def test_julgado_da_raiz_sem_ficha_falha(self):
        gravar(self.repo, "julgados/cvm/pas/2025/2.md", "outro\n")
        e = [x for x in self.validar() if "sem ficha" in x]
        self.assertEqual(e, ["julgados/cvm/pas/2025/2.md: sem ficha"])

    def test_indice_md_e_indices_da_raiz_nao_contam_como_julgado(self):
        gravar(self.repo, "julgados/indice.md", "# i\n")
        gravar(self.repo, "julgados/indices/x.md", "# i\n")
        self.assertEqual(self.validar(), [])


if __name__ == "__main__":
    unittest.main()
