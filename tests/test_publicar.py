"""Testes de scripts/publicar.py, scripts/vigia.py (cálculo do hash e prazos), scripts/varrer_pr.py
e da linha "Fontes conferidas até" do indice.py. Repo mínimo em pasta temporária, sem git real."""
import json
import os
import shutil
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import indice  # noqa: E402
import publicar as pub  # noqa: E402
import varrer_pr  # noqa: E402
import vigia  # noqa: E402

CPF_FICTICIO = "529.982." + "247-25"  # por concatenação, para não haver CPF literal no repo


def _gravar(caminho, texto):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)


def _ler(caminho):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


class Base(unittest.TestCase):
    def setUp(self):
        self.raiz = tempfile.mkdtemp()
        mk = {"name": "x", "plugins": [
            {"name": "normas", "source": "./plugins/normas", "version": "1.1.1"},
            {"name": "julgados-pas", "source": "./plugins/julgados-pas", "version": "0.5.0"}]}
        _gravar(os.path.join(self.raiz, ".claude-plugin", "marketplace.json"), json.dumps(mk))
        for nome, v in (("normas", "1.1.1"), ("julgados-pas", "0.5.0")):
            _gravar(os.path.join(self.raiz, "plugins", nome, ".claude-plugin", "plugin.json"),
                    json.dumps({"name": nome, "version": v}))
        _gravar(self.p("plugins", "normas", "normas", "indice.md"), "# Índice\n" + indice.GERADO + "\n")
        _gravar(self.p("plugins", "normas", "normas", "normas.json"), json.dumps([{"id": "a"}, {"id": "b"}]))
        _gravar(self.p("plugins", "normas", "normas", "cvm", "a.md"), "texto a\n")
        _gravar(self.p("plugins", "julgados-pas", "julgados", "indice.md"), "# Índice\n")
        _gravar(self.p("plugins", "julgados-pas", "julgados", "pas", "2026", "p1.md"), "pas 1\n")
        _gravar(self.p("CHANGELOG.md"), "# Histórico de versões\n\n## v1.1.1 (2026-11-04)\n\n- x\n")
        os.makedirs(self.p("fontes"))
        pub.registrar(self.raiz, "2026-11-04")
        self.indices = []

    def tearDown(self):
        shutil.rmtree(self.raiz)

    def p(self, *partes):
        return os.path.join(self.raiz, *partes)

    def publicar(self, hoje="2026-11-09"):
        return pub.publicar(self.raiz, hoje, indice=lambda r: self.indices.append(r))


class TestHash(Base):
    def test_hash_ignora_versao_e_linha_conferido(self):
        pasta = self.p("plugins", "normas")
        h = pub.hash_plugin(pasta)
        _gravar(os.path.join(pasta, ".claude-plugin", "plugin.json"), json.dumps({"version": "9.9.9"}))
        _gravar(os.path.join(pasta, "normas", "indice.md"),
                "# Índice\n" + indice.GERADO + "\nFontes conferidas até 2026-11-09.\n")
        self.assertEqual(pub.hash_plugin(pasta), h)
        _gravar(os.path.join(pasta, "normas", "cvm", "a.md"), "texto a, alterado\n")
        self.assertNotEqual(pub.hash_plugin(pasta), h)

    def test_hash_inclui_o_nome_do_arquivo(self):
        pasta = self.p("plugins", "julgados-pas")
        h = pub.hash_plugin(pasta)
        os.rename(os.path.join(pasta, "julgados", "pas", "2026", "p1.md"),
                  os.path.join(pasta, "julgados", "pas", "2026", "p2.md"))
        self.assertNotEqual(pub.hash_plugin(pasta), h)


class TestPublicar(Base):
    def test_sem_mudanca_nao_sobe_mas_grava_conferido(self):
        self.assertEqual(self.publicar(), [])
        reg = _ler(self.p("fontes", "versoes-plugins.json"))
        self.assertEqual(reg["conferido_em"], "2026-11-09")
        self.assertEqual(self.indices, [self.raiz])
        with open(self.p("CHANGELOG.md"), encoding="utf-8") as f:
            self.assertNotIn("Dados até", f.read())

    def test_so_o_plugin_mudado_sobe_nos_dois_manifestos(self):
        _gravar(self.p("plugins", "julgados-pas", "julgados", "pas", "2026", "p2.md"), "pas 2\n")
        self.assertEqual(self.publicar(), [("julgados-pas", "0.5.1")])
        mk = {p["name"]: p["version"] for p in _ler(self.p(".claude-plugin", "marketplace.json"))["plugins"]}
        self.assertEqual(mk, {"normas": "1.1.1", "julgados-pas": "0.5.1"})
        self.assertEqual(_ler(self.p("plugins", "julgados-pas", ".claude-plugin", "plugin.json"))["version"], "0.5.1")
        self.assertEqual(_ler(self.p("plugins", "normas", ".claude-plugin", "plugin.json"))["version"], "1.1.1")
        reg = _ler(self.p("fontes", "versoes-plugins.json"))["plugins"]
        self.assertEqual(reg["julgados-pas"]["versao"], "0.5.1")
        self.assertEqual(reg["julgados-pas"]["hash"], pub.hash_plugin(self.p("plugins", "julgados-pas")))
        self.assertEqual(reg["normas"]["versao"], "1.1.1")
        self.assertEqual(pub.divergentes(self.raiz), [])
        with open(self.p("CHANGELOG.md"), encoding="utf-8") as f:
            txt = f.read()
        self.assertIn("- Dados até 2026-11-09: 2 atos, 2 julgados.", txt)
        self.assertLess(txt.index("Dados até"), txt.index("## v1.1.1"))

    def test_manifestos_divergentes_param(self):
        _gravar(self.p("plugins", "normas", ".claude-plugin", "plugin.json"), json.dumps({"version": "1.1.2"}))
        with self.assertRaises(RuntimeError):
            self.publicar()

    def test_sobe_patch(self):
        self.assertEqual(pub.sobe_patch("1.1.9"), "1.1.10")
        with self.assertRaises(ValueError):
            pub.sobe_patch("1.1")


class TestVigia(Base):
    def git_falso(self, base_data="2026-11-01", primeiro=None):
        def git(raiz, *args):
            if args[:2] == ("log", "-1") and args[2] == "--format=%H":
                return "abc123\n"
            if args[:2] == ("log", "--reverse"):
                return (primeiro + "\n") if primeiro else ""
            if args[:2] == ("log", "-1") and args[2] == "--format=%cs":
                return base_data + "\n"
            return ""
        return git

    def test_tudo_em_dia(self):
        self.assertEqual(vigia.problemas(self.raiz, "2026-11-05", "2026-11-04T07:00:00-03:00",
                                         git=self.git_falso()), [])

    def test_heartbeat_velho_ou_ausente(self):
        t = [x[0] for x in vigia.problemas(self.raiz, "2026-11-09", "2026-11-05T07:00:00-03:00", git=self.git_falso())]
        self.assertEqual(t, ["vigia: heartbeat parado"])
        t = [x[0] for x in vigia.problemas(self.raiz, "2026-11-09", "", git=self.git_falso())]
        self.assertEqual(t, ["vigia: heartbeat ausente"])

    def test_conteudo_sem_versao_por_mais_de_8_dias(self):
        _gravar(self.p("plugins", "normas", "normas", "cvm", "b.md"), "novo\n")
        hb = "2026-11-20T07:00:00-03:00"
        t = [x[0] for x in vigia.problemas(self.raiz, "2026-11-20", hb, git=self.git_falso(primeiro="2026-11-15"))]
        self.assertEqual(t, [])  # 5 dias
        t = [x[0] for x in vigia.problemas(self.raiz, "2026-11-20", hb, git=self.git_falso(primeiro="2026-11-10"))]
        self.assertEqual(t, ["vigia: normas sem versão nova"])

    def test_falha_ao_abrir_issue_sai_com_mensagem(self):
        from unittest import mock
        import io
        import subprocess

        def run(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 1, "", "HTTP 403: Resource not accessible")
        saida = io.StringIO()
        with mock.patch.object(vigia, "problemas", return_value=[("vigia: heartbeat ausente", "x")]), \
                mock.patch.object(vigia.subprocess, "run", side_effect=run), mock.patch("sys.stdout", saida):
            rc = vigia.main(["--abrir", "--raiz", self.raiz])
        self.assertEqual(rc, 1)
        self.assertIn("não abriu a issue", saida.getvalue())
        self.assertIn("HTTP 403", saida.getvalue())


class TestVarrerPr(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def arq(self, nome, texto):
        c = os.path.join(self.tmp, nome)
        _gravar(c, texto)
        return c

    def test_cpf_rg_e_controle(self):
        a = self.arq("a.md", "linha 1\nCPF " + CPF_FICTICIO + "\n")
        b = self.arq("b.json", '{"x": "a\\u0000b"}')
        e = self.arq("e.md", "glifo O\x01cios\n")
        c = self.arq("c.md", "texto limpo, sem dado pessoal\n")
        achados = varrer_pr.varrer_arquivos([a, b, c, os.path.join(self.tmp, "apagado.md"), self.arq("d.py", "x")])
        self.assertTrue(any(x.startswith(a + ": CPF na linha 2") for x in achados))
        achados += varrer_pr.varrer_arquivos([e])
        self.assertTrue(any(x.startswith(e + ": caractere de controle U+0001 na linha 1") for x in achados))
        self.assertTrue(any(x.startswith(b + ": caractere de controle U+0000") for x in achados))
        self.assertFalse(any(x.startswith(c) for x in achados))
        self.assertFalse(any(CPF_FICTICIO in x for x in achados))
        self.assertEqual(varrer_pr.main([c]), 0)
        self.assertEqual(varrer_pr.main([a]), 1)


class TestIndiceConferido(unittest.TestCase):
    def test_linha_depois_de_gerado(self):
        arqs = {"indice.md": "# Índice\n\n" + indice.GERADO + "\n\n## Perímetro\n"}
        indice.com_conferido(arqs, "2026-11-09")
        self.assertIn(indice.GERADO + "\nFontes conferidas até 2026-11-09.\n\n## Perímetro", arqs["indice.md"])

    def test_sem_campo_nada_muda(self):
        tmp = tempfile.mkdtemp()
        try:
            c = os.path.join(tmp, "v.json")
            _gravar(c, json.dumps({"plugins": {}}))
            self.assertIsNone(indice.ler_conferido(c))
            self.assertIsNone(indice.ler_conferido(os.path.join(tmp, "nao-existe.json")))
            _gravar(c, json.dumps({"conferido_em": "2026-11-09"}))
            self.assertEqual(indice.ler_conferido(c), "2026-11-09")
        finally:
            shutil.rmtree(tmp)
        arqs = {"indice.md": "x\n" + indice.GERADO + "\n"}
        self.assertEqual(indice.com_conferido(dict(arqs), None), arqs)


if __name__ == "__main__":
    unittest.main()
