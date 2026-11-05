"""Converte as fontes baixadas dos julgados (cache de julgados_baixar.py) em Markdown com o
frontmatter do contrato, no caminho de `julgados_comum.caminho_julgado`.

- Colegiado (e TC com item do Colegiado): HTML do <article> por html_bcb.html_para_md, em
  `## Decisão`; anexos em seções próprias (anexo alheio fica fora); termos em
  `## Termo de compromisso`.
- PAS: PDF pelo PDFKit; página com menos de 20 caracteres vai para OCR (Vision). Seções pelos
  cabeçalhos da peça (Extrato, Relatório, Voto, Declaração de voto, Manifestação da área
  técnica); sem cabeçalho reconhecível, `## Texto`.
- PAS fora da listagem (origem `noticia`): `## Extrato` do SEI e as peças dos PDFs da notícia
  (seção pelo cabeçalho ou pelo rótulo do link); ementa (`ementa_fonte: cvm`), data, relator e
  resultado do extrato; `fonte_original` é a URL da notícia.
- TC sem item do Colegiado: o termo (PDF ou extrato do SEI, ISO-8859-1, tabela vira bloco).
- Decisões antigas: um arquivo por ano, `## ATA ...` por reunião e `### ` por decisão
  (segmentação por heurística, anotada em `incerteza`).
- Linhas repetidas na borda (3 primeiras ou últimas linhas) de 3 ou mais páginas saem
  (cabeçalho e rodapé; a mesma linha no miolo fica); páginas por OCR têm "§" e romanos lidos
  errado corrigidos em padrões estreitos (corrigir_ocr); todo o texto passa por pii.limpar.
  Resultado só por regex segura; tema fica vazio; citações por citacoes.py (sem o módulo,
  ficam vazias).
- Cobertura: conferência independente (html.parser; pypdf para PDF, se instalado) da fração
  das palavras da fonte presentes na saída; um relatório JSON por lote em
  dados/fase-2d/relatorios/.

Uso:
  python3 scripts/julgados_converter.py --ids cvm-pas-rj2015-1234,cvm-col-20251202-d3228
  python3 scripts/julgados_converter.py --onda 1 --tipo pas --limite 20
"""
import argparse
import bisect
import collections
import datetime
import difflib
import json
import os
import re
import sys
import tempfile
from html import unescape
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import html_bcb  # noqa: E402
import julgados_baixar as jb  # noqa: E402
import julgados_comum as jc  # noqa: E402
import julgados_extracao as je  # noqa: E402
import pdf_macos  # noqa: E402
import pii  # noqa: E402
from inventario import _data_cvm  # noqa: E402

RELATORIOS = os.path.join(jc.RAIZ, "dados", "fase-2d", "relatorios")
LIGACOES_CRSFN = os.path.join(jc.RAIZ, "dados", "fase-2d", "crsfn-ligacoes.json")
DADOS_ABERTOS_PAS = os.path.join(jc.RAIZ, "dados", "fase-2d", "inventario", "pas",
                                 "processo_sancionador.csv")
_LIGACOES_CRSFN = None  # carregam na 1ª consulta (ou vêm prontas, nos testes)
_FASES_PAS = None
MIN_CARACTERES_PAGINA = 20
MIN_PAGINAS_REPETIDA = 3
COBERTURA_BAIXA = 0.9

# ---------------------------------------------------------------- PDF


def _pypdf_paginas(caminho):
    """Páginas pelo pypdf, ou None sem o módulo (Python da CLT, por exemplo)."""
    try:
        import pypdf
    except ImportError:
        return None
    leitor = pypdf.PdfReader(caminho)
    return [(p.extract_text() or "") for p in leitor.pages]


def _numero_de_paginas(caminho):
    """Número de páginas do PDF pelo pypdf, ou None (sem o módulo ou PDF ilegível)."""
    try:
        import pypdf
        return len(pypdf.PdfReader(caminho).pages)
    except Exception:  # noqa: BLE001 — sem o número, nenhuma página é descartada
        return None


# Erros sistemáticos do OCR (Vision), corrigidos só nas páginas lidas por OCR e só em padrões
# estreitos: "§" lido como "8" depois de "art. N," ("art. 17, 82°" -> "art. 17, §2º"; "§§" como
# "88": "art. 141, 884° e 5°" -> "§§4º"); romanos "I e II" dos incisos lidos como "1", "l",
# "11", "Il"; "Il"/"lI" abrindo título de seção ("Il - DA ILEGALIDADE").
_OCR_PARAGRAFO = re.compile(
    r"(\b(?:arts?\.|artigos?)\s*\d+[A-Z]?(?:-[A-Z])?,?\s+)8(8?)\s?(\d{1,2})\s*[°º]")
_OCR_INCISOS = re.compile(r"\b(incisos?\s+)(?:I|1|l)(\s+e\s+)(?:II|11|Il|lI)\b")
_OCR_TITULO_II = re.compile(r"(?m)^([ \t]*)(?:Il|lI)(?=\s+[-–]\s|\.)")
# romano isolado depois de "inciso" com "l" ou "1" no lugar de "I" ("inciso Il", "inciso VIll");
# só se tem "l" (algarismo puro fica: "inciso 1" pode ser numeração arábica da norma)
_OCR_INCISO = re.compile(r"\b(incisos?\s+)([IVXl1]*l[IVXl1]*)(?![\wÀ-ÿ])")
_ROMANO = re.compile(r"^(?:X{0,3})(?:IX|IV|V?I{0,3})$")
# "§" lido como "$" antes do número com grau ("art. 24, $ 1°"); "R$"/"US$" ficam
_OCR_CIFRAO = re.compile(r"(?<![A-Za-z])\$(\s?)(\d{1,2})\s*[°º]")


# "CNPJ/ME" só existe a partir de 2019 (Ministério da Economia); antes, é "CNPJ/MF" lido errado
_OCR_CNPJ_ME = re.compile(r"\bCNPJ(\s*/\s*)ME\b")
DATA_CNPJ_ME = "2019-01-01"

# "Não" lido como "Vão" no início da frase, antes de verbo ou expressão que só segue a negação
# ("Vão é possível", "Vão obstante"); "Vão se" + gerúndio é o verbo "ir" ("Vão se tornando").
_OCR_NAO = re.compile(r"(^|[.!?:;][ \t]+|\n[ \t]*)Vão(?=[ \t]+(?:é|há|foi|houve|obstante|cabe|"
                      r"consta|existe|pode|deve|sendo|se(?![ \t]+\w+ndo\b))\b)")


def corrigir_ocr(texto, data=None):
    """Texto de página lida por OCR com "§" e os romanos I e II corrigidos (padrões acima),
    "Vão" no início da frase como "Não" (antes de é, há, foi etc.) e, em
    julgado anterior a 2019 (`data` AAAA-MM-DD), "CNPJ/ME" como "CNPJ/MF"."""
    if data and data < DATA_CNPJ_ME:
        texto = _OCR_CNPJ_ME.sub(r"CNPJ\1MF", texto)
    texto = _OCR_PARAGRAFO.sub(lambda m: "%s§%s%sº" % (m.group(1), "§" if m.group(2) else "",
                                                      m.group(3)), texto)
    texto = _OCR_INCISOS.sub(r"\1I\2II", texto)
    texto = _OCR_NAO.sub(r"\1Não", texto)

    def _inciso(m):
        rom = m.group(2).replace("l", "I").replace("1", "I")
        return m.group(1) + rom if rom and _ROMANO.match(rom) else m.group(0)

    texto = _OCR_INCISO.sub(_inciso, texto)
    texto = _OCR_CIFRAO.sub(r"§\1\2º", texto)
    return _OCR_TITULO_II.sub(r"\1II", texto)


# Siglas da CVM deformadas pelo OCR com um "i" ou "l" a mais ("PAiS", "CVMi", "SMIl") ou com "l"
# no lugar de "I" ("CNAl", "SOl"). Só siglas da lista; a letra a mais só sai se a sigla limpa
# aparece em outro ponto do documento.
SIGLAS_OCR = frozenset((
    "CVM", "PAS", "CNPJ", "CPF", "SEP", "SIN", "SMI", "SRE", "SNC", "SPS", "SOI", "SFI", "SGE",
    "SDM", "SSE", "SAD", "PFE", "CNAI", "SPL", "SMA", "SRI", "STI", "SSR", "GOI", "GEA", "GEO",
    "GER"))
_OCR_SIGLA = re.compile(r"(?<![\wÀ-ÿ])([A-Z]{2,}[il][A-Z]*|[A-Z][il][A-Z]{2,})(?![\wÀ-ÿ])")


def corrigir_siglas_ocr(pagina, contexto):
    """Página lida por OCR com as siglas deformadas corrigidas (ver acima); `contexto`: texto do
    documento em que a sigla limpa precisa aparecer para a letra a mais sair."""
    def _sigla(m):
        t = m.group(1)
        sem = re.sub("[il]", "", t)
        if sem in SIGLAS_OCR:
            limpa = re.search(r"(?<![\wÀ-ÿ])%s(?![\wÀ-ÿ])" % sem, contexto)
            return sem if limpa else t
        troca = t.replace("l", "I")
        return troca if troca in SIGLAS_OCR else t

    return _OCR_SIGLA.sub(_sigla, pagina)


# PDF que desenha o mesmo texto 2 ou 3 vezes em camadas sobrepostas (cada camada com pedaços
# diferentes): o PDFKit devolve as camadas em linhas seguidas. Linhas seguidas cujo trecho comum
# cobre 80% da menor, e que só se estendem uma à outra, viram uma; só na página em que isso é
# sistemático (5 pares e 10% das linhas), para não fundir repetição de verdade.
SOBREPOSICAO_MIN_PARES, SOBREPOSICAO_FRACAO, SOBREPOSICAO_COBRE = 5, 0.10, 0.80


def _fundir_sobrepostas(a, b):
    a, b = a.strip(), b.strip()
    menor = min(len(a), len(b))
    if menor < 15:
        return None
    i, j, k = difflib.SequenceMatcher(None, a, b, autojunk=False).find_longest_match(
        0, len(a), 0, len(b))
    if k < SOBREPOSICAO_COBRE * menor:
        return None
    if (i and j) or (i + k < len(a) and j + k < len(b)):
        return None  # as duas divergem no começo ou no fim: linhas diferentes, não camadas
    comeco = a[:i] if i >= j else b[:j]
    fim = a[i + k:] if len(a) - i >= len(b) - j else b[j + k:]
    return comeco + a[i:i + k] + fim


def desfazer_sobreposicao(pagina):
    """Página do PDFKit sem as camadas de texto sobrepostas (ver acima)."""
    linhas = pagina.split("\n")
    cheias = [x for x in linhas if x.strip()]
    pares = sum(1 for x, y in zip(cheias, cheias[1:]) if _fundir_sobrepostas(x, y))
    if pares < SOBREPOSICAO_MIN_PARES or pares < SOBREPOSICAO_FRACAO * len(cheias):
        return pagina
    out = []
    for x in linhas:
        junta = _fundir_sobrepostas(out[-1], x) if out and out[-1].strip() and x.strip() else None
        if junta is not None:
            out[-1] = junta
        else:
            out.append(x)
    return "\n".join(out)


# Ordem das linhas: em alguns PDFs o PDFKit põe um trecho de linha fora do lugar (o fim de um
# parágrafo colado ao número dele, "7. abertas:", ou uma linha entre as vírgulas de uma citação
# quebrada, "artigo 9°\n<linha de baixo>\n, parágrafo 4°"). O pypdf, extrator independente, lê
# a ordem do fluxo do PDF. A página do PDFKit é cortada em trechos achados no pypdf (texto sem
# espaços; um trecho não passa de uma linha); os trechos fora da maior sequência crescente de
# posições no pypdf estão fora de ordem. Só volta ao lugar o trecho (1) de palavras inteiras,
# com 4 letras ou dígitos e sem começar por número de parágrafo, posto entre palavras inteiras
# e nunca logo depois de um número de parágrafo, (2) a até 4 linhas do destino e (3) com um gatilho do defeito: o que vem antes dele na linha
# é só o número do parágrafo, ou há linha que começa com pontuação solta a até 3 linhas. O texto do PDFKit não muda, só a ordem
# dos trechos (o pypdf decide a ordem, nunca o conteúdo).
ORDEM_MIN_TRECHO, ORDEM_JANELA, ORDEM_VIZINHANCA = 4, 4, 3
_ORDEM_NUMERO = re.compile(r"[ \t]*\d{1,3}(?: \d)?[ \t]?\.[ \t]+")
_ORDEM_PONTUACAO = re.compile(r"[ \t]*[,;.:)][ \t]")


def _sem_espacos(texto):
    """(texto sem espaços, índice no original de cada caractere)."""
    idx = [i for i, c in enumerate(texto) if not c.isspace()]
    return "".join(texto[i] for i in idx), idx


def _trechos_no_pypdf(pk, py):
    """[(início, fim, posição no pypdf)] da página do PDFKit, em trechos contíguos achados no
    pypdf (o maior prefixo, sem passar de uma linha). Trecho de menos de 4 caracteres só vale
    perto da posição esperada; trecho não achado gruda no anterior (posição None só no 1º)."""
    ck, ik = _sem_espacos(pk)
    cp, _ = _sem_espacos(py)
    n = len(ck)
    if not n or not cp:
        return []
    quebra = [False] * (n + 1)
    for j in range(n - 1):
        if "\n" in pk[ik[j]:ik[j + 1]]:
            quebra[j + 1] = True
    pecas, i, esperado = [], 0, 0
    while i < n:
        lim = i + 1
        while lim < n and not quebra[lim]:
            lim += 1
        lo, hi = 0, lim - i
        while lo < hi:
            m = (lo + hi + 1) // 2
            if ck[i:i + m] in cp:
                lo = m
            else:
                hi = m - 1
        k, pos = lo, None
        if k >= ORDEM_MIN_TRECHO:
            pos = cp.find(ck[i:i + k], esperado)
            if pos < 0:
                pos = cp.find(ck[i:i + k])
        elif k >= 1:
            p = cp.find(ck[i:i + k], esperado)
            if 0 <= p <= esperado + 3:
                pos = p
        k = max(k, 1)
        if pos is None and pecas:
            pecas[-1][1] = i + k
        else:
            pecas.append([i, i + k, pos])
            if pos is not None:
                esperado = pos + k
        i += k
    return [(ik[a], ik[b] if b < n else len(pk), p) for a, b, p in pecas]


def _maior_crescente(seq):
    """Índices da maior subsequência crescente de `seq`."""
    topos, idx, ant = [], [], [-1] * len(seq)
    for i, x in enumerate(seq):
        j = bisect.bisect_left(topos, x)
        if j == len(topos):
            topos.append(x)
            idx.append(i)
        else:
            topos[j], idx[j] = x, i
        ant[i] = idx[j - 1] if j else -1
    out, k = set(), idx[-1] if idx else -1
    while k >= 0:
        out.add(k)
        k = ant[k]
    return out


def reordenar_pela_ordem_do_pypdf(pk, py, debug=None):
    """Página do PDFKit `pk` com os trechos fora de ordem de volta ao lugar que têm no texto do
    pypdf `py` (regra acima) e, depois, as linhas soltas (mover_linhas_soltas). `debug`: lista
    que recebe (trecho, gatilho) de cada trecho ou linha movida."""
    return mover_linhas_soltas(_reordenar_trechos(pk, py, debug), py, debug)


def _reordenar_trechos(pk, py, debug=None):
    us = _trechos_no_pypdf(pk, py or "")
    if not us:
        return pk
    pos = [u[2] if u[2] is not None else -1 for u in us]
    fixos = sorted(_maior_crescente(pos))
    if len(fixos) == len(us):
        return pk
    fpos = [pos[i] for i in fixos]
    linhas = pk.split("\n")

    def _inteiro(a, b):  # trecho de palavras inteiras, com o espaço do fim
        return (a == 0 or pk[a - 1].isspace()) and pk[b - 1].isspace()

    mover = {}
    for i in range(len(us)):
        if i in fixos or not _inteiro(us[i][0], us[i][1]):
            continue
        trecho = pk[us[i][0]:us[i][1]]
        if (sum(ch.isalnum() for ch in trecho) < ORDEM_MIN_TRECHO
                or _ORDEM_NUMERO.match(trecho)):  # pontuação solta; número de parágrafo
            continue
        j = bisect.bisect_left(fpos, pos[i])
        alvo = fixos[j - 1] if j else -1
        if alvo >= 0 and not pk[us[alvo][1] - 1].isspace():
            continue
        fim = us[alvo][1] if alvo >= 0 else 0
        if _ORDEM_NUMERO.fullmatch(pk[pk.rfind("\n", 0, fim) + 1:fim]):
            continue  # entraria entre um número de parágrafo e o texto dele
        la = pk.count("\n", 0, us[i][0])
        lb = pk.count("\n", 0, us[alvo][0]) if alvo >= 0 else 0
        if abs(lb - la) > ORDEM_JANELA:
            continue
        prefixo = pk[pk.rfind("\n", 0, us[i][0]) + 1:us[i][0]]
        if prefixo.strip() and _ORDEM_NUMERO.fullmatch(prefixo):
            mover[i] = (alvo, "numero")
        elif any(_ORDEM_PONTUACAO.match(x) or x.strip() in (",", ".", ";")
                 for x in linhas[max(0, la - ORDEM_VIZINHANCA):la + ORDEM_VIZINHANCA + 1]):
            mover[i] = (alvo, "pontuacao")
    if not mover:
        return pk
    if debug is not None:
        debug.extend((pk[us[i][0]:us[i][1]], g) for i, (_, g) in sorted(mover.items()))
    seq = [i for i in range(len(us)) if i not in mover]
    for i in sorted(mover, key=lambda k: pos[k]):
        alvo = mover[i][0]
        k = seq.index(alvo) + 1 if alvo >= 0 else 0
        while k < len(seq) and seq[k] in mover and pos[seq[k]] < pos[i]:
            k += 1
        seq.insert(k, i)
    return pk[:us[0][0]] + "".join(pk[us[i][0]:us[i][1]] for i in seq)


# Linha solta inteira fora do lugar (depois da passada por trechos): uma palavra curta tirada da
# frase ("de que se trata foi aplicada" + linha "não"; "atestado pela homologado" + linha
# "SAD e") ou uma linha inteira levada para longe ("22. seção." e a linha "Em defesa conjunta...
# nesta" no fim da página). A linha volta para o lugar em que o pypdf a põe quando: (1) no lugar
# atual o pypdf a contradiz (o texto de antes ou o de depois não encosta nela no pypdf) e, sem
# ela, o texto de antes encosta no de depois (o lugar velho se fecha); (2) o lugar novo é único:
# só um ponto da página, entre palavras inteiras, tem à esquerda e à direita os 12 caracteres
# que cercam a linha no pypdf; (3) o lugar novo é meio de frase (a linha não fecha frase e o
# texto seguinte começa em minúscula, ou o texto anterior não fecha frase e a linha começa em
# minúscula); (4) linha curta (até 3 palavras, 2 letras ou mais) só a até 4 linhas; linha mais
# longa (20 caracteres ou mais) vai a qualquer ponto da página, se aparece uma só vez no pypdf
# da página, mas não para as 3 primeiras linhas fora do timbre nem as 3 últimas (o rodapé que o
# pypdf põe no alto da página). Não se movem a primeira e a última linha da página, linha sem
# letra (número de página), linha com paginação ("Página 6 de 46", "pg. 38", "Voto 17 de 18")
# nem linha de timbre. O texto da linha não muda.
ORDEM_CONTEXTO, ORDEM_LINHA_CURTA, ORDEM_LINHA_LONGA, ORDEM_MAX_LINHAS = 12, 3, 20, 5
_FIM_DE_FRASE = ".;:!?"
_PAGINACAO = re.compile(
    r"(?i)\bp[áa]g(?:ina|\.)?\s*\d+\s*(?:de|/)\s*\d+|\bpg\.\s*\d+|\b\d+\s+de\s+\d+\s*$")


def _mover_uma_linha(pk, cp, debug):
    """Página com uma linha solta de volta ao lugar (regra acima), ou None."""
    linhas = pk.split("\n")
    cs = [re.sub(r"\s+", "", x) for x in linhas]
    cheias = [i for i, c in enumerate(cs) if c]
    m = ORDEM_CONTEXTO
    for li in cheias[1:-1]:
        c, solta = cs[li], linhas[li].strip()
        curta = len(solta.split()) <= ORDEM_LINHA_CURTA
        if curta:
            if sum(ch.isalpha() for ch in c) < 2:
                continue
        elif len(c) < ORDEM_LINHA_LONGA or cp.count(c) != 1:
            continue
        if (not any(ch.isalpha() for ch in c) or _linha_de_timbre(solta)
                or _PAGINACAO.search(solta)):
            continue
        antes, depois = "".join(cs[:li])[-m:], "".join(cs[li + 1:])[:m]
        if (antes + c in cp and c + depois in cp) or antes + depois not in cp:
            continue
        texto = "\n".join(linhas[:li] + linhas[li + 1:])
        cr, ir = _sem_espacos(texto)
        destinos = set()
        p = cp.find(c)
        while p >= 0:
            a, b = cp[max(0, p - m):p], cp[p + len(c):p + len(c) + m]
            q = cr.find(a + b) if a and b else -1
            while q >= 0:
                destinos.add(q + len(a))
                q = cr.find(a + b, q + 1)
            p = cp.find(c, p + 1)
        if len(destinos) != 1:
            continue
        s = destinos.pop()
        ini, vao = ir[s], texto[ir[s - 1] + 1:ir[s]]
        if not vao:
            continue  # destino no meio de uma palavra
        destino = texto.count("\n", 0, ini)
        if curta and abs((destino if destino < li else destino + 1) - li) > ORDEM_JANELA:
            continue
        if not curta:
            acima = sum(1 for x in texto[:ini].split("\n")
                        if x.strip() and not _linha_de_timbre(x))
            if not BORDA_LINHAS <= acima <= len(cheias) - 1 - BORDA_LINHAS:
                continue  # destino na borda da página
        esquerda = texto[:ini].rstrip()
        if not ((solta[-1] not in _FIM_DE_FRASE and texto[ini].islower())
                or (esquerda[-1:] not in _FIM_DE_FRASE and solta[0].islower())):
            continue
        if debug is not None:
            debug.append((solta, "linha-curta" if curta else "linha-longe"))
        return texto[:ini] + solta + ("\n" if "\n" in vao else " ") + texto[ini:]
    return None


def mover_linhas_soltas(pk, py, debug=None):
    """Página do PDFKit `pk` com as linhas soltas de volta ao lugar que têm no pypdf `py`
    (regra acima). `debug`: lista que recebe (linha, "linha-curta" ou "linha-longe")."""
    cp = _sem_espacos(py or "")[0]
    if not cp:
        return pk
    for _ in range(ORDEM_MAX_LINHAS):
        nova = _mover_uma_linha(pk, cp, debug)
        if nova is None:
            break
        pk = nova
    return pk


def _paginas_pypdf_ou_nada(caminho):
    """Páginas do pypdf normalizadas, ou None (sem o módulo, PDF ilegível)."""
    try:
        pags = _pypdf_paginas(caminho)
    except Exception:  # noqa: BLE001 — sem o pypdf, a ordem do PDFKit fica
        return None
    return [jc.normalizar_pdf(p) for p in pags] if pags is not None else None


# Imagem grande numa página com texto (tabela colada como imagem, trecho escaneado): o PDFKit
# não lê o que está nela. Imagem que cobre de 10% a 90% da página, sem texto (pypdf) dentro da
# área dela, passa pelo OCR só na área da imagem; as linhas lidas entram antes da primeira linha
# de texto abaixo da imagem (ou no fim da página). Vale também a faixa larga de 3% a 10% da página
# (largura de metade da página ou mais): o recorte de uma citação ou de uma tabela de poucas
# linhas, que a figura pequena (logotipo, assinatura) não alcança; a faixa na mesma posição em 3
# páginas ou mais (cabeçalho em imagem) fica de fora, e o OCR da faixa com 12% ou mais das
# palavras embaralhadas (gráfico, tela de sistema) não entra. Não entram linhas de timbre
# nem linhas longas que já estão na página; o bloco só entra com confiança média de 0,8, 3 linhas, 100 caracteres
# e 12 caracteres por linha, em média (o logotipo da CVM e os rótulos de gráfico ficam de fora).
IMAGEM_FRACAO_MIN, IMAGEM_FRACAO_MAX, IMAGEM_TEXTO_DENTRO = 0.10, 0.90, 20
IMAGEM_PIXELS_MIN = 60000
IMAGEM_FAIXA_MIN, IMAGEM_FAIXA_LARGURA = 0.03, 0.5
IMAGEM_CONFIANCA, IMAGEM_LINHAS, IMAGEM_CARACTERES, IMAGEM_LINHA_LONGA = 0.8, 3, 100, 15
IMAGEM_MEDIA_LINHA = 12
# --marcar-imagens (decisão do Diogo no D3649, 2026-11-05): a imagem que entraria pelo OCR vira só
# a marca abaixo, sem o texto lido (nível segue pdf-extraido); sem a opção, o OCR segue o padrão.
MARCA_IMAGEM = "[imagem com texto não convertida; ver o PDF oficial]"
MARCAR_IMAGENS = False
IMAGEM_EMBARALHADO = 0.12
_OCR_PALAVRA_OK = re.compile(r"[\wÀ-ÿ.,;:()\[\]%/\-–—'\"“”‘’ºª°§$+&=<>@#!?]+")
_OCR_VOGAL = re.compile(r"[aeiouyáéíóúâêôãõàAEIOUYÁÉÍÓÚÂÊÔÃÕÀ]")


def _palavra_embaralhada(t):
    t = t.strip("*|•")  # nota (*) e borda de tabela nas pontas não contam
    if not t:
        return False
    if not _OCR_PALAVRA_OK.fullmatch(t) or "_" in t:
        return True
    letras = re.sub(r"[^A-Za-zÀ-ÿ]", "", t)
    if len(letras) >= 3 and re.search(r"[a-zß-ÿ][A-ZÀ-Þ]", letras):
        return True  # caixa trocada no meio da palavra ("DYqCA", "SAlOs")
    return (len(letras) >= 4 and not re.search(r"\d", t) and not letras.isupper()
            and not _OCR_VOGAL.search(letras))  # palavra sem vogal ("Telfnc"), não hora "17h11m"


def _ocr_embaralhado(texto):
    """True se 12% ou mais das palavras de 3+ caracteres do OCR estão embaralhadas (caractere
    fora do alfabeto e da pontuação, caixa trocada no meio, palavra sem vogal)."""
    palavras = [t for t in texto.split() if len(t) >= 3]
    ruins = sum(_palavra_embaralhada(t) for t in palavras)
    return bool(palavras) and ruins >= IMAGEM_EMBARALHADO * len(palavras)


def _tipo_de_imagem(w, h, largura, area):
    """"grande" (10% a 90% da página), "faixa" (3% a 10%, metade da largura ou mais) ou None."""
    fr = w * h / area if area else 0
    if IMAGEM_FRACAO_MIN <= fr < IMAGEM_FRACAO_MAX:
        return "grande"
    if IMAGEM_FAIXA_MIN <= fr < IMAGEM_FRACAO_MIN and w >= IMAGEM_FAIXA_LARGURA * largura:
        return "faixa"
    return None


def _sem_faixas_repetidas(caixas):
    """[(página, caixa, seguinte, é faixa)] sem a faixa na mesma posição em 3 páginas ou mais
    (cabeçalho ou rodapé em imagem, não conteúdo)."""
    def _pos(c):
        return tuple(round(v) for v in c)
    vezes = collections.Counter(_pos(c) for _, c, _, f in caixas if f)
    return [x for x in caixas if not x[3] or vezes[_pos(x[1])] < MIN_PAGINAS_REPETIDA]


def _imagens_sem_texto(caminho):
    """[(página, (x, y, largura, altura), texto da linha logo abaixo da imagem, é faixa)] das
    imagens grandes ou em faixa sem texto dentro (regra acima), pelo pypdf; [] sem o módulo ou
    com PDF ilegível."""
    try:
        import pypdf
        leitor = pypdf.PdfReader(caminho)
        out = []
        for n, pag in enumerate(leitor.pages):
            res = pag.get("/Resources")
            res = res.get_object() if res else {}
            xo = res.get("/XObject") if res else None
            xo = xo.get_object() if xo else {}
            if not any(v.get_object().get("/Subtype") == "/Image"
                       and (v.get_object().get("/Width") or 0) * (v.get_object().get("/Height") or 0)
                       >= IMAGEM_PIXELS_MIN for v in xo.values()):
                continue
            largura = float(pag.mediabox.width)
            area = largura * float(pag.mediabox.height)
            caixas, textos = [], []

            def _op(op, args, cm, tm):
                if op == b"Do" and args:
                    v = xo.get(args[0])
                    if v is not None and v.get_object().get("/Subtype") == "/Image":
                        caixas.append((min(cm[4], cm[4] + cm[0]), min(cm[5], cm[5] + cm[3]),
                                       abs(cm[0]), abs(cm[3])))

            def _txt(texto, cm, tm, fonte, tamanho):
                if texto.strip():
                    textos.append((tm[4] * cm[0] + tm[5] * cm[2] + cm[4],
                                   tm[4] * cm[1] + tm[5] * cm[3] + cm[5], texto.strip()))

            pag.extract_text(visitor_operand_before=_op, visitor_text=_txt)
            for x, y, w, h in caixas:
                tipo = _tipo_de_imagem(w, h, largura, area)
                if tipo is None:
                    continue
                dentro = sum(len(t) for a, b, t in textos if x <= a <= x + w and y <= b <= y + h)
                if dentro > IMAGEM_TEXTO_DENTRO:
                    continue
                abaixo = sorted((-b, a, t) for a, b, t in textos if b < y - 1)
                linhas = []
                for b, a, t in abaixo:
                    if linhas and abs(linhas[-1][0] - b) < 2:
                        linhas[-1][1].append(t)
                    else:
                        linhas.append((b, [t]))
                seguinte = "\n".join(" ".join(ts) for _, ts in linhas[:3])
                out.append((n, (x, y, w, h), seguinte, tipo == "faixa"))
        # de cima para baixo: duas imagens antes da mesma linha entram na ordem da página
        out.sort(key=lambda z: (z[0], -(z[1][1] + z[1][3])))
        return _sem_faixas_repetidas(out)
    except Exception:  # noqa: BLE001 — sem pypdf ou PDF ilegível: sem OCR de imagem
        return []


def _ocr_regiao(caminho, pagina, caixa, pm):
    """(texto, confiança média) do OCR só da área `caixa` da página, ou None."""
    try:
        import pypdf
        escritor = pypdf.PdfWriter()
        pag = escritor.add_page(pypdf.PdfReader(caminho).pages[pagina])
        x, y, w, h = caixa
        pag.mediabox = pag.cropbox = pypdf.generic.RectangleObject([x, y, x + w, y + h])
        with tempfile.TemporaryDirectory() as tmp:
            regiao = os.path.join(tmp, "regiao-imagem.pdf")
            with open(regiao, "wb") as f:
                escritor.write(f)
            texto, conf = pm.ocr(regiao)
    except Exception:  # noqa: BLE001 — sem pypdf, sem macOS ou PDF ilegível: fica o PDFKit
        return None
    return texto, (sum(conf) / len(conf) if conf else 0.0)


def inserir_texto_de_imagem(pagina, texto_ocr, seguinte, original=None, substituto=None):
    """Página com as linhas do OCR da imagem antes da linha `seguinte` (ou no fim): regra acima.
    `substituto`: entra ele, e não o bloco lido, quando o bloco passaria pela regra.
    `original`: a página antes do OCR das outras imagens; a semelhança (60%) se mede contra ela,
    para o bloco de uma imagem não apagar as linhas parecidas da imagem seguinte (cláusulas quase
    iguais); contra o já inserido, só a linha idêntica sai (a mesma imagem lida duas vezes)."""
    compacta, idx = _sem_espacos(pagina)
    lida = compacta if original is None else _sem_espacos(original)[0]
    linhas_atuais = {re.sub(r"\s+", "", x) for x in pagina.split("\n")}
    bloco = []
    for linha in jc.normalizar_pdf(texto_ocr).split("\n"):
        c = re.sub(r"\s+", "", linha)
        if not c or _linha_de_timbre(linha):
            continue
        if len(c) >= IMAGEM_LINHA_LONGA:
            if c in lida or c in linhas_atuais:
                continue
            m = difflib.SequenceMatcher(None, c, lida, autojunk=False).find_longest_match(
                0, len(c), 0, len(lida))
            if m.size >= 0.6 * len(c):
                continue
        bloco.append(linha.strip())
    total = sum(len(re.sub(r"\s+", "", x)) for x in bloco)
    if (len(bloco) < IMAGEM_LINHAS or total < IMAGEM_CARACTERES
            or total < IMAGEM_MEDIA_LINHA * len(bloco)):
        return pagina
    texto = (substituto or "\n".join(bloco)) + "\n"
    for linha in (seguinte or "").split("\n"):
        c = re.sub(r"\s+", "", linha)
        k = compacta.find(c) if len(c) >= 6 else -1
        if k >= 0:
            ini = pagina.rfind("\n", 0, idx[k]) + 1
            return pagina[:ini] + texto + pagina[ini:]
    return pagina + ("" if not pagina or pagina.endswith("\n") else "\n") + texto


def texto_pdf(caminho, pm=pdf_macos, data=None):
    """(páginas, nível, motor, avisos, nº de páginas por OCR). PDFKit primeiro (pypdf fora do
    macOS); páginas com menos de 20 caracteres passam pelo OCR do Vision. `data` (AAAA-MM-DD)
    do julgado, para as correções de OCR que dependem dela."""
    avisos = []
    try:
        paginas, motor = pm.texto_pdfkit(caminho).split("\f"), "pdfkit"
    except pm.ErroPdfMacos:
        paginas, motor = _pypdf_paginas(caminho), "pypdf"
        if paginas is None:
            raise
    # elemento final vazio só sai se passar do número real de páginas: a última página sem
    # texto (assinatura escaneada) é página de verdade e vai ao OCR
    n_real = len(paginas) if motor == "pypdf" else _numero_de_paginas(caminho)
    if n_real is not None and len(paginas) > n_real and not paginas[-1].strip():
        paginas = paginas[:-1]
    paginas = [jc.normalizar_pdf(p) for p in paginas]
    if motor == "pdfkit":
        sem_camadas = [desfazer_sobreposicao(p) for p in paginas]
        pys = _paginas_pypdf_ou_nada(caminho)
        if pys is not None and len(pys) == len(paginas):
            sem_camadas = [x if x != p or len(p.strip()) < MIN_CARACTERES_PAGINA
                           else reordenar_pela_ordem_do_pypdf(p, y)
                           for p, x, y in zip(paginas, sem_camadas, pys)]
        paginas = sem_camadas
    vazias = [i for i, p in enumerate(paginas) if len(p.strip()) < MIN_CARACTERES_PAGINA]
    nivel, n_ocr = "pdf-extraido", 0
    if vazias:
        try:
            texto, conf = pm.ocr(caminho)
            pags_ocr, lidas = texto.split("\f"), []
            for i in vazias:
                if i < len(pags_ocr) and pags_ocr[i].strip():
                    paginas[i] = corrigir_ocr(jc.normalizar_pdf(pags_ocr[i]), data)
                    n_ocr += 1
                    lidas.append(i)
            contexto = "\n".join(paginas)
            for i in lidas:
                paginas[i] = corrigir_siglas_ocr(paginas[i], contexto)
            if n_ocr:
                nivel = "ocr"
                confs = [conf[i] for i in vazias if i < len(conf)]
                avisos.append("OCR em %d de %d página(s)%s" % (
                    n_ocr, len(paginas),
                    ", confiança média %.2f" % (sum(confs) / len(confs)) if confs else ""))
        except pm.ErroPdfMacos:
            avisos.append("%d página(s) sem texto e sem OCR (fora do macOS)" % len(vazias))
    if motor == "pdfkit":
        n_img, originais = 0, list(paginas)
        for i, caixa, seguinte, *faixa in _imagens_sem_texto(caminho):
            if i >= len(paginas) or i in vazias:
                continue
            lido = _ocr_regiao(caminho, i, caixa, pm)
            if not lido or lido[1] < IMAGEM_CONFIANCA:
                continue
            texto = corrigir_siglas_ocr(corrigir_ocr(jc.normalizar_pdf(lido[0]), data),
                                        "\n".join(paginas))
            if faixa and faixa[0] and _ocr_embaralhado(texto):
                continue
            nova = inserir_texto_de_imagem(paginas[i], texto, seguinte, originais[i],
                                           MARCA_IMAGEM if MARCAR_IMAGENS else None)
            if nova != paginas[i]:
                paginas[i], n_img = nova, n_img + 1
        if n_img and MARCAR_IMAGENS:
            avisos.append("%d imagem(ns) com texto marcada(s), sem OCR" % n_img)
        elif n_img:
            nivel = "ocr"
            avisos.append("OCR de %d imagem(ns) sem texto em página(s) com texto" % n_img)
    return paginas, nivel, motor, avisos, n_ocr


_CABECALHOS = (
    ("Extrato", re.compile(r"EXTRATO D[AE] SESS[ÃA]O DE JULGAMENTO\b.*")),
    ("Relatório", re.compile(r"RELAT[ÓO]RIO|Relat[óo]rio")),
    ("Voto", re.compile(r"VOTO(?: (?:D[OA]|VENCEDOR|VENCIDO|DE DESEMPATE)\b.*)?|Voto")),
    ("Declaração de voto", re.compile(r"(?:DECLARA[ÇC][ÃA]O|MANIFESTA[ÇC][ÃA]O) DE VOTO\b.*|"
                                      r"(?:Declara[çc][ãa]o|Manifesta[çc][ãa]o) de [Vv]oto\b.*")),
    ("Manifestação da área técnica",
     re.compile(r"MANIFESTA[ÇC][ÃA]O D[AE] (?:[ÁA]REA T[ÉE]CNICA|SUPERINTEND[ÊE]NCIA)\b.*")),
)
_CURTOS = {"RELATÓRIO", "RELATORIO", "Relatório", "Relatorio", "VOTO", "Voto"}


def _cabecalho(linha):
    s = linha.strip()
    if len(s) > 90:
        return None
    for nome, rx in _CABECALHOS:
        if rx.fullmatch(s):
            return nome
    return None


# Bloco de partes no topo das peças ("Interessados: A" e os demais nomes nas linhas seguintes):
# linha só com nome, repetida no topo de cada peça, é parte do processo, não cabeçalho.
_ROTULO_PARTES = re.compile(
    r"\s*\**\s*(?:Interessad[oa]s?|Acusad[oa]s?|Indiciad[oa]s?|Recorrentes?)\s*\**\s*:", re.I)
_ROTULO = re.compile(r"\s*\**\s*[A-ZÀ-Ý][\wÀ-ÿ.\-/ ]{0,40}:")
BORDA_LINHAS = 3
# nota de rodapé: número de chamada seguido de texto ("12 Doc. 1619945.", "3 Fls. 20/21."); a
# chave com os números trocados por # repetiria entre páginas. "1 de 4" é número de página.
_NOTA_DE_RODAPE = re.compile(r"\s*\d{1,3}\s*(?!(?:de|of)\s+\d)[A-Za-zÀ-ÿ\"“(]")


def _linhas_de_partes(linhas):
    """Índices das linhas de blocos "Interessados:", "Acusados:", "Indiciados:" e "Recorrentes:"
    (singular também): do rótulo até a linha em branco, o próximo rótulo ou cabeçalho de peça."""
    dentro, bloco = False, set()
    for i, linha in enumerate(linhas):
        if _ROTULO_PARTES.match(linha):
            dentro = True
        elif dentro and (not linha.strip() or _ROTULO.match(linha) or _cabecalho(linha)):
            dentro = False
        if dentro:
            bloco.add(i)
    return bloco


def tirar_repetidas(paginas, minimo=MIN_PAGINAS_REPETIDA, retirado=None, borda=BORDA_LINHAS):
    """Junta as páginas sem o cabeçalho e o rodapé de página: linha (de 8 caracteres ou mais)
    que aparece na borda (entre as `borda` primeiras ou últimas linhas não vazias) de `minimo` ou
    mais páginas, duas delas seguidas e na mesma borda, com os números trocados por # (número de
    página; a linha sem letra conta pelo texto inteiro). Só a ocorrência na borda sai: a mesma linha no miolo da página é texto da peça
    (termos parecidos, fecho, subtítulo, data). Título repetido só no topo de cada peça (páginas
    não seguidas), nota de rodapé, cabeçalho de peça e bloco de partes ("Interessados:") ficam.
    Devolve (texto, nº de linhas retiradas)."""
    def chave(linha):
        # linha só de números (linha de tabela: "29.100 12:24:42 / 12:30:41") conta pelo texto
        # inteiro: com os números trocados por #, linhas diferentes da tabela virariam uma só
        t = re.sub(r"\s+", " ", linha.strip())
        return re.sub(r"\d+", "#", t) if re.search(r"[^\W\d_]", t) else t

    def candidatas(linhas):
        # o timbre não ocupa lugar na borda: o cabeçalho de 5 linhas (logotipo, endereços, site)
        # empurraria a linha do processo para o miolo; as linhas de timbre dentro da borda contam
        cheias = [i for i, x in enumerate(linhas) if x.strip() and not _linha_de_timbre(x)]
        if not cheias:
            return set()
        topo, pe = cheias[:borda][-1], cheias[-borda:][0]
        partes = _linhas_de_partes(linhas)
        return {i for i, x in enumerate(linhas)
                if (i <= topo or i >= pe) and len(x.strip()) >= 8
                and not (i <= topo and i in partes)  # partes ficam no topo; o pé é rodapé
                and not _cabecalho(x) and not _NOTA_DE_RODAPE.match(x)}

    divididas = [p.splitlines() for p in paginas]
    bordas = [candidatas(ls) for ls in divididas]
    paginas_da_chave = {}  # chave -> posições (entre as páginas com texto) e borda (topo ou pé)
    posicao = -1
    for ls, bs in zip(divididas, bordas):
        if any(x.strip() for x in ls):
            posicao += 1
        meio = len(ls) / 2
        for i in bs:
            paginas_da_chave.setdefault(chave(ls[i]), set()).add((posicao, i < meio))
    # cabeçalho e rodapé de página aparecem na mesma borda de páginas seguidas; o fecho de um
    # termo no pé de uma página e no topo da seguinte não conta
    fora = {k for k, ps in paginas_da_chave.items()
            if len({p for p, _ in ps}) >= minimo and any((p + 1, t) in ps for p, t in ps)}
    saida, retiradas = [], 0
    for ls, bs in zip(divididas, bordas):
        for i, linha in enumerate(ls):
            if i in bs and chave(linha) in fora:
                retiradas += 1
                if retirado is not None:
                    retirado.append(linha)
                continue
            saida.append(linha.rstrip())
        saida.append("")
    return "\n".join(saida), retiradas


# Timbre e rodapé da CVM e do SEI, por padrão explícito: valem também nas páginas por OCR e
# nos PDFs curtos, onde a regra da linha repetida não alcança. Saem antes do pii.py (o telefone
# da CVM não é dado pessoal).
_CEP_CVM = r"(?:20050-901|01333-010|70712-900|01049-000|20159-900)"
_SEDE_CVM = (r"(?:Rua\s+Sete\s+de\s+Setembro,?\s*11[01]|Rua\s+Cincinato\s+Braga,?\s*340|"
             r"Rua\s+Formosa,?\s*367|"
             r"SCN\s*Q\.?\s*0?2\b|Corporate\s+Financial\s+Center)")
_TEL_CVM = r"\(?\b(?:21|11|61)\)?\s*(?:3554|2146|3327|3233)[-.\s]?\d{4}(?:\s*/\s*\d{4})?"
_LINHA_TIMBRE = re.compile(
    r".*%s.*|.*%s.*(?:Andar|CEP|Tel|Brasil).*|%s[\s,/\dº°ªe-]*|" % (_CEP_CVM, _SEDE_CVM, _SEDE_CVM)
    + r"(?:(?:Site|Tel\.?|Fax|Telefone|SAC|Ouvidoria|Brasil)[:.\s]*|www\.cvm\.gov\.br/?|https?://www\.cvm"
      r"\.gov\.br/?|(?:https?://)?www\.gov\.br/cvm/?|%s|[\s|•–—,;/-])+|" % _TEL_CVM
    + r"SEI/CVM\s*-\s*\d{5,9}\s*-\s.{0,160}|"
      r"https?://sei\.cvm\.gov\.br/sei/controlador\.php\S*|autenticidade,(?:\s+and)?|"
      r"\d{1,3}\s+(?:of|de)\s+\d{1,3}\s+\d{2}/\d{2}/\d{4},?\s+\d{1,2}:\d{2}(?::\d{2})?|"
      r"(?:.{0,100}\(\d{6,9}\)\s*)?SEI\s*[\d./\s-]{10,30}/\s*pg\.?\s*\d+|"
      r"COMISS[ÃA]O\s+DE\s+V\s?ALORES\s+MOBILI[ÁA]RIOS", re.I)
_FRAGMENTO_TIMBRE = "COMISSÃO DE VALORES MOBILIÁRIOS"
# assinatura do SEI de 2014-2017 pela Lei 11.419/2006 ("..., conforme art. 1º, III, "b", da Lei
# 11.419/2006."), com o nº de série do certificado (alínea "a") e a versão em inglês; e a sobra
# dela em linha própria, que começa por vírgula (o PDFKit separa o nome do signatário do fim)
_LEI_SEI = r"art\.\s*1º\s*,\s*III\s*,\s*\"[ab]\"\s*,\s*da\s+Lei\s+11\.419/2006"
_SERIE_SEI = r"(?:\s*N[º°]\s*de\s+S[ée]rie\s+do\s+Certificado:\s*\d+\.?)?"
_SPANS_SEI = (
    re.compile(r"Documento\s+assinado\s+eletronicamente\s+por\s(?:(?!Documento\s+assinado).){1,300}?"
               r"conforme\s+" + _LEI_SEI + r"\.?" + _SERIE_SEI, re.S | re.I),
    re.compile(r"Document\s+electronic(?:ally)?\s+signed\s+by\s(?:(?!Document\s+electronic).){1,300}?"
               r"art\.\s*1º\s*,\s*III\s*,\s*\"[ab]\"\s*,\s*of\s+Law\s+11\.419/2006\.?"
               r"(?:\s*Certificate\s+serial\s+number:\s*\d+\.?)?", re.S | re.I),
    re.compile(r"(?m)^[ \t]*,\s*conforme\s+" + _LEI_SEI + r"\.?" + _SERIE_SEI),
    re.compile(r"Documento\s+assinado\s+eletronicamente\s+por\s.{1,300}?(?:Decreto\s+n\S*\s*8\.539"
               r"(?:,?\s*de\s+8\s+de\s+outubro\s+de\s+2015)?|de\s+8\s+de\s+outubro\s+de\s+2015)\.?",
               re.S | re.I),
    re.compile(r"Documento\s+assinado\s+eletronicamente\s+por\s[^\n]{1,200}?,\s*em\s+\d{1,2}/\d{1,2}/"
               r"\d{4}(?:,?\s+[àa]s\s+\d{1,2}:\d{2})?\.?", re.I),
    re.compile(r"A\s+autenticidade\s+(?:deste|do)\s+documento\s+pode\s+ser\s+conferida.{1,300}?"
               r"c[óo]digo\s+CRC[\s*_\"]{0,10}[0-9A-F]+[*_\"]*\.?[*_]*", re.S | re.I),
    re.compile(r"This\s+document'?s\s+authenticity\s+can\s+be\s+verified.{1,300}?C[óo]digo\s+CRC"
               r"[\s*_\"]{0,10}[0-9A-F]+[*_\"]*\.?[*_]*", re.S | re.I),
    re.compile(r"Refer[êe]ncia:\s*Processo\s+n\S*\s*[\d./-]+\s+SEI\s+n\S*\s*\d+\.?", re.I),
)


_SO_BRASIL = re.compile(r"\s*Brasil[:.\s]*", re.I)


def _linha_de_timbre(linha):
    """Linha de timbre por si só. "Brasil" sozinho, com qualquer pontuação, não conta: é o fim de
    "Banco Central do / Brasil.", "no / Brasil;" ou "B3 S.A. / – Brasil,"; só é timbre logo
    depois do endereço (ver tirar_timbre)."""
    s = re.sub(r"\s+", " ", linha.strip())
    if not s or re.fullmatch(r"[\W_]*brasil[\W_]*", s, re.I):
        return False
    if len(s) >= 5 and s.upper() == s and s in _FRAGMENTO_TIMBRE and re.search(r"[A-ZÀ-Ý]{3}", s):
        return True  # pedaço do logotipo lido pelo OCR ("VALORES", "MOBILIÁRIOS")
    return bool(_LINHA_TIMBRE.fullmatch(s)) and bool(re.search(r"[A-Za-z0-9]", s))


def tirar_timbre(texto, retirado=None):
    """Texto sem o timbre e o rodapé da CVM e do SEI: endereços das sedes, CEPs, telefones e site
    da CVM; "Documento assinado eletronicamente por ...", "A autenticidade deste documento ...",
    "Referência: Processo nº ... SEI nº ..." (o número SEI citado no meio do texto fica);
    cabeçalho e rodapé da impressão do SEI. Devolve (texto, nº de trechos retirados)."""
    retirado = [] if retirado is None else retirado
    n0 = len(retirado)
    for rx in _SPANS_SEI:
        partes, ini = [], 0
        for m in rx.finditer(texto):
            a, b = m.start(), m.end()
            ls = texto.rfind("\n", 0, a) + 1
            if not texto[ls:a].strip(" \t*_"):
                a = ls
            le = texto.find("\n", b)
            le = len(texto) if le < 0 else le
            if not texto[b:le].strip(" \t*_."):
                b = min(le + 1, len(texto))
            partes.append(texto[ini:a])
            retirado.append(texto[a:b])
            ini = b
        partes.append(texto[ini:])
        texto = "".join(partes)
    linhas, anterior_timbre = [], False
    for linha in texto.split("\n"):
        if _linha_de_timbre(linha) or (anterior_timbre and _SO_BRASIL.fullmatch(linha)):
            retirado.append(linha)
            anterior_timbre = True
        else:
            linhas.append(linha)
            anterior_timbre = anterior_timbre if not linha.strip() else False
    return "\n".join(linhas), len(retirado) - n0


def _escapar(linha):
    return "\\" + linha if linha.lstrip().startswith("#") else linha


def _limpar_bloco(linhas):
    txt = "\n".join(_escapar(x) for x in linhas)
    return re.sub(r"\n{3,}", "\n\n", txt).strip()


def segmentar(texto):
    """[(seção, texto)] pelos cabeçalhos de peça (linha inteira); sem nenhum, [("Texto", ...)].
    O que vem antes do primeiro cabeçalho fica em "Texto"."""
    secoes, atual, linhas = [], "Texto", []
    for linha in texto.splitlines():
        nome = _cabecalho(linha)
        if nome:
            if _limpar_bloco(linhas):
                secoes.append((atual, _limpar_bloco(linhas)))
            atual, linhas = nome, ([] if linha.strip() in _CURTOS else [linha.strip()])
            continue
        linhas.append(linha)
    if _limpar_bloco(linhas):
        secoes.append((atual, _limpar_bloco(linhas)))
    return secoes


# ---------------------------------------------------------------- HTML

_ARTIGO = re.compile(r"<article\b[^>]*contentTextoGeral[^>]*>(.*?)</article>", re.S | re.I)
_VEJA_MAIS = re.compile(r"<div[^>]*class=\"[^\"]*(?:contentVejaMais|bottomPrint)[^\"]*\".*",
                        re.S | re.I)
_TITULO_COL = re.compile(r"<p[^>]*class=\"[^\"]*text-uppercase[^\"]*\"[^>]*>(.*?)</p>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")


def _txt(html):
    return re.sub(r"\s+", " ", unescape(_TAG.sub(" ", html or ""))).strip()


def artigo(html):
    m = _ARTIGO.search(html)
    return m.group(1) if m else html


class _Texto(HTMLParser):
    """Texto visível, para a conferência independente (sem script e style)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes, self._pular = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._pular += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._pular:
            self._pular -= 1

    def handle_data(self, data):
        if not self._pular:
            self.partes.append(data)


def texto_html_independente(html):
    p = _Texto()
    p.feed(html)
    return " ".join(p.partes)


def colegiado_da_pagina(html):
    """(título, data, relator, markdown da decisão) da página do item do Colegiado."""
    corpo = artigo(html)
    m = re.search(r"<h2[^>]*>(.*?)</h2>", corpo, re.S | re.I)
    data = jc.data_br(_txt(m.group(1))) if m else None
    t = _TITULO_COL.search(corpo)
    titulo = _txt(t.group(1)) if t else ""
    rel = re.search(r"Relator[a]?:\s*([^<\n(]+)", corpo)
    relator = _txt(rel.group(1)).rstrip(" .") if rel else ""
    miolo = _VEJA_MAIS.sub("", corpo)
    miolo = re.sub(r"<h2[^>]*>.*?</h2>", "", miolo, flags=re.S | re.I)
    if t:
        miolo = miolo.replace(t.group(0), "")
    return titulo, data, relator, html_bcb.html_para_md(miolo).strip()


def pas_da_pagina(html):
    """(título, data, ementa) da página do PAS."""
    corpo = artigo(html)
    m = re.search(r"<h2[^>]*>(.*?)</h2>", corpo, re.S | re.I)
    titulo = _txt(m.group(1)) if m else ""
    d = re.search(r"Data da Sess[ãa]o de julgamento</b>(.*?)</p>", corpo, re.S | re.I)
    data = _data_cvm(_txt(d.group(1))) if d else None
    e = re.search(r"<b>\s*Ementa\s*</b>(.*?)(?:<div|</section)", corpo, re.S | re.I)
    ementa = _txt(e.group(1)) if e else ""
    return titulo, data, ementa


def sei_para_md(html):
    """Extrato do SEI (ISO-8859-1): sem imagens; tabela, linha e célula viram bloco."""
    html = re.sub(r"<img\b[^>]*>", "", html, flags=re.I)
    html = re.sub(r"<(/?)(?:table|tbody|thead|tr|td|th)\b[^>]*>", r"<\1div>", html, flags=re.I)
    m = re.search(r"<body\b[^>]*>(.*)</body>", html, re.S | re.I)
    return html_bcb.html_para_md(m.group(1) if m else html).strip()


# ---------------------------------------------------------------- metadados


def relator_do_texto(texto):
    m = re.search(r"(?m)^\s*(?:Diretora?\s+)?Relatora?(?: do [Vv]oto [Vv]encedor)?\s*:\s*(.+?)\s*$",
                  texto)
    if not m:
        return ""
    r = re.sub(r"^(?:Diretora?|Presidente)\s+", "", m.group(1)).strip(" .")
    return r if len(r) <= 80 else ""


def rito_do_texto(texto):
    achados = set()
    if re.search(r"rito\s+simplificado", texto, re.I):
        achados.add("simplificado")
    if re.search(r"rito\s+ordin[áa]rio", texto, re.I):
        achados.add("ordinario")
    return achados.pop() if len(achados) == 1 else ""


def _um(familias, texto):
    achados = [nome for nome, rx in familias if re.search(rx, texto, re.I)]
    return achados[0] if len(achados) == 1 else ""


_RES_TC = (("aceito", r"deliberou\s+(?:por\s+)?aceitar\b"),
           ("rejeitado", r"deliberou\s+(?:por\s+)?rejeitar\b"))
_RES_COL = (("provido", r"\bdeu\s+provimento\b|\bdar\s+provimento\b"),
            ("nao-provido", r"\bneg(?:ou|ar)\s+provimento\b"),
            ("parcial", r"\bprovimento\s+parcial\b|\bparcial\s+provimento\b"),
            ("deferido", r"\bdeferiu\b|\bdeferir\s+o\s+pedido\b"),
            ("indeferido", r"\bindeferiu\b|\bindeferir\s+o\s+pedido\b"))
_RES_PAS = (("absolvicao", r"\babsolv"),
            ("condenacao", r"\bcondena|\bmulta\b|\badvert[êe]ncia\b|\binabilita"),
            ("extincao", r"extin[çc][ãa]o\s+da\s+punibilidade"))


def resultado(tipo, texto, item):
    """Só por regex segura: um padrão e um só. Na dúvida, vazio."""
    if tipo == "termo-compromisso":
        return item.get("resultado") or _um(_RES_TC, texto)
    if tipo == "decisao-colegiado":
        return _um(_RES_COL, texto)
    if tipo == "pas":
        m = re.search(r"EXTRATO D[AE] SESS[ÃA]O.*?(?=\n##|\Z)", texto, re.S)
        return _um(_RES_PAS, m.group(0)) if m else ""
    return ""


_CITACOES = {}


def citacoes(texto):
    """(normas_citadas, dispositivos_citados, aviso) por citacoes.py; sem o módulo, vazios."""
    try:
        import citacoes as cit
        if "ids" not in _CITACOES:
            _CITACOES["ids"] = cit.carregar_ids()
        ids = _CITACOES["ids"]
        lista = cit.extrair_citacoes(texto, ids)
        normas = cit.formatar_normas_citadas(lista, cit.normas_mencionadas(texto, ids))
        disp = cit.formatar_dispositivos_citados(lista)
    except Exception as e:  # noqa: BLE001 — módulo ausente ou em obras: campos vazios
        return "", "", "citações não extraídas (%s)" % type(e).__name__
    return _sem_fora_sem_numero(normas, disp)


def _sem_fora_sem_numero(normas, disp):
    """Guarda: rótulo `fora:` sempre leva número (fora:lei-9784). Sem número, sai da lista de
    normas e dos dispositivos, com aviso."""
    def ruim(x):
        x = x.strip()
        return x.startswith("fora:") and not re.search(r"\d", x.split("#")[0].split(" ")[0])
    itens_n = [x for x in normas.split(";") if x.strip()] if normas else []
    itens_d = [x for x in disp.split(";") if x.strip()] if disp else []
    tirados = [x.strip() for x in itens_n + itens_d if ruim(x)]
    if not tirados:
        return normas, disp, ""
    n = "; ".join(x.strip() for x in itens_n if not ruim(x))
    d = "; ".join(x.strip() for x in itens_d if not ruim(x))
    return n, d, "rótulo fora: sem número descartado (%s)" % ", ".join(sorted(set(tirados)))


# ---------------------------------------------------------------- cobertura


def _palavras(texto):
    return set(re.findall(r"[a-zà-ÿ0-9]{4,}", (texto or "").lower()))


def _compacto(texto):
    t = re.sub(r"\s+", "", (texto or "").lower())
    return t, t.replace("-", "").replace("­", "")


def medir(referencia, saida, retirado="", antes_pii=""):
    """Cobertura das palavras (4+ letras) da referência na saída. Palavra ausente que é pedaço de
    texto da saída sem espaços conta como coberta (o extrator parte ou cola palavras); a que está
    no timbre/rodapé retirado vai para `retiradas`, e a cortada pelo pii.py para `pii`, fora da
    conta. Devolve {cobertura, palavras, retiradas, pii, faltam (até 20)}."""
    ref = _palavras(referencia)
    if not ref:
        return {"cobertura": None, "palavras": 0, "fragmentos": 0, "retiradas": 0, "pii": 0,
                "faltam": []}
    fora = sorted(ref - _palavras(saida))
    comp = _compacto(saida)
    n_fora = len(fora)
    fora = [w for w in fora if w not in comp[0] and w not in comp[1]]
    fragmentos = n_fora - len(fora)
    ret_p, ret_c = _palavras(retirado), _compacto(retirado)
    retiradas = [w for w in fora if w in ret_p or w in ret_c[0] or w in ret_c[1]]
    fora = [w for w in fora if w not in set(retiradas)]
    pii_p, pii_c = _palavras(antes_pii), _compacto(antes_pii)
    cortadas = [w for w in fora if w in pii_p or w in pii_c[0]]
    fora = [w for w in fora if w not in set(cortadas)]
    base = len(ref) - len(retiradas) - len(cortadas)
    return {"cobertura": round((base - len(fora)) / base, 4) if base else None,
            "palavras": len(ref), "fragmentos": fragmentos, "retiradas": len(retiradas),
            "pii": len(cortadas),
            "faltam": fora[:20]}


def cobertura(referencia, saida):
    return medir(referencia, saida)["cobertura"]


def regiao_html(html, regiao):
    """Trecho da página que o conversor usa: `artigo` (o <article> sem a caixa de anexos),
    `pas` (título, data e ementa da página do PAS) ou `sei` (corpo do extrato, sem imagens)."""
    if regiao == "pas":
        corpo = artigo(html)
        partes = re.findall(r"<h2[^>]*>.*?</h2>", corpo, re.S | re.I)
        d = re.search(r"Data da Sess[ãa]o de julgamento</b>(.*?)</p>", corpo, re.S | re.I)
        e = re.search(r"<b>\s*Ementa\s*</b>(.*?)(?:<div|</section)", corpo, re.S | re.I)
        if d:
            partes.append(_data_cvm(_txt(d.group(1))) or "")
        if e:
            partes.append(e.group(1))
        return " ".join(partes)
    if regiao == "sei":
        m = re.search(r"<body\b[^>]*>(.*)</body>", html, re.S | re.I)
        return re.sub(r"<img\b[^>]*>", "", m.group(1) if m else html, flags=re.I)
    return _VEJA_MAIS.sub("", artigo(html))


def conferir(arq, caminho, motor, saida, regiao="artigo", retirado="", antes_pii=""):
    """Cobertura de um arquivo da fonte por extrator independente do usado na conversão."""
    if caminho.lower().endswith(".pdf"):
        if motor == "pypdf":
            return {"arquivo": arq, "cobertura": None, "conferencia": "sem conferência independente"}
        try:
            pags = _pypdf_paginas(caminho)
        except Exception as e:  # noqa: BLE001 — PDF que o pypdf não lê
            return {"arquivo": arq, "cobertura": None, "conferencia": "pypdf falhou (%s)" %
                    type(e).__name__}
        if pags is None:
            return {"arquivo": arq, "cobertura": None, "conferencia": "sem conferência independente"}
        return dict({"arquivo": arq, "conferencia": "pypdf"},
                    **medir(" ".join(pags), saida, retirado, antes_pii))
    with open(caminho, "rb") as f:
        html = jc.decodificar(f.read())
    ref = texto_html_independente(regiao_html(html, regiao))
    return dict({"arquivo": arq, "conferencia": "html.parser"},
                **medir(ref, saida, retirado, antes_pii))


# ---------------------------------------------------------------- conversão


_NIVEL_ORDEM = {"html-convertido": 0, "pdf-extraido": 1, "ocr": 2}

_SECAO_ANEXO = (("Parecer do Comitê de Termo de Compromisso", r"PARECER DO COMIT"),
                ("Declaração de voto", r"(?:DECLARA[ÇC][ÃA]O|MANIFESTA[ÇC][ÃA]O) DE VOTO"),
                ("Voto", r"^\s*VOTO\b"),
                ("Relatório", r"^\s*RELAT[ÓO]RIO\b"),
                ("Manifestação da área técnica", r"MANIFESTA[ÇC][ÃA]O D[AE] [ÁA]REA|"
                                                 r"MEMORANDO|PARECER (?:DA|DO) (?:SEP|SIN|SMI|SRE|"
                                                 r"SNC|SSE|SPS|SOI|SDM|SMI|SGE)"),
                ("Termo de compromisso", r"TERMO DE COMPROMISSO"),
                ("Extrato", r"EXTRATO"))


def secao_do_anexo(rotulo):
    for nome, rx in _SECAO_ANEXO:
        if re.search(rx, rotulo or "", re.I):
            return nome
    return "Texto"


class Conversao:
    """Acumula seções, nível, avisos e conferência de um julgado."""

    def __init__(self, pasta, pm, data=None):
        self.pasta, self.pm, self.data = pasta, pm, data  # data do julgado, para o OCR
        self.secoes, self.avisos, self.conferencias = [], [], []
        self.nivel, self.paginas_ocr, self.linhas_repetidas = "html-convertido", 0, 0
        self._fontes = []  # (arquivo, caminho, motor, região do HTML)
        self.brutos = []  # texto dos PDFs antes de tirar as repetidas (relator, data)
        self.retirado = []  # linhas e trechos de timbre e rodapé retirados
        self.trechos_timbre = 0
        self.imagens_marcadas = 0  # --marcar-imagens

    def _subir(self, nivel):
        if _NIVEL_ORDEM[nivel] > _NIVEL_ORDEM[self.nivel]:
            self.nivel = nivel

    def caminho(self, arq):
        return os.path.join(self.pasta, arq["arquivo"])

    def pdf(self, arq, limpar_repetidas=True):
        paginas, nivel, motor, avisos, n_ocr = texto_pdf(self.caminho(arq), self.pm, self.data)
        self._subir(nivel)
        self.paginas_ocr += n_ocr
        self.imagens_marcadas += sum(p.count(MARCA_IMAGEM) for p in paginas)
        self.avisos += ["%s: %s" % (arq["arquivo"], a) for a in avisos]
        self._fontes.append((arq["arquivo"], self.caminho(arq), motor, None))
        self.brutos.append("\n".join(paginas))
        if limpar_repetidas:
            texto, n = tirar_repetidas(paginas, retirado=self.retirado)
            self.linhas_repetidas += n
        else:
            texto = "\n".join(paginas)
        return self.timbre(texto)

    def timbre(self, texto):
        texto, n = tirar_timbre(texto, self.retirado)
        self.trechos_timbre += n
        return texto

    def html(self, arq, regiao="artigo"):
        with open(self.caminho(arq), "rb") as f:
            dados = f.read()
        self._fontes.append((arq["arquivo"], self.caminho(arq), "html", regiao))
        return jc.decodificar(dados, {"content-type": arq.get("content_type", "")})

    def documento(self, arq, secao_padrao):
        """Seções de um arquivo anexo: PDF segmentado (sem cabeçalho, `secao_padrao`), extrato
        do SEI ou página HTML."""
        if arq["arquivo"].lower().endswith(".pdf"):
            segs = segmentar(self.pdf(arq))
            return [(secao_padrao if s == "Texto" else s, t) for s, t in segs]
        sei = "sei.cvm.gov.br" in arq["url"] or arq["papel"] in ("termo", "sei")
        html = self.html(arq, "sei" if sei else "artigo")
        md = sei_para_md(html) if sei else html_bcb.html_para_md(artigo(html)).strip()
        md = self.timbre(md).strip()
        return [(secao_padrao, md)] if md else []

    def conferir(self, saida, antes_pii=""):
        ret = "\n".join(self.retirado)
        self.conferencias = [conferir(a, c, m, saida, r or "artigo", ret, antes_pii)
                             for a, c, m, r in self._fontes]


def _arquivos(reg, *papeis):
    return [a for a in reg["arquivos"] if a["papel"] in papeis]


def _montar_corpo(titulo, secoes, nivel_secao="##"):
    partes = ["# " + (titulo or "Sem título")]
    for nome, texto in secoes:
        partes.append("%s %s\n\n%s" % (nivel_secao, nome, texto) if texto else
                      "%s %s" % (nivel_secao, nome))
    return "\n\n".join(partes).strip() + "\n"


# Complemento entre COLEGIADO e a data ("COM O SUPERINTENDENTE GERAL", 1979) é aceito: ATA não
# reconhecida faz o texto dela cair junto com a capa.
_ATA = re.compile(r"ATA DA REUNI[ÃA]O(?: [A-ZÇÃÁÉÍÓÚÊÔ]+)? D[OE] COLEGIADO(?: N[º°o]\.?\s*\d+)?"
                  r"(?: [A-ZÇÃÁÉÍÓÚÊÔÀ ]{2,60}?)? DE (\d{1,2})\.(\d{1,2})\.(\d{2,4})")
_PARTICIPANTE = re.compile(r"^[A-ZÀ-Ý][A-ZÀ-Ý .'\-]+\s+[–-]\s+(?:Presidente|Diretora?|"
                           r"Superintendente|Procurador)", re.I)


def _ano4(a):
    a = int(a)
    return a + (1900 if a >= 50 else 2000) if a < 100 else a


def _caixa_alta(linha):
    letras = re.sub(r"[^A-Za-zÀ-ÿ]", "", linha)
    return len(letras) >= 12 and letras.upper() == letras


def decisoes_antigas(texto):
    """[(cabeçalho da ATA, data, [(título da decisão, texto)])] do PDF anual. Antes da primeira
    ATA (endereço, lista de datas) sai. Decisão = título em caixa alta depois dos participantes."""
    atas = list(_ATA.finditer(texto))
    out = []
    for i, m in enumerate(atas):
        fim = atas[i + 1].start() if i + 1 < len(atas) else len(texto)
        data = "%04d-%02d-%02d" % (_ano4(m.group(3)), int(m.group(2)), int(m.group(1)))
        linhas = texto[m.end():fim].splitlines()
        decisoes, titulo, corpo, abertura = [], None, [], []
        participantes = True
        for linha in linhas:
            s = linha.strip()
            if participantes and (not s or s.upper().startswith("PARTICIPANTES")
                                  or _PARTICIPANTE.match(s)):
                abertura.append(s)
                continue
            participantes = False
            if s and _caixa_alta(s) and not _PARTICIPANTE.match(s) and (titulo is None or corpo):
                if titulo is not None:
                    decisoes.append((titulo, _limpar_bloco(corpo)))
                titulo, corpo = s, []
                continue
            if s and _caixa_alta(s) and titulo is not None and not corpo:
                titulo += " " + s  # título em mais de uma linha
                continue
            if titulo is None:
                abertura.append(s)
            else:
                corpo.append(linha)
        if titulo is not None:
            decisoes.append((titulo, _limpar_bloco(corpo)))
        out.append((m.group(0), data, _limpar_bloco(abertura), decisoes))
    return out


_CARGO_RELATOR = re.compile(r"^(?:Presidente|Diretora?)(?:\s+(?:Interin[oa]|Substitut[oa]))?\s+")


# parágrafo depois da decisão: presença, composição da sessão e votos (o vencido não decide)
_FIM_DECISAO = (r"\n\s*\n\s*(?:Após|Presentes?\b|Participaram|Ausentes?\b|[OA] Diretora?\b|"
                r"[OA] President[ea]\b|[^\n]*\bvotou\b)")


def extrato_sei(md):
    """{data, relator, ementa, decisao} do extrato de sessão de julgamento do SEI em markdown."""
    plano = re.sub(r"\*+", "", md)
    d = re.search(r"Data do julgamento:\s*(\d{1,2}/\d{1,2}/\d{4})", plano)
    r = re.search(r"(?m)^\s*Relatora?:\s*(.+?)\s*$", plano)
    e = re.search(r"(?m)^\s*Ementa:\s*(.+?)\s*$", plano)
    dec = re.search(r"(?ms)^\s*Decis[ãa]o:\s*(.+?)(?=%s|\Z)" % _FIM_DECISAO, plano)
    relator = _CARGO_RELATOR.sub("", r.group(1)).strip(" .") if r else ""
    return {"data": jc.data_br(d.group(1)) if d else None,
            "relator": relator if len(relator) <= 80 else "",
            "ementa": re.sub(r"\s+", " ", e.group(1)).strip() if e else "",
            "decisao": dec.group(1) if dec else ""}


def _pas_da_noticia(item, reg, cv, incerteza):
    """PAS fora da listagem (origem `noticia`): `## Extrato` do SEI e as peças dos PDFs da
    notícia; ementa, data, relator e resultado do extrato; fonte original é a notícia."""
    secoes, ext = [], {"data": None, "relator": "", "ementa": "", "decisao": ""}
    for arq in _arquivos(reg, "sei"):
        segs = cv.documento(arq, "Extrato")
        secoes += segs
        ext = extrato_sei("\n".join(t for _, t in segs))
    if not _arquivos(reg, "sei"):
        incerteza.append("sem extrato do SEI")
    pdfs = _arquivos(reg, "pdf")
    for arq in pdfs:
        padrao = secao_do_anexo(arq.get("rotulo"))
        for s, t in segmentar(cv.pdf(arq)):
            s = padrao if s == "Texto" else s
            if secoes and secoes[-1][0] == s:  # capa da peça e a peça: uma seção só
                secoes[-1] = (s, secoes[-1][1] + "\n" + t)
            else:
                secoes.append((s, t))
    if not pdfs:
        incerteza.append("sem PDF das peças; corpo só com o extrato")
    titulo = "PAS CVM nº %s" % item.get("processo", "")
    ementa, fonte_ementa = jc.ementa_sem_partes(ext["ementa"]), "cvm"
    if not ementa:
        texto = "\n".join(t for _, t in secoes)
        m = re.search(r"(?m)^\s*Ementa:\s*(.+(?:\n(?!\s*\n).+)*)", texto)
        ementa = jc.ementa_sem_partes(m.group(1)) if m else ""
    if not ementa:
        ementa, fonte_ementa = "Processo administrativo sancionador. Proc. %s." % \
            item.get("processo", ""), "titulo"
    res = _um(_RES_PAS, ext["decisao"]) if ext["decisao"] else None
    noticia = _arquivos(reg, "noticia")
    fonte = noticia[0] if noticia else reg["arquivos"][0]
    return titulo, ext["data"], ext["relator"], ementa, fonte_ementa, secoes, fonte, res


def ligacoes_crsfn(caminho=LIGACOES_CRSFN):
    """{processo CVM normalizado: [ids de acórdão do CRSFN]} (crsfn.py); sem o arquivo, {}."""
    if not os.path.exists(caminho):
        return {}
    with open(caminho, encoding="utf-8") as f:
        return json.load(f).get("ligacoes") or {}


def fases_pas(caminho=DADOS_ABERTOS_PAS):
    """{NUP só dígitos: (fase atual, data da última movimentação)} dos dados abertos do PAS."""
    if not os.path.exists(caminho):
        return {}
    import csv
    out = {}
    with open(caminho, encoding="latin-1", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            nup_ = re.sub(r"\D", "", row.get("NUP") or "")
            if nup_:
                out[nup_] = ((row.get("Fase_Atual") or "").strip(),
                             (row.get("Data_Ultima_Movimentacao") or "").strip())
    return out


def recurso_crsfn(valores, ligacoes=None, fases=None):
    """Aviso de recurso ao CRSFN para o `incerteza` do PAS: os acórdãos ligados ao processo
    (crsfn-ligacoes.json) ou, sem acórdão, a fase "Recurso CRSFN" dos dados abertos; senão ""."""
    global _LIGACOES_CRSFN, _FASES_PAS
    if ligacoes is None:
        if _LIGACOES_CRSFN is None:
            _LIGACOES_CRSFN = ligacoes_crsfn()
        ligacoes = _LIGACOES_CRSFN
    chaves = jc.processos(valores.get("processo", "")) + [valores.get("nup") or ""]
    ids = []
    for k in chaves:
        for i in ligacoes.get(k, []) if k else []:
            if i not in ids:
                ids.append(i)
    if ids:
        return "recurso ao CRSFN: " + ", ".join(ids)
    if fases is None:
        if _FASES_PAS is None:
            _FASES_PAS = fases_pas()
        fases = _FASES_PAS
    nup_ = re.sub(r"\D", "", valores.get("nup") or jc.nup(valores.get("processo", "")))
    fase, data = fases.get(nup_, ("", "")) if nup_ else ("", "")
    if fase == "Recurso CRSFN":
        return "recurso ao CRSFN em andamento (dados abertos, %s)" % data
    return ""


def converter_item(item, pasta, pm=pdf_macos):
    """(valores do frontmatter, corpo, Conversao) de um julgado já baixado em `pasta`."""
    reg = jb.ler_registro(pasta)
    if not reg or not reg.get("arquivos"):
        raise ValueError("%s: fonte não baixada" % item["id"])
    cv = Conversao(pasta, pm, item.get("data"))
    tipo = item["tipo"]
    principal = reg["arquivos"][0]
    incerteza = list(item.get("incerteza", []))
    titulo, data, relator, ementa, fonte_ementa = "", item.get("data"), item.get("relator", ""), \
        "", "titulo"
    secoes, rito = [], item.get("rito", "")
    res_extrato, ementa_pag = None, ""

    if tipo == "pas" and item.get("origem") == "noticia":
        titulo, d, rel, ementa, fonte_ementa, secoes, fonte, res_extrato = _pas_da_noticia(
            item, reg, cv, incerteza)
        data, relator = d or data, relator or rel
        bruto = "\n".join(cv.brutos)
        relator = relator or relator_do_texto(bruto)
        rito = rito or rito_do_texto(bruto)

    elif tipo == "pas":
        if principal["papel"] == "pagina":
            titulo, d, ementa_pag = pas_da_pagina(cv.html(principal, "pas"))
            data = cv.data = d or data
        else:
            ementa_pag = ""
        pdfs = _arquivos(reg, "pdf", "documento")
        for arq in pdfs:
            secoes += segmentar(cv.pdf(arq))
        texto = "\n".join(t for _, t in secoes)
        bruto = "\n".join(cv.brutos)
        if not relator:
            relator = relator_do_texto(bruto)
        if not data:
            m = re.search(r"Data do julgamento:\s*(\d{1,2}/\d{1,2}/\d{4})", bruto)
            data = jc.data_br(m.group(1)) if m else None
        if not ementa_pag:
            m = re.search(r"(?m)^\s*Ementa:\s*(.+(?:\n(?!\s*\n).+)*)", texto)
            ementa_pag = m.group(1) if m else ""
        ementa, fonte_ementa = jc.ementa_sem_partes(ementa_pag), "cvm"
        cv.retirado.append(ementa_pag)  # nomes das partes que saem da ementa não são falta
        if not ementa:
            ementa, fonte_ementa = jc.ementa_de_titulo(item.get("titulo", "")), "titulo"
        if not pdfs:
            incerteza.append("sem PDF da decisão; corpo só com a ementa da página")
            secoes = [("Texto", ementa_pag)] if ementa_pag else []
        rito = rito or rito_do_texto(bruto)
        fonte = pdfs[0] if pdfs else principal
        titulo = titulo or item.get("processo", "")

    elif tipo == "decisao-antiga":
        texto = cv.pdf(principal, limpar_repetidas=False)
        atas = decisoes_antigas(texto)
        if not atas:
            secoes = segmentar(texto)
            incerteza.append("PDF anual sem ATA reconhecível; texto inteiro")
            corpo_md = _montar_corpo(item.get("titulo"), secoes)
        else:
            partes = ["# " + item.get("titulo", "")]
            for cab, _d, abertura, decs in atas:
                partes.append("## " + cab + ("\n\n" + abertura if abertura else ""))
                for t, c in decs:
                    partes.append("### %s\n\n%s" % (t, c) if c else "### " + t)
            corpo_md = "\n\n".join(partes).strip() + "\n"
            # o PDF anual traz atas de anos anteriores: data da primeira reunião do ano do id
            datas = [d for _, d, _, _ in atas]
            ano = item["id"].split("-")[2][:4]
            data = min([d for d in datas if d[:4] == ano] or datas)
            incerteza.append("decisões separadas por heurística (título em caixa alta), %d ATA(s) "
                             "e %d decisão(ões); data da primeira reunião do ano do arquivo"
                             % (len(atas), sum(len(x[3]) for x in atas)))
        titulo = item.get("titulo", "")
        ementa = jc.ementa_de_titulo(titulo)
        fonte = principal

    elif principal["papel"] == "pagina":  # Colegiado e TC com item do Colegiado
        titulo, d, rel, md = colegiado_da_pagina(cv.html(principal))
        md = cv.timbre(md).strip()
        data, relator = d or data, rel or relator
        cv.data = data
        secoes = [("Decisão", md)] if md else []
        for arq in _arquivos(reg, "anexo"):
            if jc.anexo_alheio(arq.get("rotulo")):
                continue
            nome = secao_do_anexo(arq.get("rotulo"))
            for s, t in cv.documento(arq, nome):
                if s == "Texto" and arq.get("rotulo"):
                    t = "**%s**\n\n%s" % (arq["rotulo"], t)
                secoes.append((s, t))
        for arq in _arquivos(reg, "termo"):
            secoes += cv.documento(arq, "Termo de compromisso")
        titulo = titulo or item.get("titulo", "")
        ementa = jc.ementa_de_titulo(titulo, item.get("classe") or None)
        fonte = principal

    else:  # TC sem item do Colegiado: termo em PDF ou extrato do SEI
        for arq in _arquivos(reg, "documento", "sei", "termo"):
            secoes += cv.documento(arq, "Termo de compromisso")
        titulo = "Termo de compromisso – %s" % item.get("processo", "")
        incerteza.append("título montado (tabela de termos de compromisso)")
        # a data do nome do PDF da CVM nem sempre é a da decisão; vale a da aprovação no texto
        aprov = data_de_aprovacao("\n".join(t for _, t in secoes))
        if aprov and aprov != data:
            data = cv.data = aprov
        ementa = "Termo de compromisso. Proc. %s." % item.get("processo", "")
        fonte = principal

    if tipo != "decisao-antiga":
        corpo_md = _montar_corpo(titulo, secoes)
    antes_pii = corpo_md
    corpo_md, cortes = pii.limpar_contando(corpo_md)
    if not re.search(r"(?m)^## ", corpo_md):
        corpo_md = corpo_md.rstrip("\n") + "\n\n## Texto\n"
        incerteza.append("fonte sem texto extraível")
    cv.pii = cortes
    if cv.linhas_repetidas:
        cv.avisos.append("%d linha(s) de cabeçalho/rodapé retiradas" % cv.linhas_repetidas)
    if cv.trechos_timbre:
        cv.avisos.append("%d trecho(s) de timbre/rodapé da CVM e do SEI retirados" % cv.trechos_timbre)

    normas, disp, aviso = citacoes(corpo_md)
    if aviso:
        cv.avisos.append(aviso)
    if tipo == "decisao-colegiado" or tipo == "termo-compromisso" or tipo == "pas":
        res = resultado(tipo, corpo_md, item)
    else:
        res = ""
    if res_extrato is not None:
        res = res_extrato
    cv.conferir("\n".join([corpo_md, ementa, data or "", relator]), antes_pii)
    baixas = [c for c in cv.conferencias if c["cobertura"] is not None
              and c["cobertura"] < COBERTURA_BAIXA]
    if baixas:
        incerteza.append("cobertura abaixo de %d%% na conferência independente"
                         % int(COBERTURA_BAIXA * 100))
    if cv.paginas_ocr:
        incerteza.append("%d página(s) por OCR" % cv.paginas_ocr)
    if cv.imagens_marcadas:
        incerteza.append("%d imagem(ns) com texto não convertida(s), marcada(s) no texto; ver o PDF oficial"
                         % cv.imagens_marcadas)
    if not data:
        raise ValueError("%s: sem data (página, inventário e PDF)" % item["id"])
    valores = {
        "id": item["id"], "orgao": "cvm", "tipo": tipo, "classe": item.get("classe", ""),
        "processo": item.get("processo", "") or jc.pas_do_titulo(item.get("titulo")),
        "nup": item.get("nup", ""), "rito": rito,
        "data": data, "relator": pii.limpar(relator), "resultado": res,
        "ementa": pii.limpar(ementa), "ementa_fonte": fonte_ementa if ementa else "",
        "tema": "", "tema_fonte": "", "normas_citadas": normas, "dispositivos_citados": disp,
        "fonte_original": fonte["url"], "sha256_fonte": fonte["sha256"],
        "baixado_em": fonte["baixado_em"], "nivel_verificacao": cv.nivel,
        "incerteza": "; ".join(dict.fromkeys(x for x in incerteza if x)),
    }
    if tipo == "pas":
        aviso = recurso_crsfn(valores)
        if aviso:
            valores["incerteza"] = "; ".join(dict.fromkeys(
                [x for x in valores["incerteza"].split("; ") if x] + [aviso]))
    # D3: nome de pessoa física na ementa sai do frontmatter; a publicada fica em ## Ementa
    publicada = re.sub(r"^\s*Ementa\s*:\s*", "", re.sub(r"\s+", " ", ementa_pag), flags=re.I)
    publicada = pii.limpar(publicada).strip()
    valores, corpo_md, _ = je.ementa_sem_pessoas(valores, corpo_md, publicada=publicada)
    return valores, corpo_md, cv


_APROVACAO = re.compile(
    r"aprovad[ao]\s+pelo\s+Colegiado(?:\s+da\s+CVM)?\s+em\s+reuni[ãa]o\s+(?:realizada\s+)?"
    r"(?:de|em)\s+(\d{1,2})[./](\d{1,2})[./](\d{2,4})", re.I)


def data_de_aprovacao(texto):
    """AAAA-MM-DD de "aprovada pelo Colegiado da CVM em reunião de 09/12/2014", ou None."""
    m = _APROVACAO.search(texto or "")
    if not m:
        return None
    d, mes, a = (int(x) for x in m.groups())
    a = a + 2000 if a < 100 else a
    try:
        return datetime.date(a, mes, d).isoformat()
    except ValueError:
        return None


def _preservar_extracao(valores, caminho):
    """Reconversão não apaga a extração (Task 4): ementa e tema extraídos ficam enquanto a fonte
    não trouxer os seus; relator antigo fica se a conversão não achar outro. O resultado já
    gravado, quando não vazio, fica sempre: não tem _fonte, e a extração o grava por cima do da
    conversão (Fase 3b: reconversão trocava "provido" extraído por "indeferido" do conversor)."""
    try:
        antigo, _ = je.ler_julgado(caminho)
    except (OSError, ValueError):
        return valores
    v = dict(valores)
    if antigo.get("ementa_fonte") == "extracao" and v.get("ementa_fonte") in ("titulo", ""):
        v["ementa"], v["ementa_fonte"] = antigo.get("ementa", ""), "extracao"
    if antigo.get("tema_fonte") == "extracao" and not v.get("tema"):
        v["tema"], v["tema_fonte"] = antigo.get("tema", ""), "extracao"
    # ementa extraída: a extração gravou o resultado, também o vazio de suspenso ou sem deliberação
    # Colegiado e termo: o resultado é da extração (também o vazio de julgamento suspenso); a
    # reconversão não o troca. PAS e CRSFN: o já gravado, quando não vazio, fica.
    if (antigo.get("resultado") or antigo.get("ementa_fonte") == "extracao"
            or antigo.get("tipo") in ("decisao-colegiado", "termo-compromisso", "decisao-antiga")):
        v["resultado"] = antigo.get("resultado", "")
    if not v.get("relator") and antigo.get("relator"):
        v["relator"] = antigo["relator"]
    return v


def gravar_julgado(valores, corpo, raiz=jc.RAIZ):
    caminho = jc.caminho_julgado(valores["tipo"], valores["id"], valores["data"][:4], raiz)
    valores = _preservar_extracao(valores, caminho)
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    tmp = caminho + ".parcial"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(jc.sem_controle(jc.frontmatter(valores) + corpo))
    os.replace(tmp, caminho)
    return caminho


def main(argv=None, pm=pdf_macos):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ids", help="ids separados por vírgula")
    ap.add_argument("--ano", type=int)
    ap.add_argument("--tipo", choices=jc.TIPOS)
    ap.add_argument("--onda", type=int, choices=sorted(jc.ONDAS))
    ap.add_argument("--limite", type=int)
    ap.add_argument("--inventario", default=jb.INVENTARIO)
    ap.add_argument("--cache", default=jb.CACHE)
    ap.add_argument("--raiz", default=jc.RAIZ, help="raiz do repositório (saída em plugins/)")
    ap.add_argument("--relatorios", default=RELATORIOS)
    ap.add_argument("--marcar-imagens", action="store_true",
                    help="imagem com texto vira marca, sem OCR (decisão por item)")
    a = ap.parse_args(argv)
    global MARCAR_IMAGENS
    MARCAR_IMAGENS = a.marcar_imagens
    ids = [x.strip() for x in a.ids.split(",") if x.strip()] if a.ids else None
    itens = jc.selecionar(jb.carregar_inventario(a.inventario), ids=ids, ano=a.ano, tipo=a.tipo,
                          onda=a.onda, limite=a.limite)
    relatorio = {"gerado_em": jc.hoje_sp(), "argumentos": vars(a), "itens": []}
    falhas = 0
    for it in itens:
        pasta = jb.pasta_do_item(it, a.cache)
        linha = {"id": it["id"], "tipo": it["tipo"]}
        try:
            valores, corpo, cv = converter_item(it, pasta, pm)
            caminho = gravar_julgado(valores, corpo, a.raiz)
            linha.update({"caminho": os.path.relpath(caminho, a.raiz), "bytes": len(corpo.encode()),
                          "nivel": cv.nivel, "paginas_ocr": cv.paginas_ocr,
                          "secoes": re.findall(r"(?m)^## (.+)$", corpo), "pii": cv.pii,
                          "cobertura": cv.conferencias, "avisos": cv.avisos,
                          "resultado": valores["resultado"], "incerteza": valores["incerteza"]})
            print("%s -> %s (%s)" % (it["id"], linha["caminho"], cv.nivel))
        except Exception as e:  # noqa: BLE001 — um julgado ruim não para o lote
            falhas += 1
            linha["erro"] = "%s: %s" % (type(e).__name__, str(e)[:300])
            print("%s: ERRO %s" % (it["id"], linha["erro"]), file=sys.stderr)
        relatorio["itens"].append(linha)
    os.makedirs(a.relatorios, exist_ok=True)
    nome = "conversao-%s.json" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    with open(os.path.join(a.relatorios, nome), "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("%d convertido(s), %d erro(s); relatório %s" % (len(itens) - falhas, falhas,
                                                         os.path.join(a.relatorios, nome)))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
