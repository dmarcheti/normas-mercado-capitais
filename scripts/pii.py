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
import unicodedata

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
    # ":" entre os grupos: "CPF: 008: 350..." lido pelo OCR no bloco de assinatura
    r"(" + _D + r"(?:[\s.,:\-–/]{0,2}" + _D + r"){7,11}[\s.,:\-–/]{0,2}\d)(?![0-9])", re.I)
# CPF só com dígitos: 11 dígitos soltos com dígito verificador válido.
_CPF_PURO = re.compile(r"(?<![\w./-])\d{11}(?![\w/])")


_CPF_LINHA = re.compile(r"(?m)^[ \t]*CPF\s*:[ \t]*(\S[^\n]{2,40}?)[ \t]*$")


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
    # linha "CPF:" do bloco de assinatura lida pelo OCR com ruído ("CPF: 11 /0· 11'1. -l)o"):
    # o valor sai se tem dígitos e nenhuma palavra
    for m in _CPF_LINHA.finditer(texto):
        v = m.group(1)
        if len(re.findall(r"\d", v)) >= 3 and not re.search(r"[A-Za-zÀ-ÿ]{3,}", v):
            spans.append(m.span(1))
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
    # "carteira de identidade expedida pelo IFP sob o nº X"
    r"(?:\s+(?:expedid[ao]|emitid[ao])\s+pel[ao]\s+[A-Z][A-Z/\-.]{1,14}(?=\s+sob\b|\s*n))?"
    r"(?:\s*/\s*[A-Z]{2,}){0,3}\s*(?:[:\-–]\s*)?(?:(?:sob\s+o\s+)?(?:[nN]\.?\s?[º°oO'’]\.?|n\.|número)\s*)?[:\s]*"
    # o número (com ruído de OCR e órgão emissor) vai até a vírgula, o ponto e vírgula, o " e " ou
    # o "inscrito"/"expedida" seguinte; precisa de 4 dígitos para contar
    # (vírgula colada em dígito é separador lido errado pelo OCR: "12,345.678-9")
    r"((?:\d|[A-Z]\d|(?:RNE-?)?[A-Z]{1,2}-\s?\d)(?:[^,;\n()]|,(?=\d)){2,38}?(?=\s*(?:,(?!\d)|[;)\n]|\s+e(?:\s|$)|\s+inscrit|\s+expedid|\s+emitid|\s+portador|\s+CPF|\s+Nome|$))"
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
            # ponto solto do OCR no meio do logradouro ("Rua Professor Lourenço. Menicucci, 111")
            if re.match(r"\.\s+[A-ZÀ-Ý][\wÀ-ÿ]+,\s*\d", texto[fim:fim + 40]):
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
                  r"peruan|venezuelan|libanês|naturalizad|norueg|suec|dinamarqu|finland|"
                  r"austr[ií]ac|russ|polon|h[úu]ngar|tchec|grec|israelense|sul-african|angolan|"
                  r"moçambican|indian|coreano|australian|irland|luxemburgu|cubano|equatorian|"
                  r"bolivian|panamenh|guatemaltec|dominican|estadunidense)[a-zçãêé]*")
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
# Frase do fecho das decisões do Colegiado sobre termo de compromisso: "Na qualidade de
# testemunhas, assinaram Fulano de Tal e Beltrana Exemplo" (singular, "como testemunhas," e a
# ordem "assinaram, na qualidade de testemunhas, ..."). Saem só os nomes, e só quando a lista
# vai até o fim da frase: "Como testemunhas, assinaram os conselheiros Fulano (...) e Beltrano"
# narra o fato do processo (as testemunhas do contrato são partes) e fica.
# Palavra do nome: maiúscula inicial (o itálico quebrado do HTML põe "*" depois dela: "J*osé")
# ou inicial com ponto.
_FRASE_PAL = r"[A-ZÀ-Ý](?:\*{1,2}(?=[a-zà-ÿ]))?(?:[A-Za-zÀ-ÿ'’\-]+|\.)?"
_FRASE_NOME = (_FRASE_PAL + r"(?:[ \t]+(?:(?:d[aeo]s?|del|di|van|von)[ \t]+)?" + _FRASE_PAL + r")*")
_FRASE_TESTEMUNHAS = re.compile(
    r"(?:(?i:na\s+qualidade\s+de\s+testemunhas?)[\s*_]*,?|(?i:como\s+testemunhas?)[\s*_]*,)"
    r"[\s*_]*(?i:assinaram|assinou)[\s*_]+"
    r"|(?i:assinaram|assinou)[\s*_]*,[\s*_]*(?i:na\s+qualidade\s+de|como)\s+(?i:testemunhas?)"
    r"[\s*_]*,[\s*_]+")
_FRASE_LISTA = re.compile(_FRASE_NOME + r"(?:(?:[ \t]*,[ \t]*|[ \t]+e[ \t]+)" + _FRASE_NOME + r")*"
                          r"(?=[ \t*_]*(?:[.;]|\n|$))")


def _testemunhas_frase(texto):
    """Nomes da frase "Na qualidade de testemunhas, assinaram X e Y", um trecho por nome."""
    spans = []
    for g in _FRASE_TESTEMUNHAS.finditer(texto):
        lista = _FRASE_LISTA.match(texto, g.end())
        if lista:
            spans += [m.span() for m in re.finditer(_FRASE_NOME, texto[:lista.end()])
                      if m.start() >= lista.start()]
    return spans


# Testemunha ou informante nomeado no texto corrido de um julgado ("a oitiva da testemunha Fulano
# de Tal", "as testemunhas A B e C D", "testemunha de defesa A B"): sai só o nome, fica o papel
# ("a testemunha [dado pessoal retirado]"). Decisão D2 da Fase 5: a testemunha não é sujeito da
# decisão. O gatilho é a palavra testemunha ou informante; "depoente" e "declarante" não entram,
# porque nos julgados o depoente ou declarante é, muitas vezes, parte (acusado, recorrente).
# Ficam fora, de propósito, o nome ANTES do gatilho ("A e B voltaram a subscrever, como
# testemunhas, o Aditivo": partes e conselheiros), a vírgula depois de "como testemunhas"
# ("Como testemunhas, A e B assinaram") e qualquer nome sem o gatilho colado.
_TM_SP = r"(?:[ \t]+|[ \t]*\n[ \t]*)"
_TM_PAL = r"(?:[A-ZÀ-Ý][a-zà-ÿ'’\-]+|[A-ZÀ-Ý]{2,}(?:['’\-][A-ZÀ-Ý]+)*|[A-ZÀ-Ý]\.)"
_TM_CONN = r"(?:d[aeo]s?|del|di|van|von)"
_TM_NOME = _TM_PAL + r"(?:" + _TM_SP + r"(?:" + _TM_CONN + _TM_SP + r")?" + _TM_PAL + r")+"
_TM_TITULO = r"(?:(?:Srs?|Sras?|Drs?|Dras?)\.?" + _TM_SP + r")?"
_TM_FILLER = (r"(?:" + _TM_SP + r"(?:d[aeo]s?" + _TM_SP + r"(?:defesa|acusa[çc][ãa]o)|defesa|acusa[çc][ãa]o|"
              r"arrolad[ao]s?|listad[ao]s?|ouvid[ao]s?|[úu]nic[ao]|"
              r"por" + _TM_SP + r"(?:ele|ela|eles|elas)" + _TM_SP + r"arrolad[ao]s?))*")
_TM_A = re.compile(r"\b(?P<g>[Tt]estemunhas?|[Ii]nformantes?)\b" + _TM_FILLER +
                   r"(?P<sep>[ \t]*[,:][ \t]*|" + _TM_SP + r"|[ \t]*\([ \t]*)" +
                   _TM_TITULO + r"(?P<nome>" + _TM_NOME + r")")
_TM_SP0 = r"[ \t]*(?:\n[ \t]*)?"  # espaço opcional, com uma quebra de linha simples (hard-wrap)
_TM_ITEM = re.compile(r"(?:[ \t]*," + _TM_SP0 + r"(?:e" + _TM_SP + r")?|" + _TM_SP + r"e" + _TM_SP + r")"
                      + _TM_TITULO + r"(?P<nome>" + _TM_NOME + r")")
# nome seguido de aposto e do próximo nome: "A B, ex-funcionária da Alfa, e C D"
_TM_APOSTO = re.compile(r"[ \t]*," + _TM_SP0 + r"[a-zà-ÿ](?:[^,.;()\n]|\n(?!\s*\n)){0,60}," + _TM_SP0 + r"e" + _TM_SP + _TM_TITULO +
                        r"(?P<nome>" + _TM_NOME + r")")
_TM_ANTES = re.compile(r"(?:\bcomo|\b(?:qualidade|condi[çc][ãa]o)\s+de)\s+$", re.I)
_TM_ATO = r"(?i:oitiva|inquiri[çc][ãa]o|intima[çc][ãa]o|depoimento)s?"
_TM_QUALID = r"(?i:na" + _TM_SP + r"(?:qualidade|condi[çc][ãa]o)" + _TM_SP + r"de|como)"
# "a oitiva de A B, na qualidade de testemunha", "documentos enviados por A B, na qualidade de
# testemunha": preposição + um nome + vírgula + o papel no singular (plural, sem preposição:
# "A e B, como testemunhas" é o caso dos conselheiros que subscrevem, e fica)
_TM_B = re.compile(r"\b(?i:d[eao]s?|por|pel[ao]s?)" + _TM_SP + _TM_TITULO + r"(?P<nome>" + _TM_NOME +
                   r")(?=(?:[ \t]*\([^()\n]{0,60}\))?[ \t]*,[ \t]*(?i:est[ea])?[ \t]*" + _TM_QUALID + _TM_SP + r"(?i:testemunha)\b)")
# "prova oral trazida por A B, testemunha dos Reclamantes"
_TM_E = re.compile(r"\b(?i:d[eao]s?|por|pel[ao]s?)" + _TM_SP + _TM_TITULO + r"(?P<nome>" + _TM_NOME +
                   r")(?=[ \t]*,[ \t]*(?i:testemunha)" + _TM_SP + r"(?i:d[aeo]s?)" + _TM_SP + r")")
# "requereu a oitiva, na condição de testemunhas, de A B, C D e E F"
_TM_C = re.compile(r"\b" + _TM_ATO + r"[^.;\n]{0,15}?,[ \t]*" + _TM_QUALID + _TM_SP +
                   r"(?i:testemunhas?),[ \t]*(?i:d[eao]s?)" + _TM_SP + _TM_TITULO +
                   r"(?P<nome>" + _TM_NOME + r")")
# "como testemunha de tal fato o seu agente, Sr. A B": o título depois da vírgula marca o nome
_TM_D = re.compile(r"\b[Tt]estemunhas?\b(?:[^.;()\n]|\n(?!\s*\n)){0,90}?,[ \t]*(?:Srs?|Sras?|Drs?|Dras?)\.[ \t]*"
                   r"(?P<nome>" + _TM_NOME + r")")
# "as oitivas de A B e C D, para demonstrar": plural e lista de nomes (no singular, "oitiva de A B"
# costuma ser a de um acusado, e não entra)
_TM_F = re.compile(r"\b[Oo]itivas" + _TM_SP + r"d[eao]s?" + _TM_SP + _TM_TITULO + r"(?P<nome>" + _TM_NOME + r")")
# primeira palavra que não é nome de pessoa (cargo, órgão, peça, parte do processo)
_TM_NAO_NOME = re.compile(
    r"(?:diretor|diretora|diretores|diretoras|presidente|relator|relatora|conselheir[oa]s?|"
    r"superintendente|superintend[êe]ncia|procurador|procuradora|procuradoria|acusa[çc][ãa]o|acusad[oa]s?|"
    r"defesa|colegiado|comiss[ãa]o|comit[êe]|cvm|minist[ée]rio|banco|companhia|sociedade|fundo|"
    r"autarquia|[áa]rea|ger[êe]ncia|tribunal|juiz|ju[íi]zo|termo|autos|processo|delibera[çc][ãa]o|"
    r"instru[çc][ãa]o|resolu[çc][ãa]o|parecer|of[íi]cio|lei|c[óo]digo|justi[çc]a|pol[íi]cia|"
    r"recorrentes?|requerentes?|compromitentes?|investigad[oa]s?|advogad[oa]s?|estado|uni[ãa]o|"
    r"grupo|ceo|cfo|s\.a|ltda)$", re.I)
_TM_EMPRESA = re.compile(r"\b(?:S\.\s?A|S/A|Ltda)\b")


_TM_CONECTORES = {"de", "da", "do", "das", "dos", "del", "di", "van", "von"}


def _tm_nome_ok(m):
    """m: match com o grupo 'nome'. Olha 6 caracteres além do nome para pegar 'S.A.' cortado em 'S.'."""
    nome = m.group("nome")
    primeira = re.split(r"\s+", nome.strip())[0].rstrip(".")
    if all(re.fullmatch(r"[A-ZÀ-Ý]\.", t) for t in re.split(r"\s+", nome.strip()) if t.lower() not in _TM_CONECTORES):
        return False  # só iniciais ("A. F. G."): a fonte já abreviou, não há o que cortar
    return (not _TM_NAO_NOME.match(primeira)
            and not _TM_EMPRESA.search(nome + m.string[m.end("nome"):m.end("nome") + 6]))


# O HTML/PDF às vezes quebra parágrafo no meio do nome ("Ana Maria" / linha em branco / "Souza de
# Lima"). A continuação só conta se tiver um conector (de/da/do...), para não pegar o começo de um
# parágrafo novo ("Assim, ...").
_TM_CONTINUA = re.compile(r"[ \t]*\n[ \t]*\n[ \t]*(?:" + _TM_PAL + _TM_SP + r")?" + _TM_CONN + _TM_SP + _TM_PAL +
                          r"(?![\wÀ-ÿ])")


def _tm_estende(texto, spans):
    out = []
    for a, b in spans:
        c = _TM_CONTINUA.match(texto, b)
        out.append((a, c.end()) if c else (a, b))
    return out


def _tm_chave(nome):
    """Nome sem acento, caixa e espaço extra, para comparar grafias do mesmo nome."""
    sem = unicodedata.normalize("NFD", nome)
    return " ".join("".join(c for c in sem if not unicodedata.combining(c)).lower().split())


# Administrador ou dirigente de empresa ou entidade citado nessa função (CEO, presidente, diretor,
# conselheiro, gerente, superintendente...) fica, mesmo ouvido como testemunha: como os servidores no
# exercício da função, o nome é do cargo. Vale para o julgado inteiro: se qualquer ocorrência do nome
# vem com o papel, nenhuma sai (nem pelo gatilho, nem pela repetição, nem pela lista). Funcionário,
# operador, corretor, geólogo, arquiteto, perito e "ex-funcionária" não são dirigentes e continuam saindo.
_TM_CARGO = (r"(?i:\b(?:ex[- ]?)?(?:ceo|cfo|presidentes?|diretor(?:es|a|as)?|conselheir[oa]s?|chairman|"
             r"gerentes?|superintendentes?)\b)")
_TM_QUAL = (r"(?:" + _TM_SP + r"(?:(?i:d[aeo]s?" + _TM_SP + r"[a-zà-ÿ]+)|(?i:d[aeo]s?|e|financeir[oa]|geral|"
            r"presidente|administrativ[oa]|executiv[oa]|conselho|administra[çc][ãa]o|diretoria)|"
            r"(?-i:[A-ZÀ-Ý][\wÀ-ÿ&.\-]*)|-[A-Za-zÀ-ÿ]+)|[ \t]*-[ \t]*[A-Za-zÀ-ÿ]+){0,6}")
_TM_PAPEL_ANTES = re.compile(_TM_CARGO + _TM_QUAL + r"[ \t]*,?" + _TM_SP0 +
                             r"(?:Sr[as]?\.?" + _TM_SP + r")?(?P<nome>" + _TM_NOME + r")")
_TM_PAPEL_DEPOIS = re.compile(r"(?P<nome>" + _TM_NOME + r")[ \t]*," + _TM_SP0 +
                              r"(?:(?i:o|a|ex|atual|ent[ãa]o|seu|sua)" + _TM_SP + r"){0,2}" + _TM_CARGO)


def _tm_toks(nome):
    return [t for t in _tm_chave(nome.replace("*", "")).split() if t not in _TM_CONECTORES]


def _tm_mesmo_nome(a, b):
    """Mesma pessoa: uma sequência de palavras (2 ou mais) é o começo ou o fim da outra."""
    a, b = (a, b) if len(a) <= len(b) else (b, a)
    return len(a) >= 2 and (b[:len(a)] == a or b[-len(a):] == a)


def _executivos(texto):
    """Nomes (listas de palavras sem acento nem caixa) que aparecem com papel de dirigente."""
    out = []
    for rx in (_TM_PAPEL_ANTES, _TM_PAPEL_DEPOIS):
        out += [_tm_toks(m.group("nome")) for m in rx.finditer(texto)]
    return out


def _tm_sem_executivos(texto, spans, execs):
    if not execs:
        return spans
    return [(a, b) for a, b in spans
            if not any(_tm_mesmo_nome(_tm_toks(texto[a:b]), e) for e in execs)]


def _testemunhas_corrido(texto, execs=None):
    """Nomes de testemunha/informante no texto corrido, um trecho por nome (só o nome)."""
    spans = []
    for m in _TM_A.finditer(texto):
        if _TM_ANTES.search(texto[max(0, m.start() - 30):m.start()]):
            continue  # "como testemunhas, A e B assinaram" / "tinham como testemunha A": ato das
            #           partes (assinatura de contrato), narra o fato; as partes ficam
        if not _tm_nome_ok(m):
            continue
        spans.append(m.span("nome"))
        if m.group("g").lower().endswith("s"):  # lista: só no plural
            pos = m.end()
            while True:
                n = _TM_ITEM.match(texto, pos) or _TM_APOSTO.match(texto, pos)
                if not n or not _tm_nome_ok(n):
                    break
                spans.append(n.span("nome"))
                pos = n.end()
    for rx in (_TM_B, _TM_D, _TM_E):
        spans += [m.span("nome") for m in rx.finditer(texto) if _tm_nome_ok(m)]
    for m in _TM_C.finditer(texto):
        if not _tm_nome_ok(m):
            continue
        spans.append(m.span("nome"))
        pos = m.end()
        while True:
            n = _TM_ITEM.match(texto, pos)
            if not n or not _tm_nome_ok(n):
                break
            spans.append(n.span("nome"))
            pos = n.end()
    grupos = []
    for m in _TM_F.finditer(texto):
        if not _tm_nome_ok(m):
            continue
        itens, pos = [], m.end()
        while True:
            n = _TM_ITEM.match(texto, pos)
            if not n or not _tm_nome_ok(n):
                break
            itens.append(n.span("nome"))
            pos = n.end()
        if itens:  # só lista de nomes: "oitiva de A B" (singular) costuma ser de parte
            grupos.append(([m.span("nome")] + itens, texto[pos:pos + 200]))
    # "as oitivas de A e B, haja vista que ambos são também acusados": quem o próprio julgado
    # chama de acusado fica, em qualquer ponto do texto em que apareça numa lista de oitivas
    acusados = set()
    for sp, resto in grupos:
        if re.search(r"\bacusad[oa]s?\b", re.split(r"\.(?:\s|$)", resto)[0], re.I):
            acusados.update(_tm_chave(texto[a:b]) for a, b in sp)
    for sp, _ in grupos:
        if not any(_tm_chave(texto[a:b]) in acusados for a, b in sp):
            spans += sp
    if execs is None:
        execs = _executivos(texto)
    return _unir(_tm_estende(texto, _tm_sem_executivos(texto, spans, execs)))


# O mesmo nome, por extenso, em outro ponto do mesmo julgado ("o pedido de depoimento de A B",
# "A B afirmou"): sai também, sem exigir carimbo. Só o nome completo (as mesmas palavras, qualquer
# espaço ou quebra entre elas, sem distinguir caixa), e não quando uma palavra com inicial
# maiúscula na mesma linha o prolonga ("A B Santos" é outra pessoa).
def _testemunhas_repetidas(texto, nomes, execs=None):
    spans = []
    todos = set(nomes)
    for nome in nomes:  # "A B C de D" também aparece como "A B C" (sobrenome final omitido)
        t = nome.split()
        if len(t) >= 5 and t[-2].lower() in _TM_CONECTORES:
            todos.add(" ".join(t[:-2]))
    for nome in sorted(todos, key=len, reverse=True):
        palavras = nome.split()
        # nome de 3 palavras ou mais: um sobrenome a mais ("A B C D" para "A B C") é a mesma pessoa
        extra = (r"(?:[ \t]+(?-i:[A-ZÀ-Ý][a-zà-ÿ]+))?"
                 if len([w for w in palavras if w.lower() not in _TM_CONECTORES]) >= 3 else "")
        rx = re.compile(r"(?<![\wÀ-ÿ])" + r"\s+".join(map(re.escape, palavras)) + extra
                        + r"(?![\wÀ-ÿ])(?!(?-i:[ \t]+(?:d[aeo]s?[ \t]+)?[A-ZÀ-Ý]))", re.I)
        spans += [m.span() for m in rx.finditer(texto)]
    if execs is None:
        execs = _executivos(texto)
    return _tm_sem_executivos(texto, spans, execs)


# Enumeração contígua de nomes (vírgulas e "e", sem verbo entre os membros) em que ao menos um
# membro já foi cortado como testemunha: "Compareceram [m], [m] e A B. Este último substituiu...",
# "oitivas de [m] e A B, para demonstrar". Os outros nomes da enumeração saem também. Roda depois
# das regras de testemunha e antes de qualquer outra, quando todo marcador do texto é de testemunha.
_TM_MARC = re.escape(MARCADOR)
_TM_MEMBRO = r"(?:" + _TM_TITULO + _TM_NOME + r"|" + _TM_MARC + r")"
_TM_SEP = r"(?:[ \t]*," + _TM_SP0 + r"(?:e" + _TM_SP + r")?|" + _TM_SP + r"e" + _TM_SP + r")"
_TM_RUN = re.compile(_TM_MEMBRO + r"(?:" + _TM_SEP + _TM_MEMBRO + r")+")
_TM_SO_NOME = re.compile(_TM_TITULO + r"(?P<nome>" + _TM_NOME + r")")


def _tm_pessoa(nome):
    """Membro de enumeração só sai se parecer pessoa: sem sigla ("CEO da HRT", "Grupo EBX")."""
    toks = [t for t in nome.split() if t.lower() not in _TM_CONECTORES]
    if all(t.isupper() for t in toks):
        return True  # nome todo em caixa alta
    return not any(len(t.rstrip(".")) >= 2 and t.isupper() for t in toks)


def _testemunhas_listas(texto, execs=None):
    spans = []
    for run in _TM_RUN.finditer(texto):
        if MARCADOR not in run.group(0):
            continue
        for m in _TM_SO_NOME.finditer(texto, run.start(), run.end()):
            if _tm_nome_ok(m) and _tm_pessoa(m.group("nome")):
                spans.append(m.span("nome"))
    if execs is None:
        execs = _executivos(texto)
    return _tm_sem_executivos(texto, spans, execs)


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
# título de anexo ("Anexo 1", "ANEXO I"): o documento seguinte começa, o bloco acaba
_TITULO_ANEXO = re.compile(r"^\**\s*(?:ANEXO|Anexo)\s+(?:\d+|[IVXL]+)\b")


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
            if len(s) > 90 or s.startswith("#") or n >= 10 or _TITULO_ANEXO.match(s):
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
# Depois do nome, só o carimbo conta: "inscrito no CPF" depois do nome é a qualificação da parte.
_CARIMBO_DEPOIS = re.compile(r"reconhe[cç]|\bfirmas?\b|tabeli|cart[óo]rio", re.I)


_SEM_ACENTO = {"a": "aáàâã", "e": "eéê", "i": "ií", "o": "oóôõ", "u": "uúü", "c": "cç"}


def _letra_sem_acento(ch):
    base = ch.lower().translate(str.maketrans("áàâãéêíóôõúüç", "aaaaeeiooouuc"))
    return "[%s]" % _SEM_ACENTO[base] if base in _SEM_ACENTO else re.escape(ch)


def _outras_ocorrencias(texto, nomes):
    """Outras ocorrências do nome da testemunha (sem distinguir acento: "João" e "JOAO" no
    carimbo), quando há contexto de carimbo/assinatura antes ou logo depois do nome."""
    spans = []
    for nome in sorted(set(nomes), key=len, reverse=True):
        partes = nome.split()
        rx = re.compile(r"(?<![\wÀ-ÿ])" + r"\s+".join("".join(_letra_sem_acento(c) for c in p)
                                                     for p in partes)
                        + r"(?![\wÀ-ÿ])", re.I)
        if any(len(p.strip(".")) == 1 for p in partes) and len(partes) >= 3:
            # nome abreviado no bloco ("João P. M Figueiredo"): no carimbo vem por extenso
            # ("JOAO PEDRO MARTINS DO COUTO DE FIGUEIREDO"); primeiro e último nome iguais
            prim, ult = ("".join(_letra_sem_acento(c) for c in x) for x in (partes[0], partes[-1]))
            rx = re.compile(r"(?<![\wÀ-ÿ])%s(?:\s+[\wÀ-ÿ.]+){1,6}?\s+%s(?![\wÀ-ÿ])"
                            % (prim, ult), re.I)
        spans += [m.span() for m in rx.finditer(texto)
                  if _CONTEXTO_DE_FIRMA.search(texto, max(0, m.start() - _JANELA_DE_FIRMA),
                                               m.start())
                  or _CARIMBO_DEPOIS.search(texto, m.end(), m.end() + 40)]
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
    aplica("testemunha", _testemunhas_frase(texto), lambda t: [t.replace("*", "")])
    aplica("testemunha", _testemunhas_bloco(texto),
           lambda t: [m.group("nome") for m in _NOME_NO_BLOCO.finditer(t)])
    execs = _executivos(texto)
    antes = len(nomes)
    aplica("testemunha", _testemunhas_corrido(texto, execs), lambda t: [t.replace("*", "")])
    aplica("testemunha", _testemunhas_repetidas(texto, nomes[antes:], execs))
    antes = len(nomes)
    aplica("testemunha", _testemunhas_listas(texto, execs), lambda t: [t.replace("*", "")])
    aplica("testemunha", _testemunhas_repetidas(texto, nomes[antes:], execs))
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
