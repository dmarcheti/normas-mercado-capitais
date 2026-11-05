"""Testes da reescrita do histórico e do conferidor (gate da Fase 5). Repositórios git descartáveis em
diretório temporário; CPF e e-mail fictícios montados em pedaços, para que este arquivo não dispare a
varredura do pre-commit. Os testes que rodam o filter-repo pulam quando ele não está instalado."""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

AQUI = os.path.dirname(__file__)
SCRIPTS = os.path.join(AQUI, "..", "scripts")
sys.path.insert(0, SCRIPTS)

import conferir_reescrita as cr  # noqa: E402
import pii  # noqa: E402
import reescrever_historico as rh  # noqa: E402

TEM_FILTER_REPO = importlib.util.find_spec("git_filter_repo") is not None
M = pii.MARCADOR
CPF_A = "123.456." + "789-09"
EMAIL_PESSOAL = "pessoa" + "@" + "exemplo-pessoal.com"
EMAIL_NOREPLY = "autor@users.noreply.github.com"
REPLAY = "Historico normativo (replay)"
NORMA = "plugins/normas/atos/a.md"
JUL_CPF = "plugins/julgados-cvm/julgados/2025.md"
JUL_BLOCO = "plugins/julgados-cvm/julgados/2024.md"
LATERAL = "notas/lateral.md"
TRECHO_BLOCO = "residente na Rua das Flores"

TEXTO_CPF = "# Julgados 2025\nLinha comum A\nO acusado, CPF %s, compareceu.\nLinha comum B\n" % CPF_A
TEXTO_BLOCO = ("# Julgado 2024\nlinha A\ny, brasileiro, casado,\nengenheiro, %s, 100, São Paulo, e mais\nlinha B\n"
               % TRECHO_BLOCO)


def _env(nome, email, data, committer=None):
    committer = committer or (nome, email)
    return dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                GIT_AUTHOR_NAME=nome, GIT_AUTHOR_EMAIL=email, GIT_AUTHOR_DATE=data,
                GIT_COMMITTER_NAME=committer[0], GIT_COMMITTER_EMAIL=committer[1], GIT_COMMITTER_DATE=data)


NORMAL = ("Autor Teste", "autor@exemplo.invalid")


def git(cwd, *args, env=None, entrada=None):
    r = subprocess.run(["git", "-C", cwd, "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false"] + list(args),
                       check=True, capture_output=True, input=entrada,
                       env=env or _env(NORMAL[0], NORMAL[1], "2024-03-01T12:00:00 -0300"))
    return r.stdout.decode("utf-8", "replace").strip()


def commitar(repo, arquivos, msg, data, autor=NORMAL, committer=None):
    for caminho, conteudo in arquivos.items():
        destino = os.path.join(repo, caminho)
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "w", encoding="utf-8") as f:
            f.write(conteudo)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg, env=_env(autor[0], autor[1], data, committer))
    return git(repo, "rev-parse", "HEAD")


def rodar(mod, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        codigo = mod.main(argv)
    return codigo, out.getvalue(), err.getvalue()


def criar_espelho(raiz, original, nome="e.git"):
    """Espelho bare sem remote, só com main (= fase-5 do original) e as tags, em .../dados/fase-5/espelho/."""
    espelho = os.path.join(raiz, "dados", "fase-5", "espelho", nome)
    os.makedirs(espelho)
    git(espelho, "init", "-q", "--bare", "-b", "main")
    git(espelho, "fetch", "-q", original, "fase-5:refs/heads/main", "refs/tags/*:refs/tags/*")
    return espelho


def escrever(caminho, texto):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)
    return caminho


class Cenario:
    """Repo original com os cinco ingredientes do brief, achados.jsonl e mailmap."""

    @classmethod
    def montar(cls):
        cls.raiz = tempfile.mkdtemp()
        cls.orig = os.path.join(cls.raiz, "orig")
        os.makedirs(cls.orig)
        git(cls.orig, "init", "-q", "-b", "fase-5")
        replay = (REPLAY, "replay@users.noreply.github.com")
        # (i) normas antes do primeiro dado pessoal
        cls.r1 = commitar(cls.orig, {NORMA: "# Norma A\nArt. 1º v1.\n"}, "ato 1", "2024-01-01T10:00:00 -0300", replay)
        cls.r2 = commitar(cls.orig, {NORMA: "# Norma A\nArt. 1º v2.\n"}, "ato 2", "2024-01-02T10:00:00 -0300", replay)
        git(cls.orig, "tag", "-a", "v1.0.0", "-m", "primeira", env=_env(NORMAL[0], EMAIL_NOREPLY, "2024-01-03T10:00:00 -0300"))
        git(cls.orig, "branch", "lateral")
        # (ii) CPF num commit e (iii) bloco que perde linhas
        cls.j1 = commitar(cls.orig, {JUL_CPF: TEXTO_CPF, JUL_BLOCO: TEXTO_BLOCO},
                          "grava julgados", "2024-02-01T10:00:00 -0300")
        git(cls.orig, "checkout", "-q", "lateral")
        commitar(cls.orig, {LATERAL: "lateral\n"}, "ramo lateral", "2024-02-02T10:00:00 -0300")
        git(cls.orig, "checkout", "-q", "fase-5")
        # (iv) merge de autor e committer com e-mail pessoal
        pessoal = ("Pessoa Teste", EMAIL_PESSOAL)
        git(cls.orig, "merge", "-q", "--no-ff", "lateral", "-m", "merge pela interface",
            env=_env(pessoal[0], pessoal[1], "2024-02-03T10:00:00 -0300"))
        cls.merge = git(cls.orig, "rev-parse", "HEAD")
        cls.j2 = commitar(cls.orig, {JUL_CPF: TEXTO_CPF.replace(CPF_A, M), JUL_BLOCO: pii.limpar(TEXTO_BLOCO)},
                          "limpa julgados", "2024-02-04T10:00:00 -0300")
        cls.r3 = commitar(cls.orig, {NORMA: "# Norma A\nArt. 1º v3.\n"}, "ato 3", "2024-02-05T10:00:00 -0300", replay)
        # (v) tag anotada de tagger pessoal, sobre commit que será reescrito
        git(cls.orig, "tag", "-a", "v1.1.0", "-m", "segunda",
            env=_env(pessoal[0], pessoal[1], "2024-02-06T10:00:00 -0300"))
        # achados.jsonl pelo próprio varrer_historico.py
        termos = escrever(os.path.join(cls.raiz, "termos.txt"), "# lista de teste\nTermo Proibido Zeta\n")
        cls.hist = os.path.join(cls.raiz, "historico")
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "varrer_historico.py"), "--repo", cls.orig,
                            "--saida", cls.hist, "--termos", termos, "--base", "fase-5", "--processos", "1"],
                           capture_output=True)
        assert r.returncode in (0, 1), r.stderr.decode()[-500:]
        cls.achados = os.path.join(cls.hist, "achados.jsonl")
        cls.mailmap = escrever(os.path.join(cls.raiz, "mailmap"),
                               "Pessoa Teste <%s> <%s>\n" % (EMAIL_NOREPLY, EMAIL_PESSOAL))

    @classmethod
    def desmontar(cls):
        shutil.rmtree(cls.raiz, ignore_errors=True)


def log_completo(espelho):
    return subprocess.run(["git", "-C", espelho, "log", "-p", "-m", "--all", "--format=fuller"],
                          capture_output=True, check=True).stdout.decode("utf-8", "replace")


@unittest.skipUnless(TEM_FILTER_REPO, "git_filter_repo não instalado")
class ReescritaTest(Cenario, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.montar()
        cls.espelho = criar_espelho(cls.raiz, cls.orig)
        cls.saida = os.path.join(cls.raiz, "saida")
        cls.antes_log = log_completo(cls.espelho)
        cls.codigo, cls.out, cls.err = rodar(
            rh, ["--repo", cls.espelho, "--achados", cls.achados, "--mailmap", cls.mailmap, "--saida", cls.saida])
        with open(os.path.join(cls.saida, "reescrita.json"), encoding="utf-8") as f:
            cls.rel = json.load(f)
        cls.mapa = rh.ler_commit_map(os.path.join(cls.saida, "commit-map"))

    @classmethod
    def tearDownClass(cls):
        cls.desmontar()

    def test_precondicoes_do_cenario(self):
        self.assertIn(CPF_A, self.antes_log)
        self.assertIn(EMAIL_PESSOAL, self.antes_log)
        self.assertIn(TRECHO_BLOCO, self.antes_log)
        self.assertNotEqual(len(TEXTO_BLOCO.split("\n")), len(pii.limpar(TEXTO_BLOCO).split("\n")))

    def test_saida_zero(self):
        self.assertEqual(self.codigo, 0, self.err)

    def test_cpf_e_trecho_do_bloco_nao_aparecem_em_commit_nenhum(self):
        depois = log_completo(self.espelho)
        self.assertNotIn(CPF_A, depois)
        self.assertNotIn(TRECHO_BLOCO, depois)
        self.assertIn(M, depois)

    def test_email_pessoal_trocado_em_commits_e_tags(self):
        self.assertNotIn(EMAIL_PESSOAL, log_completo(self.espelho))
        tags = git(self.espelho, "for-each-ref", "--format=%(taggeremail)", "refs/tags")
        self.assertNotIn(EMAIL_PESSOAL, tags)
        self.assertIn(EMAIL_NOREPLY, git(self.espelho, "log", "--all", "--format=%ae %ce"))

    def test_commits_anteriores_mantem_o_sha(self):
        self.assertEqual(self.mapa[self.r1], self.r1)
        self.assertEqual(self.mapa[self.r2], self.r2)
        self.assertNotEqual(self.mapa[self.j1], self.j1)
        self.assertEqual(self.rel["primeiro_commit_alterado"], {"antigo": self.j1, "novo": self.mapa[self.j1]})

    def test_arvore_da_ponta_igual(self):
        self.assertEqual(git(self.orig, "rev-parse", "fase-5^{tree}"), git(self.espelho, "rev-parse", "main^{tree}"))

    def test_tags_reescritas(self):
        self.assertEqual(git(self.espelho, "rev-parse", "v1.0.0"), git(self.orig, "rev-parse", "v1.0.0"))
        self.assertEqual(git(self.espelho, "rev-parse", "v1.1.0^{commit}"), self.mapa[self.r3])
        self.assertNotEqual(git(self.espelho, "rev-parse", "v1.1.0"), git(self.orig, "rev-parse", "v1.1.0"))

    def test_sem_refs_de_replace(self):
        self.assertEqual(git(self.espelho, "for-each-ref", "refs/replace"), "")

    def test_merge_continua_merge(self):
        self.assertEqual(len(git(self.espelho, "rev-list", "--parents", "-n1", self.mapa[self.merge]).split()), 3)

    def test_relatorio_so_com_contagens_e_shas(self):
        r = self.rel
        self.assertEqual(r["blobs_no_mapa"], 2)
        self.assertEqual(r["blobs_trocados"], 2)
        self.assertEqual(r["blobs_do_mapa_nunca_vistos"], [])
        self.assertEqual(r["blobs_sem_troca_efetiva"], [])
        self.assertEqual(r["commits_reescritos"], 4)  # j1, merge, j2, r3
        self.assertEqual(r["commits_total"], 7)
        bruto = json.dumps(r) + self.out
        for segredo in (CPF_A, EMAIL_PESSOAL, TRECHO_BLOCO):
            self.assertNotIn(segredo, bruto)
        for nome in ("commit-map", "ref-map"):
            self.assertTrue(os.path.isfile(os.path.join(self.saida, nome)))

    def test_conferidor_passa(self):
        codigo, out, err = rodar(cr, ["--antes", self.orig, "--ref-antes", "fase-5", "--depois", self.espelho,
                                      "--commit-map", os.path.join(self.saida, "commit-map")])
        self.assertEqual(codigo, 0, out + err)
        self.assertIn("RESULTADO: PASSOU", out)

    def test_conferidor_falha_se_a_ponta_mudar(self):
        codigo, out, _ = rodar(cr, ["--antes", self.orig, "--ref-antes", "fase-5~1", "--depois", self.espelho,
                                    "--commit-map", os.path.join(self.saida, "commit-map")])
        self.assertEqual(codigo, 1, out)
        self.assertIn("[FALHOU] a.", out)


@unittest.skipUnless(TEM_FILTER_REPO, "git_filter_repo não instalado")
class ConferidorDetectaTest(Cenario, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.montar()

    @classmethod
    def tearDownClass(cls):
        cls.desmontar()

    def test_espelho_sem_reescrita_falha_no_email(self):
        espelho = criar_espelho(self.raiz, self.orig, "intacto.git")
        shas = git(self.orig, "rev-list", "fase-5").split("\n")
        mapa = escrever(os.path.join(self.raiz, "identidade"), "old new\n" + "".join("%s %s\n" % (s, s) for s in shas))
        codigo, out, _ = rodar(cr, ["--antes", self.orig, "--ref-antes", "fase-5", "--depois", espelho,
                                    "--commit-map", mapa])
        self.assertEqual(codigo, 1, out)
        self.assertIn("[FALHOU] e.", out)
        self.assertIn("[ok] a.", out)
        self.assertNotIn(EMAIL_PESSOAL, out)

    def test_mudar_normas_falha_em_a_c_e_d(self):
        espelho = criar_espelho(self.raiz, self.orig, "adulterado.git")
        blob = git(self.orig, "rev-parse", "fase-5:" + NORMA)
        rh.rodar_filter_repo(espelho, {blob: b"# Norma A\nArt. 1o adulterado.\n"}, self.mailmap)
        mapa = os.path.join(espelho, "filter-repo", "commit-map")
        codigo, out, _ = rodar(cr, ["--antes", self.orig, "--ref-antes", "fase-5", "--depois", espelho,
                                    "--commit-map", mapa])
        self.assertEqual(codigo, 1, out)
        for letra in "acd":
            self.assertIn("[FALHOU] %s." % letra, out)

    def test_mudar_fora_dos_julgados_falha_em_d(self):
        espelho = criar_espelho(self.raiz, self.orig, "fora.git")
        blob = git(self.orig, "rev-parse", "fase-5:" + LATERAL)
        rh.rodar_filter_repo(espelho, {blob: b"adulterado\n"}, self.mailmap)
        mapa = os.path.join(espelho, "filter-repo", "commit-map")
        codigo, out, _ = rodar(cr, ["--antes", self.orig, "--ref-antes", "fase-5", "--depois", espelho,
                                    "--commit-map", mapa])
        self.assertEqual(codigo, 1, out)
        self.assertIn("[FALHOU] d.", out)
        self.assertNotIn("[FALHOU] c.", out)

    def test_tag_que_nao_existe_falha_em_f(self):
        espelho = criar_espelho(self.raiz, self.orig, "semtag.git")
        git(espelho, "tag", "-d", "v1.0.0")
        shas = git(self.orig, "rev-list", "fase-5").split("\n")
        mapa = escrever(os.path.join(self.raiz, "identidade2"), "old new\n" + "".join("%s %s\n" % (s, s) for s in shas))
        codigo, out, _ = rodar(cr, ["--antes", self.orig, "--ref-antes", "fase-5", "--depois", espelho,
                                    "--commit-map", mapa])
        self.assertEqual(codigo, 1, out)
        self.assertIn("[FALHOU] f.", out)

    def test_erro_de_execucao_e_2(self):
        codigo, _, err = rodar(cr, ["--antes", self.orig, "--ref-antes", "fase-5", "--depois", self.raiz + "/nao",
                                    "--commit-map", self.mailmap])
        self.assertEqual(codigo, 2, err)


class RecusasTest(unittest.TestCase):
    """Não dependem do filter-repo: a recusa vem antes de qualquer reescrita."""

    @classmethod
    def setUpClass(cls):
        cls.raiz = tempfile.mkdtemp()
        cls.orig = os.path.join(cls.raiz, "orig")
        os.makedirs(cls.orig)
        git(cls.orig, "init", "-q", "-b", "fase-5")
        commitar(cls.orig, {"a.md": "a\n"}, "um", "2024-01-01T10:00:00 -0300")
        cls.achados = escrever(os.path.join(cls.raiz, "achados.jsonl"), "")
        cls.mailmap = escrever(os.path.join(cls.raiz, "mailmap"), "")
        cls.saida = os.path.join(cls.raiz, "saida")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.raiz, ignore_errors=True)

    def reescrever(self, repo):
        return rodar(rh, ["--repo", repo, "--achados", self.achados, "--mailmap", self.mailmap,
                          "--saida", self.saida])

    def espelho(self, nome):
        return criar_espelho(self.raiz, self.orig, nome)

    def test_repo_nao_bare(self):
        destino = os.path.join(self.raiz, "dados", "fase-5", "espelho", "nao-bare")
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        git(self.raiz, "clone", "-q", "-b", "fase-5", self.orig, destino)
        git(destino, "branch", "-m", "main")
        git(destino, "remote", "remove", "origin")
        codigo, _, err = self.reescrever(destino)
        self.assertEqual(codigo, 2)
        self.assertIn("bare", err)

    def test_caminho_fora_de_dados_fase_5_espelho(self):
        fora = os.path.join(self.raiz, "outro", "e.git")
        os.makedirs(fora)
        git(fora, "init", "-q", "--bare", "-b", "main")
        git(fora, "fetch", "-q", self.orig, "fase-5:refs/heads/main")
        codigo, _, err = self.reescrever(fora)
        self.assertEqual(codigo, 2)
        self.assertIn("espelho", err)

    def test_repo_com_remote(self):
        e = self.espelho("com-remote.git")
        git(e, "remote", "add", "origin", self.orig)
        codigo, _, err = self.reescrever(e)
        self.assertEqual(codigo, 2)
        self.assertIn("remote", err)

    def test_ref_fora_de_main_e_tags(self):
        e = self.espelho("ref-extra.git")
        git(e, "update-ref", "refs/heads/outra", "refs/heads/main")
        codigo, _, err = self.reescrever(e)
        self.assertEqual(codigo, 2)
        self.assertIn("ref", err)

    def test_ref_de_pull(self):
        e = self.espelho("ref-pull.git")
        git(e, "update-ref", "refs/pull/1/head", "refs/heads/main")
        codigo, _, _ = self.reescrever(e)
        self.assertEqual(codigo, 2)

    def test_recusa_nao_altera_o_espelho(self):
        e = self.espelho("intacto.git")
        git(e, "remote", "add", "origin", self.orig)
        antes = git(e, "rev-parse", "main")
        self.reescrever(e)
        self.assertEqual(git(e, "rev-parse", "main"), antes)
        self.assertFalse(os.path.exists(self.saida) and os.path.exists(os.path.join(self.saida, "reescrita.json")))


class AplicarBlocosTest(unittest.TestCase):
    def achado(self, linhas, original, limpo, fora=None):
        a = {"linhas": linhas, "original": original, "limpo": limpo}
        if fora is not None:
            a["linhas_fora_da_base"] = fora
        return a

    def test_mesmo_numero_de_linhas_troca_so_as_fora_da_base(self):
        texto = "a\nb\nc\nd"
        a = self.achado([2, 3], "b\nc", "B\nC", fora=[3])
        self.assertEqual(rh.aplicar_blocos(texto, [a]), "a\nb\nC\nd")

    def test_numero_diferente_troca_o_bloco_inteiro(self):
        texto = "a\nb\nc\nd\n"
        a = self.achado([2, 3], "b\nc", "X", fora=[2])
        self.assertEqual(rh.aplicar_blocos(texto, [a]), "a\nX\nd\n")

    def test_blocos_do_fim_para_o_comeco(self):
        texto = "a\nb\nc\nd\ne"
        a1 = self.achado([1], "a", "A", fora=[1])
        a2 = self.achado([3, 4], "c\nd", "Z", fora=[3, 4])
        self.assertEqual(rh.aplicar_blocos(texto, [a1, a2]), "A\nb\nZ\ne")

    def test_bloco_que_nao_bate_falha(self):
        with self.assertRaises(rh.ErroReescrita):
            rh.aplicar_blocos("a\nb", [self.achado([2], "outro", "x", fora=[2])])

    def test_blocos_sobrepostos_falham(self):
        with self.assertRaises(rh.ErroReescrita):
            rh.aplicar_blocos("a\nb\nc", [self.achado([1, 2], "a\nb", "x", fora=[1]),
                                          self.achado([2, 3], "b\nc", "y", fora=[2])])

    def test_crlf_e_preservado_nas_linhas_nao_trocadas(self):
        texto = "a\r\nb\r\nc\r\n"
        a = self.achado([2], "b\r", "B\r", fora=[2])
        self.assertEqual(rh.aplicar_blocos(texto, [a]), "a\r\nB\r\nc\r\n")


class SelecaoTest(unittest.TestCase):
    def achado(self, regra, caminhos, blob="a" * 40, tipo="blob"):
        return {"tipo": tipo, "regra": regra, "blob": blob, "caminhos": caminhos, "linhas": [1],
                "original": "x", "limpo": "y"}

    def test_so_pii_em_julgados(self):
        j, n = "plugins/julgados-cvm/julgados/a.md", "plugins/normas/atos/a.md"
        por_blob, ign = rh.selecionar([
            self.achado("pii-cpf", [j], blob="1" * 40),
            self.achado("pii-multipla", [j], blob="2" * 40),
            self.achado("pii-cpf", [n], blob="3" * 40),
            self.achado("termo", [j], blob="4" * 40),
            self.achado("cpf-direto", [j], blob="5" * 40),
            self.achado("controle", [n], blob="6" * 40),
            self.achado("email-metadado", [], tipo="commit"),
            self.achado("msg-pii", [], tipo="mensagem"),
        ])
        self.assertEqual(sorted(por_blob), ["1" * 40, "2" * 40])
        self.assertEqual(ign["pii-fora-dos-julgados"], 1)
        self.assertEqual(ign["termo"], 1)
        self.assertEqual(ign["metadado"], 2)

    def test_blob_misto_e_erro(self):
        with self.assertRaises(rh.ErroReescrita):
            rh.selecionar([self.achado("pii-cpf", ["plugins/julgados-cvm/julgados/a.md", "plugins/normas/atos/a.md"])])


if __name__ == "__main__":
    unittest.main()
