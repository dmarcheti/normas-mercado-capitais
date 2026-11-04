"""Conjunto rotulado de 20 casos para medir o revisor LLM (Task 4 da Fase 4) e o placar.

    python3 scripts/revisor_casos.py montar [--conjunto 1|2]
    python3 scripts/revisor_casos.py pontuar --rodada rodada-1 [--conjunto 1|2]

`montar` grava em dados/fase-4/revisor-casos/ (conjunto 1) ou em .../v2/ (conjunto 2), fora do
Git (os defeitos levam dado pessoal sintético), julgados com id anônimo `caso-NN`, em ordem
embaralhada, e `casos.json` com o gabarito. Conjunto 1 (semente 20261104):

- 10 limpos: julgados atuais de tipos variados que a auditoria da 3b conferiu sem erro
  (`fontes/amostra-fase3b*.json` e `dados/fase-3b/comparacao*.json`), sorteados por estrato com a
  semente registrada em `casos.json`; ficam de fora os que trazem, na parte que o revisor vê,
  CPF ou RG achados por `pii`, endereço na qualificação, caractere de lixo ou timbre da CVM;
- 10 com um defeito injetado, cada um numa cópia de outro julgado limpo.

Conjunto 2 (semente 20261105, correção 1 da revisão): 10 limpos SEM esse filtro (só saem os que
`pii` marca com CPF ou RG no arquivo inteiro) e 5 defeitos com variantes que o prompt não traz
como exemplo (CPF só com dígitos, passaporte, celular, nascimento por extenso, ementa contrária
em outra formulação).

Os números de CPF e RG são montados por concatenação a partir de dígitos sorteados: nenhum número
literal no código (o pre-commit barra). `pontuar` lê `<rodada>/resultado.json` e confere cada
caso contra o gabarito. Não roda git.
"""
import argparse
import glob
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import julgados_comum as jc  # noqa: E402
import julgados_extracao as je  # noqa: E402
import pii  # noqa: E402
import revisor as rv  # noqa: E402

PASTA = os.path.join(jc.RAIZ, "dados", "fase-4", "revisor-casos")
SEMENTE = 20261104
MARCA = pii.MARCADOR
TIMBRE = ("MINISTÉRIO DA ECONOMIA - ME\nCOMISSÃO DE VALORES MOBILIÁRIOS - CVM\n"
          "Rua Sete de Setembro, 111 - 32º andar - Bairro Centro - Rio de Janeiro/RJ - "
          "CEP 20050-901 - www.cvm.gov.br")
_TRIAGEM_TIMBRE = re.compile(r"Sete de Setembro|SEI/CVM|Documento assinado|www\.cvm|MINISTÉRIO DA ECONOMIA")
_ENDERECO = re.compile(r"\b(?:Rua|Av\.|Avenida|Alameda|Travessa|Estrada|Rodovia|Praça|apto|apartamento)\b")

# (tipo, nivel_verificacao): dois de Colegiado HTML, dois de Colegiado PDF, dois de PAS PDF, um TC
# em PDF, dois do CRSFN (HTML e PDF) e um OCR (PAS)
LIMPOS = [("decisao-colegiado", "html-convertido"), ("decisao-colegiado", "html-convertido"),
          ("decisao-colegiado", "pdf-extraido"), ("decisao-colegiado", "pdf-extraido"),
          ("pas", "pdf-extraido"), ("pas", "pdf-extraido"),
          ("termo-compromisso", "pdf-extraido"),
          ("acordao-crsfn", "html-convertido"), ("acordao-crsfn", "pdf-extraido"),
          ("pas", "ocr")]

# nome do defeito: (tipo esperado, tipo de julgado, nível de verificação)
DEFEITOS = [
    ("cpf-com-dois-pontos", "dado-pessoal", "pas", "pdf-extraido"),
    ("rg-com-orgao-antes", "dado-pessoal", "termo-compromisso", "pdf-extraido"),
    ("endereco-na-qualificacao", "dado-pessoal", "pas", "pdf-extraido"),
    ("testemunha-no-carimbo", "dado-pessoal", "termo-compromisso", "ocr"),
    ("ementa-contraria", "ementa-contraria", "decisao-colegiado", "pdf-extraido"),
    ("resultado-em-julgamento-suspenso", "resultado-contrario", "decisao-colegiado", "html-convertido"),
    ("corte-de-residentes-no-brasil", "corte-indevido", "termo-compromisso", "pdf-extraido"),
    ("texto-truncado-no-dispositivo", "texto-truncado", "decisao-colegiado", "pdf-extraido"),
    ("timbre-repetido", "lixo-conversao", "acordao-crsfn", "pdf-extraido"),
    ("linha-da-decisao-duplicada", "lixo-conversao", "decisao-colegiado", "html-convertido"),
]
# Conjunto 2 (correção 1 da revisão): defeitos com variantes que o prompt NÃO traz como exemplo
DEFEITOS_2 = [
    ("cpf-so-digitos", "dado-pessoal", "pas", "pdf-extraido"),
    ("passaporte", "dado-pessoal", "termo-compromisso", "pdf-extraido"),
    ("telefone-celular", "dado-pessoal", "pas", "pdf-extraido"),
    ("nascimento-por-extenso", "dado-pessoal", "termo-compromisso", "pdf-extraido"),
    ("ementa-contraria-outra-formulacao", "ementa-contraria", "decisao-colegiado",
     "html-convertido"),
]
# conjunto: (semente, limpos pré-filtrados, defeitos); o conjunto 1 é o da rodada 1 (filtrado)
CONJUNTOS = {1: (SEMENTE, True, DEFEITOS), 2: (20261105, False, DEFEITOS_2)}
EMENTA_NEGATIVA = ("A pretensão da requerente foi rejeitada pelo Colegiado, que manteve "
                   "integralmente a posição da área técnica.")
EMENTA_POSITIVA = ("O Colegiado acolheu a pretensão da requerente e reformou a posição da "
                   "área técnica.")
CORTE_RESIDENTES = "cvm-col-20221108-d2718"  # traz "residentes no Brasil" na parte visível
INVERSO = [("indeferiu", "deferiu"), ("deferiu", "indeferiu"),
           ("negou provimento", "deu provimento"), ("deu provimento", "negou provimento"),
           ("não provido", "provido"), ("nao provido", "provido"),
           ("aceitou", "rejeitou"), ("rejeitou", "aceitou"),
           ("concedeu", "negou"), ("negou", "concedeu"), ("dispensou", "indeferiu a dispensa de")]


# ---------------------------------------------------------------- números sintéticos


def cpf_valido(rng):
    """CPF de dígito verificador válido, por concatenação de dígitos sorteados."""
    d = [rng.randint(1, 9)] + [rng.randint(0, 9) for _ in range(8)]
    for tam in (9, 10):
        soma = sum(x * (tam + 1 - i) for i, x in enumerate(d))
        d.append((soma * 10 % 11) % 10)
    s = "".join(str(x) for x in d)
    return s[:3], s[3:6], s[6:9], s[9:]


def rg_sintetico(rng):
    g = [str(rng.randint(10, 49)), "".join(str(rng.randint(0, 9)) for _ in range(3)),
         "".join(str(rng.randint(0, 9)) for _ in range(3))]
    return "%s.%s.%s-%d" % (g[0], g[1], g[2], rng.randint(0, 9))


# ---------------------------------------------------------------- arquivos


def _partir(caminho):
    with open(caminho, encoding="utf-8") as f:
        texto = f.read()
    m = je._FM.match(texto)
    return texto[:m.end()], texto[m.end():]


def _trocar_campo(fm, campo, valor):
    novo, n = re.subn(r"(?m)^%s:.*$" % campo, lambda _: "%s: %s" % (campo, valor), fm, count=1)
    if n != 1:
        raise ValueError("campo %s ausente" % campo)
    return novo


def _inserir_na_qualificacao(corpo, bloco, depois_de=None):
    """Insere `bloco` (linhas) numa quebra de linha da parte visível da qualificação. Se
    `depois_de` (regex) casar com uma linha das 40 primeiras, entra depois dela; senão, depois da
    linha 20 (no meio de frase, se houver continuação em minúscula)."""
    linhas = corpo.lstrip("\n").splitlines()
    alvo = None
    if depois_de:
        for i, x in enumerate(linhas[:40]):
            if re.search(depois_de, x):
                alvo = i
                break
    if alvo is None:
        alvo = 20
        for i in range(15, min(60, len(linhas) - 1)):
            if linhas[i].strip() and linhas[i + 1][:1].islower():
                alvo = i
                break
    linhas[alvo + 1:alvo + 1] = bloco.splitlines()
    return "\n".join(linhas) + "\n"


def _unidade_regex(unidade):
    return r"\s+".join(re.escape(p) for p in unidade.split())


def _unidade_da_deliberacao(corpo):
    """(início, fim, texto) no corpo da última unidade de deliberação do recorte da 3b."""
    decisao = je._secao(corpo, "Decisão")
    unidades = je._unidades(je.limpar_decisao(decisao))
    escolhidas = je._deliberacao(unidades)
    if not escolhidas:
        raise ValueError("sem deliberação")
    # a unidade com mais palavras entre as escolhidas; o recorte traz todas
    u = max((unidades[i] for i in escolhidas), key=lambda x: len(x.split()))
    m = re.search(_unidade_regex(u), corpo)
    if not m:
        raise ValueError("unidade não achada no corpo")
    return m.start(), m.end(), u


# ---------------------------------------------------------------- defeitos


def injetar(nome, caminho, rng):
    """Devolve (frontmatter, corpo, trecho) do caso com o defeito `nome` injetado no julgado
    `caminho`; `trecho` é o que o revisor deve achar."""
    fm, corpo = _partir(caminho)
    v, _ = je.ler_julgado(caminho)
    if nome == "cpf-com-dois-pontos":
        a, b, c, dv = cpf_valido(rng)
        trecho = "CPF: %s:%s:%s-%s" % (a, b, c, dv)
        linha = "Márcio Albuquerque Teixeira, administrador de carteira, " + trecho + ","
        corpo = _inserir_na_qualificacao(corpo, linha, r"Acusad|Proponente|Interessad")
    elif nome == "rg-com-orgao-antes":
        trecho = "RG SSP/SP " + rg_sintetico(rng)
        corpo = _inserir_na_qualificacao(
            corpo, "Helena Matos Carvalho, portadora do " + trecho + ", sócia da proponente,",
            r"Proponente|Compromiss|Interessad")
    elif nome == "endereco-na-qualificacao":
        trecho = "residente e domiciliado na Rua das Acácias, nº 123, apto 45, Jardim Paulista, São Paulo/SP"
        corpo = _inserir_na_qualificacao(corpo, "Rogério Pimentel Andrade, " + trecho + ",",
                                         r"Acusad|Interessad")
    elif nome == "testemunha-no-carimbo":
        trecho = "Reconheço por semelhança a firma de ROBERTO CAVALCANTI DUARTE, na qualidade de testemunha"
        corpo = corpo.rstrip("\n") + (
            "\n\n1º TABELIONATO DE NOTAS - SÃO PAULO - SP\n" + trecho + ".\n"
            "Em testemunho da verdade.\nSelo digital de autenticidade.\n")
    elif nome == "cpf-so-digitos":
        a, b, c, dv = cpf_valido(rng)
        trecho = "inscrita no cadastro de pessoas físicas sob o número " + a + b + c + dv
        corpo = _inserir_na_qualificacao(corpo, "Fernanda Lima Prado, " + trecho + ",",
                                         r"Acusad|Interessad")
    elif nome == "passaporte":
        trecho = "titular do passaporte nº YA" + "".join(str(rng.randint(0, 9)) for _ in range(7))
        corpo = _inserir_na_qualificacao(corpo, "Daniel Rocha Villar, " + trecho + ",",
                                         r"Proponente|Compromiss|Interessad")
    elif nome == "telefone-celular":
        trecho = "celular (11) 9%d-%d" % (rng.randint(1000, 9999), rng.randint(1000, 9999))
        corpo = _inserir_na_qualificacao(corpo, "Patrícia Nogueira Sá, contato pelo " + trecho + ",",
                                         r"Acusad|Interessad")
    elif nome == "nascimento-por-extenso":
        trecho = "nascido em 14 de março de 1971"
        corpo = _inserir_na_qualificacao(corpo, "Eduardo Bastos Lacerda, " + trecho + ",",
                                         r"Proponente|Compromiss|Interessad")
    elif nome == "ementa-contraria-outra-formulacao":
        trecho = EMENTA_NEGATIVA if v["resultado"] in ("deferido", "provido") else EMENTA_POSITIVA
        fm = _trocar_campo(fm, "ementa", trecho)
    elif nome == "ementa-contraria":
        ementa = v["ementa"]
        trecho = None
        for velho, novo in INVERSO:
            if re.search(r"(?i)\b%s\b" % re.escape(velho), ementa):
                nova = re.sub(r"(?i)\b%s\b" % re.escape(velho), novo, ementa, count=1)
                fm = _trocar_campo(fm, "ementa", nova)
                trecho = nova
                break
        if trecho is None:
            raise ValueError("ementa sem verbo de decisão para inverter")
    elif nome == "resultado-em-julgamento-suspenso":
        fm = _trocar_campo(fm, "resultado", "deferido")
        trecho = "resultado: deferido"
    elif nome == "corte-de-residentes-no-brasil":
        corpo, n = re.subn(r"residentes no Brasil", MARCA, corpo, count=1)
        if n != 1:
            raise ValueError("sem 'residentes no Brasil'")
        trecho = MARCA
    elif nome == "texto-truncado-no-dispositivo":
        ini, fim_, u = _unidade_da_deliberacao(corpo)
        palavras = u.split()
        k = max(8, int(len(palavras) * 0.55))
        ultima = palavras[k - 1]
        cortada = ultima[:max(3, len(ultima) // 2)]
        trecho = " ".join(palavras[max(0, k - 5):k - 1] + [cortada])
        corpo = corpo[:ini] + " ".join(palavras[:k - 1] + [cortada]) + corpo[fim_:]
    elif nome == "timbre-repetido":
        trecho = TIMBRE.splitlines()[1]
        corpo = _inserir_na_qualificacao(corpo, TIMBRE)
        linhas = corpo.rstrip("\n").splitlines()
        pos = max(len(linhas) - 25, len(linhas) // 2)
        for i in range(len(linhas) - 25, len(linhas) - 3):
            if i > 0 and linhas[i].strip() and linhas[i + 1][:1].islower():
                pos = i
                break
        linhas[pos + 1:pos + 1] = TIMBRE.splitlines()
        corpo = "\n".join(linhas) + "\n"
    elif nome == "linha-da-decisao-duplicada":
        ini, fim_, u = _unidade_da_deliberacao(corpo)
        bloco = corpo[ini:fim_]
        corpo = corpo[:fim_] + "\n" + bloco + corpo[fim_:]
        trecho = " ".join(bloco.split())[:160]
    else:
        raise ValueError(nome)
    return fm, corpo, trecho


# ---------------------------------------------------------------- seleção


def _auditados_sem_erro():
    """{id: caminho} dos julgados que a 3b auditou sem erro em nenhuma rodada."""
    amostra = {}
    for f in glob.glob(os.path.join(jc.RAIZ, "fontes", "amostra-fase3b*.json")):
        with open(f, encoding="utf-8") as fh:
            for it in json.load(fh)["itens"]:
                if it.get("arquivo"):
                    amostra[it["id"]] = it["arquivo"]
    erros = {}
    for f in sorted(glob.glob(os.path.join(jc.RAIZ, "dados", "fase-3b", "comparacao*.json"))):
        with open(f, encoding="utf-8") as fh:
            for it in json.load(fh)["itens"]:
                erros.setdefault(it["id"], []).append(bool(it.get("erro")))
    return {i: os.path.join(jc.RAIZ, c) for i, c in amostra.items()
            if i in erros and not any(erros[i]) and os.path.isfile(os.path.join(jc.RAIZ, c))}


def _limpo_na_parte_visivel(caminho):
    it = rv.item_julgado(caminho)
    vis = rv.texto_do_item(it)
    if pii.achar_cpfs(vis) or pii.achar_rgs(vis) or "�" in vis or _TRIAGEM_TIMBRE.search(vis):
        return False
    return not _ENDERECO.search(it["qualificacao"] + "\n" + it["fim"])


def _marcado_com_dado_pessoal(caminho):
    """O próprio acervo (pii) acha CPF ou RG em algum ponto do arquivo."""
    with open(caminho, encoding="utf-8") as f:
        t = f.read()
    return bool(pii.achar_cpfs(t) or pii.achar_rgs(t))


def selecionar(semente=SEMENTE, filtrar=True, defeitos=DEFEITOS):
    """([(tipo, nivel, id, caminho)] dos 10 limpos, [(defeito, id, caminho)] das bases).
    `filtrar`: tira os limpos com sinal de dado pessoal ou timbre na parte que o revisor vê
    (conjunto 1). Sem filtro (conjunto 2), os limpos entram como estão no acervo; só saem os que o
    `pii` marca com CPF ou RG no arquivo inteiro."""
    rng = random.Random(semente)
    pool = {}
    for i, c in sorted(_auditados_sem_erro().items()):
        if not filtrar and _marcado_com_dado_pessoal(c):
            continue
        v, _ = je.ler_julgado(c)
        pool.setdefault((v.get("tipo"), v.get("nivel_verificacao")), []).append((i, c))
    usados = set()
    limpos = []
    for tipo, nivel in LIMPOS:
        cand = [(i, c) for i, c in pool.get((tipo, nivel), []) if i not in usados
                and (not filtrar or _limpo_na_parte_visivel(c))]
        i, c = rng.choice(cand)
        usados.add(i)
        limpos.append((tipo, nivel, i, c))
    bases = []
    for nome, _, tipo, nivel in defeitos:
        if nome == "corte-de-residentes-no-brasil":
            achado = [j["url"] for j in je.julgados() if j["id"] == CORTE_RESIDENTES]
            bases.append((nome, CORTE_RESIDENTES, achado[0]))
            usados.add(CORTE_RESIDENTES)
            continue
        if nome == "resultado-em-julgamento-suspenso":
            cand = []
            for j in je.julgados():
                if j["tipo"] != tipo or j["id"] in usados:
                    continue
                v, corpo = je.ler_julgado(j["url"])
                if (v.get("nivel_verificacao") == nivel and not v.get("resultado")
                        and "suspenso por pedido de vista" in v.get("ementa", "")
                        and je.situacao_deliberacao(je._secao(corpo, "Decisão")) == "suspenso"):
                    cand.append((j["id"], j["url"]))
            i, c = rng.choice(sorted(cand))
            usados.add(i)
            bases.append((nome, i, c))
            continue
        cand = []
        for i, c in pool.get((tipo, nivel), []):
            if i in usados or (filtrar and not _limpo_na_parte_visivel(c)):
                continue
            if nome in ("ementa-contraria", "ementa-contraria-outra-formulacao",
                        "texto-truncado-no-dispositivo", "linha-da-decisao-duplicada"):
                v, corpo = je.ler_julgado(c)
                try:
                    _unidade_da_deliberacao(corpo)
                except ValueError:
                    continue
                if nome == "ementa-contraria-outra-formulacao" and v.get("resultado") not in (
                        "deferido", "indeferido", "provido", "nao-provido"):
                    continue
                if nome == "ementa-contraria" and not (
                        v.get("ementa_fonte") == "extracao" and v.get("resultado") in
                        ("deferido", "indeferido", "provido", "nao-provido")
                        and any(re.search(r"(?i)\b%s\b" % re.escape(a), v["ementa"])
                                for a, _ in INVERSO)):
                    continue
            cand.append((i, c))
        i, c = rng.choice(cand)
        usados.add(i)
        bases.append((nome, i, c))
    return limpos, bases


def montar(conjunto=1, pasta=None):
    semente, filtrar, defeitos = CONJUNTOS[conjunto]
    pasta = pasta or (PASTA if conjunto == 1 else os.path.join(PASTA, "v%d" % conjunto))
    rng = random.Random(semente)
    limpos, bases = selecionar(semente, filtrar, defeitos)
    casos = []
    for tipo, nivel, i, c in limpos:
        casos.append({"origem": i, "rotulo": "limpo", "tipo": tipo, "nivel": nivel,
                      "defeito": "", "esperado": "", "trecho": "", "_fonte": c})
    esperados = {n: e for n, e, _, _ in defeitos}
    for nome, i, c in bases:
        v, _ = je.ler_julgado(c)
        casos.append({"origem": i, "rotulo": "defeito", "tipo": v["tipo"],
                      "nivel": v.get("nivel_verificacao"), "defeito": nome,
                      "esperado": esperados[nome], "trecho": "", "_fonte": c})
    rng.shuffle(casos)
    os.makedirs(pasta, exist_ok=True)
    for f in glob.glob(os.path.join(pasta, "caso-*.md")):
        os.remove(f)
    for n, caso in enumerate(casos, 1):
        cid = "caso-%02d" % n
        fm, corpo = _partir(caso.pop("_fonte"))
        caminho_tmp = os.path.join(pasta, ".origem.md")
        with open(caminho_tmp, "w", encoding="utf-8") as f:
            f.write(fm + corpo)
        if caso["defeito"]:
            fm, corpo, caso["trecho"] = injetar(caso["defeito"], caminho_tmp, rng)
        os.remove(caminho_tmp)
        fm = _trocar_campo(fm, "id", cid)
        caso["caso"] = cid
        caso["arquivo"] = os.path.join(pasta, cid + ".md")
        with open(caso["arquivo"], "w", encoding="utf-8") as f:
            f.write(fm + corpo)
        if caso["defeito"]:
            vis = rv.texto_do_item(rv.item_julgado(caso["arquivo"]))
            alvo = re.sub(r"\s+", " ", caso["trecho"])
            if alvo not in re.sub(r"\s+", " ", vis):
                raise AssertionError("%s: defeito %s não aparece na parte que o revisor vê"
                                     % (cid, caso["defeito"]))
    with open(os.path.join(pasta, "casos.json"), "w", encoding="utf-8") as f:
        json.dump({"semente": semente, "casos": casos}, f, ensure_ascii=False, indent=1)
    return casos


# ---------------------------------------------------------------- placar


def _norm(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _toca(trecho_alerta, trecho_defeito):
    a, d = _norm(trecho_alerta), _norm(trecho_defeito)
    if not a or not d:
        return False
    if a in d or d in a:
        return True
    # sobreposição de pelo menos 25 caracteres
    for i in range(0, max(1, len(d) - 24)):
        if d[i:i + 25] in a:
            return True
    return False


def pontuar(rodada, pasta=PASTA):
    with open(os.path.join(pasta, "casos.json"), encoding="utf-8") as f:
        casos = json.load(f)["casos"]
    with open(os.path.join(pasta, rodada, "resultado.json"), encoding="utf-8") as f:
        res = json.load(f)
    certos, falsos, linhas = 0, 0, []
    for c in casos:
        r = res.get(c["caso"], {"ok": False, "alertas": [{"tipo": "ausente"}]})
        tipos = [a["tipo"] for a in r["alertas"]]
        if c["rotulo"] == "limpo":
            if tipos:
                falsos += 1
            linhas.append((c["caso"], "limpo", c["tipo"] + "/" + c["nivel"],
                           "FALSO ALARME: " + ", ".join(tipos) if tipos else "ok"))
        else:
            tipo_certo = c["esperado"] in tipos
            local = any(a["tipo"] == c["esperado"] and _toca(a.get("trecho"), c["trecho"])
                        for a in r["alertas"])
            certos += tipo_certo
            linhas.append((c["caso"], c["defeito"], c["tipo"] + "/" + c["nivel"],
                           ("ACERTO" if tipo_certo else "PERDEU") + (", trecho certo" if local else
                           ", trecho diferente" if tipo_certo else "")
                           + " (alertas: %s)" % (", ".join(tipos) or "nenhum")))
    return certos, falsos, linhas


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("montar")
    m.add_argument("--conjunto", type=int, default=1, choices=sorted(CONJUNTOS))
    p = sub.add_parser("pontuar")
    p.add_argument("--rodada", required=True)
    p.add_argument("--conjunto", type=int, default=1, choices=sorted(CONJUNTOS))
    a = ap.parse_args(argv)
    if a.cmd == "montar":
        casos = montar(a.conjunto)
        for c in casos:
            print(c["caso"], c["rotulo"], c["defeito"] or "-", c["origem"], c["tipo"], c["nivel"])
        return 0
    pasta = PASTA if a.conjunto == 1 else os.path.join(PASTA, "v%d" % a.conjunto)
    certos, falsos, linhas = pontuar(a.rodada, pasta)
    for l in linhas:
        print(" | ".join(l))
    n_def = sum(1 for l in linhas if l[1] != "limpo")
    print("defeitos marcados com o tipo certo: %d de %d; falsos alarmes: %d de %d limpos"
          % (certos, n_def, falsos, len(linhas) - n_def))
    return 0


if __name__ == "__main__":
    sys.exit(main())
