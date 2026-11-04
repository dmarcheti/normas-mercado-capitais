#!/usr/bin/env python3
"""Job diário da Fase 4 (Task 3b): detecta, aplica, abre PR e faz o merge pelo critério.

Uso (só pelo scripts/job_diario.sh, que prepara o worktree e roda o job.py DO WORKTREE):
  python3 ~/normas-auto/worktree/scripts/job.py --clone REPO --worktree ~/normas-auto/worktree
      [--hoje AAAA-MM-DD] [--trava ~/normas-auto/job.pid] [--herdar PID] [--sem-publicar]
O código que lê o token e faz o merge é sempre o do origin/main (o worktree), nunca o da cópia de
desenvolvimento: fora do worktree, o job.py recusa rodar (saída 1).

Uma execução:
  a. worktree já preparado pelo wrapper (fetch, origin/main, `dados` como link simbólico para o
     dados/ do clone); aqui: branch `auto/AAAA-MM-DD` a partir de `origin/main`, `git clean -fd -e
     dados` e conferência do link (`dados/` real no worktree: falha);
  b. ids em PR aberto (`gh pr list`: branch `auto/item-<id>` e o marcador do corpo) vão ao
     `--excluir-ids` do detector;
  c. detectar.py (`todas` às segundas ou quando a última semanal com sucesso, em
     ~/normas-auto/estado.json, tem mais de 7 dias; senão `diaria`), com `--execucao-id` conferido
     no deteccao.json (o anterior é apagado antes), e atualizar.py, com `--sombra` enquanto
     `fontes/automacao.json` disser {"sombra": true}; `--sem-llm` se o `claude` não responder;
  d. um commit por ato (identidade neutra do replay, data do DOU) e um para o resto
     (`Atualizacao automatica`, mensagem `auto: <o quê>`); o pre-commit roda, nunca --no-verify;
  e. push só de `auto/*`, com o token do Keychain (sem token: status "sem token"; sem lista de
     PRs, sem push; pela sessão do gh, só o heartbeat e as issues `fonte-mudou` e `job-falhou`).
     Nenhum push quando o critério traz `bloqueio_push` (varredura reprovada ou arquivo não
     revertido): só uma issue `push-bloqueado` por item, com o id e o tipo do problema. PR do dia
     com o resumo.md; item `precisa-diogo` ou `aguarda-consolidado` (classe C, replay manual) em PR
     próprio `auto/item-<id>` (commit vazio: o atualizar já reverteu o item; o corpo leva só id,
     classe, tipo do alerta e caminhos, nunca texto de julgado); branch já no remoto sem PR
     aberto: `auto/item-<id>-<AAAAMMDD>`, nada é apagado. O job nunca faz merge de PR de item;
  f. merge do PR do dia só com `pr_automatico_antes_do_ci`, sombra desligada, todas as classes em
     `classes_automaticas` e o CI do evento `pull_request` concluído para o sha empurrado: run do
     ci.yml com os jobs `testes` e `gitleaks` presentes e todos os jobs com `success` (até 30 min;
     esgotado: sem merge e issue). Merge `gh pr merge --rebase --match-head-commit <sha>`, sem
     force e sem --admin (o repo não tem proteção de branch);
  h. heartbeat: variáveis ULTIMA_VERIFICACAO, ULTIMO_STATUS e DIAS_SEM_OK (dias seguidos fora de
     "ok", contados em ~/normas-auto/estado.json) do repo, gravadas mesmo com falha;
  i. fonte com falha: issue `fonte-mudou` (uma por fonte, sem duplicar); perímetro duvidoso:
     issue `perimetro`; execução com falha: issue `job-falhou` (uma aberta por vez).
Na execução `todas`, depois do dia, roda scripts/publicar.py num branch `auto/publicar-AAAA-MM-DD`,
com o mesmo critério (classe `publicar` em `classes_automaticas`).
Saída 0 = execução concluída (mesmo com item para o Diogo); 1 = falha; 3 = outra execução ativa.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import montar_historico as mh  # noqa: E402

REPO_GH = "dmarcheti/normas-mercado-capitais"
CLONE_PADRAO = os.path.normpath(os.path.join(AQUI, ".."))
BASE = os.path.expanduser("~/normas-auto")
AUTO_NOME = "Atualizacao automatica"
AUTO_EMAIL = "auto@normas-mercado-capitais.invalid"
TOKEN_SERVICO = "normas-auto-token"
CAMINHOS_DO_COMMIT = ("plugins", "fontes", ".claude-plugin", "CHANGELOG.md")
MARCADOR = "<!-- normas-auto: %s -->"
MARCADOR_RE = re.compile(r"<!-- normas-auto: (\{.*?\}) -->")
ROTULOS = {"precisa-diogo": "d93f0b", "aguarda-consolidado": "fbca04", "fonte-mudou": "b60205",
           "perimetro": "5319e7", "sombra": "c5def5", "automatico": "0e8a16", "job-falhou": "b60205",
           "push-bloqueado": "b60205"}
DIAS_SEMANAL = 7  # `todas` quando a última semanal com sucesso tem mais que isto
CI_ESPERA = 1800  # 30 min
CI_INTERVALO = 30
CI_WORKFLOW = ".github/workflows/ci.yml"
CI_JOBS_EXIGIDOS = ("testes", "gitleaks")
ITEM_DATADO_RE = re.compile(r"-\d{8}(?:-\d+)?$")

STATUS_OK, STATUS_FONTE, STATUS_TOKEN, STATUS_LLM, STATUS_FALHA, STATUS_BLOQUEIO = (
    "ok", "falha de fonte", "sem token", "LLM indisponível", "falha", "push bloqueado")
GRAVIDADE = {STATUS_OK: 0, STATUS_LLM: 1, STATUS_FONTE: 2, STATUS_BLOQUEIO: 2, STATUS_TOKEN: 3, STATUS_FALHA: 4}


class Falha(Exception):
    """Interrompe a execução: nada de push nem de merge depois dela."""


# ---------------------------------------------------------------- trava

class Trava:
    """Arquivo com o PID, criado com O_CREAT|O_EXCL. Outra execução viva do job: recusa. PID morto
    (ou de outro processo): a trava é retomada. `herdar`: o wrapper tomou a trava com o PID dele e
    é o pai deste processo (nohup caffeinate -i python3 ...); o job passa a trava para o próprio PID."""

    def __init__(self, caminho, pid=None, vivo=None, herdar=None, ppid=None):
        self.caminho, self.pid = caminho, pid or os.getpid()
        self.vivo, self.herdar = vivo, herdar
        self.ppid = ppid if ppid is not None else os.getppid()

    def _ler(self):
        try:
            with open(self.caminho) as f:
                return int(f.read().strip() or "0")
        except (OSError, ValueError):
            return 0

    def _criar(self):
        try:
            fd = os.open(self.caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            return False
        with os.fdopen(fd, "w") as f:
            f.write("%d\n" % self.pid)
        return True

    def _gravar(self):
        tmp = "%s.%d" % (self.caminho, self.pid)
        with open(tmp, "w") as f:
            f.write("%d\n" % self.pid)
        os.replace(tmp, self.caminho)

    def tomar(self):
        os.makedirs(os.path.dirname(self.caminho) or ".", exist_ok=True)
        for _ in range(2):
            if self._criar():
                return True
            outro = self._ler()
            if outro == self.pid:
                return True
            if self.herdar and outro == self.herdar and self.herdar == self.ppid:
                self._gravar()
                return True
            if outro and (self.vivo or processo_do_job)(outro):
                return False
            try:
                os.remove(self.caminho)  # PID morto ou que não é o job
            except FileNotFoundError:
                pass
        return False

    def soltar(self):
        if self._ler() != self.pid:
            return
        try:
            os.remove(self.caminho)
        except OSError:
            pass


def processo_do_job(pid):
    """PID vivo e que é o job (job.py ou o wrapper job_diario.sh): PID reaproveitado não trava."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    try:
        r = subprocess.run([shutil.which("ps") or "/bin/ps", "-p", str(pid), "-o", "command="],
                           capture_output=True, text=True)
    except OSError:
        return True
    cmd = r.stdout
    return "job.py" in cmd or "job_diario" in cmd


# ---------------------------------------------------------------- utilidades

def rodar_real(cmd, cwd=None, env=None, timeout=None):
    try:
        r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "", "tempo esgotado: %s" % " ".join(cmd[:3])
    except FileNotFoundError as e:
        return 127, "", str(e)
    return r.returncode, r.stdout, r.stderr


def ler_json(caminho, padrao=None):
    if not os.path.exists(caminho):
        return padrao
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def ids_de_prs(prs):
    """Ids que estão em PR aberto: branch `auto/item-<id>` e o marcador do corpo."""
    ids = set()
    for pr in prs:
        ref = pr.get("headRefName") or ""
        if ref.startswith("auto/item-"):
            resto = ref[len("auto/item-"):]
            ids.add(resto)
            if ITEM_DATADO_RE.search(resto):  # auto/item-<id>-<AAAAMMDD>[-n]
                ids.add(ITEM_DATADO_RE.sub("", resto))
        for m in MARCADOR_RE.finditer(pr.get("body") or ""):
            try:
                ids.update(json.loads(m.group(1)).get("ids", []))
            except ValueError:
                pass
    return sorted(ids)


def marcador_de(pr):
    m = MARCADOR_RE.search(pr.get("body") or "")
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except ValueError:
        return {}


def alvos_da_chave(chave):
    partes = (chave or "").split("|")
    return [a for a in (partes[2].split(",") if len(partes) > 2 else []) if a]


def pode_merge(crit, classes, cfg, ci_ok):
    """Condição do merge do PR do dia: (bool, motivo)."""
    if cfg.get("sombra", True):
        return False, "modo sombra: o merge é do Diogo"
    if not (crit or {}).get("conjunto", {}).get("pr_automatico_antes_do_ci"):
        return False, "critério antes do CI não passou"
    fora = sorted(set(classes) - set(cfg.get("classes_automaticas") or []))
    if fora:
        return False, "classe(s) fora de classes_automaticas: %s" % ", ".join(fora)
    if not classes:
        return False, "nenhum item automático"
    if not ci_ok:
        return False, "CI não ficou verde"
    return True, "critério e CI verdes"


# ---------------------------------------------------------------- job

class Job:
    def __init__(self, clone=CLONE_PADRAO, worktree=None, hoje=None, rodar=None, ambiente=None,
                 dormir=None, agora=None, log=None, publicar=True, estado=None):
        self.clone = os.path.abspath(clone)
        self.wt = os.path.abspath(worktree or os.path.join(BASE, "worktree"))
        self.hoje = hoje or datetime.date.today().isoformat()
        self.rodar_cmd = rodar or rodar_real
        self.env = dict(ambiente if ambiente is not None else os.environ)
        self.dormir = dormir or time.sleep
        self.agora = agora or (lambda: datetime.datetime.now().astimezone().isoformat(timespec="seconds"))
        self.log = log or (lambda m: print("[%s] %s" % (time.strftime("%H:%M:%S"), m), flush=True))
        self.publicar = publicar
        self.estado_arq = estado or os.path.join(BASE, "estado.json")  # fora do Git
        self.semanal_ok = False
        self.execucao_det = None
        self.freq = None
        self.status = STATUS_OK
        self.token = None
        self.rotulos_ok = set()
        self.saida = os.path.join(self.wt, "dados", "auto", self.hoje)
        self.relatorio = {"hoje": self.hoje, "prs": [], "merges": [], "issues": [], "avisos": []}

    # -- execução de comandos
    def rodar(self, cmd, cwd=None, env=None, timeout=None):
        rc, out, err = self.rodar_cmd(cmd, cwd=cwd or self.wt, env=env or self.env, timeout=timeout)
        if rc != 0:
            self.log("rc %s: %s | %s" % (rc, " ".join(c if "token" not in c.lower() else "***" for c in cmd[:6]),
                                         (err or out or "").strip()[-300:]))
        return rc, out or "", err or ""

    def git(self, *args, cwd=None, env=None):
        return self.rodar(["git"] + list(args), cwd=cwd, env=env)

    def git_ok(self, *args, cwd=None, env=None):
        rc, out, err = self.git(*args, cwd=cwd, env=env)
        if rc != 0:
            raise Falha("git %s: %s" % (" ".join(args[:2]), (err or out).strip()[-200:]))
        return out

    def env_gh(self):
        e = dict(self.env)
        if self.token:
            e["GH_TOKEN"] = self.token
        return e

    def gh(self, *args, timeout=None):
        return self.rodar(["gh"] + list(args) + ["--repo", REPO_GH], env=self.env_gh(), timeout=timeout)

    def py(self, script, *args):
        return self.rodar(["python3", os.path.join("scripts", script)] + list(args))

    def piora(self, status):
        if GRAVIDADE[status] > GRAVIDADE[self.status]:
            self.status = status

    # -- a. worktree
    def ler_token(self):
        rc, out, _ = self.rodar(["security", "find-generic-password", "-s", TOKEN_SERVICO, "-w"],
                                cwd=self.clone)
        return out.strip() if rc == 0 and out.strip() else None

    def conferir_dados(self):
        """`dados` do worktree tem de ser link para o dados/ do clone (o .gitignore `dados/` não casa
        com link: sem o `-e dados`, o clean o apagaria e nasceria um dados/ real)."""
        dados, alvo = os.path.join(self.wt, "dados"), os.path.join(self.clone, "dados")
        if not os.path.lexists(dados):
            os.symlink(alvo, dados)
        if not os.path.islink(dados) or os.path.realpath(dados) != os.path.realpath(alvo):
            raise Falha("%s não é link para %s: confira o worktree à mão" % (dados, alvo))

    def preparar_worktree(self, branch):
        """O wrapper já fez fetch, worktree e checkout do origin/main; aqui só o branch do dia."""
        if not os.path.exists(os.path.join(self.wt, ".git")):
            raise Falha("worktree ausente em %s: o job_diario.sh o prepara" % self.wt)
        self.conferir_dados()
        self.git_ok("checkout", "--force", "-B", branch, "origin/main")
        self.git_ok("clean", "-fd", "-e", "dados")
        self.conferir_dados()

    def branch_do_dia(self):
        """auto/AAAA-MM-DD, ou -2, -3... se o do dia já está no remoto (nunca reescreve)."""
        _, out, _ = self.git("ls-remote", "--heads", "origin", "auto/%s*" % self.hoje, cwd=self.clone)
        existentes = {l.split("refs/heads/")[-1].strip() for l in out.splitlines() if "refs/heads/" in l}
        nome, n = "auto/%s" % self.hoje, 1
        while nome in existentes:
            n += 1
            nome = "auto/%s-%d" % (self.hoje, n)
        return nome

    def branch_do_item(self, id_):
        """auto/item-<id>; já no remoto (sem PR aberto, senão o id estaria excluído):
        auto/item-<id>-<AAAAMMDD>[-n]. Nada é apagado nem reescrito."""
        base = "auto/item-%s" % id_
        _, out, _ = self.git("ls-remote", "--heads", "origin", base + "*", cwd=self.clone)
        existentes = {l.split("refs/heads/")[-1].strip() for l in out.splitlines() if "refs/heads/" in l}
        if base not in existentes:
            return base
        nome = cand = "%s-%s" % (base, self.hoje.replace("-", ""))
        n = 1
        while cand in existentes:
            n += 1
            cand = "%s-%d" % (nome, n)
        return cand

    def ler_estado(self):
        try:
            e = ler_json(self.estado_arq, {})
        except (OSError, ValueError):
            e = {}
        return e if isinstance(e, dict) else {}

    def gravar_estado(self, e):
        os.makedirs(os.path.dirname(self.estado_arq) or ".", exist_ok=True)
        tmp = self.estado_arq + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(e, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.estado_arq)

    def frequencia(self):
        """`todas` às segundas ou com a última semanal com sucesso há mais de DIAS_SEMANAL dias."""
        hoje = datetime.date.fromisoformat(self.hoje)
        if hoje.weekday() == 0:
            return "todas"
        try:
            ult = datetime.date.fromisoformat(self.ler_estado().get("ultima_semanal_ok") or "")
        except (TypeError, ValueError):
            return "todas"
        return "todas" if (hoje - ult).days > DIAS_SEMANAL else "diaria"

    def config(self):
        return ler_json(os.path.join(self.wt, "fontes", "automacao.json"), {}) or {}

    # -- b. PRs abertos
    def prs_abertos(self):
        rc, out, _ = self.gh("pr", "list", "--state", "open", "--limit", "500",
                             "--json", "number,headRefName,body,labels")
        if rc != 0:
            raise Falha("gh pr list falhou: sem a lista de PRs abertos, o detector repetiria itens")
        return json.loads(out or "[]")

    # -- c. detecção e aplicação
    def detectar(self, excluir):
        os.makedirs(self.saida, exist_ok=True)
        arq = os.path.join(self.saida, "excluir-ids.json")
        with open(arq, "w", encoding="utf-8") as f:
            json.dump(excluir, f, ensure_ascii=False)
        self.freq = freq = self.frequencia()
        self.execucao_det = "%s-%d-%s" % (self.hoje, os.getpid(), os.urandom(4).hex())
        cam = os.path.join(self.saida, "deteccao.json")
        if os.path.exists(cam):
            os.remove(cam)  # sem isto, um detector que cai deixaria o deteccao.json de ontem
        rc, out, _ = self.py("detectar.py", "--frequencia", freq, "--saida", self.saida, "--excluir-ids", arq,
                             "--execucao-id", self.execucao_det)
        det = ler_json(cam)
        if det is None:
            raise Falha("detectar.py rc %s sem deteccao.json" % rc)
        if det.get("execucao_id") != self.execucao_det:
            raise Falha("deteccao.json não é desta execução (%r)" % det.get("execucao_id"))
        self.log("detectar (%s): rc %s, %d item(ns)" % (freq, rc, len(det.get("itens", []))))
        return det

    def llm_disponivel(self):
        rc, out, _ = self.rodar(["claude", "-p", "Responda só: ok", "--max-turns", "1"], timeout=180)
        return rc == 0 and "ok" in out.lower()

    def atualizar(self, det, cfg):
        args = ["--deteccao", os.path.join(self.saida, "deteccao.json"), "--raiz", self.wt,
                "--saida", self.saida]
        if cfg.get("sombra", True):
            args.append("--sombra")
        if det.get("itens") and not self.llm_disponivel():
            self.log("claude não respondeu: etapas de LLM ficam para o Diogo (C18)")
            self.piora(STATUS_LLM)
            args.append("--sem-llm")
        rc, out, _ = self.py("atualizar.py", *args)
        if rc != 0:
            raise Falha("atualizar.py rc %s" % rc)
        ultima = [l for l in out.strip().splitlines() if l.startswith("{")]
        try:
            execucao = json.loads(ultima[-1])["execucao_id"]
        except (IndexError, KeyError, ValueError):
            raise Falha("atualizar.py sem execucao_id na saída")
        saidas = {}
        for nome in ("criterio.json", "itens-automaticos.json", "itens-diogo.json"):
            d = ler_json(os.path.join(self.saida, nome))
            if not d or d.get("execucao_id") != execucao:
                raise Falha("%s não é desta execução (%s)" % (nome, execucao))
            saidas[nome] = d
        resumo = os.path.join(self.saida, "resumo.md")
        if not os.path.exists(resumo):
            raise Falha("resumo.md ausente")
        with open(resumo, encoding="utf-8") as f:
            texto = f.read()
        if execucao not in texto:
            raise Falha("resumo.md não é desta execução")
        return saidas["criterio.json"], saidas["itens-automaticos.json"]["itens"], \
            saidas["itens-diogo.json"]["itens"], texto

    # -- d. commits
    def env_auto(self):
        return dict(self.env, GIT_AUTHOR_NAME=AUTO_NOME, GIT_AUTHOR_EMAIL=AUTO_EMAIL,
                    GIT_COMMITTER_NAME=AUTO_NOME, GIT_COMMITTER_EMAIL=AUTO_EMAIL)

    def staged(self):
        rc, _, _ = self.git("diff", "--cached", "--quiet")
        return rc == 1

    def commit(self, mensagem, env, vazio=False):
        args = ["commit", "-m", mensagem] + (["--allow-empty"] if vazio else [])
        rc, out, err = self.git(*args, env=env)
        if rc != 0:
            self.git("reset", "-q")  # tira do stage; os arquivos ficam
            raise Falha("commit recusado (pre-commit?): %s" % (err or out).strip()[-300:])

    def commits_do_dia(self, auto, det):
        por_id = {i["id"]: i for i in det.get("itens", [])}
        n = 0
        for it in auto:
            d = por_id.get(it["id"], {})
            if not d.get("data_dou") or not it.get("arquivos"):
                continue
            self.git_ok("add", "-A", "--", *it["arquivos"])
            if not self.staged():
                continue
            env = dict(self.env, **mh.ambiente_git({"data_dou": d["data_dou"]}))
            self.commit("auto: %s (%s, DOU de %s)" % (it["id"], it["classe"], d["data_dou"]), env)
            n += 1
        existentes = [c for c in CAMINHOS_DO_COMMIT if os.path.lexists(os.path.join(self.wt, c))]
        self.git_ok("add", "-A", "--", *existentes)
        if self.staged():
            self.commit("auto: atualização de %s (registros, índices e itens sem DOU)" % self.hoje, self.env_auto())
            n += 1
        _, sobra, _ = self.git("status", "--porcelain")
        sobra = [l for l in sobra.splitlines() if l.strip() and l[3:].rstrip("/") != "dados"]  # o link
        if sobra:
            self.relatorio["avisos"].append("fora do commit: %s" % "; ".join(sobra[:10]))
        return n

    # -- e. push e PRs
    def push(self, branch):
        if not branch.startswith("auto/"):
            raise Falha("push recusado fora de auto/*: %s" % branch)
        ajuda = "!f() { echo username=x-access-token; echo \"password=$GH_TOKEN\"; }; f"
        rc, out, err = self.git("-c", "credential.helper=", "-c", "credential.helper=%s" % ajuda,
                                "push", "origin", "HEAD:refs/heads/%s" % branch, env=self.env_gh())
        if rc != 0:
            raise Falha("push de %s falhou: %s" % (branch, (err or out).strip()[-200:]))

    def rotulo(self, nome):
        if nome not in self.rotulos_ok:
            self.gh("label", "create", nome, "--color", ROTULOS.get(nome, "ededed"))
            self.rotulos_ok.add(nome)

    def criar_pr(self, branch, titulo, corpo, rotulos=()):
        args = ["pr", "create", "--base", "main", "--head", branch, "--title", titulo, "--body", corpo]
        for r in rotulos:
            self.rotulo(r)
            args += ["--label", r]
        rc, out, _ = self.gh(*args)
        if rc != 0:
            raise Falha("gh pr create %s falhou" % branch)
        url = out.strip().splitlines()[-1] if out.strip() else ""
        self.relatorio["prs"].append({"branch": branch, "url": url, "rotulos": list(rotulos)})
        return url or branch

    def pr_do_item(self, it, det_item):
        rot = "aguarda-consolidado" if it.get("classe") == "C" else "precisa-diogo"
        branch = self.branch_do_item(it["id"])
        self.git_ok("checkout", "--force", "-B", branch, "origin/main")
        self.commit("auto: %s espera o Diogo (%s)" % (it["id"], it["classe"]), self.env_auto(), vazio=True)
        self.push(branch)
        marca = {"ids": [it["id"]], "classe": it.get("classe"),
                 "norma_alvo": (det_item or {}).get("norma_alvo") or alvos_da_chave(it.get("chave"))}
        # só id, classe, tipo do alerta e caminhos: nada de texto de julgado (diff e trechos ficam em
        # dados/auto/<dia>/ na máquina do job, fora do Git)
        corpo = "\n".join([
            "# %s (%s)" % (it["id"], it.get("classe")), "",
            "Alerta: %s" % (it.get("motivo") or "")[:300], "",
            "Caminhos: %s" % (", ".join("`%s`" % c for c in (it.get("caminhos") or [])) or "nenhum"), "",
            ("Commit vazio: o aviso e o pendente seguem no PR do dia (parte automática); este PR pede o "
             "replay manual, guarda a espera e tira o id da detecção." if it.get("parte_automatica") else
             "Commit vazio: o item foi revertido pelo atualizar.py; este PR guarda a espera e tira o id "
             "da detecção."), "", MARCADOR % json.dumps(marca, ensure_ascii=False)])
        return self.criar_pr(branch, "auto: %s (%s)" % (it["id"], rot), corpo, [rot])

    # -- f. CI e merge
    def gh_api(self, caminho):
        rc, out, _ = self.rodar(["gh", "api", caminho], env=self.env_gh())
        if rc != 0:
            return None
        try:
            return json.loads(out or "{}")
        except ValueError:
            return None

    def estado_ci(self, sha):
        """("verde" | "vermelho" | "pendente", motivo) do ci.yml no evento pull_request para `sha`."""
        d = self.gh_api("repos/%s/actions/runs?head_sha=%s&event=pull_request&per_page=100" % (REPO_GH, sha))
        if d is None:
            return "pendente", "API do Actions sem resposta"
        runs = [r for r in d.get("workflow_runs") or []
                if (r.get("path") or "").split("@")[0] == CI_WORKFLOW and r.get("event") == "pull_request"
                and r.get("head_sha") == sha]
        if not runs:
            return "pendente", "sem run do ci.yml (pull_request) para %s" % sha[:12]
        run = max(runs, key=lambda r: (r.get("run_attempt") or 1, r.get("id") or 0))
        if run.get("status") != "completed":
            return "pendente", "ci.yml em %s" % run.get("status")
        jd = self.gh_api("repos/%s/actions/runs/%s/jobs?per_page=100" % (REPO_GH, run.get("id")))
        if jd is None:
            return "pendente", "jobs do run %s sem resposta" % run.get("id")
        jobs = {j.get("name"): j for j in jd.get("jobs") or []}
        faltam = [n for n in CI_JOBS_EXIGIDOS if n not in jobs]
        if faltam:
            return "vermelho", "job(s) ausente(s) no ci.yml: %s" % ", ".join(faltam)
        ruins = sorted("%s=%s" % (n, j.get("conclusion")) for n, j in jobs.items()
                       if j.get("status") != "completed" or j.get("conclusion") != "success")
        if ruins or run.get("conclusion") != "success":
            return "vermelho", "ci.yml: %s" % (", ".join(ruins) or run.get("conclusion"))
        return "verde", "ci.yml verde (%s)" % ", ".join(sorted(jobs))

    def esperar_ci(self, sha, branch):
        """(verde?, motivo). Espera até CI_ESPERA; esgotado: issue e sem merge."""
        dormido, t0 = 0, time.monotonic()
        while True:
            estado, motivo = self.estado_ci(sha)
            if estado != "pendente":
                return estado == "verde", motivo
            if dormido >= CI_ESPERA or time.monotonic() - t0 >= CI_ESPERA:
                break
            self.dormir(CI_INTERVALO)
            dormido += CI_INTERVALO
        self.issue("CI sem conclusão: %s" % branch, "precisa-diogo",
                   "O CI (ci.yml, pull_request) de `%s` no sha %s não concluiu em %d min (%s). Sem merge."
                   % (branch, sha, CI_ESPERA // 60, motivo))
        return False, "CI sem conclusão em %d min (%s)" % (CI_ESPERA // 60, motivo)

    def merge(self, ref, sha):
        rc, _, _ = self.gh("pr", "merge", ref, "--rebase", "--delete-branch", "--match-head-commit", sha)
        if rc == 0:
            self.relatorio["merges"].append(ref)
        return rc == 0

    def comentar(self, ref, texto):
        self.gh("pr", "comment", ref, "--body", texto)

    def head(self):
        sha = self.git_ok("rev-parse", "HEAD").strip()
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise Falha("sha do HEAD ilegível: %r" % sha)
        return sha

    # -- i. issues
    def issue(self, titulo, rotulo, corpo):
        rc, out, _ = self.gh("issue", "list", "--state", "open", "--label", rotulo, "--limit", "200",
                             "--json", "title")
        if rc == 0 and any(i.get("title") == titulo for i in json.loads(out or "[]")):
            return False
        self.rotulo(rotulo)
        self.gh("issue", "create", "--title", titulo, "--label", rotulo, "--body", corpo)
        self.relatorio["issues"].append(titulo)
        return True

    def issues_da_deteccao(self, det, so_fontes=False):
        for fonte, ent in sorted((det.get("fontes") or {}).items()):
            if ent.get("status") != "ok":
                self.piora(STATUS_FONTE)
                self.issue("fonte-mudou: %s" % fonte, "fonte-mudou",
                           "Detecção de %s em %s: %s\n\n```json\n%s\n```" % (
                               fonte, self.hoje, ent.get("motivo") or "falha",
                               json.dumps({k: v for k, v in ent.items() if k != "etapas"}, ensure_ascii=False)[:3000]))
        for it in [] if so_fontes else det.get("itens", []):
            if (it.get("dados") or {}).get("perimetro") == "duvidosa":
                self.issue("perimetro: %s" % it["id"], "perimetro",
                           "Item %s (%s) com perímetro duvidoso: %s\n\n%s" % (
                               it["id"], it.get("classe"), it.get("motivo") or "", it.get("url") or ""))

    def job_falhou(self, motivo):
        """Issue `job-falhou`, uma aberta por vez (sem token: pela sessão do gh, como o heartbeat)."""
        try:
            self.issue("job-falhou", "job-falhou", "Execução de %s com falha: %s\n\nLog: "
                       "`~/normas-auto/logs/%s.log`." % (self.hoje, motivo[:500], self.hoje))
        except Exception as e:  # noqa: BLE001 - a issue não pode esconder a falha original
            self.log("issue job-falhou não aberta: %s" % e)

    def bloquear_push(self, bloqueio):
        """Varredura reprovada ou arquivo não revertido: nenhum push de auto/*; issue só com id e tipo."""
        self.piora(STATUS_BLOQUEIO)
        for b in bloqueio:
            self.issue("push bloqueado: %s" % b.get("id"), "push-bloqueado",
                       "Item `%s`: %s. Nenhum push de `auto/*` nesta execução (%s); o detalhe fica em "
                       "`dados/auto/%s/` na máquina do job." % (b.get("id"), b.get("problema"), self.hoje, self.hoje))
        self.relatorio["avisos"].append("push bloqueado: %s" % ", ".join(
            "%s (%s)" % (b.get("id"), b.get("problema")) for b in bloqueio))

    # -- h. heartbeat
    def heartbeat(self):
        """Grava as variáveis mesmo com falha: o ULTIMO_STATUS e o DIAS_SEM_OK dizem se foi ok."""
        e = self.ler_estado()
        try:
            dias = int(e.get("dias_sem_ok") or 0)
        except (TypeError, ValueError):
            dias = 0
        if self.status == STATUS_OK:
            dias = 0
        elif e.get("ultimo_dia") == self.hoje:
            dias = max(dias, 1)  # segunda execução do dia não conta outro dia
        else:
            dias += 1
        e.update({"ultimo_dia": self.hoje, "ultimo_status": self.status, "dias_sem_ok": dias})
        if self.semanal_ok:
            e["ultima_semanal_ok"] = self.hoje
        try:
            self.gravar_estado(e)
        except OSError as x:
            self.log("estado.json não gravado: %s" % x)
        self.gh("variable", "set", "ULTIMA_VERIFICACAO", "--body", self.agora())
        self.gh("variable", "set", "ULTIMO_STATUS", "--body", self.status)
        self.gh("variable", "set", "DIAS_SEM_OK", "--body", str(dias))

    # -- publicar (execução `todas`)
    def rodar_publicar(self, cfg):
        branch = "auto/publicar-%s" % self.hoje
        self.git_ok("checkout", "--force", "-B", branch, "origin/main")
        rc, out, _ = self.py("publicar.py", "--hoje", self.hoje)
        if rc != 0:
            raise Falha("publicar.py rc %s" % rc)
        self.git_ok("add", "-A", "--", *[c for c in CAMINHOS_DO_COMMIT if os.path.lexists(os.path.join(self.wt, c))])
        if not self.staged():
            return
        self.commit("auto: publica as versões dos plugins (%s)" % self.hoje, self.env_auto())
        if not self.token:
            return
        sha = self.head()
        self.push(branch)
        url = self.criar_pr(branch, "auto: versões dos plugins (%s)" % self.hoje,
                            "Versão semanal dos plugins (C10).\n\n```\n%s\n```" % out.strip()[-2000:],
                            ["sombra"] if cfg.get("sombra", True) else [])
        ok = (not cfg.get("sombra", True) and "publicar" in (cfg.get("classes_automaticas") or []))
        if ok and self.esperar_ci(sha, branch)[0]:
            self.merge(url, sha)

    # -- execução
    def executar(self):
        try:
            self.token = self.ler_token()
            if not self.token:
                # antes de qualquer gh: sem token, o gh cairia na sessão logada de outra conta
                self.piora(STATUS_TOKEN)
                self.log("sem token no Keychain (%s): sem gh, sem push" % TOKEN_SERVICO)
            branch = self.branch_do_dia()
            self.preparar_worktree(branch)
            cfg = self.config()
            prs = self.prs_abertos() if self.token else []
            excluir = ids_de_prs(prs)
            det = self.detectar(excluir)
            self.issues_da_deteccao(det, so_fontes=not self.token)  # sem token: pela sessão do gh
            crit, auto, diogo, resumo = self.atualizar(det, cfg)
            bloqueio = crit["conjunto"].get("bloqueio_push") or []
            if bloqueio:
                self.bloquear_push(bloqueio)
                return 0
            n = self.commits_do_dia(auto, det)
            if not self.token:
                self.relatorio["avisos"].append("sem token: %d commit(s) locais em %s, sem push" % (n, branch))
                return 0
            if n:
                sha = self.head()
                self.push(branch)
                marca = {"ids": sorted({x["id"] for x in auto}), "execucao_id": crit["execucao_id"]}
                classes = sorted({x["classe"] for x in auto})
                rot = ["sombra"] if cfg.get("sombra", True) else []
                if not crit["conjunto"].get("pr_automatico_antes_do_ci"):
                    rot.append("precisa-diogo")
                url = self.criar_pr(branch, "auto: atualização de %s" % self.hoje,
                                    resumo + "\n" + MARCADOR % json.dumps(marca, ensure_ascii=False), rot)
                ci, motivo_ci = self.esperar_ci(sha, branch)
                ok, motivo = pode_merge(crit, classes, cfg, ci)
                self.comentar(url, "Critério depois do CI (%s): %s; %s." % (
                    motivo_ci, "merge automático" if ok else "merge do Diogo", motivo))
                if ok:
                    self.merge(url, sha)
            por_id = {i["id"]: i for i in det.get("itens", [])}
            for it in diogo:
                self.pr_do_item(it, por_id.get(it["id"]))
            if self.freq == "todas":
                if self.publicar:
                    self.git_ok("fetch", "origin")
                    self.rodar_publicar(cfg)
                # semanal com sucesso: todas as fontes ok e publicar sem falha
                self.semanal_ok = all((e or {}).get("status") == "ok" for e in (det.get("fontes") or {}).values())
            return 0
        except Falha as e:
            self.log("falha: %s" % e)
            self.piora(STATUS_FALHA)
            self.relatorio["avisos"].append(str(e))
            self.job_falhou(str(e))
            return 1
        except Exception as e:  # noqa: BLE001 - erro inesperado também é falha, não "ok"
            self.log("falha inesperada: %s: %s\n%s" % (type(e).__name__, e, traceback.format_exc()))
            self.piora(STATUS_FALHA)
            self.relatorio["avisos"].append("%s: %s" % (type(e).__name__, e))
            self.job_falhou("%s: %s" % (type(e).__name__, str(e)[:300]))
            return 1
        finally:
            self.heartbeat()
            self.log("status: %s; %s" % (self.status, json.dumps(self.relatorio, ensure_ascii=False)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--clone", default=CLONE_PADRAO)
    ap.add_argument("--worktree", default=os.path.join(BASE, "worktree"))
    ap.add_argument("--hoje")
    ap.add_argument("--trava", default=os.path.join(BASE, "job.pid"))
    ap.add_argument("--herdar", type=int, help="PID do wrapper que tomou a trava (pai deste processo)")
    ap.add_argument("--sem-publicar", action="store_true")
    a = ap.parse_args(argv)
    trava = Trava(a.trava, herdar=a.herdar)
    if not trava.tomar():
        print("job: outra execução ativa (trava %s)" % a.trava)
        return 3
    try:
        aqui, wt = os.path.realpath(AQUI), os.path.realpath(os.path.join(a.worktree, "scripts"))
        if aqui != wt or os.path.realpath(a.clone) == os.path.realpath(a.worktree):
            print("job: rode o job.py do worktree (%s) com --clone do clone principal, pelo "
                  "job_diario.sh; este é %s" % (wt, aqui))
            return 1
        return Job(a.clone, a.worktree, a.hoje, publicar=not a.sem_publicar).executar()
    finally:
        trava.soltar()


if __name__ == "__main__":
    sys.exit(main())
