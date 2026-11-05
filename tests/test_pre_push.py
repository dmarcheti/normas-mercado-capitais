"""Testes de scripts/pre_push.py e do hook .githooks/pre-push, com repos git descartáveis em pasta
temporária (sem rede, sem tocar no repo real)."""
import io
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(AQUI, "..")
sys.path.insert(0, os.path.join(RAIZ, "scripts"))

import pre_push  # noqa: E402

ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
           GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid",
           GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull, GIT_CONFIG_NOSYSTEM="1")
ZERO = "0" * 40


def git(cwd, *args, check=True):
    p = subprocess.run(["git", "-C", cwd] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True, env=ENV)
    if check and p.returncode != 0:
        raise AssertionError("git %s: %s" % (args, p.stderr))
    return p


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pre-push-teste-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        git(self.repo, "init", "-q", "-b", "main")
        self.antigo = self.commit("antigo")      # histórico antigo
        self.novo_main = self.commit("depois do antigo")
        git(self.repo, "checkout", "-q", "--orphan", "limpo")
        self.limpo = self.commit("raiz nova")     # sem o antigo como ancestral
        self.lista = os.path.join(self.tmp, "historico.txt")

    def commit(self, msg):
        arq = os.path.join(self.repo, "a.txt")
        with open(arq, "a") as f:
            f.write(msg + "\n")
        git(self.repo, "add", "a.txt")
        git(self.repo, "commit", "-q", "-m", msg)
        return git(self.repo, "rev-parse", "HEAD").stdout.strip()

    def escrever_lista(self, *linhas):
        with open(self.lista, "w") as f:
            f.write("\n".join(linhas) + "\n")

    def config(self, valor=None):
        git(self.repo, "config", "normas.historicoAntigo", valor or self.lista)

    def rodar(self, *refs):
        entrada = "".join("%s %s refs/heads/x %s\n" % (r, s, ZERO) for r, s in refs)
        err = io.StringIO()
        rc = pre_push.main(entrada, cwd=self.repo, err=err)
        return rc, err.getvalue()


class TestPrePush(Base):
    def test_ancestral_proibido_recusa(self):
        self.escrever_lista("# histórico antigo", self.antigo + "  # primeiro commit")
        self.config()
        rc, err = self.rodar(("refs/heads/main", self.novo_main))
        self.assertEqual(rc, 1)
        self.assertIn("RECUSADO", err)
        self.assertIn(self.antigo[:12], err)

    def test_proprio_commit_da_lista_recusa(self):
        self.escrever_lista(self.antigo)
        self.config()
        rc, _ = self.rodar(("refs/heads/main", self.antigo))
        self.assertEqual(rc, 1)

    def test_sem_ancestral_passa(self):
        self.escrever_lista(self.antigo)
        self.config()
        rc, err = self.rodar(("refs/heads/limpo", self.limpo))
        self.assertEqual((rc, err), (0, ""))

    def test_uma_ref_ruim_entre_varias_recusa(self):
        self.escrever_lista(self.antigo)
        self.config()
        rc, _ = self.rodar(("refs/heads/limpo", self.limpo), ("refs/heads/main", self.novo_main))
        self.assertEqual(rc, 1)

    def test_config_ausente_passa_com_aviso(self):
        rc, err = self.rodar(("refs/heads/main", self.novo_main))
        self.assertEqual(rc, 0)
        self.assertIn("não configurado", err)

    def test_arquivo_ausente_recusa(self):
        self.config(os.path.join(self.tmp, "nao-existe.txt"))
        rc, err = self.rodar(("refs/heads/limpo", self.limpo))
        self.assertEqual(rc, 1)
        self.assertIn("RECUSADO", err)

    def test_arquivo_ilegivel_recusa(self):
        self.escrever_lista(self.antigo)
        self.config()
        os.chmod(self.lista, 0)
        self.addCleanup(os.chmod, self.lista, stat.S_IRUSR | stat.S_IWUSR)
        if os.access(self.lista, os.R_OK):
            self.skipTest("o usuário lê arquivo sem permissão (root)")
        rc, _ = self.rodar(("refs/heads/limpo", self.limpo))
        self.assertEqual(rc, 1)

    def test_caminho_que_e_pasta_recusa(self):
        self.config(self.tmp)
        rc, _ = self.rodar(("refs/heads/limpo", self.limpo))
        self.assertEqual(rc, 1)

    def test_linha_que_nao_e_sha_recusa(self):
        self.escrever_lista(self.antigo, "abc123")
        self.config()
        rc, err = self.rodar(("refs/heads/limpo", self.limpo))
        self.assertEqual(rc, 1)
        self.assertIn("inválida", err)

    def test_sha_inexistente_no_repo_e_ignorado(self):
        self.escrever_lista("1" * 40, "# comentário", "", "2" * 40)
        self.config()
        rc, err = self.rodar(("refs/heads/main", self.novo_main))
        self.assertEqual((rc, err), (0, ""))

    def test_sha_inexistente_nao_esconde_o_existente(self):
        self.escrever_lista("1" * 40, self.antigo)
        self.config()
        rc, _ = self.rodar(("refs/heads/main", self.novo_main))
        self.assertEqual(rc, 1)

    def test_lista_vazia_passa(self):
        self.escrever_lista("# nada")
        self.config()
        rc, _ = self.rodar(("refs/heads/main", self.novo_main))
        self.assertEqual(rc, 0)

    def test_delecao_de_ref_passa(self):
        self.escrever_lista(self.antigo)
        self.config()
        rc, _ = self.rodar(("(delete)", ZERO))
        self.assertEqual(rc, 0)

    def test_sha_local_inexistente_e_erro_e_recusa(self):
        self.escrever_lista(self.antigo)
        self.config()
        rc, err = self.rodar(("refs/heads/x", "3" * 40))
        self.assertEqual(rc, 1)
        self.assertIn("RECUSADO", err)

    def test_entrada_vazia_passa(self):
        self.escrever_lista(self.antigo)
        self.config()
        rc, _ = self.rodar()
        self.assertEqual(rc, 0)


class TestHookDePonta(Base):
    """Push de verdade para um remoto local, com o hook real chamando o script real."""

    def setUp(self):
        super().setUp()
        self.remoto = os.path.join(self.tmp, "remoto.git")
        subprocess.run(["git", "init", "-q", "--bare", self.remoto], check=True, env=ENV)
        hooks = os.path.join(self.tmp, "hooks")
        os.makedirs(hooks)
        modelo = os.path.join(RAIZ, ".githooks", "pre-push")
        with open(modelo) as f:
            self.assertIn("pre_push.py", f.read())
        self.assertTrue(os.access(modelo, os.X_OK))
        # o hook do repo procura scripts/pre_push.py na raiz do repo de trabalho: copia as duas peças
        os.makedirs(os.path.join(self.repo, "scripts"))
        shutil.copy(os.path.join(RAIZ, "scripts", "pre_push.py"), os.path.join(self.repo, "scripts"))
        os.makedirs(os.path.join(self.repo, ".githooks"))
        shutil.copy(modelo, os.path.join(self.repo, ".githooks", "pre-push"))
        git(self.repo, "config", "core.hooksPath", ".githooks")
        git(self.repo, "remote", "add", "origin", self.remoto)

    def test_push_recusado_e_liberado(self):
        self.escrever_lista(self.antigo)
        self.config()
        p = git(self.repo, "push", "origin", "main", check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("RECUSADO", p.stderr)
        self.assertEqual(git(self.remoto, "branch", "--list").stdout.strip(), "")
        p = git(self.repo, "push", "origin", "limpo", check=False)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("limpo", git(self.remoto, "branch", "--list").stdout)

    def test_sem_config_o_push_passa_com_aviso(self):
        p = git(self.repo, "push", "origin", "main", check=False)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("não configurado", p.stderr)


if __name__ == "__main__":
    unittest.main()
