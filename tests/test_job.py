"""Testes de scripts/job.py: git, gh, security, claude e os scripts são simulados (sem rede, sem
macOS e sem processo real). O worktree é uma pasta temporária com `.git` falso."""
import datetime
import io
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import job  # noqa: E402

HOJE = "2026-11-04"  # quarta-feira
QUINTA = "2026-11-05"
RAIZ = os.path.normpath(os.path.join(AQUI, ".."))
AGENDA = {"ancora": "2026-11-18", "intervalo_dias": 14, "hora": 13}
EXEC = "20261104T070000-123"
SHA = "0123456789abcdef0123456789abcdef01234567"


def runs_ci(estado, sha=SHA):
    """Respostas simuladas da API do Actions para o head sha: (runs, jobs)."""
    if estado == "pendente":
        return {"workflow_runs": [{"id": 9, "path": job.CI_WORKFLOW, "event": "pull_request", "head_sha": sha,
                                   "status": "in_progress", "conclusion": None}]}, {"jobs": []}
    if estado == "so-push":  # run do evento push, verde, mas nenhum de pull_request
        return {"workflow_runs": [{"id": 8, "path": job.CI_WORKFLOW, "event": "push", "head_sha": sha,
                                   "status": "completed", "conclusion": "success"}]}, {"jobs": []}
    nomes = ["testes", "varredura", "gitleaks"]
    if estado == "sem-gitleaks":
        nomes.remove("gitleaks")
    conc = "failure" if estado == "vermelho" else "success"
    jobs = [{"name": n, "status": "completed", "conclusion": conc if n == "testes" else "success"} for n in nomes]
    return ({"workflow_runs": [{"id": 10, "path": job.CI_WORKFLOW, "event": "pull_request", "head_sha": sha,
                                "status": "completed", "conclusion": conc}]}, {"jobs": jobs})


class Simulador:
    """Responde aos comandos por regra; grava cada chamada em `chamadas`."""

    def __init__(self, job_saida, token="SEGREDO-123", prs=(), det=None, crit=None, auto=(), diogo=(),
                 ci="verde", issues_abertas=(), exec_id=EXEC, atualizar_rc=0, commit_rc=0, remotos=(),
                 wt=None, clone=None, det_falha=False, issue_rc=0):
        self.saida = job_saida
        self.token, self.prs, self.ci = token, list(prs), ci
        self.remotos, self.wt, self.clone = list(remotos), wt, clone
        self.det = det or {"gerado_em": HOJE, "fontes": {"cvm": {"status": "ok"}}, "itens": []}
        self.crit = crit or {"execucao_id": EXEC, "conjunto": {"pr_automatico": False,
                                                               "pr_automatico_antes_do_ci": True}, "itens": []}
        self.auto, self.diogo = list(auto), list(diogo)
        self.issues_abertas = list(issues_abertas)
        self.exec_id, self.atualizar_rc, self.commit_rc = exec_id, atualizar_rc, commit_rc
        self.chamadas = []
        self.det_falha, self.issue_rc = det_falha, issue_rc
        self.staged = bool(self.auto)

    def __call__(self, cmd, cwd=None, env=None, timeout=None):
        self.chamadas.append((list(cmd), env or {}))
        c = cmd[0]
        if c == "security":
            return (0, self.token + "\n", "") if self.token else (44, "", "not found")
        if c == "claude":
            return 0, "ok", ""
        if c == "python3":
            return self.script(cmd[1], cmd[2:])
        if c == "git":
            return self.git(cmd[1:])
        if c == "gh":
            return self.gh(cmd[1:])
        return 0, "", ""

    def script(self, script, args):
        nome = os.path.basename(script)
        if nome == "detectar.py":
            os.makedirs(self.saida, exist_ok=True)
            if self.det_falha:  # detector que cai sem gravar
                return 2, "", "caiu"
            det = dict(self.det)
            if "execucao_id" not in det:
                det["execucao_id"] = args[args.index("--execucao-id") + 1]
            with open(os.path.join(self.saida, "deteccao.json"), "w") as f:
                json.dump(det, f)
            return 0, "", ""
        if nome == "atualizar.py":
            for n, d in (("criterio.json", self.crit),
                         ("itens-automaticos.json", {"execucao_id": EXEC, "itens": self.auto}),
                         ("itens-diogo.json", {"execucao_id": EXEC, "itens": self.diogo})):
                with open(os.path.join(self.saida, n), "w") as f:
                    json.dump(d, f)
            with open(os.path.join(self.saida, "resumo.md"), "w") as f:
                f.write("# Atualização\n\nExecução: `%s`.\n" % EXEC)
            return self.atualizar_rc, json.dumps({"execucao_id": self.exec_id}) + "\n", ""
        if nome == "teste_final.py":
            return 0, "ok", ""
        return 0, "", ""

    def git(self, a):
        if a[0] == "rev-parse":
            return 0, SHA + "\n", ""
        if a[0] == "ls-remote":
            padrao = a[-1].rstrip("*")
            return 0, "".join("abc\trefs/heads/%s\n" % r for r in self.remotos if r.startswith(padrao)), ""
        if a[0] == "clean" and self.wt and not ("-e" in a and a[a.index("-e") + 1] == "dados"):
            dados = os.path.join(self.wt, "dados")  # como o git: o .gitignore `dados/` não casa com link
            if os.path.islink(dados):
                os.remove(dados)
            return 0, "", ""
        if a[0] == "diff" and "--cached" in a:
            r = 1 if self.staged else 0
            return r, "", ""
        if a[0] == "commit":
            if self.commit_rc:
                return self.commit_rc, "", "Varredura bloqueou o commit"
            return 0, "", ""
        return 0, "", ""

    def gh(self, a):
        if a[:2] == ["pr", "list"]:
            return 0, json.dumps(self.prs), ""
        if a[:2] == ["pr", "create"]:
            return 0, "https://github.com/x/y/pull/7\n", ""
        if a[0] == "api":
            runs, jobs = runs_ci(self.ci)
            return 0, json.dumps(jobs if "/jobs" in a[1] else runs), ""
        if a[:2] == ["issue", "list"]:
            return 0, json.dumps([{"title": t} for t in self.issues_abertas]), ""
        if a[:2] == ["issue", "create"] and self.issue_rc:
            return self.issue_rc, "", "erro"
        return 0, "", ""

    # consultas
    def cmds(self, *prefixo):
        return [c for c, _ in self.chamadas if c[:len(prefixo)] == list(prefixo)]

    def gh_cmds(self, *prefixo):
        return [c for c, _ in self.chamadas if c[0] == "gh" and c[1:1 + len(prefixo)] == list(prefixo)]

    def variavel(self, nome):
        for c in self.gh_cmds("variable", "set", nome):
            return c[c.index("--body") + 1]
        return None


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.clone = os.path.join(self.tmp, "clone")
        self.wt = os.path.join(self.tmp, "wt")
        os.makedirs(os.path.join(self.clone, "dados"))
        os.makedirs(os.path.join(self.wt, "fontes"))
        os.makedirs(os.path.join(self.wt, "plugins"))
        open(os.path.join(self.wt, ".git"), "w").close()
        os.symlink(os.path.join(self.clone, "dados"), os.path.join(self.wt, "dados"))  # como o wrapper
        self.cfg({"sombra": True, "classes_automaticas": []})
        self.estado = os.path.join(self.tmp, "normas-auto", "estado.json")
        self.gravar_estado({})

    def gravar_estado(self, e):
        os.makedirs(os.path.dirname(self.estado), exist_ok=True)
        with open(self.estado, "w") as f:
            json.dump(e, f)

    def ler_estado(self):
        with open(self.estado) as f:
            return json.load(f)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def cfg(self, c):
        with open(os.path.join(self.wt, "fontes", "automacao.json"), "w") as f:
            json.dump(c, f)

    def rodar(self, hoje=HOJE, publicar=True, **kw):
        saida = os.path.join(self.wt, "dados", "auto", hoje)
        sim = Simulador(saida, wt=self.wt, clone=self.clone, **kw)
        j = job.Job(self.clone, self.wt, hoje, rodar=sim, ambiente={"PATH": "/bin"},
                    dormir=lambda s: None, agora=lambda: "2026-11-04T07:00:00-03:00", log=lambda m: None,
                    estado=self.estado, publicar=publicar)
        rc = j.executar()
        return rc, sim, j


AUTO_H = {"id": "bcb-res-102", "chave": "bcb-res-102|H|bcb-res-102", "classe": "H", "estado": "automatico",
          "arquivos": ["plugins/normas/normas/bcb/x.md"]}


class TestTrava(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cam = os.path.join(self.tmp, "sub", "job.pid")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_outra_execucao_viva_recusa(self):
        self.assertTrue(job.Trava(self.cam, pid=100, vivo=lambda p: True).tomar())
        self.assertFalse(job.Trava(self.cam, pid=200, vivo=lambda p: True).tomar())

    def test_trava_de_pid_morto_e_retomada(self):
        job.Trava(self.cam, pid=100, vivo=lambda p: True).tomar()
        t = job.Trava(self.cam, pid=200, vivo=lambda p: False)
        self.assertTrue(t.tomar())
        with open(self.cam) as f:
            self.assertEqual(f.read().strip(), "200")

    def test_soltar_so_a_propria(self):
        job.Trava(self.cam, pid=100, vivo=lambda p: True).tomar()
        job.Trava(self.cam, pid=200, vivo=lambda p: True).soltar()
        self.assertTrue(os.path.exists(self.cam))
        job.Trava(self.cam, pid=100, vivo=lambda p: True).soltar()
        self.assertFalse(os.path.exists(self.cam))

    def test_main_sai_com_3_se_travado(self):
        os.makedirs(os.path.dirname(self.cam))
        with open(self.cam, "w") as f:
            f.write("%d\n" % os.getppid())
        with mock.patch.object(job, "processo_do_job", return_value=True):
            self.assertEqual(job.main(["--trava", self.cam, "--hoje", HOJE]), 3)

    def test_pid_vivo_que_nao_e_o_job_nao_trava(self):
        os.makedirs(os.path.dirname(self.cam))
        with open(self.cam, "w") as f:
            f.write("%d\n" % os.getppid())  # vivo (o pai deste processo)
        import subprocess
        cmd = {"v": "/bin/zsh -l\n"}
        ps = lambda c, **kw: subprocess.CompletedProcess(c, 0, cmd["v"], "")  # noqa: E731
        with mock.patch.object(job.subprocess, "run", side_effect=ps):
            cmd["v"] = "caffeinate -i python3 /x/worktree/scripts/job.py --clone /x\n"
            self.assertFalse(job.Trava(self.cam, pid=200).tomar())
            cmd["v"] = "/bin/zsh -l\n"  # PID reaproveitado por outro processo
            self.assertTrue(job.Trava(self.cam, pid=200).tomar())

    def test_trava_atomica_o_excl(self):
        reais = []
        orig = os.open

        def abrir(caminho, flags, *a):
            reais.append(flags)
            return orig(caminho, flags, *a)
        with mock.patch.object(job.os, "open", side_effect=abrir):
            self.assertTrue(job.Trava(self.cam, pid=100, vivo=lambda p: True).tomar())
        self.assertTrue(all(f & os.O_CREAT and f & os.O_EXCL for f in reais) and reais)

    def test_herda_a_trava_do_wrapper_pai(self):
        job.Trava(self.cam, pid=50, vivo=lambda p: True).tomar()  # o wrapper (pid 50)
        self.assertFalse(job.Trava(self.cam, pid=200, vivo=lambda p: True, herdar=50, ppid=51).tomar())
        t = job.Trava(self.cam, pid=200, vivo=lambda p: True, herdar=50, ppid=50)
        self.assertTrue(t.tomar())
        with open(self.cam) as f:
            self.assertEqual(f.read().strip(), "200")

    def test_main_recusa_rodar_fora_do_worktree(self):
        wt = os.path.join(self.tmp, "wt")
        rc = job.main(["--trava", self.cam, "--hoje", HOJE, "--worktree", wt, "--clone", self.tmp])
        self.assertEqual(rc, 1)
        self.assertFalse(os.path.exists(self.cam))  # a trava foi solta


class TestPodeMerge(unittest.TestCase):
    CRIT = {"conjunto": {"pr_automatico_antes_do_ci": True}}

    def test_tudo_ok(self):
        self.assertTrue(job.pode_merge(self.CRIT, ["H"], {"sombra": False, "classes_automaticas": ["H"]}, True)[0])

    def test_sombra_nunca(self):
        self.assertFalse(job.pode_merge(self.CRIT, ["H"], {"sombra": True, "classes_automaticas": ["H"]}, True)[0])

    def test_sem_campo_sombra_conta_como_sombra(self):
        self.assertFalse(job.pode_merge(self.CRIT, ["H"], {"classes_automaticas": ["H"]}, True)[0])

    def test_classe_fora(self):
        self.assertFalse(job.pode_merge(self.CRIT, ["H", "J"], {"sombra": False, "classes_automaticas": ["H"]}, True)[0])

    def test_ci_vermelho(self):
        self.assertFalse(job.pode_merge(self.CRIT, ["H"], {"sombra": False, "classes_automaticas": ["H"]}, False)[0])

    def test_criterio_antes_do_ci_falso(self):
        crit = {"conjunto": {"pr_automatico_antes_do_ci": False}}
        self.assertFalse(job.pode_merge(crit, ["H"], {"sombra": False, "classes_automaticas": ["H"]}, True)[0])


class TestJob(Base):
    def test_sem_token_para_antes_do_push(self):
        det = {"fontes": {"cvm": {"status": "falha"}}, "itens": []}
        rc, sim, j = self.rodar(token=None, auto=[AUTO_H], det=det)
        self.assertEqual(rc, 0)
        self.assertEqual(sim.cmds("git", "-c"), [])  # push
        gh = [(c, e) for c, e in sim.chamadas if c[0] == "gh"]
        self.assertTrue(gh)
        # pela sessão do gh: só o heartbeat e a issue fonte-mudou
        self.assertTrue(all(c[1:3] == ["variable", "set"] or c[1] in ("issue", "label") for c, _ in gh), gh)
        self.assertTrue(all("GH_TOKEN" not in e for _, e in gh))
        self.assertEqual(sim.gh_cmds("pr", "list"), [])
        titulos = [c[c.index("--title") + 1] for c in sim.gh_cmds("issue", "create")]
        self.assertEqual(titulos, ["fonte-mudou: cvm"])
        self.assertEqual(sim.variavel("ULTIMO_STATUS"), "sem token")
        self.assertEqual(sim.variavel("ULTIMA_VERIFICACAO"), "2026-11-04T07:00:00-03:00")
        self.assertTrue(sim.cmds("git", "commit"))

    def test_token_vai_so_no_ambiente(self):
        self.cfg({"sombra": False, "classes_automaticas": ["H"]})
        rc, sim, _ = self.rodar(auto=[AUTO_H], publicar=False)  # só o PR do dia
        for c, env in sim.chamadas:
            self.assertNotIn("SEGREDO-123", " ".join(c))
        push = [(c, e) for c, e in sim.chamadas if c[:2] == ["git", "-c"]]
        self.assertEqual(len(push), 1)
        self.assertEqual(push[0][1].get("GH_TOKEN"), "SEGREDO-123")
        self.assertIn("HEAD:refs/heads/auto/%s" % HOJE, push[0][0])
        self.assertNotIn("--force", push[0][0])

    def test_sombra_nao_faz_merge(self):
        rc, sim, _ = self.rodar(auto=[AUTO_H], publicar=False)  # só o PR do dia
        self.assertEqual(rc, 0)
        self.assertEqual(len(sim.gh_cmds("pr", "create")), 1)
        self.assertEqual(sim.gh_cmds("pr", "merge"), [])
        self.assertIn("--sombra", sim.cmds("python3", "scripts/atualizar.py")[0])
        coment = sim.gh_cmds("pr", "comment")[0]
        self.assertIn("merge do Diogo", coment[coment.index("--body") + 1])
        self.assertEqual(sim.variavel("ULTIMO_STATUS"), "ok")

    def test_merge_com_criterio_e_ci_verde(self):
        self.cfg({"sombra": False, "classes_automaticas": ["H"]})
        rc, sim, _ = self.rodar(auto=[AUTO_H])
        self.assertNotIn("--sombra", sim.cmds("python3", "scripts/atualizar.py")[0])
        merges = sim.gh_cmds("pr", "merge")
        self.assertEqual(len(merges), 1)
        self.assertIn("--rebase", merges[0])
        self.assertNotIn("--admin", merges[0])
        self.assertEqual(merges[0][merges[0].index("--match-head-commit") + 1], SHA)
        apis = [c[2] for c in sim.gh_cmds("api")]
        self.assertTrue(any("head_sha=%s" % SHA in a and "event=pull_request" in a for a in apis), apis)

    def test_sem_merge_com_ci_vermelho(self):
        self.cfg({"sombra": False, "classes_automaticas": ["H"]})
        _, sim, _ = self.rodar(auto=[AUTO_H], ci="vermelho")
        self.assertEqual(sim.gh_cmds("pr", "merge"), [])
        self.assertEqual(sim.gh_cmds("issue", "create"), [])

    def test_sem_merge_sem_o_job_gitleaks(self):
        self.cfg({"sombra": False, "classes_automaticas": ["H"]})
        _, sim, _ = self.rodar(auto=[AUTO_H], ci="sem-gitleaks")
        self.assertEqual(sim.gh_cmds("pr", "merge"), [])
        coment = sim.gh_cmds("pr", "comment")[0]
        self.assertIn("gitleaks", coment[coment.index("--body") + 1])

    def test_ci_so_do_push_nao_conta_e_esgota_em_30_min(self):
        self.cfg({"sombra": False, "classes_automaticas": ["H"]})
        for estado in ("so-push", "pendente"):
            _, sim, _ = self.rodar(auto=[AUTO_H], ci=estado)
            self.assertEqual(sim.gh_cmds("pr", "merge"), [])
            consultas = [c for c in sim.gh_cmds("api") if "actions/runs?" in c[2]]
            self.assertEqual(len(consultas), job.CI_ESPERA // job.CI_INTERVALO + 1)
            titulos = [c[c.index("--title") + 1] for c in sim.gh_cmds("issue", "create")]
            self.assertEqual(titulos, ["CI sem conclusão: auto/%s" % HOJE])

    def test_sem_merge_sem_criterio(self):
        self.cfg({"sombra": False, "classes_automaticas": ["H"]})
        crit = {"execucao_id": EXEC, "conjunto": {"pr_automatico_antes_do_ci": False}, "itens": []}
        _, sim, _ = self.rodar(auto=[AUTO_H], crit=crit)
        self.assertEqual(sim.gh_cmds("pr", "merge"), [])
        cria = sim.gh_cmds("pr", "create")[0]
        self.assertIn("precisa-diogo", cria)

    def test_sem_merge_com_classe_fora_da_lista(self):
        self.cfg({"sombra": False, "classes_automaticas": ["I"]})
        _, sim, _ = self.rodar(auto=[AUTO_H])
        self.assertEqual(sim.gh_cmds("pr", "merge"), [])

    def test_execucao_id_de_outra_execucao_bloqueia(self):
        self.cfg({"sombra": False, "classes_automaticas": ["H"]})
        rc, sim, _ = self.rodar(auto=[AUTO_H], exec_id="outra")
        self.assertEqual(rc, 1)
        self.assertEqual(sim.cmds("git", "-c"), [])
        self.assertEqual(sim.gh_cmds("pr", "merge"), [])
        self.assertEqual(sim.variavel("ULTIMO_STATUS"), "falha")

    def test_atualizar_rc_diferente_de_zero_bloqueia(self):
        rc, sim, _ = self.rodar(auto=[AUTO_H], atualizar_rc=2)
        self.assertEqual(rc, 1)
        self.assertEqual(sim.gh_cmds("pr", "create"), [])

    def test_pre_commit_recusado_bloqueia_push(self):
        rc, sim, _ = self.rodar(auto=[AUTO_H], commit_rc=1)
        self.assertEqual(rc, 1)
        self.assertEqual(sim.cmds("git", "-c"), [])
        for c in sim.cmds("git", "commit"):
            self.assertNotIn("--no-verify", c)

    def test_exclui_ids_em_pr_aberto(self):
        prs = [{"number": 3, "headRefName": "auto/item-cvm-res-250", "body": "", "labels": []},
               {"number": 4, "headRefName": "auto/2026-11-03",
                "body": "x\n" + job.MARCADOR % json.dumps({"ids": ["bcb-res-9", "pas-1"]}), "labels": []}]
        _, sim, j = self.rodar(prs=prs)
        det = sim.cmds("python3", "scripts/detectar.py")[0]
        arq = det[det.index("--excluir-ids") + 1]
        with open(arq) as f:
            self.assertEqual(json.load(f), ["bcb-res-9", "cvm-res-250", "pas-1"])
        self.assertEqual(det[det.index("--frequencia") + 1], "todas")

    def test_toda_execucao_e_completa_e_publica(self):
        for dia in (HOJE, QUINTA, "2026-11-09"):
            _, sim, _ = self.rodar(hoje=dia)
            det = sim.cmds("python3", "scripts/detectar.py")[0]
            self.assertEqual(det[det.index("--frequencia") + 1], "todas")
            self.assertTrue(sim.cmds("python3", "scripts/publicar.py"))

    # -- revisão final: heartbeat, dado pessoal, deteccao.json, execução feita
    def titulos(self, sim):
        return [c[c.index("--title") + 1] for c in sim.gh_cmds("issue", "create")]

    def test_erro_inesperado_e_falha_com_issue_e_heartbeat(self):
        with mock.patch.object(job.Job, "commits_do_dia", side_effect=KeyError("x")):
            rc, sim, _ = self.rodar(auto=[AUTO_H])
        self.assertEqual(rc, 1)
        self.assertEqual(sim.variavel("ULTIMO_STATUS"), "falha")
        self.assertEqual(sim.variavel("EXECUCOES_SEM_OK"), "1")
        self.assertIsNone(sim.variavel("DIAS_SEM_OK"))
        self.assertNotIn("ultima_execucao_ok", self.ler_estado())
        self.assertEqual(self.titulos(sim), ["job-falhou"])
        self.assertEqual(sim.cmds("git", "-c"), [])

    def test_falha_abre_job_falhou_sem_duplicar(self):
        rc, sim, _ = self.rodar(auto=[AUTO_H], atualizar_rc=2)
        self.assertEqual(rc, 1)
        self.assertEqual(self.titulos(sim), ["job-falhou"])
        corpo = sim.gh_cmds("issue", "create")[0]
        self.assertIn("atualizar.py rc 2", corpo[corpo.index("--body") + 1])
        _, sim, _ = self.rodar(auto=[AUTO_H], atualizar_rc=2, issues_abertas=["job-falhou"])
        self.assertEqual(self.titulos(sim), [])

    def test_falha_sem_token_abre_job_falhou_pela_sessao(self):
        rc, sim, _ = self.rodar(token=None, atualizar_rc=2)
        self.assertEqual(rc, 1)
        self.assertEqual(self.titulos(sim), ["job-falhou"])
        self.assertTrue(all("GH_TOKEN" not in e for c, e in sim.chamadas if c[0] == "gh"))

    def test_execucoes_sem_ok_conta_execucoes_seguidas(self):
        self.gravar_estado({"execucoes_sem_ok": 1, "ultima_execucao_ok": "2026-10-21"})
        _, sim, _ = self.rodar(atualizar_rc=2)
        self.assertEqual(sim.variavel("EXECUCOES_SEM_OK"), "2")
        _, sim, _ = self.rodar(hoje=QUINTA, atualizar_rc=2)
        self.assertEqual(sim.variavel("EXECUCOES_SEM_OK"), "3")
        self.assertEqual(self.ler_estado()["ultima_execucao_ok"], "2026-10-21")  # falha não conta
        det = {"fontes": {"cvm": {"status": "falha"}}, "itens": []}
        _, sim, _ = self.rodar(hoje=QUINTA, det=det)  # concluída, mas fora de "ok": conta para a vigia
        self.assertEqual(sim.variavel("EXECUCOES_SEM_OK"), "4")
        self.assertEqual(self.ler_estado()["ultima_execucao_ok"], QUINTA)
        _, sim, _ = self.rodar(hoje="2026-11-06", auto=[AUTO_H])
        self.assertEqual(sim.variavel("EXECUCOES_SEM_OK"), "0")
        e = self.ler_estado()
        self.assertEqual((e["ultimo_status"], e["ultima_execucao_ok"]), ("ok", "2026-11-06"))

    def test_bloqueio_da_varredura_nao_faz_push_e_abre_issue_so_com_id_e_tipo(self):
        crit = {"execucao_id": EXEC, "itens": [], "conjunto": {
            "pr_automatico_antes_do_ci": False,
            "bloqueio_push": [{"id": "cvm-col-1", "problema": "varredura: CPF"},
                              {"id": "pas-2", "problema": "arquivo não revertido"}]}}
        diogo = [{"id": "pas-2", "chave": "pas-2|J|", "classe": "J", "motivo": "x", "caminhos": []}]
        rc, sim, _ = self.rodar(auto=[AUTO_H], crit=crit, diogo=diogo)
        self.assertEqual(rc, 0)
        self.assertEqual(sim.cmds("git", "-c"), [])
        self.assertEqual(sim.gh_cmds("pr", "create"), [])
        self.assertEqual(self.titulos(sim), ["push bloqueado: cvm-col-1", "push bloqueado: pas-2"])
        corpo = sim.gh_cmds("issue", "create")[0]
        self.assertIn("varredura: CPF", corpo[corpo.index("--body") + 1])
        self.assertEqual(sim.variavel("ULTIMO_STATUS"), "push bloqueado")

    def test_corpo_do_pr_de_item_sem_texto_do_julgado(self):
        texto = "Fulano de Tal, inscrito no CPF sob o n\u00ba " + "123." + "456"
        diogo = [{"id": "cvm-col-1", "chave": "cvm-col-1|J|", "classe": "J", "motivo": "revisor marcou: nome",
                  "o_que_seria_feito": "converter", "diff": texto,
                  "caminhos": ["plugins/julgados-colegiado/julgados/2026/cvm-col-1.md"]}]
        _, sim, _ = self.rodar(diogo=diogo)
        corpo = sim.gh_cmds("pr", "create")[0]
        corpo = corpo[corpo.index("--body") + 1]
        self.assertNotIn("Fulano", corpo)
        self.assertIn("revisor marcou: nome", corpo)
        self.assertIn("plugins/julgados-colegiado/julgados/2026/cvm-col-1.md", corpo)

    def test_deteccao_de_outra_execucao_e_falha(self):
        det = {"execucao_id": "ontem", "fontes": {"cvm": {"status": "ok"}}, "itens": []}
        rc, sim, _ = self.rodar(det=det)
        self.assertEqual(rc, 1)
        self.assertEqual(sim.cmds("python3", "scripts/atualizar.py"), [])

    def test_deteccao_velha_e_apagada_antes_do_detector(self):
        saida = os.path.join(self.wt, "dados", "auto", HOJE)
        os.makedirs(saida)
        with open(os.path.join(saida, "deteccao.json"), "w") as f:
            json.dump({"fontes": {}, "itens": []}, f)
        rc, sim, _ = self.rodar(det_falha=True)
        self.assertEqual(rc, 1)
        self.assertFalse(os.path.exists(os.path.join(saida, "deteccao.json")))
        self.assertEqual(sim.cmds("python3", "scripts/atualizar.py"), [])

    def test_execucao_ok_grava_ultima_execucao_ok(self):
        _, sim, _ = self.rodar()
        self.assertEqual(sim.variavel("ULTIMO_STATUS"), "ok")
        self.assertEqual(self.ler_estado()["ultima_execucao_ok"], HOJE)

    def test_execucao_concluida_fora_de_ok_conta_como_feita(self):
        det_fonte = {"fontes": {"cvm": {"status": "ok"}, "b3": {"status": "falha"}}, "itens": []}
        crit_bloq = {"execucao_id": EXEC, "itens": [], "conjunto": {
            "pr_automatico_antes_do_ci": False, "bloqueio_push": [{"id": "pas-2", "problema": "varredura"}]}}
        casos = {"falha de fonte": dict(det=det_fonte), "sem token": dict(token=None),
                 "push bloqueado": dict(auto=[AUTO_H], crit=crit_bloq)}
        for status, kw in casos.items():
            os.remove(self.estado)
            rc, sim, _ = self.rodar(**kw)
            self.assertEqual((rc, sim.variavel("ULTIMO_STATUS")), (0, status))
            e = self.ler_estado()
            self.assertEqual(e["ultima_execucao_ok"], HOJE, status)
            self.assertEqual(e["execucoes_sem_ok"], 1, status)
            self.assertEqual(sim.variavel("EXECUCOES_SEM_OK"), "1")

    def test_llm_indisponivel_conta_como_feita(self):
        det = {"fontes": {}, "itens": [{"id": "pas-1", "classe": "J"}]}
        saida = os.path.join(self.wt, "dados", "auto", HOJE)
        sim = Simulador(saida, det=det)
        orig = sim.__call__

        def rodar(cmd, **kw):
            if cmd[0] == "claude":
                return 1, "", "not logged in"
            return orig(cmd, **kw)
        j = job.Job(self.clone, self.wt, HOJE, rodar=rodar, ambiente={}, dormir=lambda s: None,
                    agora=lambda: "t", log=lambda m: None, estado=self.estado)
        self.assertEqual(j.executar(), 0)
        self.assertEqual(j.status, "LLM indisponível")
        self.assertEqual(self.ler_estado()["ultima_execucao_ok"], HOJE)

    def test_falha_nao_conta_como_feita(self):
        rc, sim, _ = self.rodar(atualizar_rc=2)
        self.assertEqual((rc, sim.variavel("ULTIMO_STATUS")), (1, "falha"))
        self.assertNotIn("ultima_execucao_ok", self.ler_estado())
        with mock.patch.object(job.Job, "commits_do_dia", side_effect=KeyError("x")):  # exceção
            rc, _, _ = self.rodar(auto=[AUTO_H])
        self.assertEqual(rc, 1)
        self.assertNotIn("ultima_execucao_ok", self.ler_estado())

    def test_item_do_diogo_ganha_pr_proprio_com_rotulo(self):
        diogo = [{"id": "cvm-res-251", "chave": "cvm-res-251|C|cvm-res-175", "classe": "C",
                  "motivo": "replay manual", "o_que_seria_feito": "replay", "diff": ""},
                 {"id": "pas-9", "chave": "pas-9|J|", "classe": "J", "motivo": "OCR",
                  "o_que_seria_feito": "", "diff": ""}]
        _, sim, _ = self.rodar(diogo=diogo)
        cria = sim.gh_cmds("pr", "create")
        heads = [c[c.index("--head") + 1] for c in cria]
        self.assertEqual(heads, ["auto/item-cvm-res-251", "auto/item-pas-9"])  # sem mudança no dia, sem PR do dia
        self.assertIn("aguarda-consolidado", cria[0])
        self.assertIn("precisa-diogo", cria[1])
        corpo = cria[0][cria[0].index("--body") + 1]
        self.assertEqual(job.marcador_de({"body": corpo})["norma_alvo"], ["cvm-res-175"])
        vazios = [c for c in sim.cmds("git", "commit") if "--allow-empty" in c]
        self.assertEqual(len(vazios), 2)

    def test_classe_c_com_parte_automatica_pede_replay_manual(self):
        diogo = [{"id": "cvm-res-251", "chave": "cvm-res-251|C|cvm-res-175", "classe": "C",
                  "parte_automatica": True, "motivo": "replay manual", "o_que_seria_feito": "replay", "diff": ""}]
        _, sim, _ = self.rodar(diogo=diogo)
        cria = sim.gh_cmds("pr", "create")
        corpo = cria[0][cria[0].index("--body") + 1]
        self.assertIn("aguarda-consolidado", cria[0])
        self.assertIn("seguem no PR do dia", corpo)
        self.assertIn("replay manual", corpo)

    def test_job_nunca_faz_merge_de_pr_de_item(self):
        self.cfg({"sombra": False, "classes_automaticas": ["A", "B1", "C", "H", "J", "publicar"]})
        diogo = [{"id": "cvm-res-251", "chave": "cvm-res-251|C|cvm-res-175", "classe": "C", "motivo": "replay manual"}]
        prs = [{"number": 5, "headRefName": "auto/item-cvm-res-9", "labels": [{"name": "aguarda-consolidado"}],
                "body": job.MARCADOR % json.dumps({"ids": ["cvm-res-9"], "classe": "C", "norma_alvo": ["cvm-res-175"]})}]
        det = {"fontes": {}, "itens": [{"id": "x", "classe": "B", "norma_alvo": ["cvm-res-175"],
                                        "dados": {"consolidado_novo": True}}]}
        _, sim, _ = self.rodar(diogo=diogo, prs=prs, det=det)
        self.assertEqual(sim.gh_cmds("pr", "merge"), [])
        self.assertEqual(sim.cmds("git", "rebase"), [])
        self.assertEqual(sim.cmds("python3", "scripts/teste_final.py"), [])

    def test_branch_de_item_ja_no_remoto_ganha_a_data(self):
        diogo = [{"id": "pas-9", "chave": "pas-9|J|", "classe": "J", "motivo": "OCR"}]
        _, sim, _ = self.rodar(diogo=diogo, remotos=["auto/item-pas-9", "auto/item-pas-9-20261104",
                                                     "auto/item-pas-90"])
        cria = sim.gh_cmds("pr", "create")
        self.assertEqual([c[c.index("--head") + 1] for c in cria], ["auto/item-pas-9-20261104-2"])
        push = [c for c in sim.cmds("git", "-c") if "push" in c]
        self.assertEqual([c[-1] for c in push], ["HEAD:refs/heads/auto/item-pas-9-20261104-2"])
        for c in push:
            self.assertFalse([x for x in c if x in ("--delete", "-d", "--force", "-f") or x.startswith((":", "+"))], c)
        self.assertEqual(job.ids_de_prs([{"headRefName": "auto/item-pas-9-20261104-2", "body": ""}]),
                         ["pas-9", "pas-9-20261104-2"])

    def test_issue_de_fonte_sem_duplicar(self):
        det = {"fontes": {"cvm": {"status": "falha", "motivo": "HTTP 500"},
                          "bcb": {"status": "falha", "motivo": "piso"}}, "itens": []}
        _, sim, _ = self.rodar(det=det, issues_abertas=["fonte-mudou: cvm"])
        titulos = [c[c.index("--title") + 1] for c in sim.gh_cmds("issue", "create")]
        self.assertEqual(titulos, ["fonte-mudou: bcb"])
        self.assertEqual(sim.variavel("ULTIMO_STATUS"), "falha de fonte")

    def test_issue_de_perimetro(self):
        det = {"fontes": {}, "itens": [{"id": "crsfn-1", "classe": "J", "dados": {"perimetro": "duvidosa"}}]}
        _, sim, _ = self.rodar(det=det)
        titulos = [c[c.index("--title") + 1] for c in sim.gh_cmds("issue", "create")]
        self.assertEqual(titulos, ["perimetro: crsfn-1"])

    def test_commit_por_ato_com_data_do_dou(self):
        auto = [{"id": "cvm-res-250", "classe": "A", "arquivos": ["plugins/normas/normas/cvm/r250.md"]}]
        det = {"fontes": {}, "itens": [{"id": "cvm-res-250", "classe": "A", "data_dou": "2026-11-03"}]}
        _, sim, _ = self.rodar(auto=auto, det=det)
        commits = [(c, e) for c, e in sim.chamadas if c[:2] == ["git", "commit"]]
        self.assertGreaterEqual(len(commits), 1)
        c, e = commits[0]
        self.assertTrue(e["GIT_AUTHOR_DATE"].startswith("2026-11-03"))
        self.assertEqual(e["GIT_AUTHOR_EMAIL"], "replay@normas-mercado-capitais.invalid")
        c2, e2 = commits[1]
        self.assertEqual(e2["GIT_AUTHOR_EMAIL"], job.AUTO_EMAIL)
        self.assertTrue(c2[c2.index("-m") + 1].startswith("auto: "))

    def test_llm_indisponivel_passa_sem_llm(self):
        det = {"fontes": {}, "itens": [{"id": "pas-1", "classe": "J"}]}
        saida = os.path.join(self.wt, "dados", "auto", HOJE)
        sim = Simulador(saida, det=det)
        orig = sim.__call__

        def rodar(cmd, **kw):
            if cmd[0] == "claude":
                sim.chamadas.append((list(cmd), {}))
                return 1, "", "not logged in"
            return orig(cmd, **kw)
        j = job.Job(self.clone, self.wt, HOJE, rodar=rodar, ambiente={}, dormir=lambda s: None,
                    agora=lambda: "t", log=lambda m: None)
        j.executar()
        self.assertIn("--sem-llm", sim.cmds("python3", "scripts/atualizar.py")[0])
        self.assertEqual(sim.variavel("ULTIMO_STATUS"), "LLM indisponível")

    def test_push_so_de_auto(self):
        j = job.Job(self.clone, self.wt, HOJE, rodar=lambda *a, **k: (0, "", ""), ambiente={},
                    log=lambda m: None)
        with self.assertRaises(job.Falha):
            j.push("main")

    def test_branch_do_dia_nao_reescreve_o_remoto(self):
        def rodar(cmd, **kw):
            if cmd[:2] == ["git", "ls-remote"]:
                return 0, "abc\trefs/heads/auto/%s\nabd\trefs/heads/auto/%s-2\n" % (HOJE, HOJE), ""
            return 0, "", ""
        j = job.Job(self.clone, self.wt, HOJE, rodar=rodar, ambiente={}, log=lambda m: None)
        self.assertEqual(j.branch_do_dia(), "auto/%s-3" % HOJE)

    def test_clean_preserva_o_link_de_dados(self):
        _, sim, _ = self.rodar(auto=[AUTO_H], publicar=False)  # o fetch antes do publicar é do job
        self.assertEqual(sim.cmds("git", "clean"), [["git", "clean", "-fd", "-e", "dados"]])
        dados = os.path.join(self.wt, "dados")
        self.assertTrue(os.path.islink(dados))
        self.assertEqual(os.readlink(dados), os.path.join(self.clone, "dados"))
        self.assertEqual(sim.cmds("git", "worktree"), [])  # o worktree é do wrapper
        self.assertEqual(sim.cmds("git", "fetch"), [])

    def test_dados_real_no_worktree_e_falha(self):
        os.remove(os.path.join(self.wt, "dados"))
        os.makedirs(os.path.join(self.wt, "dados"))
        rc, sim, _ = self.rodar(auto=[AUTO_H])
        self.assertEqual(rc, 1)
        self.assertEqual(sim.cmds("python3", "scripts/detectar.py"), [])
        self.assertEqual(sim.cmds("git", "-c"), [])

    def test_sem_worktree_e_falha(self):
        os.remove(os.path.join(self.wt, ".git"))
        rc, _, _ = self.rodar()
        self.assertEqual(rc, 1)


# ---------------------------------------------------------------- agenda quinzenal

def sp(texto):
    """datetime no fuso de São Paulo (-03:00, sem horário de verão)."""
    return datetime.datetime.fromisoformat(texto + "-03:00")


class TestAgenda(unittest.TestCase):
    def roda(self, agora, estado=None, forcar=False):
        return job.deve_rodar(sp(agora), estado or {}, AGENDA, forcar=forcar)[0]

    def test_quarta_prevista_antes_das_13h_nao_roda(self):
        roda, motivo = job.deve_rodar(sp("2026-11-18T12:59"), {}, AGENDA)
        self.assertFalse(roda)
        self.assertTrue(motivo.startswith("fora da agenda; próxima prevista 2026-11-18"), motivo)

    def test_quarta_prevista_as_13h_roda(self):
        self.assertTrue(self.roda("2026-11-18T13:00"))
        self.assertTrue(self.roda("2026-12-02T13:00", {"ultima_execucao_ok": "2026-11-18"}))

    def test_quarta_seguinte_nao_prevista_nao_roda(self):
        roda, motivo = job.deve_rodar(sp("2026-11-25T13:00"), {"ultima_execucao_ok": "2026-11-18"}, AGENDA)
        self.assertFalse(roda)
        self.assertEqual(motivo, "fora da agenda; próxima prevista 2026-12-02")
        self.assertFalse(self.roda("2026-11-18T15:00", {"ultima_execucao_ok": "2026-11-18"}))  # já feita

    def test_quinta_depois_de_quarta_perdida_roda_a_qualquer_hora(self):
        for hora in ("00:05", "08:30", "13:00", "23:59"):
            self.assertTrue(self.roda("2026-11-19T%s" % hora), hora)
        self.assertTrue(self.roda("2026-12-03T07:00", {"ultima_execucao_ok": "2026-11-18"}))

    def test_duas_semanas_perdidas_roda_uma_vez_so(self):
        estado = {"ultima_execucao_ok": "2026-11-18"}  # perdeu 2026-12-02 e 2026-12-16
        self.assertTrue(self.roda("2026-12-17T09:00", estado))
        estado = {"ultima_execucao_ok": "2026-12-17", "ultima_tentativa": "2026-12-17"}
        self.assertFalse(self.roda("2026-12-17T13:00", estado))
        self.assertFalse(self.roda("2026-12-18T13:00", estado))
        self.assertFalse(self.roda("2026-12-30T12:00", estado))
        self.assertTrue(self.roda("2026-12-30T13:00", estado))

    def test_falha_na_quarta_tenta_de_novo_na_quinta(self):
        estado = {"ultima_execucao_ok": "2026-11-18", "ultima_tentativa": "2026-12-02"}  # 12-02 falhou
        self.assertFalse(self.roda("2026-12-02T18:00", estado))
        self.assertTrue(self.roda("2026-12-03T08:00", estado))

    def test_duas_tentativas_no_mesmo_dia_so_uma(self):
        estado = {"ultima_execucao_ok": "2026-11-18", "ultima_tentativa": "2026-12-03"}
        roda, motivo = job.deve_rodar(sp("2026-12-03T13:00"), estado, AGENDA)
        self.assertFalse(roda)
        self.assertTrue(motivo.startswith("fora da agenda; próxima prevista 2026-12-16"), motivo)
        self.assertIn("2026-12-02 segue pendente", motivo)

    def test_antes_da_ancora_nao_roda(self):
        roda, motivo = job.deve_rodar(sp("2026-11-17T13:00"), {}, AGENDA)
        self.assertFalse(roda)
        self.assertEqual(motivo, "fora da agenda; próxima prevista 2026-11-18")
        self.assertFalse(self.roda("2026-11-04T13:00", {"ultima_execucao_ok": "2026-11-04"}))

    def test_forcar_roda(self):
        self.assertTrue(self.roda("2026-11-04T09:00", forcar=True))
        self.assertTrue(self.roda("2026-11-18T09:00", {"ultima_tentativa": "2026-11-18"}, forcar=True))
        # R1 forçada com sucesso antes da âncora: a quarta 2026-11-18 roda normalmente
        self.assertTrue(self.roda("2026-11-18T13:00", {"ultima_execucao_ok": "2026-11-04"}))

    def test_agenda_ilegivel_levanta(self):
        for ruim in (None, {}, dict(AGENDA, intervalo_dias=0), dict(AGENDA, hora="13"),
                     dict(AGENDA, ancora="18/11/2026")):
            with self.assertRaises(ValueError):
                job.deve_rodar(sp("2026-11-18T13:00"), {}, ruim)

    def test_agenda_versionada_e_quarta_as_13h(self):
        with open(os.path.join(RAIZ, "fontes", "automacao.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["agenda"], AGENDA)
        self.assertEqual(datetime.date.fromisoformat(cfg["agenda"]["ancora"]).weekday(), 2)  # quarta
        self.assertTrue(cfg["sombra"])


class TestChecarAgenda(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.clone = os.path.join(self.tmp, "clone")
        os.makedirs(os.path.join(self.clone, "fontes"))
        self.estado = os.path.join(self.tmp, "normas-auto", "estado.json")
        self.cfg({"sombra": True, "agenda": AGENDA})
        self.linhas = []

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def cfg(self, c):
        with open(os.path.join(self.clone, "fontes", "automacao.json"), "w") as f:
            json.dump(c, f)

    def checar(self, agora, forcar=False):
        return job.checar_agenda(self.clone, self.estado, agora=sp(agora), forcar=forcar,
                                 saida=self.linhas.append)

    def test_fora_da_agenda_uma_linha_sem_gravar_estado(self):
        with mock.patch.object(job.subprocess, "run", side_effect=AssertionError("sem processo")):
            rc = self.checar("2026-11-17T13:00")
        self.assertEqual(rc, job.SAIDA_FORA_DA_AGENDA)
        self.assertEqual(self.linhas, ["fora da agenda; próxima prevista 2026-11-18"])
        self.assertFalse(os.path.exists(self.estado))

    def test_roda_e_grava_a_tentativa_uma_vez_por_dia(self):
        self.assertEqual(self.checar("2026-11-19T08:00"), 0)
        with open(self.estado) as f:
            self.assertEqual(json.load(f), {"ultima_tentativa": "2026-11-19"})
        self.assertEqual(self.checar("2026-11-19T13:00"), job.SAIDA_FORA_DA_AGENDA)  # segundo disparo
        self.assertEqual(self.checar("2026-11-20T13:00"), 0)  # a de 11-19 falhou: tenta de novo

    def test_forcar_pela_main_roda_e_aceita_no_job(self):
        saida = io.StringIO()
        with mock.patch("sys.stdout", saida):
            rc = job.main(["--checar-agenda", "--clone", self.clone, "--estado", self.estado, "--forcar"])
        self.assertEqual(rc, 0)
        self.assertIn("--forcar", saida.getvalue())

    def test_agenda_ilegivel_sai_com_2(self):
        self.cfg({"sombra": True})
        self.assertEqual(self.checar("2026-11-18T13:00"), 2)
        self.assertFalse(os.path.exists(self.estado))


class TestLaunchd(unittest.TestCase):
    PLIST = os.path.join(RAIZ, "launchd", "br.normas.auto.plist")

    def test_plist_valido_as_13h_e_no_login(self):
        plutil = shutil.which("plutil")  # sem macOS (o gate): só o parse do XML
        if plutil:
            r = subprocess.run([plutil, "-lint", self.PLIST], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(self.PLIST, "rb") as f:
            p = plistlib.load(f)
        self.assertEqual(p["StartCalendarInterval"], {"Hour": 13, "Minute": 0})
        self.assertIs(p["RunAtLoad"], True)
        self.assertNotIn("KeepAlive", p)
        self.assertEqual(p["StartCalendarInterval"]["Hour"], AGENDA["hora"])

    def test_wrapper_checa_a_agenda_antes_da_rede(self):
        with open(os.path.join(RAIZ, "scripts", "job_diario.sh"), encoding="utf-8") as f:
            sh = f.read()
        corpo = sh[sh.index("set -u"):]
        i = corpo.index("--checar-agenda")
        for depois in ("fetch", "worktree add", "tomar", "caffeinate -i python3"):
            self.assertLess(i, corpo.index(depois), depois)
        self.assertIn("10) exit 0", corpo)


if __name__ == "__main__":
    unittest.main()
