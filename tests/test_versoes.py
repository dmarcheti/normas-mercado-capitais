"""Versões dos plugins no repo (Fase 4, C10): manifestos iguais, versão que não desce em relação
à última tag e registro de `fontes/versoes-plugins.json` coerente com o conteúdo."""
import json
import os
import re
import shutil
import subprocess
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import publicar as pub  # noqa: E402

REPO = pub.REPO


def _ler(c):
    with open(c, encoding="utf-8") as f:
        return json.load(f)


def _git(*args):
    r = subprocess.run(["git"] + list(args), cwd=REPO, capture_output=True, text=True)
    return r.returncode, r.stdout


def _em_repo_git():
    return shutil.which("git") is not None and os.path.exists(os.path.join(REPO, ".git")) \
        and _git("rev-parse", "--is-inside-work-tree")[1].strip() == "true"


def _hash_estrito():
    """O hash precisa bater exatamente no commit do `publicar` (PR auto/publicar-*) ou quando o
    próprio job pede; entre uma segunda e outra, o merge diário muda o conteúdo sem mudar a versão."""
    return os.environ.get("NORMAS_VERIFICAR_HASH") == "1" or \
        os.environ.get("GITHUB_HEAD_REF", "").startswith("auto/publicar-")


class TestVersoes(unittest.TestCase):
    def setUp(self):
        self.plugins = pub.plugins_do_marketplace(REPO)

    def test_versao_igual_nos_dois_manifestos(self):
        self.assertTrue(self.plugins)
        for nome, pasta, v_mk in self.plugins:
            self.assertEqual(pub.versao_do_plugin(pasta), v_mk, nome)
            self.assertRegex(v_mk, r"^\d+\.\d+\.\d+$", nome)

    def test_versao_nao_desce_em_relacao_a_ultima_tag(self):
        if not _em_repo_git():
            self.skipTest("fora de um repositório git")
        rc, out = _git("tag", "--list", "v*", "--sort=-v:refname")
        tags = [t for t in out.split() if re.fullmatch(r"v\d+\.\d+\.\d+", t)]
        if rc != 0 or not tags:
            self.skipTest("sem tag semver")
        for nome, pasta, v in self.plugins:
            rel = os.path.relpath(os.path.join(pasta, ".claude-plugin", "plugin.json"), REPO).replace(os.sep, "/")
            rc, out = _git("show", "%s:%s" % (tags[0], rel))
            if rc != 0:
                continue  # plugin que não existia na tag
            antes = json.loads(out)["version"]
            self.assertGreaterEqual(pub.chave_versao(v), pub.chave_versao(antes), "%s desceu de %s" % (nome, antes))

    def test_registro_acompanha_a_versao_atual(self):
        cam = os.path.join(REPO, pub.REGISTRO)
        if not os.path.exists(cam):
            self.skipTest("sem registro de versões")
        reg = _ler(cam).get("plugins", {})
        for nome, pasta, v in self.plugins:
            self.assertIn(nome, reg, "plugin sem registro: rode scripts/publicar.py")
            self.assertEqual(reg[nome]["versao"], v, "%s: versão subiu sem o publicar gravar o hash" % nome)
            self.assertRegex(reg[nome]["hash"], r"^[0-9a-f]{64}$")

    def test_hash_bate_no_commit_do_publicar(self):
        if not _hash_estrito():
            self.skipTest("hash estrito só no PR auto/publicar-* ou com NORMAS_VERIFICAR_HASH=1")
        self.assertEqual(pub.divergentes(REPO), [])


if __name__ == "__main__":
    unittest.main()
