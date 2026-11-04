#!/usr/bin/env python3
"""Versão semanal dos plugins (Fase 4, C10; chamado pelo job às segundas).

Uso:
  python3 scripts/publicar.py [--hoje AAAA-MM-DD] [--raiz REPO]
  python3 scripts/publicar.py --registrar        # só grava o hash da versão atual (sem subir)
  python3 scripts/publicar.py --verificar        # saída 1 se algum hash registrado não bate

Para cada plugin de `.claude-plugin/marketplace.json` cujo conteúdo difere do hash registrado em
`fontes/versoes-plugins.json`:
- sobe o PATCH em `plugins/<p>/.claude-plugin/plugin.json` e no `marketplace.json`, juntos;
- grava o hash novo e a versão no registro.
Sempre: `conferido_em` no registro (o `indice.py` gera dele a linha "Fontes conferidas até
AAAA-MM-DD" no `indice.md` de cada plugin) e, havendo versão nova, a linha "Dados até
AAAA-MM-DD: N atos, M julgados" no CHANGELOG.md.

Hash do conteúdo (`hash_plugin`, usado também pela vigia): sha256 de caminho relativo e bytes de
cada arquivo do plugin, em ordem, fora `.claude-plugin/plugin.json` (onde está a versão) e a
linha "Fontes conferidas até" dos `indice.md` (muda toda semana sem mudar o dado). Plugin fora do
registro é registrado na versão atual, sem subir.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(AQUI, ".."))
REGISTRO = os.path.join("fontes", "versoes-plugins.json")
MARKETPLACE = os.path.join(".claude-plugin", "marketplace.json")
LINHA_CONFERIDO = "Fontes conferidas até"
# o que o .gitignore deixa fora do Git não entra no hash (a vigia calcula no checkout do runner)
IGNORAR = {".DS_Store", ".env"}
IGNORAR_EXT = (".pdf", ".docx", ".xlsx")


def ler_json(caminho, padrao=None):
    if not os.path.exists(caminho):
        return padrao
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def gravar_json(caminho, dado):
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(json.dumps(dado, ensure_ascii=False, indent=2) + "\n")


def _conteudo_para_hash(rel, dados):
    if os.path.basename(rel) == "indice.md":
        linhas = dados.split(b"\n")
        alvo = LINHA_CONFERIDO.encode("utf-8")
        dados = b"\n".join(l for l in linhas if not l.startswith(alvo))
    return dados


def hash_plugin(pasta):
    """sha256 do conteúdo do plugin em `pasta` (ver docstring do módulo)."""
    h = hashlib.sha256()
    arquivos = []
    for dirpath, dirs, nomes in os.walk(pasta):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for n in nomes:
            if n in IGNORAR or n.endswith(IGNORAR_EXT) or os.path.islink(os.path.join(dirpath, n)):
                continue
            rel = os.path.relpath(os.path.join(dirpath, n), pasta).replace(os.sep, "/")
            if rel == ".claude-plugin/plugin.json":
                continue
            arquivos.append(rel)
    for rel in sorted(arquivos):
        with open(os.path.join(pasta, *rel.split("/")), "rb") as f:
            dados = f.read()
        h.update(rel.encode("utf-8") + b"\0")
        h.update(_conteudo_para_hash(rel, dados) + b"\0")
    return h.hexdigest()


def plugins_do_marketplace(raiz):
    mk = ler_json(os.path.join(raiz, MARKETPLACE), {})
    return [(p["name"], os.path.normpath(os.path.join(raiz, p["source"])), p.get("version"))
            for p in mk.get("plugins", [])]


def versao_do_plugin(pasta):
    return (ler_json(os.path.join(pasta, ".claude-plugin", "plugin.json"), {}) or {}).get("version")


def sobe_patch(versao):
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", versao or "")
    if not m:
        raise ValueError("versão fora do semver: %r" % versao)
    return "%s.%s.%d" % (m.group(1), m.group(2), int(m.group(3)) + 1)


def chave_versao(v):
    return tuple(int(x) for x in v.lstrip("v").split("."))


def gravar_versao(raiz, nome, pasta, nova):
    """A versão vai ao plugin.json e ao marketplace.json juntos."""
    cam = os.path.join(pasta, ".claude-plugin", "plugin.json")
    pj = ler_json(cam)
    pj["version"] = nova
    gravar_json(cam, pj)
    cam_mk = os.path.join(raiz, MARKETPLACE)
    mk = ler_json(cam_mk)
    for p in mk["plugins"]:
        if p["name"] == nome:
            p["version"] = nova
    gravar_json(cam_mk, mk)


def contagens(raiz):
    """(atos, julgados): normas do normas.json do plugin normas e arquivos de julgados."""
    sys.path.insert(0, AQUI)
    from validar import arquivos_de_julgados  # noqa: E402
    nj = ler_json(os.path.join(raiz, "plugins", "normas", "normas", "normas.json"), []) or []
    julgados = 0
    pasta = os.path.join(raiz, "plugins")
    for p in sorted(os.listdir(pasta)) if os.path.isdir(pasta) else []:
        j = os.path.join(pasta, p, "julgados")
        if p.startswith("julgados-") and os.path.isdir(j):
            julgados += len(arquivos_de_julgados(j))
    return len(nj), julgados


def linha_changelog(raiz, hoje, subidas):
    caminho = os.path.join(raiz, "CHANGELOG.md")
    atos, julgados = contagens(raiz)
    with open(caminho, encoding="utf-8") as f:
        texto = f.read()
    versoes = ", ".join("`%s` %s" % (n, v) for n, v in subidas)
    bloco = "## Dados de %s\n\n- Dados até %s: %d atos, %d julgados.\n- Versões: %s.\n\n" % (
        hoje, hoje, atos, julgados, versoes)
    m = re.search(r"^## ", texto, flags=re.M)
    texto = texto[:m.start()] + bloco + texto[m.start():] if m else texto.rstrip("\n") + "\n\n" + bloco
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)


def rodar_indice(raiz):
    r = subprocess.run([sys.executable, os.path.join(raiz, "scripts", "indice.py")], cwd=raiz,
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("indice.py rc %d: %s" % (r.returncode, (r.stdout + r.stderr).strip()[-300:]))


def publicar(raiz, hoje, indice=rodar_indice):
    """Devolve [(plugin, versão nova)] dos que subiram."""
    cam = os.path.join(raiz, REGISTRO)
    reg = ler_json(cam, {}) or {}
    reg.setdefault("plugins", {})
    reg["conferido_em"] = hoje
    gravar_json(cam, reg)
    indice(raiz)  # a linha "Fontes conferidas até" sai do conferido_em
    subidas = []
    for nome, pasta, v_mk in plugins_do_marketplace(raiz):
        v_pj = versao_do_plugin(pasta)
        if v_pj != v_mk:
            raise RuntimeError("%s: versão diferente no plugin.json (%s) e no marketplace.json (%s)"
                               % (nome, v_pj, v_mk))
        h = hash_plugin(pasta)
        ent = reg["plugins"].get(nome)
        if ent is None:
            reg["plugins"][nome] = {"versao": v_pj, "hash": h, "publicado_em": hoje}
            continue
        if ent.get("hash") == h:
            continue
        nova = sobe_patch(v_pj)
        gravar_versao(raiz, nome, pasta, nova)
        reg["plugins"][nome] = {"versao": nova, "hash": h, "publicado_em": hoje}
        subidas.append((nome, nova))
    gravar_json(cam, reg)
    if subidas:
        linha_changelog(raiz, hoje, subidas)
    return subidas


def registrar(raiz, hoje):
    cam = os.path.join(raiz, REGISTRO)
    reg = ler_json(cam, {}) or {}
    reg.setdefault("plugins", {})
    for nome, pasta, _ in plugins_do_marketplace(raiz):
        reg["plugins"][nome] = {"versao": versao_do_plugin(pasta), "hash": hash_plugin(pasta),
                                "publicado_em": hoje}
    gravar_json(cam, reg)


def divergentes(raiz):
    """[(plugin, versão registrada, versão atual)] com hash registrado diferente do conteúdo."""
    reg = (ler_json(os.path.join(raiz, REGISTRO), {}) or {}).get("plugins", {})
    fora = []
    for nome, pasta, _ in plugins_do_marketplace(raiz):
        ent = reg.get(nome)
        if ent and ent.get("hash") != hash_plugin(pasta):
            fora.append((nome, ent.get("versao"), versao_do_plugin(pasta)))
    return fora


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raiz", default=REPO)
    ap.add_argument("--hoje", default=datetime.date.today().isoformat())
    ap.add_argument("--registrar", action="store_true")
    ap.add_argument("--verificar", action="store_true")
    a = ap.parse_args(argv)
    if a.verificar:
        fora = divergentes(a.raiz)
        for n, vr, va in fora:
            print("publicar: %s com conteúdo diferente do hash registrado (registro %s, atual %s)" % (n, vr, va))
        return 1 if fora else 0
    if a.registrar:
        registrar(a.raiz, a.hoje)
        print("publicar: registro gravado em %s" % REGISTRO)
        return 0
    subidas = publicar(a.raiz, a.hoje)
    print(json.dumps({"subidas": subidas, "conferido_em": a.hoje}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
