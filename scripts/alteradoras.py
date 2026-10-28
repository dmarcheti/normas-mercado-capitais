#!/usr/bin/env python3
"""Texto dos atos (originais e alteradores) a partir do ctresb/leis ou do DOCX da CVM.

- md_do_ctresb(texto, ato=False, docx=None): markdown do ctresb/leis (conversão
  do HTML do DOU) -> texto do ato no formato do piloto: sem frontmatter, sem o
  título repetido, sem a assinatura, sem `**`, `#` nem escapes (`1\\.`); as
  `<table>` HTML do ctresb viram tabela markdown.
  `ato=False` (original de resolução): todo início de artigo vira `## Art. Nº`
  (normalizar_artigos). `ato=True` (ato alterador): só os artigos do próprio ato
  (artigos_do_ato). O ctresb traz parte das tabelas achatadas (um parágrafo por
  célula): com `docx` (caminho de um DOCX da CVM com o mesmo texto), as tabelas
  do DOCX cujas células aparecem em sequência no ctresb são restauradas, com o
  texto do ctresb (restaurar_tabelas).
- md_do_docx(path, ato=False): o mesmo, a partir do DOCX da CVM.
- artigos_do_ato(md): marca como `## Art. Nº` só os artigos do próprio ato: a
  sequência 1º, 2º, 3º... fora de redação citada. Os artigos citados dentro das
  redações novas (entre aspas, inclusive os que seguem o primeiro de uma citação
  de vários artigos, sem aspa de abertura) ficam como texto, assim como tudo o
  que vem depois da primeira linha `ANEXO...` (anexo do ato, fora de citação).
- ementa_do_ato(md): a linha que segue o título "RESOLUÇÃO CVM Nº ...".
- escrever_alteradora(numero, md_ato, item_inventario, fonte_url, incerteza, ...):
  arquivo `alteradoras/NNNN.md` (frontmatter da SPEC, `versao_texto: original`).

Limite: a sequência de artigos do ato é a regra. Ato com artigo fora de ordem
(ou com citação cujas aspas o ctresb não fechou) perde os artigos seguintes:
`artigos_do_ato` não detecta isso; confira o último artigo (em geral a vigência).

Uso: python3 scripts/alteradoras.py <arquivo.md do ctresb|arquivo.docx> [--ato]
"""
import os
import re
import sys
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from converter import ARTIGO, NOTA_DE_ARTIGO, docx_para_md, normalizar_artigos  # noqa: E402
from normalizar import _CARACTERES  # noqa: E402

DATA_BASE = "2026-10-28"
_ABRE = re.compile(r"^\s*[\"“]")
_FECHA = re.compile(r"[\"”]\s*(?:\(\w{1,3}\))?\s*[.;]?\s*$")
_HEADING_ARTIGO = re.compile(r"^## Art\. (\d+)º?$")
_TITULO = re.compile(r"^RESOLU[ÇC][ÃÂA]O\s+CVM\b", re.I)  # a fonte da Res. 245 traz "RESOLUÇÂO"
# Em citação aberta (ctresb sem o fecho), só o artigo do ato que fala do próprio ato fecha a citação.
_ARTIGO_DO_ATO = re.compile(
    r"passa(?:m)? a vigorar|com a seguinte redação|entra(?:m)? em vigor|ficam? revogad|revogam-se"
    r"|ficam? (?:acrescentad|incluíd|alterad)", re.I)
_PUBLICACAO = re.compile(r"^\((?:Publicad[ao]|Republicad[ao])\b", re.I)  # linha entre o título e a ementa (Res. 59)
_ANEXO = re.compile(r"^ANEXO\b")
_NOME = r"[A-ZÁÂÃÀÉÊÍÓÔÕÚÇ]{2,}"
_ASSINATURA = re.compile(r"^%s(?: (?:DE|DA|DO|DOS|DAS|%s))+$" % (_NOME, _NOME))
_APOS_ASSINATURA = re.compile(r"^(?:ANEXO\b|NOTAS\b|\(\d+\))")
_NAO_ASSINATURA = re.compile(r"^(?:ANEXO|CAPÍTULO|SEÇÃO|SUBSEÇÃO|TÍTULO|LIVRO|PARTE|NOTAS|APÊNDICE)\b")


def _sem_frontmatter(texto):
    if texto.startswith("---\n"):
        fim = texto.find("\n---\n", 3)
        if fim >= 0:
            return texto[fim + 5:]
    return texto


class _Tabela(HTMLParser):
    """Uma `<table>` do ctresb -> linhas de células (texto); linha sem célula sai."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.linhas, self._linha, self._cel = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._linha = []
        elif tag in ("td", "th") and self._linha is not None:
            self._cel = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cel is not None and self._linha is not None:
            self._linha.append(" ".join("".join(self._cel).replace("\xa0", " ").split()).replace("|", "\\|"))
            self._cel = None
        elif tag == "tr" and self._linha is not None:
            if self._linha:
                self.linhas.append(self._linha)
            self._linha = None

    def handle_data(self, data):
        if self._cel is not None:
            self._cel.append(data)


def html_para_tabela(html):
    """`<table>...</table>` (ctresb) -> tabela markdown, no formato de `docx_para_md`."""
    p = _Tabela()
    p.feed(html)
    p.close()
    return _md_tabela(p.linhas) if p.linhas else ""


def _tabelas_html(texto):
    return re.sub(r"<table\b.*?</table>", lambda m: "\n\n" + html_para_tabela(m.group(0)) + "\n\n",
                  texto, flags=re.S | re.I)


def _sem_assinatura(linhas):
    """Tira o nome do signatário: linha só de maiúsculas que fecha o texto do ato
    (a próxima linha não vazia é ANEXO, NOTAS, nota de rodapé ou não existe)."""
    saida = list(linhas)
    for i in range(len(saida) - 1, -1, -1):
        l = saida[i].strip()
        if not l or not _ASSINATURA.match(l) or _NAO_ASSINATURA.match(l):
            continue
        prox = next((x.strip() for x in saida[i + 1:] if x.strip()), None)
        if prox is None or _APOS_ASSINATURA.match(prox):
            del saida[i]
    return saida


def md_do_ctresb(texto, ato=False, docx=None):
    corpo = _tabelas_html(_sem_frontmatter(texto).replace("\r\n", "\n"))
    linhas = corpo.split("\n")
    for i, linha in enumerate(linhas):
        if linha.strip():
            if linha.startswith("# "):  # título repetido: a linha seguinte é o mesmo título
                del linhas[i]
            break
    limpas = [re.sub(r"\\([.*_])", r"\1", re.sub(r"^#+\s+", "", l.replace("**", ""))).rstrip()
              for l in linhas]
    md = re.sub(r"\n{3,}", "\n\n", "\n".join(_sem_assinatura(limpas))).strip("\n") + "\n"
    if docx:
        md = restaurar_tabelas(md, tabelas_do_md(docx_para_md(docx)))[0]
    return artigos_do_ato(md) if ato else normalizar_artigos(md)


def _chave(txt):
    """Texto comparável: sem aspas (o DOCX da CVM perde as aspas simples em alguns
    quadros), travessões e espaços unificados."""
    txt = txt.replace("\xa0", " ").translate(_CARACTERES)
    return " ".join(txt.replace('"', "").replace("'", "").split())


def tabelas_do_md(md):
    """Tabelas de um markdown de `docx_para_md`: lista de tabelas, cada uma lista de
    linhas, cada linha lista de células (texto)."""
    tabelas = []
    for bloco in md.split("\n\n"):
        if not bloco.startswith("| "):
            continue
        linhas = []
        for l in bloco.split("\n"):
            if re.fullmatch(r"\|(?: --- \|)+", l):
                continue
            linhas.append(l[2:-2].split(" | "))
        tabelas.append(linhas)
    return tabelas


def _md_tabela(linhas):
    larg = max(len(l) for l in linhas)
    linhas = [l + [""] * (larg - len(l)) for l in linhas]
    md = ["| " + " | ".join(linhas[0]) + " |", "| " + " | ".join(["---"] * larg) + " |"]
    md += ["| " + " | ".join(l) + " |" for l in linhas[1:]]
    return "\n".join(md)


def restaurar_tabelas(md, tabelas):
    """Troca, no markdown, a sequência de parágrafos que é o conteúdo achatado de
    cada tabela (células não vazias, em ordem) pela tabela, com o texto do próprio
    markdown. Devolve (md, restauradas, total)."""
    linhas = md.split("\n")
    nao_vazias = [i for i, l in enumerate(linhas) if l.strip()]
    chaves = [_chave(linhas[i]) for i in nao_vazias]
    trocas, pos, achadas = [], 0, 0
    for tab in tabelas:
        celulas = [c for lin in tab for c in lin if c.strip()]
        alvo = [_chave(c.replace("\\|", "|")) for c in celulas]
        if not alvo:
            continue
        for k in range(pos, len(chaves) - len(alvo) + 1):
            if chaves[k:k + len(alvo)] == alvo:
                textos = iter(linhas[i].strip() for i in nao_vazias[k:k + len(alvo)])
                nova = [[next(textos).replace("|", "\\|") if c.strip() else "" for c in lin] for lin in tab]
                trocas.append((nao_vazias[k], nao_vazias[k + len(alvo) - 1], _md_tabela(nova)))
                pos = k + len(alvo)
                achadas += 1
                break
    for ini, fim, tabela in reversed(trocas):
        linhas[ini:fim + 1] = [tabela]
    # parágrafos que sobraram entre as células achatadas já saíram na troca; blocos vazios colapsam
    return re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)), achadas, len(tabelas)


_ASSINATURA_ELETRONICA = re.compile(r"^Assinado eletronicamente por[ \t]*\n+[^\n]+\n+[^\n]+\n?", re.M)


def md_do_docx(path, ato=False):
    """O DOCX da CVM fecha o ato com `Assinado eletronicamente por / NOME / cargo`: sai."""
    md = re.sub(r"\n{3,}", "\n\n", _ASSINATURA_ELETRONICA.sub("", docx_para_md(path)))
    return artigos_do_ato(md) if ato else normalizar_artigos(md)


def _numero_simples(num):
    m = re.fullmatch(r"(\d+)[º°]?", num)
    return int(m.group(1)) if m else None


def artigos_do_ato(md):
    esperado = 1
    aberta = False
    anexo = False
    saida = []
    for linha in md.split("\n"):
        if anexo:
            saida.append(linha)
            continue
        if esperado > 1 and not aberta and _ANEXO.match(linha):
            anexo = True  # o que vem depois é anexo do ato: seus artigos são texto
            saida.append(linha)
            continue
        h = _HEADING_ARTIGO.match(linha)
        if h and int(h.group(1)) == esperado:
            esperado += 1
            saida.append(linha)
            continue
        m = ARTIGO.match(linha)
        if (m and (not aberta or _ARTIGO_DO_ATO.search(m.group("resto")))
                and not NOTA_DE_ARTIGO.match(m.group("resto"))
                and _numero_simples(m.group("num")) == esperado):
            aberta = False
            saida.append("## Art. " + m.group("num").replace("°", "º"))
            resto = m.group("resto").strip()
            if resto:
                saida += ["", resto]
            esperado += 1
            continue
        saida.append(linha)
        if aberta:
            aberta = not ("(NR)" in linha or _FECHA.search(linha))
        elif _ABRE.match(linha):
            aberta = not ("(NR)" in linha or _FECHA.search(linha))
    if esperado == 1:
        raise ValueError("artigo 1º do ato não encontrado")
    return "\n".join(saida)


def ementa_do_ato(md):
    linhas = [l.strip() for l in md.split("\n") if l.strip()]
    for i, linha in enumerate(linhas):
        if _TITULO.match(linha):
            resto = [l for l in linhas[i + 1:] if not _PUBLICACAO.match(l)]
            if resto:
                return resto[0]
            break
    raise ValueError("título ou ementa do ato não encontrados")


def escrever_alteradora(numero, md_ato, item_inventario, fonte_url, incerteza,
                        sha256_fonte=None, fonte_consolidada=None, data_base=DATA_BASE,
                        ementa=None, id_ato=None):
    """Conteúdo de `alteradoras/NNNN.md`.

    `item_inventario`: a entrada do ato em `alteradoras` do inventário (numero, data,
    dou, url_ato). `fonte_url` = `fonte_original`. `sha256_fonte` é obrigatório
    (hash do arquivo de `fonte_consolidada`); `fonte_consolidada` omitida = DOCX
    (ou HTM, ou PDF) do ato no site da CVM, de `url_ato`. `ementa` e `id_ato`:
    para a retificação do DOU, que não tem título de resolução nem o id do ato.
    """
    if item_inventario.get("numero") != numero:
        raise ValueError("item do inventário é do ato %s, não do %s" % (item_inventario.get("numero"), numero))
    if not sha256_fonte or not re.fullmatch(r"[0-9a-f]{64}", sha256_fonte):
        raise ValueError("sha256_fonte ausente ou inválido")
    if not fonte_consolidada:
        urls = item_inventario.get("url_ato", {})
        fonte_consolidada = next((urls[k] for k in ("docx", "htm", "pdf") if k in urls), "")
    if not fonte_consolidada:
        raise ValueError("ato %s sem fonte_consolidada" % numero)
    campos = [
        ("id", id_ato or "cvm-res-%d" % numero), ("orgao", "cvm"), ("tipo", "resolucao"), ("numero", str(numero)),
        ("data", item_inventario["data"]), ("publicacao_dou", item_inventario["dou"]),
        ("ementa", ementa or ementa_do_ato(md_ato)), ("situacao", "vigente"), ("versao_texto", "original"),
        ("vigente_ate_ato", ""), ("aguarda_consolidado_oficial", "false"), ("historico_parcial", "false"),
        ("fonte_original", fonte_url), ("fonte_consolidada", fonte_consolidada),
        ("sha256_fonte", sha256_fonte), ("baixado_em", data_base), ("verificado_em", data_base),
        ("incerteza", incerteza),
    ]
    topo = ["%s: %s" % (c, v) if v else "%s:" % c for c, v in campos]
    return "---\n" + "\n".join(topo) + "\n---\n\n" + md_ato.strip("\n") + "\n"


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    ato = "--ato" in argv
    if argv[1].lower().endswith(".docx"):
        md = md_do_docx(argv[1], ato)
    else:
        with open(argv[1], encoding="utf-8") as f:
            md = md_do_ctresb(f.read(), ato)
    sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
