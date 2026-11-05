#!/usr/bin/env python3
"""Varredura do histórico do Git: dado pessoal, termo da lista privada, caractere de controle e
e-mail pessoal nos metadados, em QUALQUER versão alcançável, não só na árvore atual.

A árvore da --base (padrão main) é tratada como base já varrida por outra tarefa. Por isso o
histórico só reporta o que está em linhas que NÃO existem mais na versão atual do mesmo caminho
na base. Isso também tira do relatório o falso achado do `pii.limpar`, que não é idempotente:
sobre texto já limpo ele corta de novo em volta de "[dado pessoal retirado]", mas essas recortadas
caem em linhas que ainda existem na base.

Detectores (por blob, só nas linhas fora da base):
- pii-<regra> / pii-multipla: diff linha a linha entre o texto e `pii.limpar_contando(texto)`;
- cpf-direto / rg-direto: `pii.achar_cpfs` / `pii.achar_rgs` (as funções que o CI usa);
- termo / cnpj: `varrer_termos.varrer` (política por pasta já está lá);
- controle: `controle.CONTROLE`.
Metadados: e-mail de autor, committer e tagger fora da lista (email-metadado), mensagens de commit
e de tag anotada (pii, cpf/rg, termos).

Saídas em --saida (padrão dados/fase-5/historico, que o Git ignora):
- achados.jsonl: COM valores. Nunca versionar.
- substituicoes.txt: pares `literal:<linha>==><linha limpa>` para `git filter-repo --replace-text`.
- substituicoes-manuais.jsonl: blocos que não viram par (número de linhas diferente ou linha com
  "==>", que o filter-repo não escapa) e conflitos.jsonl (mesma linha, duas limpas diferentes).
- relatorio.json e relatorio.md: contagens, SEM nenhum valor.
- nao-lidos.jsonl: blobs que não decodificam como UTF-8 (sha e caminhos), para não sumirem.
- cache.jsonl: um registro por blob, retomável; invalida se pii.py, varrer_termos.py, controle.py,
  este script ou a lista de termos mudarem.

Saída do processo: 0 sem achado publicável; 1 com achado publicável; 2 em erro de execução
(git que falha, blob que dá exceção, lista de termos ausente). Erro nunca vira 0.
"""
import argparse
import bisect
import difflib
import hashlib
import json
import multiprocessing
import os
import re
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import controle  # noqa: E402
import pii  # noqa: E402
import varrer_termos  # noqa: E402

EXTENSOES = {".md", ".json", ".txt", ".yml", ".yaml", ".cff", ".py", ".sh", ".swift", ""}
EMAIL_OK = re.compile(r"(@users\.noreply\.github\.com|\.invalid)$|^noreply@github\.com$", re.I)
CPF_RG_VARRER = re.compile(r"^(?:CPF|RG) na linha \d+$")
AMOSTRA_LINHAS = 20
AMOSTRA_CHARS = 1000
SAIDA_PADRAO = os.path.join("dados", "fase-5", "historico")


class ErroExecucao(Exception):
    pass


# ---------------------------------------------------------------- git

def _git(repo, *args, entrada=None):
    try:
        r = subprocess.run(["git", "-C", repo] + list(args), input=entrada,
                           capture_output=True, check=True)
    except OSError:
        raise ErroExecucao("git indisponível") from None
    except subprocess.CalledProcessError as e:
        msg = e.stderr.decode("utf-8", "replace").strip().splitlines()
        raise ErroExecucao("git %s falhou: %s" % (args[0], msg[0][:200] if msg else "sem mensagem")) from None
    return r.stdout


class Leitor:
    """Um `git cat-file --batch` aberto: lê blobs em sequência, sem carregar o repositório."""

    def __init__(self, repo):
        self.p = subprocess.Popen(["git", "-C", repo, "cat-file", "--batch"], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def ler(self, sha):
        """Bytes do blob, ou None se o objeto não existe."""
        self.p.stdin.write(sha.encode("ascii") + b"\n")
        self.p.stdin.flush()
        cab = self.p.stdout.readline()
        if not cab:
            raise ErroExecucao("git cat-file encerrou")
        partes = cab.split()
        if len(partes) < 2 or partes[1] == b"missing":
            return None
        tam = int(partes[2])
        dados = self.p.stdout.read(tam)
        resto = self.p.stdout.read(1)
        if len(dados) != tam or resto != b"\n":
            raise ErroExecucao("leitura truncada no git cat-file")
        return dados

    def fechar(self):
        try:
            self.p.stdin.close()
            self.p.stdout.close()
        except OSError:
            pass
        self.p.wait()


def listar_objetos(repo, refs):
    """rev-list --objects: [(sha, caminho)] dos objetos que têm caminho (blobs e árvores)."""
    saida = _git(repo, "rev-list", "--objects", *refs).decode("utf-8", "replace")
    com_caminho = []
    for linha in saida.split("\n"):
        if not linha:
            continue
        sha, _, caminho = linha.partition(" ")
        if caminho:
            com_caminho.append((sha, caminho))
    return com_caminho


def filtrar_blobs(repo, entradas):
    """Mantém só os blobs (git cat-file --batch-check)."""
    if not entradas:
        return []
    entrada = ("\n".join(s for s, _ in entradas) + "\n").encode("ascii")
    saida = _git(repo, "cat-file", "--batch-check=%(objectname) %(objecttype)", entrada=entrada)
    tipos = saida.decode("ascii", "replace").split("\n")
    tipos = [t for t in tipos if t]
    if len(tipos) != len(entradas):
        raise ErroExecucao("batch-check devolveu %d linhas para %d objetos" % (len(tipos), len(entradas)))
    blobs = []
    for (sha, caminho), t in zip(entradas, tipos):
        partes = t.split()
        if len(partes) != 2 or partes[0] != sha or partes[1] == "missing":
            raise ErroExecucao("objeto ausente no repositório")
        if partes[1] == "blob":
            blobs.append((sha, caminho))
    return blobs


def varrer_log_raw(repo, refs, blobs):
    """Uma passada de `git log --raw`: todos os caminhos em que cada blob aparece e os commits que o
    introduzem (do mais antigo ao mais novo). O rev-list --objects só dá um caminho por objeto."""
    p = subprocess.Popen(["git", "-C", repo, "-c", "core.quotepath=off", "log", "--topo-order", "--reverse",
                          "--root", "--no-renames", "--raw", "--no-abbrev", "--format=@%H"] + list(refs),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    atual = None
    for bruta in p.stdout:
        linha = bruta.decode("utf-8", "replace").rstrip("\n")
        if linha.startswith("@"):
            atual = linha[1:]
        elif linha.startswith(":") and "\t" in linha:
            meta, caminho = linha.split("\t", 1)
            campos = meta.split()
            if len(campos) < 5:
                continue
            sha = campos[3]
            if sha in blobs:
                blobs[sha]["caminhos"].add(caminho)
                cs = blobs[sha]["commits"]
                if atual and atual not in cs and len(cs) < 5:
                    cs.append(atual)
    p.stdout.close()
    err = p.stderr.read()
    if p.wait() != 0:
        raise ErroExecucao("git log --raw falhou: %s" % err.decode("utf-8", "replace").strip()[:200])


def arvore_da_base(repo, base):
    """caminho -> sha do blob, na árvore da base (git ls-tree -r)."""
    saida = _git(repo, "ls-tree", "-r", "-z", base).decode("utf-8", "replace")
    mapa = {}
    for item in saida.split("\0"):
        if not item or "\t" not in item:
            continue
        meta, caminho = item.split("\t", 1)
        campos = meta.split()
        if len(campos) == 3 and campos[1] == "blob":
            mapa[caminho] = campos[2]
    return mapa


# ---------------------------------------------------------------- análise de um texto

def _amostra(linhas, indices):
    ind = sorted(indices)[:AMOSTRA_LINHAS]
    return "\n".join(linhas[i][:AMOSTRA_CHARS] for i in ind)


def _blocos(a, b):
    """Blocos alterados (i1, i2, j1, j2) entre as linhas originais e as limpas, sem linhas iguais
    nas pontas. O pii só troca trechos por um marcador sem quebra de linha: com o mesmo número de
    linhas, o alinhamento por índice é exato; com menos linhas, alguma troca engoliu uma quebra."""
    if len(a) == len(b):
        blocos, i, n = [], 0, len(a)
        while i < n:
            if a[i] != b[i]:
                j = i
                while j < n and a[j] != b[j]:
                    j += 1
                blocos.append((i, j, i, j))
                i = j
            else:
                i += 1
        return blocos
    ini, menor = 0, min(len(a), len(b))
    while ini < menor and a[ini] == b[ini]:
        ini += 1
    fim = 0
    while fim < menor - ini and a[-1 - fim] == b[-1 - fim]:
        fim += 1
    ma, mb = a[ini:len(a) - fim], b[ini:len(b) - fim]
    sm = difflib.SequenceMatcher(None, ma, mb, autojunk=len(ma) * len(mb) > 4_000_000)
    blocos = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        i1, i2, j1, j2 = i1 + ini, i2 + ini, j1 + ini, j2 + ini
        while i1 < i2 and j1 < j2 and a[i1] == b[j1]:
            i1 += 1
            j1 += 1
        while i1 < i2 and j1 < j2 and a[i2 - 1] == b[j2 - 1]:
            i2 -= 1
            j2 -= 1
        if i1 < i2 or j1 < j2:
            blocos.append((i1, i2, j1, j2))
    return blocos


def _regra_pii(cont):
    return "pii-" + next(iter(cont)) if len(cont) == 1 else "pii-multipla"


def _par(original, limpa):
    """Par de substituição sem o \\r final comum (o filter-repo tira \\r\\n do fim da linha)."""
    if original.endswith("\r") and limpa.endswith("\r"):
        return original[:-1], limpa[:-1]
    return original, limpa


def linha_substituicao(original, limpa):
    """`literal:<original>==><limpa>` ou None se não der para escrever no formato do filter-repo.

    O filter-repo lê a linha em bytes, tira \\r\\n do fim, parte no ÚLTIMO "==>" e trata o prefixo
    "literal:" antes do texto; com o prefixo literal:, original que começa com regex:/glob:/literal:
    não é problema. Sem como escapar um "==>" (confirmado só pela leitura do código do filter-repo,
    não instalado aqui), o par com "==>" em qualquer lado vai para os manuais.
    """
    if not original or original == limpa:
        return None
    if "==>" in original or "==>" in limpa or "\n" in original or "\n" in limpa or "\r" in limpa[-1:]:
        return None
    return "literal:%s==>%s" % (original, limpa)


def _achados_pii(texto, linhas, fora):
    limpo, cont = pii.limpar_contando(texto)
    if limpo == texto:
        return []
    b = limpo.split("\n")
    achados = []
    for i1, i2, j1, j2 in _blocos(linhas, b):
        if i1 == i2:
            continue
        idx_fora = [i for i in range(i1, i2) if i in fora]
        if not idx_fora:
            continue
        orig, lim = linhas[i1:i2], b[j1:j2]
        t_orig, t_lim = "\n".join(orig), "\n".join(lim)
        c_bloco = cont
        l2, c2 = pii.limpar_contando(t_orig)
        if c2 and l2 == t_lim:
            c_bloco = c2
        a = {"regra": _regra_pii(c_bloco), "linhas": list(range(i1 + 1, i2 + 1)),
             "linhas_fora_da_base": [i + 1 for i in idx_fora], "original": t_orig, "limpo": t_lim,
             "pares": None}
        if len(orig) == len(lim):
            a["pares"] = [list(_par(orig[k], lim[k])) for k in range(len(orig))
                          if (i1 + k) in fora and orig[k] != lim[k]]
        achados.append(a)
    return achados


def _achados_diretos(texto, linhas, fora):
    inicios, pos = [], 0
    for l in linhas:
        inicios.append(pos)
        pos += len(l) + 1
    achados = []
    for regra, achar in (("cpf-direto", pii.achar_cpfs), ("rg-direto", pii.achar_rgs)):
        hit = set()
        for a, _ in achar(texto):
            i = bisect.bisect_right(inicios, a) - 1
            if i in fora:
                hit.add(i)
        if hit:
            achados.append({"regra": regra, "linhas": [i + 1 for i in sorted(hit)],
                            "original": _amostra(linhas, hit), "limpo": None})
    return achados


def classes_de_caminho(caminhos):
    """Um caminho representante por classe de política (julgados x o resto)."""
    reps = {}
    for c in sorted(caminhos):
        reps.setdefault(bool(varrer_termos.PASTA_JULGADOS.match(c)), c)
    return list(reps.values())


def _tokens(textos, termos, liberadas):
    """Achados de termo e CNPJ de `varrer`: {(caminho, token)}; CPF e RG ficam de fora (já vistos)."""
    res = set()
    for s in varrer_termos.varrer(textos, termos, liberadas):
        for caminho in textos:
            pre = caminho + ": "
            if s.startswith(pre):
                tok = s[len(pre):]
                if not CPF_RG_VARRER.match(tok):
                    res.add((caminho, tok))
                break
    return res


def _achados_termos(linhas, fora, caminhos, termos, liberadas):
    termos_set = set(termos)
    reps = classes_de_caminho(caminhos)
    idx = sorted(fora)
    junto = "\n".join(linhas[i] for i in idx)
    tokens = _tokens({r: junto for r in reps}, termos, liberadas)
    if not tokens:
        return []
    por_regra, nao_localizado = {}, set()
    for rep in reps:
        achados_rep = {t for c, t in tokens if c == rep}
        achou = set()
        for i in idx:
            for _, tok in _tokens({rep: linhas[i]}, termos, liberadas):
                regra = "termo" if tok in termos_set else "cnpj"
                por_regra.setdefault(regra, set()).add(i)
                achou.add(tok)
        for tok in achados_rep - achou:
            nao_localizado.add("termo" if tok in termos_set else "cnpj")
    achados = []
    for regra in sorted(set(por_regra) | nao_localizado):
        ind = por_regra.get(regra, set())
        a = {"regra": regra, "linhas": [i + 1 for i in sorted(ind)],
             "original": _amostra(linhas, ind), "limpo": None}
        if regra in nao_localizado:
            a["linha_nao_localizada"] = True
        achados.append(a)
    return achados


def _achados_controle(linhas, fora):
    hit = [i for i in sorted(fora) if controle.CONTROLE.search(linhas[i])]
    if not hit:
        return []
    return [{"regra": "controle", "linhas": [i + 1 for i in hit], "original": _amostra(linhas, hit),
             "limpo": None}]


def analisar_texto(texto, caminhos, base_linhas, termos, liberadas):
    """Achados (sem valores de contexto do git) das linhas de `texto` que não estão em `base_linhas`."""
    linhas = texto.split("\n")
    fora = {i for i, l in enumerate(linhas) if l not in base_linhas}
    if not fora:
        return []
    return (_achados_pii(texto, linhas, fora) + _achados_diretos(texto, linhas, fora)
            + _achados_termos(linhas, fora, caminhos, termos, liberadas)
            + _achados_controle(linhas, fora))


def analisar_mensagem(texto, termos, liberadas):
    """Achados numa mensagem de commit ou de tag: lista de (regra, original, limpo)."""
    res = []
    limpo, cont = pii.limpar_contando(texto)
    if limpo != texto:
        res.append((_regra_pii(cont), texto, limpo))
    for regra, achar in (("cpf-direto", pii.achar_cpfs), ("rg-direto", pii.achar_rgs)):
        if achar(texto):
            res.append((regra, texto, None))
    termos_set = set(termos)
    for _, tok in sorted(_tokens({"(mensagem)": texto}, termos, liberadas)):
        res.append(("termo" if tok in termos_set else "cnpj", texto, None))
    return res


# ---------------------------------------------------------------- worker

_W = {}


def _iniciar(repo, termos, liberadas):
    _W["leitor"] = Leitor(repo)
    _W["termos"] = termos
    _W["liberadas"] = liberadas
    _W["bases"] = {}


def _linhas_da_base(sha):
    cache = _W["bases"]
    if sha not in cache:
        if len(cache) >= 8:
            cache.pop(next(iter(cache)))
        dados = _W["leitor"].ler(sha)
        if dados is None:
            raise ErroExecucao("blob da base ausente")
        cache[sha] = set(dados.decode("utf-8", "replace").split("\n"))
    return cache[sha]


def _local_do_erro(e):
    tb = e.__traceback__
    while tb and tb.tb_next:
        tb = tb.tb_next
    return "%s em %s:%d" % (type(e).__name__, os.path.basename(tb.tb_frame.f_code.co_filename),
                            tb.tb_lineno) if tb else type(e).__name__


def processar(tarefa):
    """tarefa = (sha, caminhos, shas_da_base). Nunca levanta: erro vira status "erro" (sem valores)."""
    sha, caminhos, bases = tarefa
    try:
        dados = _W["leitor"].ler(sha)
        if dados is None:
            raise ErroExecucao("blob ausente")
        try:
            texto = dados.decode("utf-8")
        except UnicodeDecodeError:
            return {"blob": sha, "status": "nao-lido", "achados": []}
        base = set()
        for b in bases:
            base |= _linhas_da_base(b)
        achados = analisar_texto(texto, caminhos, base, _W["termos"], _W["liberadas"])
        return {"blob": sha, "status": "ok", "achados": achados}
    except Exception as e:  # noqa: BLE001 - qualquer falha vira "erro", nunca "limpo"
        return {"blob": sha, "status": "erro", "erro": _local_do_erro(e)}


# ---------------------------------------------------------------- cache

def versao_regras(caminho_termos):
    h = hashlib.sha256()
    for nome in ("pii.py", "varrer_termos.py", "controle.py", "varrer_historico.py"):
        with open(os.path.join(AQUI, nome), "rb") as f:
            h.update(hashlib.sha256(f.read()).digest())
    with open(caminho_termos, "rb") as f:
        h.update(hashlib.sha256(f.read()).digest())
    return h.hexdigest()


def contexto_do_blob(caminhos, bases):
    return hashlib.sha1(json.dumps([sorted(caminhos), sorted(bases)]).encode("utf-8")).hexdigest()


def carregar_cache(caminho, versao):
    """{blob: registro} dos registros válidos. Reescreve o arquivo se houver lixo ou versão velha."""
    validos, sujo = {}, False
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            for linha in f:
                if not linha.strip():
                    continue
                try:
                    r = json.loads(linha)
                except ValueError:
                    sujo = True
                    continue
                if r.get("regras") == versao and "blob" in r:
                    validos[r["blob"]] = r
                else:
                    sujo = True
        if sujo:
            tmp = caminho + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                for r in validos.values():
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            os.replace(tmp, caminho)
    return validos


# ---------------------------------------------------------------- metadados

def _ler_commits(repo, refs):
    """Commits das refs: hash, autor, committer (nome e e-mail) e mensagem."""
    saida = _git(repo, "log", "--format=%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%B%x1e", *refs)
    commits = []
    for rec in saida.decode("utf-8", "replace").split("\x1e"):
        rec = rec.lstrip("\n")
        if not rec.strip():
            continue
        campos = rec.split("\x1f", 5)
        if len(campos) != 6:
            raise ErroExecucao("registro de commit malformado")
        commits.append(dict(zip(("hash", "autor", "email_autor", "committer", "email_committer", "mensagem"),
                                campos)))
    return commits


def _tags_anotadas(repo):
    saida = _git(repo, "for-each-ref", "refs/tags",
                 "--format=%(refname)%1f%(objecttype)%1f%(taggername)%1f%(taggeremail)%1f%(contents)%1e")
    tags = []
    for rec in saida.decode("utf-8", "replace").split("\x1e"):
        rec = rec.lstrip("\n")
        if not rec.strip():
            continue
        campos = rec.split("\x1f", 4)
        if len(campos) != 5:
            raise ErroExecucao("registro de tag malformado")
        if campos[1] == "tag":
            tags.append({"tag": campos[0], "tagger": campos[2], "email": campos[3].strip("<>"),
                         "mensagem": campos[4]})
    return tags


def achados_de_metadados(repo, refs, alcancaveis, termos, liberadas):
    """Achados de metadados e contagem de commits lidos."""
    achados = []
    commits = _ler_commits(repo, refs)
    tags = _tags_anotadas(repo)
    por_email = {}
    termos_set = set(termos)
    for c in commits:
        for papel, em in (("autor", c["email_autor"]), ("committer", c["email_committer"])):
            if em and not EMAIL_OK.search(em.strip()):
                d = por_email.setdefault(em, {"papeis": set(), "commits": []})
                d["papeis"].add(papel)
                if c["hash"] not in d["commits"]:
                    d["commits"].append(c["hash"])
        for regra, orig, limpo in analisar_mensagem(c["mensagem"], termos, liberadas):
            achados.append({"tipo": "commit-mensagem", "commit": c["hash"], "regra": "msg-" + regra,
                            "original": orig, "limpo": limpo, "publicavel": c["hash"] in alcancaveis})
        nomes = "\n".join((c["autor"], c["committer"], c["email_autor"], c["email_committer"]))
        for _, tok in sorted(_tokens({"(mensagem)": nomes}, termos, liberadas)):
            achados.append({"tipo": "commit-autoria", "commit": c["hash"],
                            "regra": "termo" if tok in termos_set else "cnpj", "original": nomes,
                            "limpo": None, "publicavel": c["hash"] in alcancaveis})
    for t in tags:
        if t["email"] and not EMAIL_OK.search(t["email"]):
            d = por_email.setdefault(t["email"], {"papeis": set(), "commits": []})
            d["papeis"].add("tagger")
            d.setdefault("tags", []).append(t["tag"])
        for regra, orig, limpo in analisar_mensagem(t["mensagem"], termos, liberadas):
            achados.append({"tipo": "tag-mensagem", "tag": t["tag"], "regra": "msg-" + regra,
                            "original": orig, "limpo": limpo, "publicavel": True})
    for em, d in sorted(por_email.items()):
        achados.append({"tipo": "metadado", "regra": "email-metadado", "original": em,
                        "papeis": sorted(d["papeis"]), "commits": d["commits"],
                        "tags": d.get("tags", []),
                        "publicavel": bool(d.get("tags")) or any(h in alcancaveis for h in d["commits"])})
    return achados, len(commits), len(tags)


# ---------------------------------------------------------------- saídas

def montar_substituicoes(achados):
    """(linhas do substituicoes.txt, manuais, conflitos) a partir dos achados de blob com regra pii-*."""
    pares, manuais = {}, []
    for a in achados:
        if a.get("tipo") != "blob" or not a["regra"].startswith("pii-"):
            continue
        base = {"blob": a["blob"], "caminhos": a["caminhos"], "linhas": a["linhas"],
                "original": a["original"], "limpo": a["limpo"]}
        if a.get("pares") is None:
            manuais.append(dict(base, motivo="numero-de-linhas-diferente"))
            continue
        for o, l in a["pares"]:
            if linha_substituicao(o, l) is None:
                manuais.append(dict(base, original=o, limpo=l, motivo="nao-escapavel"))
                continue
            pares.setdefault(o, {}).setdefault(l, set()).add(a["blob"])
    linhas, conflitos = [], []
    # Mais longo primeiro: o filter-repo aplica os literais na ordem do arquivo, e uma linha curta
    # que fosse trecho de uma longa a deixaria sem casar.
    for o in sorted(pares, key=lambda x: (-len(x), x)):
        limpas = pares[o]
        if len(limpas) > 1:
            conflitos.append({"original": o, "limpas": sorted(limpas),
                              "blobs": sorted(set().union(*limpas.values()))})
            continue
        (l,) = limpas
        linhas.append(linha_substituicao(o, l))
    return linhas, manuais, conflitos


def _prefixo(caminho):
    """Até 2 níveis de pasta; o nome do arquivo não entra (pode ser um valor)."""
    return "/".join(caminho.split("/")[:-1][:2]) or "(raiz)"


def _escrever_jsonl(caminho, registros):
    with open(caminho, "w", encoding="utf-8") as f:
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def montar_relatorio(achados, contagens, meta, tempo, codigo):
    por_regra, por_prefixo, por_pub = {}, {}, {"publicavel": 0, "nao-publicavel": 0}
    por_regra_pub = {}
    for a in achados:
        r = a["regra"]
        por_regra[r] = por_regra.get(r, 0) + 1
        chave = "publicavel" if a["publicavel"] else "nao-publicavel"
        por_pub[chave] += 1
        por_regra_pub.setdefault(r, {"publicavel": 0, "nao-publicavel": 0})[chave] += 1
        for p in sorted({_prefixo(c) for c in a.get("caminhos", [])}):
            por_prefixo[p] = por_prefixo.get(p, 0) + 1
    return {
        "base": meta["base"], "refs": meta["refs"], "versao_regras": meta["versao"],
        "blobs": contagens,
        "achados": {"total": len(achados), "por_publicavel": por_pub, "por_regra": dict(sorted(por_regra.items())),
                    "por_regra_e_publicavel": dict(sorted(por_regra_pub.items())),
                    "por_prefixo_de_caminho": dict(sorted(por_prefixo.items()))},
        "metadados": meta["metadados"],
        "tempo_segundos": round(tempo, 1),
        "codigo_de_saida": codigo,
    }


def relatorio_md(rel):
    b, a, m = rel["blobs"], rel["achados"], rel["metadados"]
    L = ["# Varredura do histórico (sem valores)", "",
         "- base: `%s`; refs: `%s`" % (rel["base"], " ".join(rel["refs"])),
         "- versão das regras: `%s`" % rel["versao_regras"][:16],
         "- tempo: %s s; código de saída: %d" % (rel["tempo_segundos"], rel["codigo_de_saida"]), "",
         "## Blobs", ""]
    nomes = [("alcancaveis", "alcançáveis (qualquer tipo de arquivo)"), ("ignorados_por_extensao", "ignorados pela extensão"),
             ("considerados", "considerados"), ("identicos_a_base", "idênticos à base (pulados)"),
             ("processados_agora", "processados nesta execução"), ("do_cache", "reaproveitados do cache"),
             ("nao_lidos", "NÃO LIDOS (não decodificam como UTF-8)"), ("erros", "ERROS de processamento")]
    L += ["- %s: %d" % (t, b[k]) for k, t in nomes]
    L += ["", "## Achados", "", "- total: %d (publicáveis: %d; não publicáveis: %d)" % (
        a["total"], a["por_publicavel"]["publicavel"], a["por_publicavel"]["nao-publicavel"]), ""]
    if a["por_regra_e_publicavel"]:
        L += ["| regra | publicável | não publicável |", "|---|---|---|"]
        L += ["| %s | %d | %d |" % (r, v["publicavel"], v["nao-publicavel"])
              for r, v in a["por_regra_e_publicavel"].items()]
        L.append("")
    if a["por_prefixo_de_caminho"]:
        L += ["Por prefixo de caminho (2 níveis):", ""]
        L += ["- `%s`: %d" % (p, n) for p, n in a["por_prefixo_de_caminho"].items()]
        L.append("")
    L += ["## Metadados", "", "- commits lidos: %d; tags anotadas: %d" % (m["commits_lidos"], m["tags_anotadas"]),
          "- commits com e-mail fora da lista aceita: %d" % m["commits_com_email_fora_da_lista"]["quantidade"]]
    L += ["  - `%s`" % h for h in m["commits_com_email_fora_da_lista"]["hashes"]]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- principal

def _extensao_ok(caminho):
    return os.path.splitext(os.path.basename(caminho))[1].lower() in EXTENSOES


def _saida_segura(repo, saida):
    """A saída tem valores: dentro do repo, só sob dados/ (que o Git ignora)."""
    r, s = os.path.realpath(repo), os.path.realpath(saida)
    if s == r or s.startswith(r + os.sep):
        return s.startswith(os.path.join(r, "dados") + os.sep)
    return True


def executar(args):
    t0 = time.time()
    repo = os.path.abspath(args.repo)
    if not os.path.isdir(repo):
        raise ErroExecucao("repositório inexistente")
    repo = os.path.realpath(_git(repo, "rev-parse", "--show-toplevel").decode("utf-8").strip())
    saida = os.path.abspath(args.saida or os.path.join(repo, SAIDA_PADRAO))
    if not _saida_segura(repo, saida):
        raise ErroExecucao("a saída tem valores e, dentro do repositório, tem de ficar sob dados/")
    refs = args.refs or ["--all"]

    caminho_termos = args.termos
    if not caminho_termos:
        antes = os.getcwd()
        os.chdir(repo)
        try:
            caminho_termos = varrer_termos._caminho_lista()
        finally:
            os.chdir(antes)
    termos = varrer_termos.carregar_termos(caminho_termos) if caminho_termos else None
    if termos is None:
        raise ErroExecucao("lista de termos não encontrada (--termos, NORMAS_TERMOS ou normas.termos)")
    liberadas = varrer_termos.carregar_liberadas(caminho_termos)
    versao = versao_regras(caminho_termos)

    _git(repo, "rev-parse", "--verify", "--quiet", args.base + "^{commit}")
    os.makedirs(saida, exist_ok=True)

    # 1. blobs, caminhos e commits
    todos = filtrar_blobs(repo, listar_objetos(repo, refs))
    blobs = {}
    for sha, caminho in todos:
        blobs.setdefault(sha, {"caminhos": set(), "commits": []})["caminhos"].add(caminho)
    varrer_log_raw(repo, refs, blobs)
    considerados = {s: d for s, d in blobs.items() if any(_extensao_ok(c) for c in d["caminhos"])}

    # 2. base e alcance
    mapa_base = arvore_da_base(repo, args.base)
    alcancaveis = {l.split(" ", 1)[0] for l in
                   _git(repo, "rev-list", "--objects", args.base, "--tags").decode("utf-8", "replace").split("\n") if l}

    # 3. tarefas
    cache = carregar_cache(os.path.join(saida, "cache.jsonl"), versao)
    contagens = {"alcancaveis": len(blobs), "ignorados_por_extensao": len(blobs) - len(considerados),
                 "considerados": len(considerados), "identicos_a_base": 0, "processados_agora": 0,
                 "do_cache": 0, "nao_lidos": 0, "erros": 0}
    tarefas, resultados, contexto, nao_lidos = [], {}, {}, []
    for sha in sorted(considerados):
        d = considerados[sha]
        bases = sorted({mapa_base[c] for c in d["caminhos"] if c in mapa_base})
        if sha in bases:
            contagens["identicos_a_base"] += 1
            continue
        ctx = contexto_do_blob(d["caminhos"], bases)
        contexto[sha] = (ctx, bases)
        r = cache.get(sha)
        if r and r.get("contexto") == ctx:
            resultados[sha] = r
            contagens["do_cache"] += 1
        else:
            tarefas.append((sha, sorted(d["caminhos"]), bases))

    # 4. processa
    if tarefas:
        arq_cache = open(os.path.join(saida, "cache.jsonl"), "a", encoding="utf-8")
        try:
            if args.processos <= 1:
                _iniciar(repo, termos, liberadas)
                try:
                    gerador = map(processar, tarefas)
                    _consumir(gerador, resultados, contexto, versao, arq_cache, contagens)
                finally:
                    _W["leitor"].fechar()
            else:
                with multiprocessing.Pool(args.processos, initializer=_iniciar,
                                          initargs=(repo, termos, liberadas)) as pool:
                    _consumir(pool.imap_unordered(processar, tarefas, chunksize=4), resultados, contexto,
                              versao, arq_cache, contagens)
        finally:
            arq_cache.close()

    # 5. achados de blob
    achados = []
    for sha, r in resultados.items():
        if r["status"] == "nao-lido":
            contagens["nao_lidos"] += 1
            nao_lidos.append({"blob": sha, "caminhos": sorted(considerados[sha]["caminhos"])})
            continue
        d = considerados[sha]
        cfb = not any(c in mapa_base for c in d["caminhos"])
        for a in r["achados"]:
            achados.append(dict(a, tipo="blob", blob=sha, caminhos=sorted(d["caminhos"]),
                                publicavel=sha in alcancaveis,
                                primeiro_commit=d["commits"][0] if d["commits"] else None,
                                commits=d["commits"], caminho_fora_da_base=cfb))

    # 6. metadados
    ach_meta, n_commits, n_tags = achados_de_metadados(repo, refs, alcancaveis, termos, liberadas)
    achados += ach_meta
    achados.sort(key=lambda a: (not a["publicavel"], a["regra"], a.get("blob") or a.get("commit") or ""))

    # 7. escrita
    _escrever_jsonl(os.path.join(saida, "achados.jsonl"), achados)
    linhas_sub, manuais, conflitos = montar_substituicoes(achados)
    with open(os.path.join(saida, "substituicoes.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(l + "\n" for l in linhas_sub))
    _escrever_jsonl(os.path.join(saida, "substituicoes-manuais.jsonl"), manuais)
    _escrever_jsonl(os.path.join(saida, "conflitos.jsonl"), conflitos)
    _escrever_jsonl(os.path.join(saida, "nao-lidos.jsonl"), nao_lidos)

    emails = [a for a in ach_meta if a["regra"] == "email-metadado"]
    hashes = sorted({h for a in emails for h in a["commits"]})
    meta = {"base": args.base, "refs": refs, "versao": versao,
            "metadados": {"commits_lidos": n_commits, "tags_anotadas": n_tags,
                          "commits_com_email_fora_da_lista": {"quantidade": len(hashes), "hashes": hashes}}}
    publicavel = any(a["publicavel"] for a in achados)
    codigo = 2 if contagens["erros"] else (1 if publicavel else 0)
    rel = montar_relatorio(achados, contagens, meta, time.time() - t0, codigo)
    with open(os.path.join(saida, "relatorio.json"), "w", encoding="utf-8") as f:
        json.dump(rel, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(os.path.join(saida, "relatorio.md"), "w", encoding="utf-8") as f:
        f.write(relatorio_md(rel))
    _resumo(rel, saida, len(manuais), len(conflitos))
    return codigo


def _consumir(gerador, resultados, contexto, versao, arq_cache, contagens):
    for r in gerador:
        contagens["processados_agora"] += 1
        if r["status"] == "erro":
            contagens["erros"] += 1
            print("erro ao processar um blob: %s" % r["erro"], file=sys.stderr)
            continue
        ctx, _ = contexto[r["blob"]]
        reg = dict(r, regras=versao, contexto=ctx)
        resultados[r["blob"]] = reg
        arq_cache.write(json.dumps(reg, ensure_ascii=False) + "\n")
        arq_cache.flush()


def _resumo(rel, saida, n_manuais, n_conflitos):
    b, a = rel["blobs"], rel["achados"]
    print("Varredura do histórico (base %s; sem valores)" % rel["base"])
    print("blobs: %d considerados, %d idênticos à base, %d processados agora, %d do cache, %d não lidos, %d erros"
          % (b["considerados"], b["identicos_a_base"], b["processados_agora"], b["do_cache"], b["nao_lidos"],
             b["erros"]))
    print("achados: %d (publicáveis %d, não publicáveis %d)" % (
        a["total"], a["por_publicavel"]["publicavel"], a["por_publicavel"]["nao-publicavel"]))
    for r, v in a["por_regra"].items():
        print("  %s: %d" % (r, v))
    print("commits com e-mail fora da lista: %d" % rel["metadados"]["commits_com_email_fora_da_lista"]["quantidade"])
    print("substituições manuais: %d; conflitos: %d" % (n_manuais, n_conflitos))
    if b["nao_lidos"]:
        print("ATENÇÃO: %d blob(s) não lidos (não decodificam como UTF-8); ver nao-lidos.jsonl" % b["nao_lidos"])
    if b["erros"]:
        print("ERRO: %d blob(s) deram erro; o resultado é incompleto" % b["erros"])
    print("saída: %s (%.1f s)" % (saida, rel["tempo_segundos"]))


def _parser():
    p = argparse.ArgumentParser(description="Varre o histórico do Git atrás de dado pessoal (sem imprimir valores).")
    p.add_argument("--repo", default=os.path.dirname(AQUI), help="raiz do repo (padrão: a deste script)")
    p.add_argument("--refs", nargs="+", default=["--all"], help="refs a varrer (padrão: --all)")
    p.add_argument("--base", default="main", help="ref tratada como atual e já varrida (padrão: main)")
    p.add_argument("--saida", default=None, help="diretório de saída (padrão: <repo>/dados/fase-5/historico)")
    p.add_argument("--processos", type=int, default=os.cpu_count() or 1)
    p.add_argument("--termos", default=None, help="lista de termos (padrão: normas.termos do git config)")
    return p


def main(argv=None):
    try:
        args = _parser().parse_args(argv)
    except SystemExit as e:
        return 2 if e.code not in (0, None) else 0
    try:
        return executar(args)
    except ErroExecucao as e:
        print("erro de execução: %s" % e, file=sys.stderr)
    except Exception as e:  # noqa: BLE001 - nunca vira 0
        print("erro de execução: %s" % _local_do_erro(e), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
