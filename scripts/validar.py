#!/usr/bin/env python3
"""Validador do frontmatter das normas (formato em SPEC.md).

- validar_norma(path) -> lista de erros (vazia = ok). Aceita os tipos da SPEC
  (v0.3.1): resolução, instrução e parecer (`NNNN.md`), ofício-circular
  (`<slug>.md`), lei (`lei-NNNNN.md`), decreto (`decreto-NNNNN.md`), lei
  complementar (`lcp-NNN.md`) e o `index.md` de norma em partes (`NNNN/index.md`,
  `lei-NNNNN/index.md` etc.).
- partes_da_norma(index_path) -> caminhos das partes, na ordem de `## Partes`.
- texto_da_norma(path) -> texto do arquivo único, ou do `index.md` seguido das
  partes (na ordem), concatenados.

Uso: python3 scripts/validar.py plugins/normas/normas
Valida cada norma em `<orgao>/resolucoes/`, `instrucoes/`, `pareceres-orientacao/`,
`oficios-circulares/<pasta>/` e em `leis/` sob o diretório dado (arquivo único ou
o `index.md` da pasta). Os atos alteradores (`alteradoras/`) e os índices
(`indice.md`, `indices/`) não seguem este schema.
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
OPCIONAIS = ["vigencia_inicio", "nivel_verificacao"]  # vêm depois de `incerteza`, nesta ordem
# tipo -> (orgao, prefixo do id, nome do arquivo, pasta sob o órgão). Ofício-circular:
# o nome do arquivo é o slug da página da CVM e o id é `cvm-<slug>` (molde None).
TIPOS = {
    "resolucao": ("cvm", "cvm-res-", "%04d", "resolucoes"),
    "instrucao": ("cvm", "cvm-instr-", "%04d", "instrucoes"),
    "parecer-orientacao": ("cvm", "cvm-po-", "%04d", "pareceres-orientacao"),
    "oficio-circular": ("cvm", "cvm-", None, "oficios-circulares"),
    "lei": ("federal", "lei-", "lei-%05d", "leis"),
    "decreto": ("federal", "decreto-", "decreto-%05d", "leis"),
    "lei-complementar": ("federal", "lcp-", "lcp-%03d", "leis"),
}
TIPOS_FEDERAIS = tuple(t for t, (orgao, *_r) in TIPOS.items() if orgao == "federal")
SITUACOES = ("vigente", "revogada", "parcialmente-revogada", "nao-informada")
# A CVM não publica a vigência de pareceres e ofícios: só neles cabe `nao-informada`.
TIPOS_SEM_VIGENCIA = ("parecer-orientacao", "oficio-circular")
NIVEIS_VERIFICACAO = ("historico-conferido", "consolidado-convertido", "ato-convertido",
                      "pdf-extraido", "ocr", "compilado-planalto")  # `ocr`: v0.3.1
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
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
        erros.append("tipo fora da lista %s: %r" % (", ".join(TIPOS), v["tipo"]))
        orgao, prefixo, molde, _pasta = TIPOS["resolucao"]
    else:
        orgao, prefixo, molde, _pasta = TIPOS[v["tipo"]]
        if v["orgao"] != orgao:
            erros.append("orgao deve ser %s para tipo %s, veio %r" % (orgao, v["tipo"], v["orgao"]))
    numero_ok = bool(re.fullmatch(r"[1-9]\d*", v["numero"]))
    if not numero_ok:
        erros.append("numero deve ser inteiro, veio %r" % v["numero"])
    if em_partes:
        nome_atual = os.path.basename(os.path.dirname(os.path.abspath(path)))
    else:
        nome_atual = os.path.basename(path)[:-3] if path.endswith(".md") else os.path.basename(path)
    if v["tipo"] == "oficio-circular":
        # sem regra entre numero e id: o id vem do slug da página da CVM (nome do arquivo)
        if not SLUG.fullmatch(nome_atual):
            erros.append("nome do arquivo do ofício deve ser o slug da página da CVM "
                         "(minúsculas, dígitos e hífen), veio %r" % nome_atual)
        elif v["id"] != prefixo + nome_atual:
            erros.append("id %r incoerente com o nome do arquivo (esperado %s%s)" % (v["id"], prefixo, nome_atual))
    elif numero_ok:
        if v["id"] != "%s%s" % (prefixo, v["numero"]):
            erros.append("id %r incoerente com numero %s (esperado %s%s)" % (v["id"], v["numero"], prefixo, v["numero"]))
        nome = molde % int(v["numero"])
        if em_partes:
            if nome_atual != nome:
                erros.append("o index.md deve ficar na pasta %s/" % nome)
        elif nome_atual != nome:
            erros.append("nome do arquivo deve ser %s.md" % nome)
    for c in DATAS:
        if not _data_valida(v[c]):
            erros.append("%s deve ser AAAA-MM-DD válida, veio %r" % (c, v[c]))
    if v["situacao"] not in SITUACOES:
        erros.append("situacao fora da lista %s: %r" % (", ".join(SITUACOES), v["situacao"]))
    elif v["situacao"] == "nao-informada" and v["tipo"] not in TIPOS_SEM_VIGENCIA:
        erros.append("situacao nao-informada só cabe em %s, não em %s" % (" e ".join(TIPOS_SEM_VIGENCIA), v["tipo"]))
    if v["versao_texto"] not in VERSOES:
        erros.append("versao_texto fora da lista %s: %r" % (", ".join(VERSOES), v["versao_texto"]))
    if v["tipo"] in TIPOS_FEDERAIS:
        if v["vigente_ate_ato"] != "":
            erros.append("vigente_ate_ato deve ficar vazio em %s (a data-base é baixado_em), veio %r" % (v["tipo"], v["vigente_ate_ato"]))
        if v["historico_parcial"] != "true":
            erros.append("historico_parcial deve ser true em %s, veio %r" % (v["tipo"], v["historico_parcial"]))
        if v["aguarda_consolidado_oficial"] != "false":
            erros.append("aguarda_consolidado_oficial deve ser false em %s, veio %r" % (v["tipo"], v["aguarda_consolidado_oficial"]))
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

    if "nivel_verificacao" in v and v["nivel_verificacao"] not in NIVEIS_VERIFICACAO:
        erros.append("nivel_verificacao fora da lista %s: %r" % (", ".join(NIVEIS_VERIFICACAO), v["nivel_verificacao"]))

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


def _normas_em(dirpath, nomes, dirs):
    return ([os.path.join(dirpath, n) for n in nomes if n.endswith(".md")] +
            [os.path.join(dirpath, d, "index.md") for d in dirs
             if os.path.isfile(os.path.join(dirpath, d, "index.md"))])


def arquivos_da_pasta(raiz, pasta):
    """Normas das pastas chamadas `pasta` sob `raiz`: cada `.md` solto, e o `index.md`
    de cada subpasta (norma em partes; as partes não são normas por si)."""
    achados = []
    for dirpath, dirs, nomes in os.walk(raiz):
        if os.path.basename(dirpath) == pasta:
            achados += _normas_em(dirpath, nomes, dirs)
    return sorted(achados)


def arquivos_de_oficios(raiz):
    """Ofícios-circulares: normas de cada subpasta (superintendência) de `oficios-circulares/`."""
    achados = []
    for dirpath, dirs, nomes in os.walk(raiz):
        if os.path.basename(os.path.dirname(dirpath)) == "oficios-circulares":
            achados += _normas_em(dirpath, nomes, dirs)
    return sorted(achados)


PASTAS_DE_NORMAS = ("resolucoes", "instrucoes", "pareceres-orientacao", "leis")


def arquivos_de_normas(raiz):
    achados = arquivos_de_oficios(raiz)
    for pasta in PASTAS_DE_NORMAS:
        achados += arquivos_da_pasta(raiz, pasta)
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
