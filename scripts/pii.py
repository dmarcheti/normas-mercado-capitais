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
_CPF_FMT = re.compile(r"(?<![\w./])(?<!\d[-–])\d{3}\s?[.,]\s?\d{3}\s?[.,]\s?\d{3}\s?[-–]\s?\d{2}(?![\w/])")
# CPF rotulado ("CPF/MF nº", "C.P.F.", "CIC", "inscrito no CPF sob o nº"), número com ruído.
_CPF_ROT = re.compile(
    r"(?:\bCPF|\bC\.\s?P\.\s?F\.?|\bCIC)(?:\s*[/I]?\s*M\.?[FE]\.?)?\s*(?:[:\-–]\s*)?"
    r"(?:(?:sob[\s\-]+o[\s\-]+)?(?:n\.?\s?[º°o'’]\.?|n\.|número)\s*)?[:\s\-–]*"
    r"(" + _D + r"(?:[\s.,\-–/]{0,2}" + _D + r"){7,11}[\s.,\-–/]{0,2}\d)(?![0-9])", re.I)
# CPF só com dígitos: 11 dígitos soltos com dígito verificador válido.
_CPF_PURO = re.compile(r"(?<![\w./-])\d{11}(?![\w/])")


def achar_cpfs(texto):
    """Trechos de CPF no texto: formatado, rotulado (com ruído de OCR) ou 11 dígitos válidos."""
    spans = []
    for m in _CPF_ROT.finditer(texto):
        num = m.group(1)
        dig = re.sub(r"\D", "", num.translate(str.maketrans("OoIl", "0011")))
        if 9 <= len(dig) <= 12 and len(set(dig)) > 1 and not re.search(r"\d{2}\.?\d{3}\.?\d{3}/\d{4}", num):
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
    r"(?:\bR\.?\s?G\.?(?=[\s:nN/])|\b[Ii]dentidade(?=\s*(?:n|:))|\b[Cc]arteira\s+de\s+[Ii]dentidade(?:\s+[Pp]rofissional)?|"
    r"\b[Cc][ée]dula\s+de\s+[Ii]dentidade|\bdocumento\s+de\s+identidade|"
    # "portador da C.I n.º" (carteira de identidade; "C.I." sozinha é comunicação interna)
    r"\bportador[ae]?\s+d[ao]\s+C\.\s?I\b\.?|\bRNE\b|"
    # "TG/SSP/SP n°": RG lido errado pelo OCR, reconhecido pelo órgão emissor
    r"\b[A-Z]G(?=\s*/\s*SSP\b))"
    r"(?:\s+(?:RNE|RG|R\.G\.)(?![\w]))?"
    r"(?:\s*/\s*[A-Z]{2,}){0,3}\s*(?:[:\-–]\s*)?(?:(?:sob\s+o\s+)?(?:[nN]\.?\s?[º°oO'’]\.?|n\.|número)\s*)?[:\s]*"
    # o número (com ruído de OCR e órgão emissor) vai até a vírgula, o ponto e vírgula, o " e " ou
    # o "inscrito"/"expedida" seguinte; precisa de 4 dígitos para contar
    # (vírgula colada em dígito é separador lido errado pelo OCR: "12,345.678-9")
    r"((?:\d|[A-Z]\d|(?:RNE-?)?[A-Z]{1,2}-\d)(?:[^,;\n()]|,(?=\d)){2,38}?(?=\s*(?:,(?!\d)|[;)\n]|\s+e(?:\s|$)|\s+inscrit|\s+expedid|\s+emitid|\s+portador|\s+CPF|\s+Nome|$))"
    r"(?:\s*,?\s*(?:expedid[ao]|emitid[ao])\s+pel[ao]\s+[A-ZÀ-Ýa-z/\-. ]{2,30}?(?=[,;)\n]|\s+e\s|$))?)")


def achar_rgs(texto):
    spans = []
    for m in _RG.finditer(texto):
        # 3 dígitos bastam com rótulo de identidade (número curto emitido por conselho profissional)
        minimo = 3 if re.search(r"dentidade", m.group(0)) else 4
        if len(re.findall(r"\d", m.group(1))) >= minimo:
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

_LOGRADOURO = (r"(?:Rua|R\.|Av\.?|Avenida|Alameda|Al\.|Travessa|Estrada|Largo|Praça|Rodovia)"
               r"(?=\s)")
_END_GATILHO = re.compile(
    r"\b(?:residentes?\s+e\s+domiciliad[oa]s?|domiciliad[oa]s?|residentes?|"
    # o verbo só com logradouro: "reside na Rua A" (e não "a questão reside no fato")
    r"resid(?:e|em|ia|iam)(?=\s+(?:na|no|à)\s+" + _LOGRADOURO + r")|"
    r"com\s+endere[çc]o(?:\s+residencial)?|endere[çc]o\s+residencial|"
    # "O endereço constante da base de dados do SERPRO é a Rua ..." (cadastro citado no voto);
    # "o último endereço informado pelo Sr. Fulano: Rua ..."
    r"endere[çc]o\s+(?:residencial\s+)?(?:constante|cadastrad[oa]|registrad[oa]|informad[oa]|"
    r"conhecid[oa]|atual|indicad[oa])(?:[^.;\n]|\bSra?\.){0,60}?(?:\s(?:é|era|seria)|(?=:))|"
    r"ficha\s+cadastral(?=\s*:\s*[\"“]?\s*" + _LOGRADOURO + r")|"
    # endereço logo depois do CPF ou do RG ("inscrita no CPF sob o nº X, na rua A, 300")
    r"(?:\bCPF|C\.P\.F|\bRG\b|identidade)[^;\n]{0,60}?,(?=\s*(?:na|no|à)\s+" + _LOGRADOURO + r"))"
    r"\s*:?\s*[\"“”]?\s*\(?\s*"
    # "residentes no Brasil", "domiciliados no exterior": lugar genérico, não endereço
    r"(?!(?:n[oa]|em|fora\s+d[oa])\s+(?:Brasil|exterior|pa[ií]s|territ[óo]rio)\b"
    r"(?![,\s]*(?:n[ao]s?|à|em)\s+(?:cidade\b|" + _LOGRADOURO + r")))"
    r"(?=(?:na|no|nas|nos|em|à|a|nest[ae])\b|:|cidade\b|" + _LOGRADOURO + r")", re.I)
# Logradouro com apartamento é endereço de pessoa, mesmo sem gatilho ("Largo A, 96 apto. 18").
_END_APTO = re.compile(r"\b" + _LOGRADOURO + r"[^;\n()]{2,80}?\b(?:apto?|aptº|apartamento)\.?\s*"
                       r"(?:n[º°]\.?\s*)?\d+", re.I)
# CEP logo depois do fim do endereço ("residente na Rua A (Centro), CEP 24000-000") sai junto.
_CEP_RESTO = re.compile(r"\)?\s*[,–-]?\s*CEP\s*:?\s*\d{2}\.?\d{3}-?\d{3}", re.I)
_ABREV = {"av", "r", "al", "pça", "pç", "praça", "rod", "est", "estr", "cj", "conj", "ap", "apto",
          "apt", "bl", "n", "nº", "s", "sta", "sto", "jd", "jardim", "vl", "pq", "lt", "qd", "sl",
          "cep", "gal", "eng", "prof", "des", "gov", "mal", "pres", "brig", "cel", "ten", "cap",
          "dr", "dra", "sr", "sra", "tv", "trav", "lgo", "sh", "shis", "qi", "ql", "km", "cond",
          "edif", "ed", "res", "loja", "sala", "andar", "nr", "num", "dep", "fl", "st"}
_NOME_CAIXA_ALTA = r"(?-i:[A-ZÀ-Ý][A-ZÀ-Ý'\-]+(?:\s+(?:[A-ZÀ-Ý][A-ZÀ-Ý'\-.]*|DA|DE|DO|DOS|DAS|E)){1,8})"
_FIM_END = re.compile(
    # parêntese no meio do endereço ("na Cidade de São Paulo (SP), na Rua A") não encerra
    r";|\n\s*\n|\)(?!\s*,?\s*(?:na|no|em|à)\s+" + _LOGRADOURO + r")|"
    r",?\s+e\s+(?:o|a|os|as)\s+(?:Sr|Sra|Srs|senhor|senhora)\b|"
    # o compromitente seguinte (", e FULANO DE TAL", "CEP 01000-000 e FULANO DE TAL")
    r",?\s+e\s+(?=" + _NOME_CAIXA_ALTA + r"(?![\w]))|"
    # outra parte qualificada logo depois (", FULANO DE TAL, brasileiro")
    r",\s*(?=" + _NOME_CAIXA_ALTA + r"\s*,\s*(?:" + r"brasileir|estrangeir|portador|inscrit|pessoa\s+jur|"
    r"com\s+sede|sociedade|empresa|institui[çc][ãa]o))|"
    # o resto da frase: "tendo em vista a proposta", "doravante", "neste ato", "cujo beneficiário"
    r",?\s+(?=tendo\s+em\s+vista\b|doravante\b|neste\s+ato\b|cuj[oa]s?\b)|"
    r",\s*(?=(?:portador|inscrit|neste\s+ato|doravante|denominad|aqui\s+representad|todos\b|ambos\b|"
    r"pessoa\s+jur|com\s+sede|"
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


_LUGAR_GENERICO = re.compile(r"\s*(?:no|em)\s+(?:exterior|Brasil|pa[íi]s)\b(?!\s*,)", re.I)
_MARCA_EMPRESA = re.compile(r"\bS\.\s?A\.|\bS/A\b|\bLtda\b|\b[Bb]anco\b|\bsede\b|\bPiso\s+[A-ZÀ-Ý]")


def _enderecos(texto):
    spans = []
    for m in _END_GATILHO.finditer(texto):
        ini = m.end()
        fim = _fim_endereco(texto, ini)
        resto = _CEP_RESTO.match(texto, fim)
        if resto:
            fim = resto.end()
        trecho = texto[ini:fim]
        # "entidade domiciliada no exterior cujo ...": lugar genérico, não endereço
        if _LUGAR_GENERICO.match(trecho):
            continue
        # "com endereço na <sede da empresa>" (Piso Itaú Unibanco, S.A., Ltda): endereço comercial fica
        if (re.match(r"com\s+endere[çc]o\s*$", m.group(0).strip(" :\"“”(\t\n"), re.I)
                and _MARCA_EMPRESA.search(trecho)):
            continue
        # endereço de pessoa jurídica ("com sede na") não dispara; aqui só o trecho com algo
        # de endereço (logradouro, número, cidade) é cortado.
        if re.search(r"\d|\b(?:rua|av|avenida|alameda|praça|estrada|rodovia|travessa|cidade|"
                     r"município|bairro|cep|quadra|lote|condomínio|SQS|SQN|SHIS|estado)\b",
                     trecho, re.I):
            spans.append((ini, fim))
    for m in _END_APTO.finditer(texto):
        if re.search(r"\bsede\b", texto[max(0, m.start() - 40):m.start()], re.I):
            continue
        fim = _fim_endereco(texto, m.end())
        resto = _CEP_RESTO.match(texto, fim)
        spans.append((m.start(), resto.end() if resto else fim))
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
# número de passaporte ("passaporte americano nº 034768885"): documento de identidade
_PASSAPORTE = re.compile(r"\bpassaporte(?:\s+[a-zà-ÿ]+){0,2}?\s*(?:n[º°o.]*\s*)?[:\s]*"
                         r"((?-i:[A-Z]{0,3})\s?\d[\dA-Z.\-]{4,14})", re.I)
_NACIONALIDADE = (r"(?:brasileir|estrangeir|portugu[êe]s|argentin|american|norte-american|italian|"
                  r"espanhol|franc[êe]s|alem[ãa]|urugua|chilen|paraguai|japon[êe]s|chin[êe]s|"
                  r"ingl[êe]s|britânic|suíç|holand[êe]s|belg|canadense|mexican|colombian|"
                  r"peruan|venezuelan|libanês|naturalizad)[a-zçã]*")
_ESTADO_CIVIL = r"(?:solteir|casad|divorciad|separad|vi[uú]v|desquitad|em\s+uni[ãa]o\s+est[áa]vel|convivente)[a-z]*"
_DOC_SEG = (r"residente|domiciliad|portador|inscrit|com\s+endere|com\s+escrit|passaporte|"
            r"R\.?G\b|CPF|C\.P\.F|carteira|"
            r"c[ée]dula|documento\s+de\s+identidade|neste|doravante|nascid|filh|registrad")
_QUALIF = re.compile(
    r"\b" + _NACIONALIDADE + r"\s*,\s*" + _ESTADO_CIVIL +
    r"(?:\s+(?:judicialmente|consensualmente|de\s+fato))?"
    r"(?:\s+(?:sob\s+(?:o\s+)?regime|em\s+regime|pelo\s+regime)[^,;]{0,80})?"
    r"(?:\s*,\s*(?!\s*(?:" + _DOC_SEG + r"))[^,;\d]{2,70}?(?=\s*[,;]|\s*$))?", re.I)
# Nacionalidade sem estado civil: só quando o que vem depois é documento ou endereço.
_QUALIF2 = re.compile(
    r"\b" + _NACIONALIDADE + r"(?:\s*,\s*(?!\s*(?:" + _DOC_SEG + r"))[^,;\d]{2,70}?){0,2}"
    r"(?=\s*,\s*(?:" + _DOC_SEG + r")|\s+com\s+escrit)", re.I)
_TESTEMUNHA_ASSIN = re.compile(
    r"(assinad[oa]\s+eletronicamente\s+por\s+)(\**)([^,\n*]{3,90}?)(\**\s*,\s*\**\s*Testemunha)",
    re.I)
# cabeçalho sozinho na linha, ou com resto curto depois dos dois-pontos ("Testemunhas: Fulano")
_TESTEMUNHAS_CAB = re.compile(
    r"^\s*\**\s*TESTEMUNHAS?\s*\**\s*(?::\s*\**\s*(?P<resto>[^\n]{0,40}?)|\**)\s*$", re.I | re.M)
# cabeçalho no meio da linha, depois de ruído de OCR do carimbo ("PRIMEIRO Testemunhas:"): só
# quando "Nome:" ou "CPF:" vem logo depois (bloco de assinatura, não "provar com testemunhas:")
_TESTEMUNHAS_CAB_MEIO = re.compile(
    r"^[^\n]{1,40}?\bTESTEMUNHAS\s*:\s*(?P<resto>[^\n]{0,40}?)\s*$", re.I | re.M)
_ASSIN_CAMPO = re.compile(r"\b(?:Nome|CPF)\s*:")


def _testemunhas_cabecalhos(texto):
    cabs = list(_TESTEMUNHAS_CAB.finditer(texto))
    cabs += [m for m in _TESTEMUNHAS_CAB_MEIO.finditer(texto)
             if _ASSIN_CAMPO.search(texto, m.end(), m.end() + 200)]
    return cabs


# carimbo de cartório e campos de assinatura: ficam no bloco (trazem nome de testemunha e signatário)
_CARIMBO = re.compile(
    r"cart[óo]ri|tabeli|reconhe[çc]|semelhan[çc]|dou\s*f[ée]|verdade|escreven|selo|emol|firma|"
    r"notar|autentic|consulte|fundos|total\s*:?\s*r\$|\b(?:nome|cpf|rg)\b|_{3,}", re.I)
# linha com cara de nome: só letras (ou o marcador), começa em maiúscula, até 8 palavras
_LINHA_NOME = re.compile(r"^(?:\[dado pessoal retirado\]|[A-ZÀ-Ý][^\d,;:()]*)$")


def _linha_do_bloco(s, seguintes):
    """Linha que continua o bloco de testemunhas: nome, campo de assinatura ou carimbo; ruído
    de OCR só quando um carimbo vem nas 3 linhas seguintes (tabela ou lista retomada depois
    do bloco, ou fala de depoimento, encerram o bloco)."""
    if _CARIMBO.search(s):
        return True
    if _LINHA_NOME.match(s) and len(s.split()) <= 8:
        return True
    return any(_CARIMBO.search(x) for x in seguintes[:3])


def _testemunhas_bloco(texto):
    """Linhas curtas depois de um cabeçalho "TESTEMUNHAS:" (nome, CPF, traço de assinatura).

    Cabeçalho no singular com texto na mesma linha ("Testemunha: Fulano") é rótulo de fala em
    depoimento: sai só o resto da linha, sem estender o bloco."""
    spans = []
    for m in _testemunhas_cabecalhos(texto):
        pos, ini, fim, vazias, n = m.end(), None, None, 0, 0
        if m.group("resto"):
            ini, fim = m.span("resto")
            if not re.search(r"TESTEMUNHAS", m.group(0), re.I):
                spans.append((ini, fim))
                continue
        linhas = list(re.finditer(r"[^\n]*(?:\n|$)", texto[pos:pos + 4000]))
        for i, lm in enumerate(linhas):
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
            seguintes = [x.group(0).strip() for x in linhas[i + 1:i + 8] if x.group(0).strip()]
            if not _linha_do_bloco(s, seguintes):
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


# Bloco de assinatura sem o cabeçalho "Testemunhas" (perdido pelo OCR): linha que começa com
# "Nome:" ("NOme FULANA" sem os dois-pontos, quando o nome em maiúsculas vem logo depois) e tem
# CPF, RG ou C.I. nas 3 linhas seguintes.
_ASSIN_NOME_INICIO = re.compile(r"^\s*\**\s*N(?:ome|Ome|OME|óme)\b(?P<dp>\s*:|(?=\s+[A-ZÀ-Ý]{2,}))")
_ASSIN_NOME = re.compile(r"\bN(?:ome|Ome|OME|óme)\s*:")
_ASSIN_FIM_NOME = re.compile(r"\bN(?:ome|Ome|OME|óme)\s*:|\bCPF\b|\bR\.?G\b|\bC\.\s?I\.")
_ASSIN_DOC = re.compile(r"\bCPF\b|\bR\.?\s?G\b|\bC\.\s?I\.|/\s*SSP\b")
# nome em uma ou duas colunas, só palavras em maiúsculas ("FULANO DE TAL BELTRANO F. DA SILVA")
_ASSIN_LINHA_MAIUSC = re.compile(r"^[A-ZÀ-Ý][A-ZÀ-Ý'\-.]*(?:\s+[A-ZÀ-Ý][A-ZÀ-Ý'\-.]*)+$")
# profissão isolada depois da qualificação já cortada ("[dado pessoal retirado], CONTADOR")
_ASSIN_PROFISSAO = re.compile(re.escape(MARCADOR) + r"\s*,\s*[A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+){0,2}\s*$")
# na linha do CPF: residência ("Res. N/ Capital") e registro em conselho ("CRC/RS 12.345")
_ASSIN_RESIDENCIA = re.compile(r"\bRes\.\s*[^\n]*?(?=\s*[-–]?\s*\bCPF\b|\s*$)")
_ASSIN_CONSELHO = re.compile(
    r"\b(?:CRC|OAB|CRM|CREA|CRA|CRO|CRECI|CORECON|CRF|CRP|CRMV)[A-Z]{0,4}\s*(?:[/\-]\s*[A-Z]{2})?"
    r"\s*(?:n[º°o]\.?\s*)?[:\s]*\d[\d.\-/]*")


def _assinatura_bloco(texto):
    """Nome, profissão, residência e registro em conselho no bloco de assinatura sem cabeçalho."""
    linhas, pos = [], 0
    for l in texto.split("\n"):
        linhas.append((pos, l))
        pos += len(l) + 1
    spans = []
    for i, (a, linha) in enumerate(linhas):
        ini = _ASSIN_NOME_INICIO.match(linha)
        if not ini:
            continue
        seguintes = [(b, l) for b, l in linhas[i + 1:i + 12] if l.strip()][:4]
        # o documento vem num campo curto do bloco (não em parágrafo ou tabela de cadastro)
        if not any(_ASSIN_DOC.search(l) and len(l.strip()) <= 90 for _, l in seguintes[:3]):
            continue
        # sem os dois-pontos ("NOme FULANA"), só se a linha seguinte for outro campo do bloco
        if ":" not in ini.group("dp") and not (
                _ASSIN_NOME_INICIO.match(seguintes[0][1]) or _ASSIN_DOC.search(seguintes[0][1])):
            continue
        # nome depois de cada "Nome:" da linha
        rotulos = [ini] + [m for m in _ASSIN_NOME.finditer(linha)
                                                       if m.start() > 0 and linha[:m.start()].strip()]
        com_nome = False
        for r in rotulos:
            fim = _ASSIN_FIM_NOME.search(linha, r.end())
            ini_n, fim_n = r.end(), fim.start() if fim else len(linha)
            trecho = linha[ini_n:fim_n]
            nome = trecho.strip(" \t*,;.-–")
            # até 2 dígitos: ruído de OCR no nome ("Fulana A. de 1", "2ILMA" por "ZILMA")
            if (nome and nome != MARCADOR and len(re.findall(r"[A-Za-zÀ-ÿ]", nome)) >= 3
                    and len(re.findall(r"\d", nome)) <= 2):
                desl = trecho.index(nome)
                spans.append((a + ini_n + desl, a + ini_n + desl + len(nome)))
                com_nome = True
        # "Nome: Nome:" com os nomes em maiúsculas na linha seguinte
        if not com_nome and seguintes:
            b, l = seguintes[0]
            s = l.strip()
            if _ASSIN_LINHA_MAIUSC.match(s) and not _ASSIN_DOC.search(s):
                spans.append((b + l.index(s), b + l.index(s) + len(s)))
        for b, l in seguintes:
            if len(l.strip()) > 90 or l.lstrip().startswith("#"):
                break
            m = _ASSIN_PROFISSAO.search(l)
            if m:
                spans.append((b + m.start(), b + m.start() + len(m.group(0).rstrip())))
            if re.search(r"\bCPF\b", l):
                spans += [(b + m.start(), b + m.end()) for m in _ASSIN_RESIDENCIA.finditer(l)
                          if m.group(0).strip() != "Res."]
                spans += [(b + m.start(), b + m.end()) for m in _ASSIN_CONSELHO.finditer(l)]
    return spans


# Nome de testemunha ou signatário cortado no bloco de assinatura: as outras ocorrências no
# documento (carimbo do cartório, com quebra de linha e caixa diferente) saem também. Só nomes de
# 2 ou mais palavras; no bloco "Testemunhas:" só o nome depois de "Nome:" (linha solta do bloco
# pode ser o signatário da CVM ou o próprio timbre).
_NOME_NO_BLOCO = re.compile(r"\bN(?:ome|Ome|OME|óme)\s*:?[ \t]*(?P<nome>[^\n]*?)"
                            r"(?=\s*(?:\bN(?:ome|Ome|OME|óme)\b|\bCPF\b|\bR\.?G\b|\bC\.\s?I\.|$))",
                            re.M)
_PALAVRA_DE_NOME = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'.\-]*")


def _nome_de_pessoa(trecho):
    """Nome limpo (2 palavras ou mais, só letras) ou None."""
    nome = re.sub(r"\s+", " ", trecho.strip(" \t\n*,;.-–"))
    palavras = nome.split()
    if (MARCADOR in nome or not palavras or len(palavras) > 8
            or not all(_PALAVRA_DE_NOME.fullmatch(p) for p in palavras)
            or sum(len(p) >= 3 for p in palavras) < 2):
        return None
    return nome


# A outra ocorrência só sai perto de carimbo, assinatura ou documento de identidade: no bloco
# digitalizado o "Nome:" também traz o compromitente, que é parte e fica no texto corrido.
_CONTEXTO_DE_FIRMA = re.compile(r"reconhe[cç]|\bfirmas?\b|testem|\bnome\s*:|\bR\.?\s?G\b|\bCPF\b"
                                r"|assinad|tabeli|cart[óo]rio", re.I)
_JANELA_DE_FIRMA = 150


def _outras_ocorrencias(texto, nomes):
    spans = []
    for nome in sorted(set(nomes), key=len, reverse=True):
        rx = re.compile(r"(?<![\wÀ-ÿ])" + r"\s+".join(re.escape(p) for p in nome.split())
                        + r"(?![\wÀ-ÿ])", re.I)
        spans += [m.span() for m in rx.finditer(texto)
                  if _CONTEXTO_DE_FIRMA.search(texto, max(0, m.start() - _JANELA_DE_FIRMA),
                                               m.start())]
    return spans


def limpar_contando(texto):
    """Texto sem dados pessoais e a contagem de cortes por regra."""
    texto = texto or ""
    cont = {}

    nomes = []

    def aplica(nome, spans, guardar=None):
        nonlocal texto
        spans = [s for s in spans if s[1] > s[0]]
        if guardar:
            nomes.extend(n for n in (_nome_de_pessoa(x) for a, b in spans
                                     for x in guardar(texto[a:b])) if n)
        if spans:
            cont[nome] = cont.get(nome, 0) + len(_unir(spans))
            texto = _substituir(texto, spans)

    aplica("testemunha", [m.span(3) for m in _TESTEMUNHA_ASSIN.finditer(texto)], lambda t: [t])
    aplica("testemunha", _testemunhas_bloco(texto),
           lambda t: [m.group("nome") for m in _NOME_NO_BLOCO.finditer(t)])
    aplica("email", [m.span() for m in _EMAIL.finditer(texto)
                     if not _EMAIL_INSTITUCIONAL.match(m.group(0))])
    aplica("nascimento", [m.span(1) for m in _NASC.finditer(texto)])
    aplica("cpf", achar_cpfs(texto))
    aplica("rg", achar_rgs(texto))
    aplica("passaporte", [m.span(1) for m in _PASSAPORTE.finditer(texto)])
    aplica("telefone", [m.span(1) for m in _TEL.finditer(texto)] +
           [m.span() for m in _TEL_DDD.finditer(texto)])
    aplica("banco", [m.span() for m in _BANCO.finditer(texto)])
    aplica("endereco", _enderecos(texto))
    aplica("qualificacao", [m.span() for m in _QUALIF.finditer(texto)])
    aplica("qualificacao", [m.span() for m in _QUALIF2.finditer(texto)])
    # por último: a profissão isolada só aparece depois do corte da qualificação
    aplica("assinatura", _assinatura_bloco(texto), lambda t: [t])
    aplica("testemunha", _outras_ocorrencias(texto, nomes))
    return texto, cont


def limpar(texto):
    return limpar_contando(texto)[0]
