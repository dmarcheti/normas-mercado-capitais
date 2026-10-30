#!/usr/bin/env python3
"""Varredura de termos proibidos antes de cada commit.

Regras:
- CNPJ (com ou sem pontuação) é regra fixa e sempre vale, salvo os CNPJs públicos de empresa
  listados em CNPJS_PUBLICOS, que fazem parte do texto de uma norma do acervo (decisão do Diogo,
  2026-10-29). Cada inclusão na lista é uma decisão dele, com o motivo.
- Nomes proibidos vêm de uma lista local (um termo por linha, "#" comenta),
  lida de $NORMAS_TERMOS. A lista nunca entra neste repositório.
- CPF (formatado, rotulado com ruído de OCR ou 11 dígitos com verificador válido) e RG
  (rótulo seguido de número) também são regra fixa (decisão D3 da Fase 2d). O que já foi
  trocado por "[dado pessoal retirado]" não dispara. O achado mostra só a linha, nunca o número,
  porque a saída do CI é pública.
- Sem a lista, o script avisa e aplica só as regras fixas.

Uso como hook: .githooks/pre-commit chama este script, que lê os arquivos
em stage. Saída 0 = ok; 1 = achados (commit bloqueado).
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pii  # noqa: E402

# Sem letra ou dígito colado: 14 dígitos dentro de um hash hexadecimal (sha256) não são CNPJ.
CNPJ = re.compile(r"(?<![0-9A-Za-z])\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?![0-9A-Za-z])")
# CNPJ (só dígitos) -> motivo. Empresa citada no texto de norma do acervo; não é dado pessoal.
CNPJS_PUBLICOS = {
    "28671705000150": "FILCB (fundo de liquidez da Câmara B3), no Regulamento do FILCB",
    "00997185000150": "Banco B3 S.A., administrador do FILCB, no Regulamento do FILCB",
    "33268302000102": "Laqus Depositária de Valores Mobiliários S.A., no Manual de Normas de Direito de Acesso da B3",
    "97521479000143": "SL Tools S.A., no Manual de Normas de Direito de Acesso da B3",
}

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
    Para CNPJ, o "termo" é o próprio número achado; para CPF e RG, "CPF na linha N".
    """
    achados = []
    padroes = [(t, _padrao_termo(t)) for t in termos]
    for arquivo in sorted(textos):
        texto = textos[arquivo]
        vistos = set()
        for m in CNPJ.finditer(texto):
            if len(set(re.sub(r"\D", "", m.group(0)))) == 1:
                continue  # 99999999999999: exemplo de CNPJ inválido citado em norma, não é CNPJ
            if re.sub(r"\D", "", m.group(0)) in CNPJS_PUBLICOS:
                continue  # CNPJ público de empresa, liberado com motivo
            if m.group(0) not in vistos:
                vistos.add(m.group(0))
                achados.append("%s: %s" % (arquivo, m.group(0)))
        for rotulo, achar in (("CPF", pii.achar_cpfs), ("RG", pii.achar_rgs)):
            for a, _ in achar(texto):
                achados.append("%s: %s na linha %d" % (arquivo, rotulo, texto.count("\n", 0, a) + 1))
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
            "AVISO: lista de termos não encontrada; só as regras fixas (CNPJ, CPF, RG) foram aplicadas.",
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
