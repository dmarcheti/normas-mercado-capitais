"""Extração por LLM de ementa, tema, resultado e relator dos julgados convertidos (Task 4 da 2d).

Lê os julgados de plugins/julgados-*/julgados/, recorta cada um (~1.200 tokens: título; o
"## Extrato" ou as ~600 primeiras e ~400 últimas palavras; o "SUMÁRIO" do parecer do comitê),
monta lotes de 25 em dados/fase-2d/extracao/<lote>/lote.json e roda `claude -p` com
scripts/prompts/julgados-extracao.md numa pasta fora do cofre que só tem o lote. Valida o
saida.json e aplica ao frontmatter, marcado como extração:

- ementa (ementa_fonte: extracao) só onde a ementa veio do título e a classe não é rotineira
  (multa cominatória fica com a ementa de modelo, decisão antiga é o arquivo do ano inteiro);
- tema (tema_fonte: extracao) sempre que vazio;
- resultado e relator só se vazios.

A ementa é reprovada se passar de 60 palavras, trouxer dado pessoal ou nome (ou nome e
sobrenome, ou sobrenome composto) de pessoa física do julgado, pela lista positiva de `Pessoas`.
Reprovada, volta uma vez num lote de retentativa com a instrução reforçada (REFORCO); se falhar
de novo, fica a ementa do título e o item é registrado em `ementa_do_titulo` no validacao.json.

    python3 scripts/julgados_extracao.py --ids a,b --model haiku [--simular]
    python3 scripts/julgados_extracao.py --onda 1 --tipo decisao-colegiado --model haiku

Não roda git. O log stream-json e o custo (total_cost_usd) de cada lote ficam na pasta do lote.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import julgados_comum as jc  # noqa: E402
import pii  # noqa: E402

PROMPT = os.path.join(jc.AQUI, "prompts", "julgados-extracao.md")
SAIDA = os.path.join(jc.RAIZ, "dados", "fase-2d", "extracao")
COFRE = os.path.realpath(os.path.expanduser("~/cerebro"))
TAMANHO_LOTE = 25
PALAVRAS_INICIO, PALAVRAS_FIM, PALAVRAS_EXTRATO, PALAVRAS_SUMARIO = 600, 400, 900, 250
MAX_PALAVRAS_EMENTA = 60
ROTINEIRAS = {"multa-cominatoria"}  # ementa de modelo, a partir do título, sem LLM (C7)
SEM_EMENTA_EXTRAIDA = {"decisao-antiga"}  # um arquivo por ano, com dezenas de decisões
TEMAS = ("divulgacao-informacoes", "informacao-privilegiada", "manipulacao-fraude",
         "deveres-administradores", "assembleia-acionistas", "ofertas-publicas", "opa",
         "fundos-investimento", "securitizacao", "intermediacao", "administracao-carteiras",
         "auditoria-independente", "contabil-demonstracoes", "registro-emissor",
         "infraestrutura-mercado", "analistas-rating", "exercicio-irregular", "criptoativos",
         "crowdfunding", "pld", "multa-cominatoria-taxa", "processual", "normativo",
         "institucional", "outros")

# ---------------------------------------------------------------- arquivos

_FM = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def ler_julgado(caminho):
    """(valores do frontmatter, corpo) de um julgado gravado pelo conversor."""
    with open(caminho, encoding="utf-8") as f:
        texto = f.read()
    m = _FM.match(texto)
    if not m:
        raise ValueError("%s: sem frontmatter" % caminho)
    valores = {}
    for linha in m.group(1).splitlines():
        k, _, v = linha.partition(":")
        valores[k.strip()] = v.strip()
    return valores, texto[m.end():].lstrip("\n")


def gravar(caminho, valores, corpo):
    tmp = caminho + ".parcial"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(jc.frontmatter(valores) + corpo)
    os.replace(tmp, caminho)


def julgados(raiz=jc.RAIZ):
    """[{id, tipo, data, url: caminho}] dos julgados gravados, para jc.selecionar."""
    out = []
    for c in sorted(glob.glob(os.path.join(raiz, "plugins", "julgados-*", "julgados", "**",
                                           "*.md"), recursive=True)):
        if os.sep + "indices" + os.sep in c:
            continue
        try:
            v, _ = ler_julgado(c)
        except ValueError:
            continue
        if v.get("id"):
            out.append({"id": v["id"], "tipo": v.get("tipo", ""), "data": v.get("data", ""),
                        "url": c})
    return out


# ---------------------------------------------------------------- recorte


def _palavras(texto, n, do_fim=False):
    p = texto.split()
    return " ".join(p[-n:] if do_fim else p[:n])


def _secao(corpo, nome):
    m = re.search(r"(?ms)^## %s\s*\n(.*?)(?=^## |\Z)" % re.escape(nome), corpo)
    return m.group(1).strip() if m else ""


def recorte(corpo):
    """Título; o "## Extrato" ou as ~600 primeiras e ~400 últimas palavras; o bloco "SUMÁRIO"
    do parecer, se houver."""
    m = re.search(r"(?m)^# (.+)$", corpo)
    titulo = m.group(1).strip() if m else ""
    texto = re.sub(r"(?m)^# .+\n?", "", corpo, count=1).strip()
    texto = re.sub(r"(?m)^#{2,6}\s+", "", texto)
    extrato = _secao(corpo, "Extrato")
    if extrato:
        miolo = _palavras(extrato, PALAVRAS_EXTRATO)
    elif len(texto.split()) <= PALAVRAS_INICIO + PALAVRAS_FIM:
        miolo = texto
    else:
        miolo = (_palavras(texto, PALAVRAS_INICIO) + "\n[...]\n"
                 + _palavras(texto, PALAVRAS_FIM, do_fim=True))
    partes = [titulo, miolo]
    s = re.search(r"(?m)^\W*SUM[ÁA]RIO\b.*$", texto)
    if s and s.group(0).strip() not in miolo:
        partes.append("SUMÁRIO: " + _palavras(texto[s.end():], PALAVRAS_SUMARIO))
    return "\n\n".join(x for x in partes if x)


def entrada(caminho):
    v, corpo = ler_julgado(caminho)
    m = re.search(r"(?m)^# (.+)$", corpo)
    return {"id": v["id"], "tipo": v.get("tipo", ""), "classe": v.get("classe", ""),
            "processo": v.get("processo", ""), "data": v.get("data", ""),
            "titulo": m.group(1).strip() if m else "", "recorte": recorte(corpo)}


def _gravar_json(caminho, obj):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def montar_lotes(caminhos, pasta, prefixo, tamanho=TAMANHO_LOTE, pessoas=None, motivos=None):
    """Grava <pasta>/<prefixo>-NNN/ com lote.json (o que o modelo vê), caminhos.json e
    pessoas.json (lista positiva de pessoas físicas por id, só para a validação); devolve as
    pastas. `motivos` {caminho: motivo}: lote de retentativa (o motivo vai no item)."""
    pessoas = pessoas or Pessoas()
    pastas = []
    for i in range(0, len(caminhos), tamanho):
        d = os.path.join(pasta, "%s-%03d" % (prefixo, i // tamanho + 1))
        os.makedirs(d, exist_ok=True)
        lote, nomes = [], {}
        for c in caminhos[i:i + tamanho]:
            e = entrada(c)
            if motivos:
                e["motivo_retentativa"] = motivos.get(c, "")
            lote.append(e)
            v, corpo = ler_julgado(c)
            nomes[e["id"]] = pessoas.do_julgado(v, corpo)
        _gravar_json(os.path.join(d, "lote.json"), lote)
        _gravar_json(os.path.join(d, "caminhos.json"), caminhos[i:i + tamanho])
        _gravar_json(os.path.join(d, "pessoas.json"), nomes)
        pastas.append(d)
    return pastas


# ---------------------------------------------------------------- modelo


def pasta_de_trabalho(trabalho=None):
    """Pasta nova fora do cofre e do repositório (o modelo só vê o lote)."""
    base = os.path.realpath(trabalho or "/private/tmp")
    for proibida in (COFRE, os.path.realpath(jc.RAIZ)):
        if base == proibida or base.startswith(proibida + os.sep):
            raise ValueError("pasta de trabalho dentro do cofre ou do repositório: %s" % base)
    os.makedirs(base, exist_ok=True)
    return tempfile.mkdtemp(prefix="julgados-extracao-", dir=base)


def comando(modelo):
    return ["claude", "-p", "--model", modelo, "--tools", "Read,Write",
            "--allowedTools", "Read,Write", "--permission-mode", "acceptEdits",
            "--strict-mcp-config", "--output-format", "stream-json", "--verbose",
            "--no-session-persistence"]


def custo(log):
    """total_cost_usd do evento result do stream-json (None se não houver)."""
    for linha in reversed(log.splitlines()):
        try:
            ev = json.loads(linha)
        except ValueError:
            continue
        if isinstance(ev, dict) and ev.get("type") == "result":
            return ev.get("total_cost_usd")
    return None


REFORCO = """

## Retentativa

Estes julgados voltaram porque a ementa da primeira rodada foi reprovada; o motivo está em
`motivo_retentativa` de cada item. Regras reforçadas para a `ementa`:

- no máximo 50 palavras (o limite é 60): conte antes de gravar;
- nenhum nome de pessoa física, nem completo, nem nome e sobrenome, nem sobrenome composto:
  escreva "o acusado", "o diretor", "os conselheiros", "a proponente". Nome de empresa, fundo e
  entidade pode ficar.

Os demais campos seguem as regras acima.
"""


def rodar_lote(pasta_lote, modelo, trabalho=None, timeout=900, reforco=""):
    """Roda o modelo numa pasta só com o lote; copia saida.json e grava log e custo."""
    with open(PROMPT, encoding="utf-8") as f:
        prompt = f.read() + reforco
    prompt += ("\n\n## Tarefa\n\nO lote está em `lote.json`, nesta pasta. Grave `saida.json` "
               "nesta pasta, conforme as regras acima, e nada mais.\n")
    work = pasta_de_trabalho(trabalho)
    shutil.copy(os.path.join(pasta_lote, "lote.json"), os.path.join(work, "lote.json"))
    r = subprocess.run(comando(modelo), input=prompt, cwd=work, capture_output=True, text=True,
                       timeout=timeout)
    with open(os.path.join(pasta_lote, "log.jsonl"), "w", encoding="utf-8") as f:
        f.write(r.stdout or "")
    if r.stderr:
        with open(os.path.join(pasta_lote, "stderr.txt"), "w", encoding="utf-8") as f:
            f.write(r.stderr)
    saida = os.path.join(work, "saida.json")
    if os.path.exists(saida):
        shutil.copy(saida, os.path.join(pasta_lote, "saida.json"))
    info = {"modelo": modelo, "codigo": r.returncode, "total_cost_usd": custo(r.stdout or ""),
            "trabalho": work, "saida": os.path.exists(saida)}
    with open(os.path.join(pasta_lote, "execucao.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    return info


# ---------------------------------------------------------------- pessoas físicas do julgado
#
# A ementa é reprovada se trouxer nome ou sobrenome composto de uma pessoa física do próprio
# julgado (lista positiva). A lista sai de dados/ em tempo de execução e só é gravada em
# dados/ (pessoas.json do lote, fora do Git e fora da pasta que o modelo vê):
#   - acusados do CSV de dados abertos (por NUP);
#   - compromitentes e proponentes das tabelas de TC aceitos e rejeitados (por processo);
#   - partes da descrição do inventário (acusados da listagem de PAS; "apresentada por" etc.);
#   - linhas "Acusado(s):" do corpo (extrato da sessão);
#   - o trecho de partes do título ("TIPO – PARTE – PROC.").
# Fica fora o que tiver marca de entidade (S.A., Ltda, Fundo, Banco...).

ACUSADOS_CSV = os.path.join(jc.RAIZ, "dados", "fase-2d", "inventario", "pas",
                            "processo_sancionador_acusado.csv")
LISTAGENS = os.path.join(jc.RAIZ, "dados", "fase-2d", "listagens")
INVENTARIO = os.path.join(jc.RAIZ, "dados", "fase-2d", "julgados-inventario.json")

_LIGACAO = frozenset(("da", "de", "do", "das", "dos", "e", "d", "del", "della", "di", "van",
                      "von", "y"))
# Palavra que marca entidade (em minúsculas e sem acento): o nome inteiro sai da lista.
_ENTIDADE = frozenset("""
s.a s.a. s/a sa ltda ltda. eireli me epp fia fic fidc fii fip fiagro fiim fim fmp fundo fundos
fund banco bank corretora distribuidora dtvm ctvm participacoes participacao securitizadora
administradora gestora investimentos investimento associacao associados companhia cia cia.
auditores auditoria consultoria consultores advogados sociedade simples holding asset capital
gestao trust partners group grupo industrial industria industrias comercio comercial
construtora incorporadora empreendimentos imobiliaria mineracao metalicos metalurgicos
siderurgica energia eletrica petroleo seguros seguradora previdencia agropecuaria agricola
alimentos servicos tecnologia telecomunicacoes textil engenharia transportes logistica
financeira credito cooperativa instituto fundacao clube bolsa mercados valores mobiliarios
inc ltd llc plc gmbh limited corporation corp co. administracao intervencao liquidacao
recuperacao judicial outros outras brasil brasileira nacional internacional importacao
exportacao representacoes comunicacao editora hotel hoteis farmaceutica quimica
""".split())
# Palavra que não é nome de gente (títulos e descrições do inventário).
_NAO_NOME = frozenset("""
recurso recursos contra decisao decisoes processo processos termo compromisso proposta
propostas pedido pedidos credenciamento autorizacao registro dispensa consulta taxa
fiscalizacao multa cominatoria arquivamento administrativo sancionador inquerito
administrador administradores carteira agente autonomo autonomos diretor diretora diretores
presidente conselheiro conselheiros acusado acusados acusada interessado interessados
recorrente recorrentes proponente proponentes sr sra dr dra cvm sep sin sre smi snc sps soi
sfi sge pfe ssr sse sma spc sdm colegiado comissao superintendencia apreciacao revisao
relator relatora rito ordinario sumario simplificado pas proc procs instrucao resolucao
deliberacao lei art nbc ta oferta publica opa reclamacao denuncia
""".split())
_TRATAMENTO = re.compile(r"^(?:(?:Sr|Sra|Srs|Dr|Dra|Sres)\.?\s+)+", re.I)


def _dobrar(texto):
    """Minúsculas sem acento, um caractere por caractere (mantém as posições)."""
    import unicodedata
    return "".join((unicodedata.normalize("NFD", ch)[0] if ch.strip() else ch).lower()
                   for ch in texto)


def _palavras_nome(nome):
    return re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’.\-]*", nome)


def pessoa(nome):
    """O nome limpo, se parece pessoa física (2 a 8 palavras, sem marca de entidade nem palavra
    de título); senão ""."""
    s = re.sub(r"\([^)]*\)?|[\"“”«»]", " ", nome or "")
    s = re.sub(r"\s+", " ", s).strip(" .,;:-–")
    s = _TRATAMENTO.sub("", re.sub(r"(?i)^(?:ou|e|a|o)\s+", "", s))
    if not s or re.search(r"\d|@|/", s):
        return ""
    toks = _palavras_nome(s)
    dobr = [_dobrar(t).strip(".") for t in toks]
    if any(d in _ENTIDADE or d + "." in _ENTIDADE for d in dobr):
        return ""
    if any(d in _NAO_NOME for d in dobr):
        return ""
    plenas = [d for d in dobr if d not in _LIGACAO and len(d) > 1]
    if not 2 <= len(plenas) <= 8:
        return ""
    return " ".join(toks)


def separar_partes(texto):
    """Nomes de uma lista de partes ("A, B e C"; um por linha; "; ")."""
    texto = re.sub(r"(?i)\be\s+outr[oa]s\b", "", texto or "")
    out = []
    for p in re.split(r"\s*(?:[,;\n]|\s+e\s+|\s+E\s+)\s*", texto):
        n = pessoa(p)
        if n and n not in out:
            out.append(n)
    return out


_DESC_PARTES = (
    re.compile(r"apresentad[ao]s?\s+(?:\(i+\)\s*)?(?:[a-zà-ÿ]+\s+){0,3}?por\s+(.{3,600}?)"
               r"(?:\(|\bna qualidade\b|\bem raz[ãa]o\b|\bno [aâ]mbito\b|\bpara\b|[;:]|\.\s|$)"),
    re.compile(r"interpost[oa]s?\s+pel[oa]s?\s+(.{3,300}?)(?:\(|\bcontra\b|\bna qualidade\b|"
               r"[;:]|\.\s|$)"),
    re.compile(r"INTERESSAD[OA]\(?S?\)?\s*:\s*(.{3,300}?)(?:\s{2,}|\b[A-Z]{4,}\s*:|$)"),
    re.compile(r"[Rr]esponsabilidade de\s+(.{3,200}?)(?:\bpor\b|\(|[;:]|\.\s|$)"),
)


def partes_da_descricao(desc, tipo=""):
    desc = re.sub(r"\s+", " ", desc or "")
    out = []
    if tipo == "pas":  # listagem de PAS: acusados em caixa alta antes da ementa
        m = re.match(r"((?:[A-ZÀ-Ý0-9.,&'’/()\-]+\s+)+?)(?=[A-ZÀ-Ý][a-zà-ÿ]|$)", desc + " ")
        if m:
            out += separar_partes(m.group(1))
    for rx in _DESC_PARTES:
        for m in rx.finditer(desc):
            out += [n for n in separar_partes(m.group(1)) if n not in out]
    return out


_ROTULO = re.compile(r"(?im)^\W*(?:acusad[oa]s?|acusado\(s\)|acusada\(s\)|interessad[oa]s?|"
                     r"recorrentes?|proponentes?|compromitentes?)\s*:[ \t]*(.*)$")
_OUTRO_ROTULO = re.compile(r"^\W*[A-ZÀ-Ý][A-Za-zÀ-ÿ()\s]{1,30}:")


def partes_do_corpo(corpo):
    """Nomes das linhas "Acusado(s):" (e afins) do corpo; o valor pode seguir nas linhas de
    baixo, até o próximo rótulo ("Ementa:", "Assunto:") ou linha em branco."""
    out = []
    linhas = corpo.splitlines()
    for i, ln in enumerate(linhas):
        m = _ROTULO.match(ln)
        if not m:
            continue
        valor = [re.sub(r"(?i)^assunto\s*:\s*", "", m.group(1)).strip()]
        for prox in linhas[i + 1:i + 30]:
            if not prox.strip() or prox.startswith("#") or _OUTRO_ROTULO.match(prox):
                break
            valor.append(prox.strip())
        out += [n for n in separar_partes("\n".join(v for v in valor if v)) if n not in out]
    return out


def partes_do_titulo(titulo):
    """O trecho de partes de "TIPO – PARTE – PROC. X" (sem o tipo e sem o processo)."""
    seg = [s.strip() for s in re.split(r"\s+[–—-]\s+", titulo or "")]
    out = []
    for s in seg[1:]:
        if re.match(r"(?i)(procs?\.?|pas|processos?|inqu[ée]rito|rj|sp|\d)", s):
            continue
        out += [n for n in separar_partes(s) if n not in out]
    return out


def _nup_digitos(texto):
    return re.sub(r"\D", "", texto or "")


class Pessoas:
    """Lista positiva de pessoas físicas por julgado; as fontes de dados/ carregam na 1ª consulta
    (ou vêm prontas, nos testes)."""

    def __init__(self, acusados=None, partes_tc=None, descricoes=None, acusados_csv=ACUSADOS_CSV,
                 listagens=LISTAGENS, inventario=INVENTARIO):
        self._acusados, self._partes_tc, self._desc = acusados, partes_tc, descricoes
        self._csv, self._listagens, self._inventario = acusados_csv, listagens, inventario

    @property
    def acusados(self):
        if self._acusados is None:
            self._acusados = {}
            if os.path.exists(self._csv):
                import csv
                with open(self._csv, encoding="latin-1", newline="") as f:
                    for row in csv.DictReader(f, delimiter=";"):
                        n = pessoa(row.get("Nome_Acusado", ""))
                        if n:
                            self._acusados.setdefault(_nup_digitos(row.get("NUP")), []).append(n)
        return self._acusados

    @property
    def partes_tc(self):
        if self._partes_tc is None:
            self._partes_tc = {}
            import julgados_inventario as ji
            for nome, colunas in (("tc_aceitos.html", (0, 4)), ("tc_rejeitados.html", (2,))):
                c = os.path.join(self._listagens, nome)
                if not os.path.exists(c):
                    continue
                with open(c, encoding="utf-8", errors="replace") as f:
                    html = f.read()
                for tds in ji._linhas_tabela(html):
                    proc = jc.normalizar_processo(ji._txt(tds[0]))
                    if not proc:
                        continue
                    for col in colunas:
                        if col >= len(tds):
                            continue
                        txt = ji._txt(tds[col])
                        if col == 0:  # "RJ96/4025 - PARTE"
                            txt = re.split(r"\s+[–-]\s+", txt, maxsplit=1)[1:] or [""]
                            txt = txt[0]
                        self._partes_tc.setdefault(proc, []).extend(separar_partes(txt))
        return self._partes_tc

    @property
    def descricoes(self):
        if self._desc is None:
            self._desc = {}
            if os.path.exists(self._inventario):
                with open(self._inventario, encoding="utf-8") as f:
                    for x in json.load(f).get("julgados", []):
                        if x.get("desc"):
                            self._desc[x["id"]] = (x.get("tipo", ""), x["desc"])
        return self._desc

    def do_julgado(self, valores, corpo):
        out = []

        vistos = set()

        def mais(nomes):
            for n in nomes:
                if _dobrar(n) not in vistos:
                    vistos.add(_dobrar(n))
                    out.append(n)

        mais(self.acusados.get(_nup_digitos(valores.get("nup")), []))
        for p in re.split(r"\s*;\s*", valores.get("processo", "")):
            proc = jc.normalizar_processo(p)
            if proc:
                mais(self.partes_tc.get(proc, []))
                if not valores.get("nup") and jc.nup(p):
                    mais(self.acusados.get(_nup_digitos(jc.nup(p)), []))
        tipo, desc = self.descricoes.get(valores.get("id", ""), ("", ""))
        mais(partes_da_descricao(desc, tipo or valores.get("tipo", "")))
        mais(partes_do_corpo(corpo))
        m = re.search(r"(?m)^# (.+)$", corpo)
        mais(partes_do_titulo(m.group(1) if m else ""))
        return out


def tem_nome(ementa, pessoas_):
    """A ementa traz duas palavras capitalizadas seguidas (com "da", "de"... no meio) que são,
    na mesma ordem, partes do nome de uma pessoa da lista? Pega nome completo, nome e sobrenome
    ("Eike Batista") e sobrenome composto ("Silva Vargas"). Devolve o trecho ou ""."""
    if not ementa or not pessoas_:
        return ""
    toks = [(m.group(0), _dobrar(m.group(0)).strip(".")) for m in
            re.finditer(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’.\-]*", ementa)]
    listas = []
    for p in pessoas_:
        d = [_dobrar(t).strip(".") for t in _palavras_nome(p)]
        listas.append([x for x in d if x not in _LIGACAO and len(x) > 1])
    for i, (orig, d) in enumerate(toks):
        if not orig[0].isupper() or d in _LIGACAO:
            continue
        j = i + 1
        while j < len(toks) and toks[j][1] in _LIGACAO and not toks[j][0][0].isupper():
            j += 1
        if j >= len(toks) or not toks[j][0][0].isupper():
            continue
        a, b = d, toks[j][1]
        for nome in listas:
            if a in nome and b in nome and nome.index(a) < len(nome) - 1 - nome[::-1].index(b):
                return "%s %s" % (orig, toks[j][0])
    return ""


# ---------------------------------------------------------------- D3 na ementa oficial

PESSOA_OMITIDA = "[pessoa física]"
AVISO_EMENTA = ("nomes de pessoa física omitidos da ementa do frontmatter; ementa integral na "
                "seção Ementa")
_PESSOAS_PADRAO = None


def _trechos_de_nome(ementa, pessoas_):
    """[(ini, fim)] dos trechos da ementa com duas ou mais palavras capitalizadas seguidas que
    são, na ordem, partes do nome de uma pessoa da lista ("da", "de"... e iniciais no meio)."""
    toks = [(m.start(), m.end(), m.group(0), _dobrar(m.group(0)).strip(".")) for m in
            re.finditer(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’.\-]*", ementa or "")]
    nomes = []
    for p in pessoas_ or ():
        d = [x for x in (_dobrar(t).strip(".") for t in _palavras_nome(p))
             if x not in _LIGACAO and len(x) > 1]
        if len(d) >= 2:
            nomes.append(d)
    out, i = [], 0
    while i < len(toks):
        ini, _, orig, d = toks[i]
        melhor = None
        if orig[0].isupper() and d not in _LIGACAO:
            for nome in nomes:
                if d not in nome:
                    continue
                pos, ult, n, k = nome.index(d), i, 1, i + 1
                while k < len(toks) and not ementa[toks[k - 1][1]:toks[k][0]].strip():
                    o2, d2 = toks[k][2], toks[k][3]
                    if d2 in _LIGACAO or (len(d2) == 1 and o2[0].isupper()):
                        k += 1
                        continue
                    if not (o2[0].isupper() and d2 in nome[pos + 1:]):
                        break
                    pos, ult, n, k = nome.index(d2, pos + 1), k, n + 1, k + 1
                if n >= 2 and (melhor is None or ult > melhor):
                    melhor = ult
        if melhor is None:
            i += 1
            continue
        fim, orig_ult = toks[melhor][1], toks[melhor][2]
        if len(toks[melhor][3]) > 1:  # ponto final da frase não é do nome (o da inicial é)
            fim -= len(orig_ult) - len(orig_ult.rstrip("."))
        out.append((ini, fim))
        i = melhor + 1
    return out


def trocar_nomes(ementa, pessoas_):
    """A ementa com cada nome da lista trocado por "[pessoa física]"."""
    for ini, fim in reversed(_trechos_de_nome(ementa, pessoas_)):
        ementa = ementa[:ini] + PESSOA_OMITIDA + ementa[fim:]
    return ementa


def _nomes_em_caixa_alta(ementa):
    """Pessoas da lista de acusados em caixa alta que abre as ementas antigas ("FULANO DE TAL e
    ACME S.A. – Ementa...")."""
    e = re.sub(r"\s+", " ", ementa or "").strip()
    m = re.match(r"^(.{3,400}?)\s+[-–—]\s+(?=\S)", e)
    return separar_partes(m.group(1)) if m and jc._caixa_alta(m.group(1)) else []


def ementa_sem_pessoas(valores, corpo, pessoas_=None, publicada=""):
    """D3 na ementa de qualquer fonte: (valores, corpo, nº de trocas). Os nomes da lista positiva
    do julgado (`pessoas_`, ou a de `Pessoas().do_julgado`) e os da lista em caixa alta antes do
    travessão viram "[pessoa física]" só no frontmatter; o corpo ganha `## Ementa` logo depois do
    `# título` com a ementa como publicada (`publicada`, ou a do frontmatter), se ainda não tem."""
    global _PESSOAS_PADRAO
    ementa = valores.get("ementa") or ""
    if pessoas_ is None:
        if _PESSOAS_PADRAO is None:
            _PESSOAS_PADRAO = Pessoas()
        pessoas_ = _PESSOAS_PADRAO.do_julgado(valores, corpo)
    lista = list(pessoas_) + _nomes_em_caixa_alta(publicada) + _nomes_em_caixa_alta(ementa)
    trechos = _trechos_de_nome(ementa, lista)
    if not trechos:
        return valores, corpo, 0
    inc = [x for x in (valores.get("incerteza") or "").split("; ") if x]
    novos = dict(valores, ementa=trocar_nomes(ementa, lista),
                 incerteza="; ".join(dict.fromkeys(inc + [AVISO_EMENTA])))
    if not re.search(r"(?m)^## Ementa\s*$", corpo):
        texto = re.sub(r"\s+", " ", publicada or ementa).strip()
        m = re.search(r"(?m)^# .*\n", corpo)
        fim = m.end() if m else 0
        resto = corpo[fim:].lstrip("\n")
        corpo = corpo[:fim] + "\n## Ementa\n\n" + texto + "\n\n" + resto
    return novos, corpo, len(trechos)


# ---------------------------------------------------------------- validação


def validar_saida(lote, saida, pessoas=None, reprovadas=None):
    """(aprovados {id: campos}, erros). Erro de lote (ids faltando ou sobrando) reprova o lote;
    campo inválido sai do item (ementa longa ou com nome de pessoa física do julgado, tema ou
    resultado fora da lista). `pessoas`: {id: [nomes]} (pessoas.json do lote); `reprovadas`, se
    dado, recebe {id: motivo} das ementas reprovadas (para a retentativa)."""
    pessoas = pessoas or {}
    reprovadas = {} if reprovadas is None else reprovadas
    erros = []
    if not isinstance(saida, list):
        return {}, ["saida.json não é uma lista"]
    por_id = {}
    for o in saida:
        if isinstance(o, dict) and o.get("id"):
            por_id[o["id"]] = o
    ids = [x["id"] for x in lote]
    faltam, sobram = set(ids) - set(por_id), set(por_id) - set(ids)
    if faltam:
        erros.append("ids faltando: %s" % ", ".join(sorted(faltam)))
    if sobram:
        erros.append("ids a mais: %s" % ", ".join(sorted(sobram)))
    if faltam or sobram:
        return {}, erros
    aprovados = {}
    for x in lote:
        o, campos = por_id[x["id"]], {}
        ementa = re.sub(r"\s+", " ", str(o.get("ementa") or "")).strip()
        if ementa:
            if len(ementa.split()) > MAX_PALAVRAS_EMENTA:
                motivo = "ementa com mais de %d palavras" % MAX_PALAVRAS_EMENTA
            elif tem_nome(ementa, pessoas.get(x["id"], [])):
                motivo = "ementa com nome de pessoa"
            elif pii.limpar(ementa) != ementa:
                motivo = "ementa com dado pessoal"
            else:
                motivo = ""
                campos["ementa"] = ementa
            if motivo:
                erros.append("%s: %s" % (x["id"], motivo))
                reprovadas[x["id"]] = motivo
        tema = str(o.get("tema") or "").strip()
        if tema in TEMAS:
            campos["tema"] = tema
        elif tema:
            erros.append("%s: tema fora da lista (%s)" % (x["id"], tema))
        res = str(o.get("resultado") or "").strip()
        if res in jc.RESULTADOS.get(x["tipo"], ()):
            campos["resultado"] = res
        elif res:
            erros.append("%s: resultado fora da lista do tipo (%s)" % (x["id"], res))
        rel = str(o.get("relator") or "").strip()
        if rel:
            campos["relator"] = pii.limpar(rel)
        aprovados[x["id"]] = campos
    return aprovados, erros


# ---------------------------------------------------------------- aplicação


def quer_ementa(v):
    """A ementa extraída substitui a do título? (não na rotineira nem na decisão antiga)"""
    return (v.get("ementa_fonte") == "titulo" and v.get("classe") not in ROTINEIRAS
            and v.get("tipo") not in SEM_EMENTA_EXTRAIDA)


def aplicar(caminho, campos):
    """Grava no frontmatter os campos extraídos, pelas regras da Task 4; devolve os alterados."""
    v, corpo = ler_julgado(caminho)
    mudou = []
    if "ementa" in campos and quer_ementa(v):
        v["ementa"], v["ementa_fonte"] = campos["ementa"], "extracao"
        mudou.append("ementa")
    if campos.get("tema") and not v.get("tema"):
        v["tema"], v["tema_fonte"] = campos["tema"], "extracao"
        mudou.append("tema")
    for c in ("resultado", "relator"):
        if campos.get(c) and not v.get(c):
            v[c] = campos[c]
            mudou.append(c)
    if mudou:
        gravar(caminho, {k: v.get(k, "") for k in jc.CAMPOS}, corpo)
    return mudou


def processar_lote(pasta_lote):
    """Valida saida.json do lote e aplica; grava validacao.json. "retentar" traz {caminho:
    motivo} das ementas reprovadas (longa, com nome, com dado pessoal) que ainda substituiriam a
    do título."""
    with open(os.path.join(pasta_lote, "lote.json"), encoding="utf-8") as f:
        lote = json.load(f)
    with open(os.path.join(pasta_lote, "caminhos.json"), encoding="utf-8") as f:
        caminhos = dict(zip([x["id"] for x in lote], json.load(f)))
    c_pessoas = os.path.join(pasta_lote, "pessoas.json")
    if os.path.exists(c_pessoas):
        with open(c_pessoas, encoding="utf-8") as f:
            pessoas = json.load(f)
    else:
        p = Pessoas()
        pessoas = {i: p.do_julgado(*ler_julgado(c)) for i, c in caminhos.items()}
    reprovadas = {}
    try:
        with open(os.path.join(pasta_lote, "saida.json"), encoding="utf-8") as f:
            saida = json.load(f)
    except (OSError, ValueError) as e:
        saida, aprovados, erros = None, {}, ["saida.json ausente ou inválido (%s)" %
                                             type(e).__name__]
    if saida is not None:
        aprovados, erros = validar_saida(lote, saida, pessoas, reprovadas)
    aplicados = {i: aplicar(caminhos[i], c) for i, c in aprovados.items()}
    retentar = {caminhos[i]: m for i, m in reprovadas.items()
                if quer_ementa(ler_julgado(caminhos[i])[0])}
    rel = {"erros": erros, "aplicados": aplicados, "retentar": retentar}
    _gravar_json(os.path.join(pasta_lote, "validacao.json"), rel)
    return rel


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ids", help="ids separados por vírgula")
    ap.add_argument("--onda", type=int, choices=sorted(jc.ONDAS))
    ap.add_argument("--tipo", choices=jc.TIPOS)
    ap.add_argument("--limite", type=int)
    ap.add_argument("--model", default="haiku", choices=("haiku", "sonnet"))
    ap.add_argument("--simular", action="store_true", help="só monta os lotes, sem o modelo")
    ap.add_argument("--trabalho", help="pasta-base de trabalho fora do cofre (padrão /private/tmp)")
    ap.add_argument("--raiz", default=jc.RAIZ)
    ap.add_argument("--saida", default=SAIDA)
    a = ap.parse_args(argv)
    ids = [x.strip() for x in a.ids.split(",") if x.strip()] if a.ids else None
    itens = jc.selecionar(julgados(a.raiz), ids=ids, tipo=a.tipo, onda=a.onda, limite=a.limite)
    if ids:
        faltam = set(ids) - {x["id"] for x in itens}
        if faltam:
            print("sem arquivo convertido: %s" % ", ".join(sorted(faltam)), file=sys.stderr)
    prefixo = "%s-%s" % (jc.hoje_sp(), a.model)
    n = len(glob.glob(os.path.join(a.saida, prefixo + "*")))
    pastas = montar_lotes([x["url"] for x in itens], a.saida,
                          prefixo + ("-%d" % n if n else ""))
    print("%d julgado(s) em %d lote(s) em %s" % (len(itens), len(pastas), a.saida))
    if a.simular:
        return 0
    total, falhas, retentar = 0.0, 0, {}

    def rodar(p, reforco=""):
        nonlocal total, falhas
        info = rodar_lote(p, a.model, a.trabalho, reforco=reforco)
        rel = processar_lote(p)
        total += info["total_cost_usd"] or 0
        falhas += info["codigo"] != 0 or any(e.split(":")[0] not in rel["aplicados"]
                                             for e in rel["erros"])  # erro de lote
        print("%s: US$ %s; %d aplicado(s); %d erro(s)" % (
            os.path.basename(p), info["total_cost_usd"],
            sum(1 for v in rel["aplicados"].values() if v), len(rel["erros"])))
        return rel

    for p in pastas:
        retentar.update(rodar(p)["retentar"])
    if retentar:  # uma vez, com a instrução reforçada; se falhar, fica a ementa do título
        ficaram = {}
        for p in montar_lotes(sorted(retentar), a.saida, os.path.basename(pastas[0])[:-4]
                              + "-retentativa", motivos=retentar):
            rel = rodar(p, REFORCO)
            ficaram.update({c: m for c, m in rel["retentar"].items()})
            rel["ementa_do_titulo"] = sorted(rel["retentar"])
            _gravar_json(os.path.join(p, "validacao.json"), rel)
        print("retentativa: %d item(ns); %d ficaram com a ementa do título" % (
            len(retentar), len(ficaram)))
        for c, m in sorted(ficaram.items()):
            print("  ementa do título: %s (%s)" % (os.path.basename(c), m), file=sys.stderr)
    print("custo total: US$ %.4f" % total)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
