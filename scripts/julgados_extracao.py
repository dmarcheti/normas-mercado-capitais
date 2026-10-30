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


def montar_lotes(caminhos, pasta, prefixo, tamanho=TAMANHO_LOTE):
    """Grava <pasta>/<prefixo>-NNN/lote.json com até `tamanho` julgados; devolve as pastas."""
    pastas = []
    for i in range(0, len(caminhos), tamanho):
        d = os.path.join(pasta, "%s-%03d" % (prefixo, i // tamanho + 1))
        os.makedirs(d, exist_ok=True)
        lote = [entrada(c) for c in caminhos[i:i + tamanho]]
        with open(os.path.join(d, "lote.json"), "w", encoding="utf-8") as f:
            json.dump(lote, f, ensure_ascii=False, indent=1)
        with open(os.path.join(d, "caminhos.json"), "w", encoding="utf-8") as f:
            json.dump(caminhos[i:i + tamanho], f, ensure_ascii=False, indent=1)
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


def rodar_lote(pasta_lote, modelo, trabalho=None, timeout=900):
    """Roda o modelo numa pasta só com o lote; copia saida.json e grava log e custo."""
    with open(PROMPT, encoding="utf-8") as f:
        prompt = f.read()
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


# ---------------------------------------------------------------- validação

# Marca de entidade: a sequência inteira é nome de empresa, fundo ou escritório (fica).
_ENTIDADE = re.compile(r"\b(S\.?\s?A\.?|Ltda|LTDA|Fundo|FUNDO|FIDC|FII|FIP|Banco|BANCO|Participa[çc]|"
                       r"PARTICIPA[ÇC]|Corretora|CORRETORA|DTVM|CTVM|Distribuidora|DISTRIBUIDORA|"
                       r"Companhia|COMPANHIA|Cia|CIA|Investimentos?|INVESTIMENTOS?|Capital|CAPITAL|"
                       r"Gest[ãa]o|GEST[ÃA]O|Securitizadora|SECURITIZADORA|Holding|Asset|Bolsa|"
                       r"BOLSA|Auditores|AUDITORES|Consultores|Associados|ASSOCIADOS|Advogados|"
                       r"Group|Grupo|GRUPO|Energia|ENERGIA|Seguros|SEGUROS|Agropecu[áa]ria|"
                       r"Empreendimentos|Imobili[áa]ria|Com[ée]rcio|Ind[úu]stria|Servi[çc]os)\b")
# Palavra institucional ou de abertura de frase: corta a sequência (o nome pode vir depois).
_CORTE = re.compile(r"^(Comiss[ãa]o|COMISS[ÃA]O|Valores|VALORES|Mobili[áa]rios|MOBILI[ÁA]RIOS|CVM|"
                    r"Colegiado|COLEGIADO|Superintend[êe]ncia|Instru[çc][ãa]o|Resolu[çc][ãa]o|"
                    r"Delibera[çc][ãa]o|Lei|Termo|TERMO|Compromisso|COMPROMISSO|Processo|PROCESSO|"
                    r"Administrativo|Sancionador|Recurso|RECURSO|Conselho|Minist[ée]rio|Brasil|"
                    r"Rio|Janeiro|S[ãa]o|Paulo|Federal|Nacional|Diretor|Diretora|Presidente|"
                    r"Relator|Relatora|Multa|Proposta|Acusado|Acusada|Acusados|Recorrente|Pedido|"
                    r"Decis[ãa]o|Voto|Parecer|Comit[êe]|Rito|Simplificado|Ordin[áa]rio|PAS|SEP|"
                    r"SIN|SRE|SMI|SNC|SPS|SOI|SFI|SGE|PFE|Absolvi[çc][ãa]o|Condena[çc][ãa]o|"
                    r"Arquivamento|Aceito|Rejeitado|Negado|Provido)$")
_NOME = re.compile(r"\b[A-ZÀ-Ý][A-Za-zÀ-ÿ'’]+(?:\s+(?:d[aeo]s?|e)?\s*[A-ZÀ-Ý][A-Za-zÀ-ÿ'’]+){1,5}")


_LIGACAO = ("da", "de", "do", "das", "dos", "e")


def nomes_do_texto(texto):
    """Sequências de 2+ palavras capitalizadas ou em caixa alta, fora de nome de entidade e
    cortadas nas palavras institucionais (candidatas a nome de pessoa física)."""
    out = set()
    for m in _NOME.finditer(texto):
        s = re.sub(r"\s+", " ", m.group(0)).strip()
        if _ENTIDADE.search(s):
            continue
        run = []
        for t in s.split() + ["CVM"]:
            if _CORTE.match(t):
                while run and run[-1].lower() in _LIGACAO:
                    run.pop()
                if len([p for p in run if p.lower() not in _LIGACAO]) >= 2:
                    out.add(" ".join(run))
                run = []
            elif run or t.lower() not in _LIGACAO:
                run.append(t)
    return out


def tem_nome(ementa, recorte_):
    """A ementa traz duas ou mais palavras capitalizadas seguidas (fora de nome de entidade) que
    também estão no recorte, em qualquer caixa? Então é nome de pessoa: reprova."""
    ref = re.sub(r"\s+", " ", recorte_).lower()
    for nome in nomes_do_texto(ementa):
        t = nome.split()
        for i in range(len(t)):
            for j in range(i + 2, len(t) + 1):
                sub = t[i:j]
                if sub[0].lower() in _LIGACAO or sub[-1].lower() in _LIGACAO:
                    continue
                if re.search(r"(?<!\w)%s(?!\w)" % re.escape(" ".join(sub).lower()), ref):
                    return True
    return False


def validar_saida(lote, saida):
    """(aprovados {id: campos}, erros). Erro de lote (ids faltando ou sobrando) reprova o lote;
    campo inválido sai do item (ementa com nome de pessoa, tema ou resultado fora da lista)."""
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
                erros.append("%s: ementa com mais de %d palavras" % (x["id"], MAX_PALAVRAS_EMENTA))
            elif tem_nome(ementa, x["recorte"]):
                erros.append("%s: ementa com nome de pessoa" % x["id"])
            elif pii.limpar(ementa) != ementa:
                erros.append("%s: ementa com dado pessoal" % x["id"])
            else:
                campos["ementa"] = ementa
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


def aplicar(caminho, campos):
    """Grava no frontmatter os campos extraídos, pelas regras da Task 4; devolve os alterados."""
    v, corpo = ler_julgado(caminho)
    mudou = []
    if ("ementa" in campos and v.get("ementa_fonte") == "titulo"
            and v.get("classe") not in ROTINEIRAS and v.get("tipo") not in SEM_EMENTA_EXTRAIDA):
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
    """Valida saida.json do lote e aplica; grava validacao.json."""
    with open(os.path.join(pasta_lote, "lote.json"), encoding="utf-8") as f:
        lote = json.load(f)
    with open(os.path.join(pasta_lote, "caminhos.json"), encoding="utf-8") as f:
        caminhos = dict(zip([x["id"] for x in lote], json.load(f)))
    try:
        with open(os.path.join(pasta_lote, "saida.json"), encoding="utf-8") as f:
            saida = json.load(f)
    except (OSError, ValueError) as e:
        saida, aprovados, erros = None, {}, ["saida.json ausente ou inválido (%s)" %
                                             type(e).__name__]
    if saida is not None:
        aprovados, erros = validar_saida(lote, saida)
    aplicados = {i: aplicar(caminhos[i], c) for i, c in aprovados.items()}
    rel = {"erros": erros, "aplicados": aplicados}
    with open(os.path.join(pasta_lote, "validacao.json"), "w", encoding="utf-8") as f:
        json.dump(rel, f, ensure_ascii=False, indent=1)
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
    total, falhas = 0.0, 0
    for p in pastas:
        info = rodar_lote(p, a.model, a.trabalho)
        rel = processar_lote(p)
        total += info["total_cost_usd"] or 0
        falhas += bool(rel["erros"]) or info["codigo"] != 0
        print("%s: US$ %s; %d aplicado(s); %d erro(s)" % (
            os.path.basename(p), info["total_cost_usd"],
            sum(1 for v in rel["aplicados"].values() if v), len(rel["erros"])))
    print("custo total: US$ %.4f" % total)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
