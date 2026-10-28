#!/usr/bin/env python3
"""Varredura de termos proibidos antes de cada commit.

Regras:
- CNPJ (com ou sem pontuação) é regra fixa e sempre vale.
- Nomes proibidos vêm de uma lista local (um termo por linha, "#" comenta),
  lida de $NORMAS_TERMOS. A lista nunca entra neste repositório.
- Sem a lista, o script avisa e aplica só a regra de CNPJ.

Uso como hook: .githooks/pre-commit chama este script, que lê os arquivos
em stage. Saída 0 = ok; 1 = achados (commit bloqueado).
"""
import os
import re
import subprocess
import sys

CNPJ = re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)")

def _caminho_lista():
    """Caminho da lista de termos, que fica fora do repositório.

    Ordem: variável NORMAS_TERMOS; depois `git config normas.termos`
    (configuração local, não versionada). Sem nenhum dos dois, None.
    """
    caminho = os.environ.get("NORMAS_TERMOS")
    if caminho:
        return caminho
    try:
        return _git("config", "--get", "normas.termos").decode("utf-8").strip() or None
    except (subprocess.CalledProcessError, OSError):
        return None


def carregar_termos(caminho):
    """Lê a lista de termos. Devolve None se o arquivo não existir."""
    try:
        with open(caminho, encoding="utf-8") as f:
            linhas = f.read().splitlines()
    except OSError:
        return None
    termos = []
    for linha in linhas:
        linha = linha.strip()
        if linha and not linha.startswith("#"):
            termos.append(linha)
    return termos


def _padrao_termo(termo):
    # Casa o termo inteiro, sem diferenciar maiúsculas, e não dentro de outra palavra.
    return re.compile(r"(?<!\w)" + re.escape(termo) + r"(?!\w)", re.IGNORECASE)


def varrer(textos, termos):
    """Devolve os achados no formato "arquivo: termo", em ordem estável.

    textos: dict nome_do_arquivo -> conteúdo. termos: lista de nomes proibidos.
    Para CNPJ, o "termo" é o próprio número achado.
    """
    achados = []
    padroes = [(t, _padrao_termo(t)) for t in termos]
    for arquivo in sorted(textos):
        texto = textos[arquivo]
        vistos = set()
        for m in CNPJ.finditer(texto):
            if m.group(0) not in vistos:
                vistos.add(m.group(0))
                achados.append("%s: %s" % (arquivo, m.group(0)))
        for termo, padrao in padroes:
            if padrao.search(texto):
                achados.append("%s: %s" % (arquivo, termo))
    return achados


def _git(*args):
    return subprocess.run(
        ["git"] + list(args), check=True, capture_output=True
    ).stdout


def _arquivos_em_stage():
    saida = _git("diff", "--cached", "--name-only", "--diff-filter=ACM", "-z")
    return [p for p in saida.decode("utf-8").split("\0") if p]


def main():
    caminho = _caminho_lista()
    termos = carregar_termos(caminho) if caminho else None
    if termos is None:
        print(
            "AVISO: lista de termos não encontrada; só a regra de CNPJ foi aplicada.",
            file=sys.stderr,
        )
        termos = []

    if len(sys.argv) > 1:
        # Modo direto: varre os arquivos indicados (útil para testar o hook).
        arquivos = sys.argv[1:]
        leitor = lambda p: open(p, "rb").read()  # noqa: E731
    else:
        arquivos = _arquivos_em_stage()
        leitor = lambda p: _git("show", ":" + p)  # noqa: E731

    textos = {}
    for arq in arquivos:
        try:
            conteudo = leitor(arq).decode("utf-8")
        except UnicodeDecodeError:
            continue  # binário
        textos[arq] = conteudo
        # O nome do arquivo também é varrido.
        textos[arq + " (nome)"] = arq

    achados = varrer(textos, termos)
    if achados:
        print("Varredura bloqueou o commit:", file=sys.stderr)
        for a in achados:
            print("  " + a, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
