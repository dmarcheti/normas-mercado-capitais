#!/usr/bin/env python3
"""Gera as fichas dos julgados para o plugin do Claude (Fase 6).

O plugin nao comporta o texto integral dos 14.991 julgados (limite de 200 MB e
5.000 arquivos). Ele leva uma ficha por julgado, agrupada em poucos arquivos
Markdown; o texto integral fica no GitHub (campo texto_integral). So a
biblioteca padrao do Python.

Uso:
    python3 scripts/fichas.py [--entrada julgados/]
                              [--saida plugins/normas/skills/consultar-normas/julgados/fichas/]
                              [--medidas dados/fase-6/medidas.json]
                              [--amostra dados/fase-6/amostra-fichas.md]
    python3 scripts/fichas.py --verificar     regenera em memoria e compara com o disco (rc 1 se diferir)

A saida padrao fica dentro da skill (a unica pasta que o claude.ai monta); os indices dos julgados
(`indice.py`) apontam para estes arquivos. `--verificar` acusa arquivo diferente, ausente ou que
sobrou de geracao anterior.

Saida: <saida>/<grupo>/<AAAA>.md, com grupos pas, tc (Colegiado com
tipo: termo-compromisso), colegiado (demais decisoes do Colegiado), crsfn e
decisoes-antigas. O ano e o da pasta (ou do nome do arquivo anual). Arquivo
acima de 24.000 bytes (UTF-8) divide em <AAAA>-01.md, <AAAA>-02.md... A ordem
das fichas e data e depois id. Cada arquivo comeca com um titulo curto do grupo
e do ano. A saida e deterministica (mesma entrada, mesmos bytes). Antes de
gravar, o script apaga os .md antigos dos grupos que ele gera.

Ficha: titulo "## <id>", uma linha "- campo: valor" para id, tipo, processo,
data, relator, resultado, ementa, tema, dispositivos_citados e
nivel_verificacao (campo opcional vazio sai vazio), depois texto_integral
(URL raw do GitHub), trecho_regra (qual regra achou o trecho) e trecho. Faltar
id ou data e erro: o script falha e diz qual arquivo. Falta de texto nunca vira
"ok": sem corpo, o trecho diz "sem texto no acervo".

Regra do trecho da decisao (ate 1.500 caracteres, cortado em limite de palavra,
com " [...]" no fim quando cortou; espacos colapsados; negritos removidos). Nos grupos `pas` e `crsfn`
o limite e 4.000 (LIMITE_TRECHO_GRUPO): decisao com varios acusados ou varias partes (multas, absolvicoes,
resultado por acusado) era cortada em 1.500 e a resposta perdia parte do dispositivo. Os demais grupos
ficam em 1.500. A divisao dos arquivos em -NN (24.000 bytes) absorve a ficha maior.
Regras testadas na ordem, a primeira que acerta vale. O titulo (linha "# ...")
fica fora da busca, porque "DECISAO" aparece nele ("recurso contra DECISAO da
SEP"): 5.236 julgados do Colegiado tinham esse marcador so por causa disso.

1. secao-acordao / secao-decisao: o corpo tem secao "## Acordao" (CRSFN) ou
   "## Decisao" (Colegiado). Era o que faltava na regra inicial: 4.773 dos
   4.787 julgados do Colegiado e 513 dos 542 do CRSFN sem marcador tinham o
   titulo de secao em vez de "Decisao:". Dentro da secao, pula o cabecalho de
   participantes ("Participantes", "Reg. n", "Relator:", "Tambem presente(s):" e
   suas linhas de continuacao, linhas de nomes) e
   comeca na primeira frase "O Colegiado ... (deliberou|decidiu|aprovou|
   deferiu|rejeitou|...)" ; sem essa frase, na primeira frase com "por
   unanimidade", "Ante o exposto" ou "voto por"; sem nenhuma, no inicio do
   texto da secao. Na secao "## Acordao" o trecho comeca no inicio da secao
   (sem procurar frase), porque a propria secao e o dispositivo.
2. decisao-dois-pontos: "Decisao:" (e o extrato dos PAS: "Decisao: Vistos,
   relatados e discutidos os autos..."). Comeca em "Decisao:".
3. acordam: "acordam" / "ACORDAM" (acordao sem secao propria). Comeca na palavra.
4. decisao-linha: linha so com "DECISAO" (ou "DECISAO:"). Comeca depois dela.
5. frase-decisoria: no corpo todo, a primeira frase "O Colegiado ... <verbo
   decisorio>"; sem ela, "decidiu", "deliberou", "por unanimidade", "Ante o
   exposto" ou "voto por" (nessa ordem). Comeca no achado.
6. fallback-fim: sem marcador, os ultimos caracteres do corpo (limite do grupo) (o campo
   resultado ja vai na ficha). Corpo vazio: "sem texto no acervo".

decisoes-antigas: cada arquivo anual (1978 a 2001) traz varias decisoes, cada
uma sob um titulo "### ..." dentro de uma "## ATA ..." (o proprio frontmatter diz
que a separacao e heuristica). Gera-se uma ficha por decisao: id
<id-do-arquivo>-NNNN (ordem no arquivo), data da ata, ementa = titulo, relator
quando ha linha "Relator:", processo quando o titulo traz "PROC. ...", e
texto_integral apontando para o arquivo anual. Subtitulos que sao so
continuacao do voto transcrito (comecam por aspas, numeracao, "DO/DA/DOS/DAS",
algarismo romano) viram texto da decisao anterior; linhas so de participantes
sao descartadas; decisao sem corpo e descartada e contada. O trecho segue a
regra frase-decisoria dentro do bloco, senao o inicio do bloco.
"""
import argparse
import json
import os
import random
import re
import sys
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import indice_decisoes as idc  # noqa: E402  (filtro de pessoa física do título)

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SKILL = os.path.join(REPO, "plugins", "normas", "skills", "consultar-normas")
ENTRADA_PADRAO = os.path.join(REPO, "julgados")
SAIDA_PADRAO = os.path.join(SKILL, "julgados", "fichas")
PASTA_FICHAS = "fichas"  # nome da pasta sob `julgados/` da skill; os indices citam "fichas/<grupo>/<arquivo>"
BASE_URL = "https://raw.githubusercontent.com/dmarcheti/normas-mercado-capitais/main/julgados/"
LIMITE_ARQUIVO = 24000
LIMITE_TRECHO = 1500
# Grupos de decisao com varias partes: o trecho vai a 4.000 caracteres. Os demais usam LIMITE_TRECHO.
LIMITE_TRECHO_GRUPO = {"pas": 4000, "crsfn": 4000}
SEMENTE_AMOSTRA = 20261112

CAMPOS = ["id", "tipo", "processo", "data", "relator", "resultado", "ementa", "tema",
          "dispositivos_citados", "nivel_verificacao"]

TITULOS = {
    "pas": "PAS da CVM",
    "tc": "Termos de compromisso da CVM",
    "colegiado": "Decisões do Colegiado da CVM",
    "crsfn": "Acórdãos do CRSFN",
    "decisoes-antigas": "Decisões antigas do Colegiado da CVM",
}
ORDEM_GRUPOS = ["pas", "tc", "colegiado", "crsfn", "decisoes-antigas"]

VERBOS = ("deliberou|decidiu|aprovou|deferiu|indeferiu|rejeitou|aceitou|negou|acolheu|determinou|"
          "acompanhou|entendeu|concluiu|resolveu|arquivou|dispensou|autorizou|concedeu|aplicou|"
          "absolveu|condenou|decidiram|deliberaram|manifestou|julgou|homologou|recusou|reconheceu")
RE_FRASE = re.compile(r"\b(?:O |A |Os )?Colegiado\b[^.]{0,250}?\b(?:%s)\b" % VERBOS, re.S)
RE_FRASE_2 = [re.compile(p, re.I) for p in (r"\bdecidiu\b", r"\bdeliberou\b", r"por unanimidade",
                                            r"\bAnte o exposto\b", r"\bvoto por\b")]
RE_SECAO = re.compile(r"(?m)^##[ \t]+(.+?)[ \t]*$")
RE_H1 = re.compile(r"(?m)\A\s*#[ \t][^\n]*\n?")
RE_PREAMBULO = re.compile(r"^\s*(\*\*|\*|·|•|Participantes|Reg\.|Relator|Pedido de vista|Também presentes?|\(\*\))", re.I)
RE_DECISAO_PP = re.compile(r"Decisão:")
RE_ACORDAM = re.compile(r"\bacordam\b", re.I)
RE_DECISAO_LINHA = re.compile(r"(?m)^\W*DECIS[ÃA]O\W*$")


class ErroFicha(Exception):
    pass


# --------------------------------------------------------------------------- leitura

def ler_julgado(caminho):
    """Devolve (frontmatter dict, corpo). Falha se faltar id ou data."""
    with open(caminho, encoding="utf-8") as f:
        texto = f.read()
    if not texto.startswith("---\n"):
        raise ErroFicha("%s: sem frontmatter" % caminho)
    fim = texto.find("\n---\n", 4)
    if fim < 0:
        raise ErroFicha("%s: frontmatter nao fecha" % caminho)
    fm = {}
    for linha in texto[4:fim].split("\n"):
        if ":" not in linha or linha.startswith((" ", "\t")):
            continue
        k, _, v = linha.partition(":")
        fm[k.strip()] = v.strip()
    for obrig in ("id", "data"):
        if not fm.get(obrig):
            raise ErroFicha("%s: campo obrigatorio '%s' ausente ou vazio" % (caminho, obrig))
    return fm, texto[fim + 5:]


# --------------------------------------------------------------------------- trecho

def _limpar(texto):
    return re.sub(r"\s+", " ", texto.replace("**", "")).strip()


def cortar(texto, limite=LIMITE_TRECHO):
    """Colapsa espacos e corta em limite de palavra (ate `limite` caracteres)."""
    t = _limpar(texto)
    if len(t) <= limite:
        return t
    corte = t[:limite]
    if not t[limite].isspace():
        i = corte.rfind(" ")
        if i > 0:
            corte = corte[:i]
    return corte.rstrip(" ,;:") + " [...]"


def _comeco_decisorio(texto):
    """Posicao da frase decisoria dentro do texto, ou None."""
    m = RE_FRASE.search(texto)
    if m:
        return m.start()
    for rx in RE_FRASE_2:
        m = rx.search(texto)
        if m:
            return m.start()
    return None


def _secoes(corpo):
    """Dict nome-da-secao(minusculo) -> texto da secao (ate a proxima '## ')."""
    achados = list(RE_SECAO.finditer(corpo))
    out = {}
    for i, m in enumerate(achados):
        fim = achados[i + 1].start() if i + 1 < len(achados) else len(corpo)
        nome = m.group(1).strip().lower()
        out.setdefault(nome, corpo[m.end():fim])
    return out


def _pular_preambulo(texto):
    linhas = texto.split("\n")
    i = 0
    while i < len(linhas) and (not linhas[i].strip() or RE_PREAMBULO.match(linhas[i])):
        if re.match(r"\s*Também presentes?", linhas[i]):
            # a lista de presentes quebra em varias linhas ate o ultimo ")"
            n = 0
            while i + 1 < len(linhas) and n < 3 and not linhas[i].rstrip().endswith(")"):
                i += 1
                n += 1
        i += 1
    return "\n".join(linhas[i:])


def trecho_decisao(corpo, limite=LIMITE_TRECHO):
    """Devolve (trecho, regra). Ver a docstring do modulo."""
    corpo = RE_H1.sub("", corpo, count=1)
    if not corpo.strip() or not re.sub(r"(?m)^#+.*$", "", corpo).strip():
        return "sem texto no acervo", "sem-texto"
    secoes = _secoes(corpo)
    for nome, regra in (("acórdão", "secao-acordao"), ("acordão", "secao-acordao"),
                        ("acordao", "secao-acordao"), ("decisão", "secao-decisao"),
                        ("decisao", "secao-decisao")):
        if nome in secoes and secoes[nome].strip():
            sec = _pular_preambulo(secoes[nome])
            if not sec.strip():
                continue
            ini = _comeco_decisorio(sec) if regra == "secao-decisao" else None
            return cortar(sec[ini or 0:], limite), regra
    m = RE_DECISAO_PP.search(corpo)
    if m:
        return cortar(corpo[m.start():], limite), "decisao-dois-pontos"
    m = RE_ACORDAM.search(corpo)
    if m:
        return cortar(corpo[m.start():], limite), "acordam"
    m = RE_DECISAO_LINHA.search(corpo)
    if m and corpo[m.end():].strip():
        return cortar(corpo[m.end():], limite), "decisao-linha"
    ini = _comeco_decisorio(corpo)
    if ini is not None:
        return cortar(corpo[ini:], limite), "frase-decisoria"
    t = _limpar(corpo)
    if len(t) > limite:
        t = t[-limite:]
        i = t.find(" ")
        t = "[...] " + (t[i + 1:] if 0 <= i < 40 else t)
    return t, "fallback-fim"


# --------------------------------------------------------------------------- fichas

def url_texto(rel):
    return BASE_URL + quote(rel.replace(os.sep, "/"), safe="/")


def formatar_ficha(campos, link, regra, trecho):
    linhas = ["## " + campos["id"]]
    for c in CAMPOS:
        v = _limpar(campos.get(c, "") or "")
        linhas.append("- %s: %s" % (c, v) if v else "- %s:" % c)
    linhas.append("- texto_integral: " + link)
    linhas.append("- trecho_regra: " + regra)
    linhas.append("- trecho: " + trecho)
    return "\n".join(linhas) + "\n"


def grupo_e_ano(rel, fm):
    p = rel.replace(os.sep, "/").split("/")
    if p[0] == "cvm" and len(p) >= 3 and p[1] == "pas":
        return "pas", p[2]
    if p[0] == "cvm" and len(p) >= 3 and p[1] == "colegiado":
        return ("tc" if fm.get("tipo") == "termo-compromisso" else "colegiado"), p[2]
    if p[0] == "cvm" and len(p) >= 3 and p[1] == "decisoes-antigas":
        return "decisoes-antigas", os.path.splitext(p[2])[0]
    if p[0] == "crsfn" and len(p) >= 3:
        return "crsfn", p[1]
    raise ErroFicha("julgados/%s: pasta fora do esquema conhecido" % rel)


def ficha_de_julgado(rel, fm, corpo):
    grupo, ano = grupo_e_ano(rel, fm)
    trecho, regra = trecho_decisao(corpo, LIMITE_TRECHO_GRUPO.get(grupo, LIMITE_TRECHO))
    return {"grupo": grupo, "ano": ano, "data": fm["data"], "id": fm["id"], "rel": rel,
            "regra": regra, "ementa": _limpar(fm.get("ementa", "") or ""),
            "texto": formatar_ficha(fm, url_texto(rel), regra, trecho)}


# --------------------------------------------------------------------------- decisoes antigas

_NOME = r"[^-–]+?"
_ROLE = r"(?:PTE|DIRETORA?|PRESIDENTE(?: EM EXERCÍCIO)?)"
_INI = (r"(?!(?:PROC|CVM)\b)[A-Z]{2,5}")
# prefixo de participantes colado ao titulo: "NOME - PTE NOME - DAM TITULO", "NOME - RTC NOME - AMRL TITULO"
RE_PREF_ROLE = re.compile(r"^(?:%s\s?[-–]+\s?%s(?:\s*\(\*\))?(?=\s|$)\s*)+" % (_NOME, _ROLE))
RE_PREF_INI = re.compile(r"^(?:%s\s?[-–]+\s?(?:%s|%s)(?:\s*\(\*\))?(?=\s|$)\s*){2,}" % (_NOME, _ROLE, _INI))
RE_CONT = re.compile(r'^(?:"|“|\d+[.)]\s|(?:DO|DA|DOS|DAS)\s|[IVX]+[\s.\-–)])')
RE_DATA_ATA = re.compile(r"(\d{2})\.(\d{2})\.(\d{4}|\d{2})\b")
RE_PROC = re.compile(r"PROC(?:ESSO)?\.?:?\s*(?:CVM\s*)?(?:N[ºo°]\s*)?((?:RJ|SP)?\s?[\d/.\-]{4,}\d)", re.I)


def _titulo_sem_participantes(h):
    """Tira o prefixo de participantes colado ao titulo."""
    m = RE_PREF_INI.match(h) or RE_PREF_ROLE.match(h)
    return h[m.end():].strip(" -–\"") if m else h


def fichas_antigas(rel, fm, corpo):
    """Uma ficha por decisao de um arquivo anual de decisoes-antigas. Devolve (fichas, descartadas)."""
    ano = os.path.splitext(os.path.basename(rel))[0]
    data_ata = fm["data"]
    unidades = []
    atual = None

    def novo(titulo):
        u = {"titulo": titulo, "data": data_ata, "linhas": []}
        unidades.append(u)
        return u

    for linha in corpo.split("\n"):
        if linha.startswith("# "):
            continue
        if linha.startswith("## ") or linha.upper().startswith("### ATA "):
            m = RE_DATA_ATA.search(linha)
            if m:
                ano_ata = m.group(3) if len(m.group(3)) == 4 else "19" + m.group(3)
                data_ata = "%s-%s-%s" % (ano_ata, m.group(2), m.group(1))
            atual = None
            continue
        if linha.startswith("### "):
            h = linha[4:].strip()
            titulo = _titulo_sem_participantes(h)
            if not titulo:                       # so participantes
                if atual is None:
                    atual = novo("")
                continue
            if atual is not None and RE_CONT.match(titulo):
                atual["linhas"].append(titulo)
                continue
            atual = novo(titulo)
            continue
        if atual is not None:          # linhas antes do 1o titulo da ata (participantes) ficam de fora
            atual["linhas"].append(linha)

    fichas, descartadas, n = [], 0, 0
    for u in unidades:
        texto = "\n".join(u["linhas"])
        if not texto.strip():
            descartadas += 1
            continue
        n += 1
        titulo = u["titulo"] or "(sem título)"
        rel_m = re.search(r"Relator:\s*([^\n]+)", texto)
        proc_m = RE_PROC.search(titulo)
        campos = {"id": "%s-%04d" % (fm["id"], n), "tipo": fm.get("tipo", ""),
                  "processo": proc_m.group(1).strip() if proc_m else "", "data": u["data"],
                  "relator": rel_m.group(1).strip() if rel_m else "", "resultado": "",
                  "ementa": titulo, "tema": "", "dispositivos_citados": "",
                  "nivel_verificacao": fm.get("nivel_verificacao", "")}
        texto = _pular_preambulo(texto)
        ini = _comeco_decisorio(texto)
        if ini is not None:
            trecho, regra = cortar(texto[ini:]), "antiga-frase-decisoria"
        else:
            trecho, regra = cortar(texto), "antiga-inicio"
        fichas.append({"grupo": "decisoes-antigas", "ano": ano, "data": u["data"], "id": campos["id"],
                       "rel": rel, "regra": regra, "campos": campos, "trecho": trecho,
                       "texto": formatar_ficha(campos, url_texto(rel), regra, trecho)})
    return fichas, descartadas


# --------------------------------------------------------------------------- coleta e saida

def coletar(entrada, log=lambda *a: None):
    """Le todos os .md da entrada e devolve (fichas, info)."""
    entrada = os.path.abspath(entrada)
    arquivos = []
    for raiz, dirs, nomes in os.walk(entrada):
        dirs.sort()
        for n in sorted(nomes):
            if n.endswith(".md") and not n.startswith("_"):
                arquivos.append(os.path.join(raiz, n))
    arquivos.sort()
    fichas, descartadas, vistos, duplicados = [], 0, set(), []
    linhas_antigas = []  # corpo de cada arquivo anual de decisões antigas, base do filtro de pessoa física
    for i, caminho in enumerate(arquivos, 1):
        rel = os.path.relpath(caminho, entrada).replace(os.sep, "/")
        fm, corpo = ler_julgado(caminho)
        if rel.startswith("cvm/decisoes-antigas/"):
            novas, d = fichas_antigas(rel, fm, corpo)
            descartadas += d
            linhas_antigas.append(corpo.split("\n"))
        else:
            novas = [ficha_de_julgado(rel, fm, corpo)]
        for f in novas:
            if f["id"] in vistos:
                duplicados.append(f["id"])
            vistos.add(f["id"])
        fichas.extend(novas)
        if i % 3000 == 0:
            log("  %d/%d arquivos lidos" % (i, len(arquivos)))
    fichas.sort(key=lambda f: (f["grupo"], f["ano"], f["data"], f["id"]))
    trocadas = _sem_pessoas_nas_ementas(fichas, linhas_antigas)
    return fichas, {"julgados_lidos": len(arquivos), "antigas_descartadas": descartadas,
                    "ids_duplicados": sorted(set(duplicados)), "antigas_ementas_trocadas": trocadas}


def _sem_pessoas_nas_ementas(fichas, linhas_antigas):
    """Troca por "[pessoa física]" o nome de pessoa na `ementa` das fichas das decisões antigas (o título
    bruto do arquivo anual), com o mesmo filtro que o índice por decisão aplicava ao título
    (`indice_decisoes.FiltroDePessoas`). O `trecho` fica como está no julgado. Devolve quantas mudaram."""
    antigas = [f for f in fichas if f["grupo"] == "decisoes-antigas"]
    if not antigas:
        return 0
    filtro = idc.FiltroDePessoas(linhas_antigas)
    filtro.aprender(f["campos"]["ementa"] for f in antigas)
    n = 0
    for f in antigas:
        novo, trocou = filtro.aplicar(f["campos"]["ementa"])
        if trocou:
            n += 1
            f["campos"]["ementa"] = novo
            f["texto"] = formatar_ficha(f["campos"], url_texto(f["rel"]), f["regra"], f["trecho"])
    return n


def empacotar(fichas, limite=LIMITE_ARQUIVO):
    """Agrupa as fichas (ja ordenadas) em arquivos. Devolve [(grupo, nome_arquivo, texto)]."""
    por_chave = {}
    for f in fichas:
        por_chave.setdefault((f["grupo"], f["ano"]), []).append(f)
    saida = []
    for (grupo, ano) in sorted(por_chave, key=lambda k: (ORDEM_GRUPOS.index(k[0]), k[1])):
        partes, atual, tam = [], [], 0
        titulo = "# %s, %s" % (TITULOS[grupo], ano)
        base = len((titulo + "\n\n").encode("utf-8")) + 24      # folga para " (parte NN de NN)"
        for f in por_chave[(grupo, ano)]:
            t = len(f["texto"].encode("utf-8")) + 1
            if atual and base + tam + t > limite:
                partes.append(atual)
                atual, tam = [], 0
            atual.append(f)
            tam += t
        partes.append(atual)
        for i, fs in enumerate(partes, 1):
            cab = titulo + (" (parte %d de %d)" % (i, len(partes)) if len(partes) > 1 else "")
            texto = cab + "\n\n" + "\n".join(f["texto"] for f in fs)
            nome = "%s.md" % ano if len(partes) == 1 else "%s-%02d.md" % (ano, i)
            saida.append((grupo, nome, texto))
    return saida


def gravar(saida_dir, arquivos):
    saida_dir = os.path.abspath(saida_dir)
    for grupo in ORDEM_GRUPOS:
        d = os.path.join(saida_dir, grupo)
        if os.path.isdir(d):
            for n in os.listdir(d):
                if n.endswith(".md"):
                    os.remove(os.path.join(d, n))
    for grupo, nome, texto in arquivos:
        d = os.path.join(saida_dir, grupo)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, nome), "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)


def medir(fichas, arquivos, info):
    por_grupo, regras, regras_g = {}, {}, {}
    maior = ("", 0)
    total = 0
    for grupo, nome, texto in arquivos:
        b = len(texto.encode("utf-8"))
        total += b
        g = por_grupo.setdefault(grupo, {"arquivos": 0, "bytes": 0, "fichas": 0})
        g["arquivos"] += 1
        g["bytes"] += b
        if b > maior[1]:
            maior = ("%s/%s" % (grupo, nome), b)
    for f in fichas:
        por_grupo[f["grupo"]]["fichas"] += 1
        regras[f["regra"]] = regras.get(f["regra"], 0) + 1
        regras_g.setdefault(f["grupo"], {})
        regras_g[f["grupo"]][f["regra"]] = regras_g[f["grupo"]].get(f["regra"], 0) + 1
    for g in por_grupo.values():
        g["mb"] = round(g["bytes"] / 1e6, 2)
    return {"mb_total": round(total / 1e6, 2), "bytes_total": total, "arquivos": len(arquivos),
            "fichas": len(fichas), "maior_arquivo": {"arquivo": maior[0], "bytes": maior[1]},
            "por_grupo": por_grupo, "fichas_por_regra": dict(sorted(regras.items())),
            "regra_por_grupo": {g: dict(sorted(r.items())) for g, r in sorted(regras_g.items())},
            **info}


def amostrar(fichas, n=20, semente=SEMENTE_AMOSTRA):
    ids = sorted(f["id"] for f in fichas)
    escolhidos = random.Random(semente).sample(ids, n)
    por_id = {f["id"]: f for f in fichas}
    partes = ["# Amostra de %d fichas (semente %d)\n" % (n, semente)]
    for i in escolhidos:
        f = por_id[i]
        partes.append("Julgado: julgados/%s\nGrupo: %s | regra: %s\n\n%s" % (f["rel"], f["grupo"], f["regra"], f["texto"]))
    return "\n---\n\n".join(partes)


def montar(entrada, log=lambda *a: None):
    """(fichas, arquivos, info) em memoria: o que `gravar` poria no disco."""
    fichas, info = coletar(entrada, log)
    return fichas, empacotar(fichas), info


def ids_por_arquivo(arquivos):
    """{id da ficha: "fichas/<grupo>/<arquivo>"} dos arquivos de `empacotar`."""
    out = {}
    for grupo, nome, texto in arquivos:
        for m in re.finditer(r"(?m)^## (.+)$", texto):
            out[m.group(1)] = "%s/%s/%s" % (PASTA_FICHAS, grupo, nome)
    return out


def diferencas(arquivos, saida_dir):
    """Lista de problemas entre `arquivos` (em memoria) e o disco em `saida_dir`."""
    saida_dir = os.path.abspath(saida_dir)
    esperados = {"%s/%s" % (g, n): t for g, n, t in arquivos}
    out = []
    for rel, texto in sorted(esperados.items()):
        caminho = os.path.join(saida_dir, *rel.split("/"))
        if not os.path.isfile(caminho):
            out.append("%s (ausente)" % rel)
            continue
        with open(caminho, "rb") as f:
            if f.read() != texto.encode("utf-8"):
                out.append("%s (diferente)" % rel)
    for grupo in ORDEM_GRUPOS:
        d = os.path.join(saida_dir, grupo)
        if os.path.isdir(d):
            out += ["%s/%s (sobrou de geracao anterior)" % (grupo, n) for n in sorted(os.listdir(d))
                    if n.endswith(".md") and "%s/%s" % (grupo, n) not in esperados]
    return out


def gerar(entrada, saida, medidas=None, amostra=None, log=print):
    fichas, arquivos, info = montar(entrada, log)
    gravar(saida, arquivos)
    m = medir(fichas, arquivos, info)
    if medidas:
        os.makedirs(os.path.dirname(os.path.abspath(medidas)), exist_ok=True)
        with open(medidas, "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
    if amostra:
        os.makedirs(os.path.dirname(os.path.abspath(amostra)), exist_ok=True)
        with open(amostra, "w", encoding="utf-8") as f:
            f.write(amostrar(fichas) + "\n")
    return m


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--entrada", default=ENTRADA_PADRAO)
    ap.add_argument("--saida", default=SAIDA_PADRAO)
    ap.add_argument("--medidas", help="grava as medidas em JSON")
    ap.add_argument("--amostra", help="grava 20 fichas sorteadas (semente 20261112)")
    ap.add_argument("--verificar", action="store_true",
                    help="regenera em memoria e compara com o disco; rc 1 se diferir")
    a = ap.parse_args(argv)
    try:
        if a.verificar:
            if not os.path.isdir(a.entrada):
                print("fichas: pasta dos julgados nao existe: %s" % a.entrada, file=sys.stderr)
                return 2
            _f, arquivos, _i = montar(a.entrada, lambda *x: print(*x, file=sys.stderr))
            dif = diferencas(arquivos, a.saida)
            if dif:
                print("fichas: %s desatualizado (%d: %s); rode python3 scripts/fichas.py" % (
                    a.saida, len(dif), ", ".join(dif[:10]) + (", ..." if len(dif) > 10 else "")))
                return 1
            print("fichas: em dia (%d arquivo(s))" % len(arquivos))
            return 0
        m = gerar(a.entrada, a.saida, a.medidas, a.amostra, log=lambda *x: print(*x, file=sys.stderr))
    except ErroFicha as e:
        print("ERRO: %s" % e, file=sys.stderr)
        return 1
    print("%d fichas em %d arquivos, %.2f MB; maior arquivo %d bytes" % (
        m["fichas"], m["arquivos"], m["mb_total"], m["maior_arquivo"]["bytes"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
