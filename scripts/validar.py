#!/usr/bin/env python3
"""Validador do frontmatter das normas (formato em SPEC.md).

validar_norma(path) -> lista de erros (vazia = ok).
Uso: python3 scripts/validar.py plugins/normas/normas
Valida cada arquivo `<orgao>/resolucoes/NNNN.md` sob o diretório dado. Os
atos alteradores (`alteradoras/`) e o índice não seguem este schema.
Saída 0 = ok; 1 = erros; 2 = uso incorreto.
"""
import datetime
import os
import re
import sys

CAMPOS = [
    "id", "orgao", "tipo", "numero", "data", "publicacao_dou", "ementa",
    "situacao", "versao_texto", "vigente_ate_ato", "aguarda_consolidado_oficial",
    "historico_parcial", "fonte_original", "fonte_consolidada", "sha256_fonte",
    "baixado_em", "verificado_em", "incerteza",
]
OPCIONAIS = ["vigencia_inicio"]  # vêm depois de `incerteza`
SITUACOES = ("vigente", "revogada", "parcialmente-revogada")
VERSOES = ("consolidado", "original")
DATAS = ("data", "publicacao_dou", "baixado_em", "verificado_em")
BOOLEANOS = ("aguarda_consolidado_oficial", "historico_parcial")
# Linha que abre a redação futura de um dispositivo (vigência diferida).
MARCA_VIGENCIA = re.compile(r"^[\s>*_#-]*vigente a partir de\b", re.I | re.M)


def ler_frontmatter(texto):
    """Devolve (pares, corpo, erro). `pares` = lista [(chave, valor)] na ordem."""
    linhas = texto.split("\n")
    if not linhas or linhas[0].strip() != "---":
        return None, texto, "frontmatter ausente (o arquivo deve começar com ---)"
    for i in range(1, len(linhas)):
        if linhas[i].strip() == "---":
            fim = i
            break
    else:
        return None, texto, "frontmatter não fechado (falta o --- final)"
    pares = []
    for n, linha in enumerate(linhas[1:fim], start=2):
        if not linha.strip():
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):(?: (.*))?$", linha.rstrip())
        if not m:
            pares.append((None, "linha %d inválida no frontmatter: %r" % (n, linha)))
            continue
        valor = (m.group(2) or "").strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        pares.append((m.group(1), valor))
    return pares, "\n".join(linhas[fim + 1:]), None


def _data_valida(valor):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
        return False
    try:
        datetime.date.fromisoformat(valor)
    except ValueError:
        return False
    return True


def validar_norma(path):
    with open(path, encoding="utf-8") as f:
        texto = f.read()
    pares, corpo, erro = ler_frontmatter(texto)
    if erro:
        return [erro]
    erros = [valor for chave, valor in pares if chave is None]
    pares = [(c, v) for c, v in pares if c is not None]
    chaves = [c for c, _ in pares]
    valores = dict(pares)

    for c in sorted({c for c in chaves if chaves.count(c) > 1}):
        erros.append("campo repetido: %s" % c)
    for c in CAMPOS:
        if c not in valores:
            erros.append("campo obrigatório ausente: %s" % c)
    for c in chaves:
        if c not in CAMPOS and c not in OPCIONAIS:
            erros.append("campo desconhecido: %s" % c)
    esperado = [c for c in CAMPOS + OPCIONAIS if c in valores]
    if not erros and chaves != esperado:
        erros.append("ordem dos campos incorreta (esperado: %s)" % ", ".join(esperado))
    if erros:
        return erros

    v = valores
    if v["orgao"] != "cvm":
        erros.append("orgao deve ser cvm, veio %r" % v["orgao"])
    if v["tipo"] != "resolucao":
        erros.append("tipo deve ser resolucao, veio %r" % v["tipo"])
    if not re.fullmatch(r"[1-9]\d*", v["numero"]):
        erros.append("numero deve ser inteiro, veio %r" % v["numero"])
    else:
        if v["id"] != "cvm-res-%s" % v["numero"]:
            erros.append("id %r incoerente com numero %s (esperado cvm-res-%s)" % (v["id"], v["numero"], v["numero"]))
        if os.path.basename(path) != "%04d.md" % int(v["numero"]):
            erros.append("nome do arquivo deve ser %04d.md" % int(v["numero"]))
    for c in DATAS:
        if not _data_valida(v[c]):
            erros.append("%s deve ser AAAA-MM-DD válida, veio %r" % (c, v[c]))
    if v["situacao"] not in SITUACOES:
        erros.append("situacao fora da lista %s: %r" % (", ".join(SITUACOES), v["situacao"]))
    if v["versao_texto"] not in VERSOES:
        erros.append("versao_texto fora da lista %s: %r" % (", ".join(VERSOES), v["versao_texto"]))
    if v["vigente_ate_ato"] != "" and not re.fullmatch(r"[1-9]\d*", v["vigente_ate_ato"]):
        erros.append("vigente_ate_ato deve ser o número do ato (inteiro) ou vazio, veio %r" % v["vigente_ate_ato"])
    for c in BOOLEANOS:
        if v[c] not in ("true", "false"):
            erros.append("%s deve ser true ou false, veio %r" % (c, v[c]))
    for c in ("ementa", "fonte_original", "fonte_consolidada"):
        if not v[c]:
            erros.append("%s não pode ficar vazio" % c)
    if not re.fullmatch(r"[0-9a-f]{64}", v["sha256_fonte"]):
        erros.append("sha256_fonte deve ter 64 caracteres hexadecimais")

    tem_marca = bool(MARCA_VIGENCIA.search(corpo))
    if "vigencia_inicio" in v:
        if not _data_valida(v["vigencia_inicio"]):
            erros.append("vigencia_inicio deve ser AAAA-MM-DD válida, veio %r" % v["vigencia_inicio"])
    elif tem_marca:
        erros.append('o texto tem bloco "vigente a partir de" mas falta vigencia_inicio no frontmatter')
    return erros


def arquivos_de_normas(raiz):
    achados = []
    for dirpath, _dirs, nomes in os.walk(raiz):
        if os.path.basename(dirpath) == "resolucoes":
            achados += [os.path.join(dirpath, n) for n in sorted(nomes) if n.endswith(".md")]
    return sorted(achados)


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    raiz = argv[1]
    if not os.path.isdir(raiz):
        print("validar: %s não existe ainda; nada a validar" % raiz)
        return 0
    arquivos = arquivos_de_normas(raiz)
    if not arquivos:
        print("validar: nenhuma norma em %s; nada a validar" % raiz)
        return 0
    total = 0
    for caminho in arquivos:
        for e in validar_norma(caminho):
            total += 1
            print("%s: %s" % (caminho, e))
    print("validar: %d arquivo(s), %d erro(s)" % (len(arquivos), total))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
