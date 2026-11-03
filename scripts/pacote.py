#!/usr/bin/env python3
"""Gera o .zip de instalação de um plugin, com a pasta de topo igual ao nome do plugin.

  python3 scripts/pacote.py julgados-tc-crsfn [--versao 0.5.0] [--saida dados/release/]

Mesma estrutura do dados/release/normas-v1.0.0.zip: entrada de cada pasta antes dos arquivos dela,
`<plugin>/.claude-plugin/plugin.json` dentro. Ordem determinística (nomes ordenados), data fixa nas
entradas e sem `.DS_Store`: o mesmo conteúdo dá o mesmo .zip. Versão padrão: a do plugin.json.
Falha se passar de 200 MB sem compressão ou de 5.000 arquivos (limites de upload do claude.ai).
"""
import argparse
import json
import os
import sys
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMITE_BYTES = 200 * 1024 * 1024
LIMITE_ARQUIVOS = 5000
IGNORAR = {".DS_Store"}
DATA = (1980, 1, 1, 0, 0, 0)


def arquivos(pasta):
    """[(caminho relativo à pasta do plugin, é pasta?)] na ordem do zip."""
    out = []

    def anda(rel):
        base = os.path.join(pasta, rel) if rel else pasta
        nomes = sorted(os.listdir(base))
        subs = [n for n in nomes if os.path.isdir(os.path.join(base, n))]
        for n in nomes:
            if n in IGNORAR or n in subs:
                continue
            out.append((os.path.join(rel, n) if rel else n, False))
        for n in subs:
            r = os.path.join(rel, n) if rel else n
            out.append((r, True))
            anda(r)

    anda("")
    return out


def _info(nome, pasta):
    zi = zipfile.ZipInfo(nome, DATA)
    if pasta:
        zi.external_attr = (0o40755 << 16) | 0x10
        zi.compress_type = zipfile.ZIP_STORED
    else:
        zi.external_attr = 0o100644 << 16
        zi.compress_type = zipfile.ZIP_DEFLATED
    return zi


def empacotar(plugin, versao=None, saida=None, raiz=RAIZ, limite_bytes=LIMITE_BYTES,
              limite_arquivos=LIMITE_ARQUIVOS, log=print):
    pasta = os.path.join(raiz, "plugins", plugin)
    manifesto = os.path.join(pasta, ".claude-plugin", "plugin.json")
    if not os.path.isfile(manifesto):
        raise SystemExit("sem %s" % os.path.relpath(manifesto, raiz))
    if versao is None:
        with open(manifesto, encoding="utf-8") as f:
            versao = json.load(f).get("version")
        if not versao:
            raise SystemExit("plugin.json sem version; passe --versao")
    saida = saida or os.path.join(raiz, "dados", "release")
    lista = arquivos(pasta)
    n_arq = sum(1 for _r, d in lista if not d)
    total = sum(os.path.getsize(os.path.join(pasta, r)) for r, d in lista if not d)
    if total > limite_bytes or n_arq > limite_arquivos:
        raise SystemExit("%s passa do limite: %d bytes sem compressão (máx. %d), %d arquivos "
                         "(máx. %d)" % (plugin, total, limite_bytes, n_arq, limite_arquivos))
    os.makedirs(saida, exist_ok=True)
    destino = os.path.join(saida, "%s-%s.zip" % (plugin, versao))
    tmp = destino + ".tmp"
    with zipfile.ZipFile(tmp, "w") as z:
        z.writestr(_info(plugin + "/", True), b"")
        for r, d in lista:
            nome = plugin + "/" + r.replace(os.sep, "/") + ("/" if d else "")
            if d:
                z.writestr(_info(nome, True), b"")
            else:
                with open(os.path.join(pasta, r), "rb") as f:
                    z.writestr(_info(nome, False), f.read())
    os.replace(tmp, destino)
    info = {"zip": destino, "versao": versao, "arquivos": n_arq, "bytes": total,
            "bytes_zip": os.path.getsize(destino)}
    log("%s: %d arquivos; %.1f MB sem compressão; zip %.1f MB" % (
        os.path.relpath(destino, raiz) if destino.startswith(raiz) else destino, n_arq,
        total / 1e6, info["bytes_zip"] / 1e6))
    return info


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("plugin")
    ap.add_argument("--versao")
    ap.add_argument("--saida")
    a = ap.parse_args(argv)
    empacotar(a.plugin, a.versao, a.saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
