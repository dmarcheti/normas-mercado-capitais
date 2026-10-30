#!/usr/bin/env python3
"""Corte de dados pessoais dos julgados (decisão D3 do plano da Fase 2d).

O nome da pessoa fica no texto (é o que a decisão publicada traz); saem CPF, RG, endereço
residencial, e-mail, telefone, data de nascimento, dados bancários, a qualificação pessoal
(nacionalidade, estado civil, profissão) e as linhas de testemunha. Cada corte vira
"[dado pessoal retirado]". CNPJ, nome e cargo ficam.

- limpar(texto) -> texto sem os dados pessoais.
- limpar_contando(texto) -> (texto, {regra: nº de cortes}).
- achar_cpfs(texto) / achar_rgs(texto) -> [(início, fim)] para a varredura antes do commit
  (o que já foi cortado não aparece, porque o marcador não tem dígitos).
"""
import re

MARCADOR = "[dado pessoal retirado]"

# Dígito com ruído de OCR (O no lugar de 0, l/I no lugar de 1), só em contexto rotulado.
_D = r"(?-i:[0-9OoIl])"


def _dv_cpf_ok(d):
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for n in (9, 10):
        s = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (s * 10) % 11 % 10 != int(d[n]):
            return False
    return True


# CPF formatado (pontos/vírgulas e hífen, com espaço solto do OCR); não casa CNPJ (2.3.3/4-2).
_CPF_FMT = re.compile(r"(?<![\w./-])\d{3}\s?[.,]\s?\d{3}\s?[.,]\s?\d{3}\s?[-–]\s?\d{2}(?![\w/])")
# CPF rotulado ("CPF/MF nº", "C.P.F.", "CIC", "inscrito no CPF sob o nº"), número com ruído.
_CPF_ROT = re.compile(
    r"(?:\bCPF|\bC\.\s?P\.\s?F\.?|\bCIC)(?:\s*[/I]\s*M\.?F\.?)?\s*(?:[:\-–]\s*)?"
    r"(?:(?:sob\s+o\s+)?(?:n[º°o'’]\.?|n\.|número)\s*)?[:\s]*"
    r"(" + _D + r"(?:[\s.,\-–/]{0,2}" + _D + r"){7,11}[\s.,\-–/]{0,2}\d)(?![0-9])", re.I)
# CPF só com dígitos: 11 dígitos soltos com dígito verificador válido.
_CPF_PURO = re.compile(r"(?<![\w./-])\d{11}(?![\w/])")


def achar_cpfs(texto):
    """Trechos de CPF no texto: formatado, rotulado (com ruído de OCR) ou 11 dígitos válidos."""
    spans = []
    for m in _CPF_ROT.finditer(texto):
        num = m.group(1)
        dig = re.sub(r"\D", "", num.translate(str.maketrans("OoIl", "0011")))
        if 9 <= len(dig) <= 11 and len(set(dig)) > 1 and not re.search(r"\d{2}\.?\d{3}\.?\d{3}/\d{4}", num):
            spans.append(m.span(1))
    for m in _CPF_FMT.finditer(texto):
        if len(set(re.sub(r"\D", "", m.group(0)))) > 1:
            spans.append(m.span())
    for m in _CPF_PURO.finditer(texto):
        if _dv_cpf_ok(m.group(0)):
            spans.append(m.span())
    return _unir(spans)


# RG: rótulo + número (com dígitos) + órgão expedidor opcional. "RG:" sem número não dispara.
_RG = re.compile(
    r"(?:\bR\.?\s?G\.?(?=[\s:nN])|\b[Cc]arteira\s+de\s+[Ii]dentidade(?:\s+[Pp]rofissional)?|"
    r"\b[Cc][ée]dula\s+de\s+[Ii]dentidade|\bdocumento\s+de\s+identidade)"
    r"(?:\s*/\s*[A-Z]{2,})?\s*(?:[:\-–]\s*)?(?:(?:sob\s+o\s+)?(?:n[º°oO'’]\.?|n\.|número)\s*)?[:\s]*"
    # o número (com ruído de OCR e órgão emissor) vai até a vírgula, o ponto e vírgula, o " e " ou
    # o "inscrito"/"expedida" seguinte; precisa de 4 dígitos para contar
    r"(\d[^,;\n()]{2,38}?(?=\s*(?:[,;)\n]|\s+e(?:\s|$)|\s+inscrit|\s+expedid|\s+emitid|\s+portador|$))"
    r"(?:\s*,?\s*(?:expedid[ao]|emitid[ao])\s+pel[ao]\s+[A-ZÀ-Ýa-z/\-. ]{2,30}?(?=[,;)\n]|\s+e\s|$))?)")


def achar_rgs(texto):
    spans = []
    for m in _RG.finditer(texto):
        if len(re.findall(r"\d", m.group(1))) >= 4:
            spans.append(m.span(1))
    return _unir(spans)


def _unir(spans):
    out = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(b, out[-1][1]))
        else:
            out.append((a, b))
    return out


def _substituir(texto, spans):
    for a, b in reversed(_unir(spans)):
        texto = texto[:a] + MARCADOR + texto[b:]
    return texto


# ---------------------------------------------------------------- endereço

_END_GATILHO = re.compile(
    r"\b(?:residentes?\s+e\s+domiciliad[oa]s?|domiciliad[oa]s?|residentes?|"
    r"com\s+endere[çc]o(?:\s+residencial)?|endere[çc]o\s+residencial)\s*:?\s*"
    r"(?=(?:na|no|nas|nos|em|à|a)\b|:)", re.I)
_ABREV = {"av", "r", "al", "pça", "pç", "praça", "rod", "est", "estr", "cj", "conj", "ap", "apto",
          "apt", "bl", "n", "nº", "s", "sta", "sto", "jd", "jardim", "vl", "pq", "lt", "qd", "sl",
          "cep", "gal", "eng", "prof", "des", "gov", "mal", "pres", "brig", "cel", "ten", "cap",
          "dr", "dra", "sr", "sra", "tv", "trav", "lgo", "sh", "shis", "qi", "ql", "km", "cond",
          "edif", "ed", "res", "loja", "sala", "andar", "nr", "num", "dep", "fl"}
_FIM_END = re.compile(
    r";|\n\s*\n|\)|"
    r",?\s+e\s+(?:o|a|os|as)\s+(?:Sr|Sra|Srs|senhor|senhora)\b|"
    r",\s*(?=(?:portador|inscrit|neste\s+ato|doravante|denominad|aqui\s+representad|"
    r"brasileir|nascid|filh[oa]\s+de|e-?mail|telefone|tel\.|fone|RG\b|R\.G\.|CPF|C\.P\.F|CIC\b|"
    r"carteira|c[ée]dula|documento\s+de\s+identidade|titular|na\s+qualidade|vem|v[êe]m|resolve|"
    r"celebra|firma|apresent|propo|requer|e\s+(?:o|a)\s))", re.I)


def _fim_endereco(texto, ini, maximo=320):
    lim = min(len(texto), ini + maximo)
    pos = ini
    while pos < lim:
        m = _FIM_END.search(texto, pos, lim)
        p = re.compile(r"\.(?=\s+[A-ZÀ-Ý])").search(texto, pos, lim)
        cand = [x for x in (m.start() if m else None, p.start() if p else None) if x is not None]
        if not cand:
            return lim
        fim = min(cand)
        if p and fim == p.start():
            palavra = re.search(r"([A-Za-zÀ-ÿº]+)$", texto[ini:fim])
            if palavra and (palavra.group(1).lower() in _ABREV or len(palavra.group(1)) == 1):
                pos = fim + 1
                continue
        return fim
    return lim


def _enderecos(texto):
    spans = []
    for m in _END_GATILHO.finditer(texto):
        ini = m.end()
        fim = _fim_endereco(texto, ini)
        trecho = texto[ini:fim]
        # endereço de pessoa jurídica ("com sede na") não dispara; aqui só o trecho com algo
        # de endereço (logradouro, número, cidade) é cortado.
        if re.search(r"\d|\b(?:rua|av|avenida|alameda|praça|estrada|rodovia|travessa|cidade|"
                     r"município|bairro|cep|quadra|lote|condomínio|SQS|SQN|SHIS|estado)\b",
                     trecho, re.I):
            spans.append((ini, fim))
    return spans


# ---------------------------------------------------------------- demais regras

_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_EMAIL_INSTITUCIONAL = re.compile(r"^[a-z]+@cvm\.gov\.br$", re.I)
_TEL = re.compile(
    r"(?:\b(?:tel(?:efones?)?|fones?|celular|cel\.|fax|whatsapp)\b\.?\s*(?:n[º°]\.?\s*)?[:.]?\s*)"
    r"((?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?(?:9\s?)?\d{4}[-.\s]?\d{4}"
    r"(?:\s*(?:/|ou|e)\s*(?:\(?\d{2}\)?\s*)?(?:9\s?)?\d{4}[-.\s]?\d{4})*)", re.I)
_TEL_DDD = re.compile(r"(?<![\w/])(?:\+55\s*)?\(\d{2}\)\s*(?:9\s?)?\d{4}[-.\s]?\d{4}(?!\d)")
_DATA = r"(?:\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{2,4}|\d{1,2}º?\s+de\s+[a-zç]+\s+de\s+\d{4})"
_NASC = re.compile(r"\b(?:nascid[oa]s?\s+(?:em|a(?:os?)?|no\s+dia)\s*|data\s+de\s+nascimento\s*[:\-]?\s*)"
                   r"(" + _DATA + ")", re.I)
_BANCO = re.compile(
    r"(?:\b(?:banco|bco\.?)\s+[\wÀ-ÿ.&\s]{2,40}?,?\s*)?"
    r"\bag[êe]ncia\s*(?:n[º°.]?\s*)?[:\s]*\d[\dxX.\-]*\s*(?:,|e|/)?\s*"
    r"(?:d[ao]\s+)?(?:conta(?:[\s-]+corrente)?|c/c|c\.c\.|cc)\s*(?:n[º°.]?\s*)?[:\s]*\d[\dxX.\-]*",
    re.I)
_NACIONALIDADE = (r"(?:brasileir|estrangeir|portugu[êe]s|argentin|american|norte-american|italian|"
                  r"espanhol|franc[êe]s|alem[ãa]|urugua|chilen|paraguai|japon[êe]s|chin[êe]s|"
                  r"ingl[êe]s|britânic|suíç|holand[êe]s|belg|canadense|mexican|colombian|"
                  r"peruan|venezuelan|libanês|naturalizad)[a-zçã]*")
_ESTADO_CIVIL = r"(?:solteir|casad|divorciad|separad|vi[uú]v|desquitad|em\s+uni[ãa]o\s+est[áa]vel|convivente)[a-z]*"
_DOC_SEG = (r"residente|domiciliad|portador|inscrit|com\s+endere|R\.?G\b|CPF|C\.P\.F|carteira|"
            r"c[ée]dula|documento\s+de\s+identidade|neste|doravante|nascid|filh|registrad")
_QUALIF = re.compile(
    r"\b" + _NACIONALIDADE + r"\s*,\s*" + _ESTADO_CIVIL +
    r"(?:\s+(?:sob\s+o\s+regime|em\s+regime|pelo\s+regime)[^,;\n]{0,80})?"
    r"(?:\s*,\s*(?!" + _DOC_SEG + r")[^,;\d]{2,70}?(?=\s*[,;]|\s*$))?", re.I)
# Nacionalidade sem estado civil: só quando o que vem depois é documento ou endereço.
_QUALIF2 = re.compile(
    r"\b" + _NACIONALIDADE + r"(?:\s*,\s*(?!" + _DOC_SEG + r")[^,;\d]{2,70}?)?"
    r"(?=\s*,\s*(?:" + _DOC_SEG + r"))", re.I)
_TESTEMUNHA_ASSIN = re.compile(
    r"(assinad[oa]\s+eletronicamente\s+por\s+)(\**)([^,\n*]{3,90}?)(\**\s*,\s*\**\s*Testemunha)",
    re.I)
_TESTEMUNHAS_CAB = re.compile(r"^\s*\**\s*TESTEMUNHAS?\s*\**\s*:?\s*\**\s*$", re.I | re.M)


def _testemunhas_bloco(texto):
    """Linhas curtas depois de um cabeçalho "TESTEMUNHAS:" (nome, CPF, traço de assinatura)."""
    spans = []
    for m in _TESTEMUNHAS_CAB.finditer(texto):
        pos, ini, fim, vazias, n = m.end(), None, None, 0, 0
        for lm in re.finditer(r"[^\n]*(?:\n|$)", texto[pos:]):
            linha = lm.group(0)
            if not linha:
                break
            s = linha.strip()
            if not s:
                vazias += 1
                if vazias >= 3:
                    break
                continue
            if len(s) > 90 or s.startswith("#") or n >= 10:
                break
            vazias = 0
            n += 1
            a = pos + lm.start() + (len(linha) - len(linha.lstrip()))
            b = pos + lm.start() + len(linha.rstrip())
            ini = a if ini is None else ini
            fim = b
        if ini is not None:
            spans.append((ini, fim))
    return spans


def limpar_contando(texto):
    """Texto sem dados pessoais e a contagem de cortes por regra."""
    texto = texto or ""
    cont = {}

    def aplica(nome, spans):
        nonlocal texto
        spans = [s for s in spans if s[1] > s[0]]
        if spans:
            cont[nome] = cont.get(nome, 0) + len(_unir(spans))
            texto = _substituir(texto, spans)

    aplica("testemunha", [m.span(3) for m in _TESTEMUNHA_ASSIN.finditer(texto)])
    aplica("testemunha", _testemunhas_bloco(texto))
    aplica("email", [m.span() for m in _EMAIL.finditer(texto)
                     if not _EMAIL_INSTITUCIONAL.match(m.group(0))])
    aplica("nascimento", [m.span(1) for m in _NASC.finditer(texto)])
    aplica("cpf", achar_cpfs(texto))
    aplica("rg", achar_rgs(texto))
    aplica("telefone", [m.span(1) for m in _TEL.finditer(texto)] +
           [m.span() for m in _TEL_DDD.finditer(texto)])
    aplica("banco", [m.span() for m in _BANCO.finditer(texto)])
    aplica("endereco", _enderecos(texto))
    aplica("qualificacao", [m.span() for m in _QUALIF.finditer(texto)])
    aplica("qualificacao", [m.span() for m in _QUALIF2.finditer(texto)])
    return texto, cont


def limpar(texto):
    return limpar_contando(texto)[0]
