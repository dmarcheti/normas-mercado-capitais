#!/usr/bin/env python3
"""Validador do frontmatter das normas (formato em SPEC.md).

- validar_norma(path) -> lista de erros (vazia = ok). Aceita resolução
  (`NNNN.md`), lei (`lei-NNNNN.md`) e o `index.md` de norma em partes
  (`NNNN/index.md`, `lei-NNNNN/index.md`).
- partes_da_norma(index_path) -> caminhos das partes, na ordem de `## Partes`.
- texto_da_norma(path) -> texto do arquivo único, ou do `index.md` seguido das
  partes (na ordem), concatenados.

Uso: python3 scripts/validar.py plugins/normas/normas
Valida cada norma em `<orgao>/resolucoes/` e em `leis/` sob o diretório dado
(arquivo único ou o `index.md` da pasta). Os atos alteradores (`alteradoras/`)
e o índice não seguem este schema.
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
TIPOS = {  # tipo -> (orgao, prefixo do id, nome do arquivo)
    "resolucao": ("cvm", "cvm-res-", "%04d"),
    "lei": ("federal", "lei-", "lei-%05d"),
}
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


def partes_da_norma(index_path):
    """Caminhos das partes, na ordem da seção `## Partes` do index.md (itens `- arquivo.md`)."""
    with open(index_path, encoding="utf-8") as f:
        linhas = f.read().split("\n")
    pasta = os.path.dirname(index_path)
    partes, dentro = [], False
    for linha in linhas:
        if re.match(r"^#{1,2}\s", linha):
            dentro = linha.strip() == "## Partes"
        elif dentro:
            m = re.match(r"^\s*[-*]\s+(.+?)\s*$", linha)
            if m:
                partes.append(os.path.join(pasta, m.group(1).strip("`")))
    return partes


def texto_da_norma(path):
    """Texto da norma: o arquivo, ou o index.md mais as partes (as que existem), em ordem."""
    with open(path, encoding="utf-8") as f:
        texto = f.read()
    if os.path.basename(path) != "index.md":
        return texto
    for parte in partes_da_norma(path):
        if os.path.exists(parte):
            with open(parte, encoding="utf-8") as f:
                texto += "\n\n" + f.read()
    return texto


def _erros_partes(index_path):
    erros = []
    partes = partes_da_norma(index_path)
    nomes = [os.path.basename(p) for p in partes]
    if not partes:
        return ["seção '## Partes' ausente ou vazia no index.md"]
    for n in sorted({n for n in nomes if nomes.count(n) > 1}):
        erros.append("parte duplicada em '## Partes': %s" % n)
    for caminho, nome in zip(partes, nomes):
        if not os.path.isfile(caminho):
            erros.append("parte listada não existe: %s" % nome)
            continue
        with open(caminho, encoding="utf-8") as f:
            texto = f.read()
        primeira = next((l for l in texto.split("\n") if l.strip()), "")
        if primeira.strip() == "---":
            erros.append("parte %s não pode ter frontmatter" % nome)
        elif not primeira.startswith("# "):
            erros.append("parte %s deve abrir com o título '# <título da parte>'" % nome)
    for nome in sorted(os.listdir(os.path.dirname(index_path))):
        if nome.endswith(".md") and nome != "index.md" and nome not in nomes:
            erros.append("arquivo fora da lista '## Partes': %s" % nome)
    return erros


def validar_norma(path):
    with open(path, encoding="utf-8") as f:
        texto = f.read()
    em_partes = os.path.basename(path) == "index.md"
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
    if v["tipo"] not in TIPOS:
        erros.append("tipo deve ser resolucao ou lei, veio %r" % v["tipo"])
        orgao, prefixo, molde = "cvm", "cvm-res-", "%04d"
    else:
        orgao, prefixo, molde = TIPOS[v["tipo"]]
        if v["orgao"] != orgao:
            erros.append("orgao deve ser %s para tipo %s, veio %r" % (orgao, v["tipo"], v["orgao"]))
    if not re.fullmatch(r"[1-9]\d*", v["numero"]):
        erros.append("numero deve ser inteiro, veio %r" % v["numero"])
    else:
        if v["id"] != "%s%s" % (prefixo, v["numero"]):
            erros.append("id %r incoerente com numero %s (esperado %s%s)" % (v["id"], v["numero"], prefixo, v["numero"]))
        nome = molde % int(v["numero"])
        if em_partes:
            if os.path.basename(os.path.dirname(os.path.abspath(path))) != nome:
                erros.append("o index.md deve ficar na pasta %s/" % nome)
        elif os.path.basename(path) != nome + ".md":
            erros.append("nome do arquivo deve ser %s.md" % nome)
    for c in DATAS:
        if not _data_valida(v[c]):
            erros.append("%s deve ser AAAA-MM-DD válida, veio %r" % (c, v[c]))
    if v["situacao"] not in SITUACOES:
        erros.append("situacao fora da lista %s: %r" % (", ".join(SITUACOES), v["situacao"]))
    if v["versao_texto"] not in VERSOES:
        erros.append("versao_texto fora da lista %s: %r" % (", ".join(VERSOES), v["versao_texto"]))
    if v["tipo"] == "lei":
        if v["vigente_ate_ato"] != "":
            erros.append("vigente_ate_ato deve ficar vazio em lei (a data-base é baixado_em), veio %r" % v["vigente_ate_ato"])
    elif v["vigente_ate_ato"] != "" and not re.fullmatch(r"[1-9]\d*", v["vigente_ate_ato"]):
        erros.append("vigente_ate_ato deve ser o número do ato (inteiro) ou vazio, veio %r" % v["vigente_ate_ato"])
    for c in BOOLEANOS:
        if v[c] not in ("true", "false"):
            erros.append("%s deve ser true ou false, veio %r" % (c, v[c]))
    for c in ("ementa", "fonte_original", "fonte_consolidada"):
        if not v[c]:
            erros.append("%s não pode ficar vazio" % c)
    if not re.fullmatch(r"[0-9a-f]{64}", v["sha256_fonte"]):
        erros.append("sha256_fonte deve ter 64 caracteres hexadecimais")

    if em_partes:
        erros += _erros_partes(path)
        corpo = texto_da_norma(path)
    tem_marca = bool(MARCA_VIGENCIA.search(corpo))
    if "vigencia_inicio" in v:
        if not _data_valida(v["vigencia_inicio"]):
            erros.append("vigencia_inicio deve ser AAAA-MM-DD válida, veio %r" % v["vigencia_inicio"])
    elif tem_marca:
        erros.append('o texto tem bloco "vigente a partir de" mas falta vigencia_inicio no frontmatter')
    return erros


def arquivos_da_pasta(raiz, pasta):
    """Normas das pastas chamadas `pasta` sob `raiz`: cada `.md` solto, e o `index.md`
    de cada subpasta (norma em partes; as partes não são normas por si)."""
    achados = []
    for dirpath, dirs, nomes in os.walk(raiz):
        if os.path.basename(dirpath) != pasta:
            continue
        achados += [os.path.join(dirpath, n) for n in nomes if n.endswith(".md")]
        achados += [os.path.join(dirpath, d, "index.md") for d in dirs
                    if os.path.isfile(os.path.join(dirpath, d, "index.md"))]
    return sorted(achados)


def arquivos_de_normas(raiz):
    return sorted(arquivos_da_pasta(raiz, "resolucoes") + arquivos_da_pasta(raiz, "leis"))


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
