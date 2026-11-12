#!/usr/bin/env python3
"""Teste 2 das leis (Decisão 8): a conversão do compilado do Planalto está fiel.

Não há gabarito independente do Planalto; o teste é de conversão:
1. os artigos da norma estão em ordem crescente, sem lacuna (9º, 9º-A, 9º-B, 10);
2. o texto da norma (a partir do primeiro `## Art.`) é igual ao texto visível
   não tachado do HTML, linha a linha. As notas do Planalto ("(Redação dada
   pela Lei ...)") ficam no texto e contam na comparação.

Conferência de conversão, não de conteúdo: texto tachado (`<strike>`, `<s>`, `<del>` e
`<span style="text-decoration:line-through">`) não conta; `<br>` e célula de tabela viram
espaço; linha de tabela do Markdown conta pelas células não vazias (separadores não contam);
artigo dentro de citação (“...”, artigo de outra lei alterada pelo artigo em curso) é
texto, não cabeçalho; "ruído de página" do Planalto (`*`, "Não remover", "Up", "Down" sozinhos
numa linha) não conta, em nenhum dos lados.

Recorte (Código Civil, arts. 1.368-C a 1.368-F): o HTML é cortado do primeiro
artigo da norma até antes do primeiro artigo de número diferente do último
artigo da norma; o resto do Código fica de fora. Um título de divisão (TÍTULO IV...,
CAPÍTULO...) que venha antes desse artigo seguinte também fica de fora.

diferencas_lei(md_lei, html_compilado) -> lista de diferenças (vazia = ok).
`html_compilado` pode ser str ou bytes (o charset vem do <meta>).

Uso: python3 scripts/teste_lei.py <id> [--norma ARQ.md] [--html ARQ.html]
<id> é lei-N, decreto-N ou lcp-N (ex.: lei-6404, decreto-11964, lcp-105). Sem
--norma, usa leis/<nome>.md ou leis/<nome>/index.md (norma em partes), com <nome>
= lei-NNNNN, decreto-NNNNN ou lcp-NNN. Sem --html, usa dados/fontes/<nome>.html
(cache de scripts/baixar.py). Saída 0 = ok; 1 = diferenças; 2 = uso/erro.
"""
import difflib
import os
import re
import sys
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from converter import com_rotulo_riscado, decodificar_html, normalizar_artigos, sem_rotulos_de_vigencia  # noqa: E402
from normalizar import _CARACTERES  # noqa: E402
from validar import texto_da_norma  # noqa: E402

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LEIS = os.path.join(RAIZ, "plugins", "normas", "skills", "consultar-normas", "normas", "leis")
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
_HEADING = re.compile(r"^## Art\. (\S+)$")
_ROTULO = re.compile(r"^(\d[\d.]*)[ºª]?(?:-([A-Z]+))?$")
_BLOCOS = {"p", "div", "li", "ul", "ol", "tr", "table", "blockquote", "center",
           "h1", "h2", "h3", "h4", "h5", "h6", "pre", "hr"}
_CELULAS = {"td", "th"}
_RUIDO = {"*", "Não remover", "Up", "Down"}
_SEPARADOR_TABELA = re.compile(r"^\|(?:\s*:?-{3,}:?\s*\|)+$")
# Título de divisão do texto ("TÍTULO IV Da Superfície"): no recorte, pertence ao artigo seguinte.
ESTRUTURA = re.compile(
    r"^(?:LIVRO|T[ÍI]TULO|SUBT[ÍI]TULO|CAP[ÍI]TULO|SE[ÇC][ÃA]O|SUBSE[ÇC][ÃA]O)\s+[IVXLCDM]+\b", re.I)
_IGNORADAS = {"script", "style", "head", "title"}
# Normas federais da camada de leis (SPEC v0.3.0): tipo -> (prefixo do id, nome do arquivo sem extensão).
TIPOS_LEI = {
    "lei": ("lei-", "lei-%05d"),
    "decreto": ("decreto-", "decreto-%05d"),
    "lei-complementar": ("lcp-", "lcp-%03d"),
}
_TACHADAS = {"strike", "s", "del"}


class _TextoVisivel(HTMLParser):
    """Texto visível do HTML, um parágrafo por bloco; sem tachado, script e style."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paragrafos, self._atual, self._riscado = [], [], []
        self._ignorar = self._tachado = self._sup = self._celulas = 0
        self._spans = []

    def _fechar(self):
        texto = com_rotulo_riscado("".join(self._atual), "".join(self._riscado))
        if texto and texto not in _RUIDO:
            self.paragrafos.append(texto)
        self._atual, self._riscado = [], []

    def handle_starttag(self, tag, attrs):
        if tag in _IGNORADAS:
            self._ignorar += 1
        elif tag in _TACHADAS:
            self._tachado += 1
        elif tag == "span":
            riscado = "line-through" in (dict(attrs).get("style") or "").lower()
            self._spans.append(riscado)
            self._tachado += riscado
        elif tag == "sup":
            self._sup += 1
        elif tag == "br":
            self._atual.append(" ")
        elif tag in _CELULAS:
            self._celulas += 1
            self._atual.append(" ")
        elif tag in _BLOCOS:
            if self._celulas and tag not in ("tr", "table"):
                self._atual.append(" ")  # parágrafo dentro de célula: a célula é uma linha só
            else:
                self._fechar()

    def handle_endtag(self, tag):
        if tag in _IGNORADAS:
            self._ignorar = max(0, self._ignorar - 1)
        elif tag in _TACHADAS:
            self._tachado = max(0, self._tachado - 1)
        elif tag == "span":
            if self._spans and self._spans.pop():
                self._tachado = max(0, self._tachado - 1)
        elif tag == "sup":
            self._sup = max(0, self._sup - 1)
        elif tag in _CELULAS:
            self._celulas = max(0, self._celulas - 1)
            self._atual.append(" ")
        elif tag in _BLOCOS:
            if self._celulas and tag not in ("tr", "table"):
                self._atual.append(" ")
            else:
                self._celulas = 0 if tag in ("tr", "table") else self._celulas
                self._fechar()

    def handle_data(self, data):
        if self._ignorar:
            return
        if self._sup and data.strip() in ("o", "O", "a", "A"):
            data = "º" if data.strip() in ("o", "O") else "ª"
        if self._tachado:
            if not self._celulas and not "".join(self._atual).strip():
                self._riscado.append(data)
            return
        self._atual.append(data)

    def close(self):
        super().close()
        self._fechar()


def _texto_do_html(html):
    p = _TextoVisivel()
    p.feed(sem_rotulos_de_vigencia(decodificar_html(html)))
    p.close()
    return "\n\n".join(p.paragrafos)


def _unidades(md):
    """Lista de (rótulo ou None, texto): cada `## Art. X` junto com o parágrafo que
    o segue; linhas `# título` (de parte) e o que vem antes do 1º artigo ficam de fora."""
    md = _FRONTMATTER.sub("", md, count=1)
    linhas = []
    for l in normalizar_artigos(md, ignorar_citacoes=True).translate(_CARACTERES).split("\n"):
        l = " ".join(l.split())
        if l.startswith("|"):  # tabela de dados do Markdown: células não vazias, sem separador
            if _SEPARADOR_TABELA.match(l):
                continue
            l = " ".join(c.strip() for c in re.split(r"(?<!\\)\|", l.strip("|")) if c.strip())
        if l and not l.startswith("# ") and l not in _RUIDO:
            linhas.append(l)
    unidades, i = [], 0
    while i < len(linhas):
        m = _HEADING.match(linhas[i])
        if m:
            texto = "Art. " + m.group(1)
            if i + 1 < len(linhas) and not _HEADING.match(linhas[i + 1]):
                texto += " " + linhas[i + 1]
                i += 1
            unidades.append((m.group(1), texto))
        elif unidades:
            unidades.append((None, linhas[i]))
        i += 1
    return unidades


def _chave(rotulo):
    m = _ROTULO.match(rotulo)
    if not m:
        return None
    return int(m.group(1).replace(".", "")), m.group(2) or ""


def _sucessor(letras):
    """"" -> A, A -> B, Z -> AA."""
    if not letras:
        return "A"
    if letras[-1] != "Z":
        return letras[:-1] + chr(ord(letras[-1]) + 1)
    return _sucessor(letras[:-1]) + "A" if len(letras) > 1 else "AA"


def _erros_de_sequencia(rotulos):
    erros, anterior = [], None
    for r in rotulos:
        k = _chave(r)
        if k is None:
            erros.append("artigo com rótulo ilegível: Art. %s" % r)
            continue
        if anterior is not None:
            (n1, l1), (n2, l2) = anterior[1], k
            proximo = (n2 == n1 and l2 == _sucessor(l1)) or (n2 == n1 + 1 and l2 == "")
            if not proximo:
                if (n2, (len(l2), l2)) <= (n1, (len(l1), l1)):
                    erros.append("artigo fora de ordem: Art. %s depois de Art. %s" % (r, anterior[0]))
                else:
                    erros.append("lacuna entre Art. %s e Art. %s" % (anterior[0], r))
        anterior = (r, k)
    return erros


def _recortar(html, rotulos):
    """Unidades do HTML do primeiro artigo da norma até antes do primeiro artigo de
    número diferente do último. Devolve (unidades, erro)."""
    inicio = next((i for i, (r, _) in enumerate(html) if r == rotulos[0]), None)
    if inicio is None:
        return [], "html sem o artigo inicial da norma: Art. %s" % rotulos[0]
    fim = len(html)
    ultimo = _chave(rotulos[-1])
    ultimo_i = next((i for i in range(inicio, len(html)) if html[i][0] == rotulos[-1]), None)
    if ultimo_i is not None and ultimo is not None:
        for i in range(ultimo_i + 1, len(html)):
            k = _chave(html[i][0]) if html[i][0] else None
            if k is not None and k[0] != ultimo[0]:
                fim = i
                break
        # divisão (TÍTULO, CAPÍTULO...) entre o último artigo e o seguinte é do seguinte
        for i in range(ultimo_i + 1, fim if fim < len(html) else ultimo_i + 1):
            if ESTRUTURA.match(html[i][1]):
                fim = i
                break
    return html[inicio:fim], None


def _contexto(unidades, i):
    while i >= 0:
        if unidades[i][0]:
            return "Art. " + unidades[i][0]
        i -= 1
    return "?"


def diferencas_lei(md_lei, html_compilado):
    norma = _unidades(md_lei)
    rotulos = [r for r, _ in norma if r]
    if not rotulos:
        return ["norma sem nenhum artigo (## Art.)"]
    dif = _erros_de_sequencia(rotulos)
    html, erro = _recortar(_unidades(_texto_do_html(html_compilado)), rotulos)
    if erro:
        return dif + [erro]
    a, b = [t for _, t in html], [t for _, t in norma]
    ops = difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            continue
        for i in range(i1, i2):
            dif.append("[%s] só no HTML: %s" % (_contexto(html, i), a[i]))
        for j in range(j1, j2):
            dif.append("[%s] só na norma: %s" % (_contexto(norma, j), b[j]))
    return dif


def nome_do_arquivo(id_norma):
    """lei-6385 -> lei-06385; decreto-11964 -> decreto-11964; lcp-105 -> lcp-105; outro id -> None."""
    for prefixo, molde in TIPOS_LEI.values():
        m = re.fullmatch(re.escape(prefixo) + r"([1-9]\d*)", id_norma)
        if m:
            return molde % int(m.group(1))
    return None


def _caminho_norma(nome):
    base = os.path.join(LEIS, nome)
    return base + ".md" if os.path.exists(base + ".md") else os.path.join(base, "index.md")


def main(argv):
    args = argv[1:]
    opcoes = {}
    for chave in ("--norma", "--html"):
        if chave in args:
            i = args.index(chave)
            opcoes[chave] = args[i + 1] if i + 1 < len(args) else None
            del args[i:i + 2]
    if len(args) != 1 or None in opcoes.values():
        print(__doc__)
        return 2
    nome = nome_do_arquivo(args[0])
    if nome is None:
        print("teste_lei: id inválido %r (esperado lei-N, decreto-N ou lcp-N)" % args[0])
        return 2
    norma = opcoes.get("--norma") or _caminho_norma(nome)
    html = opcoes.get("--html") or os.path.join(RAIZ, "dados", "fontes", nome + ".html")
    for caminho, nome in ((norma, "norma"), (html, "HTML")):
        if not os.path.exists(caminho):
            print("teste_lei: %s não encontrado: %s" % (nome, caminho))
            return 2
    with open(html, "rb") as f:
        dados = f.read()
    dif = diferencas_lei(texto_da_norma(norma), dados)
    for d in dif:
        print(d)
    print("teste_lei: %s, %d diferença(s)" % (args[0], len(dif)))
    return 1 if dif else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
