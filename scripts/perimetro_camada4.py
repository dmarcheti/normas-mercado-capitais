#!/usr/bin/env python3
"""Perímetro da camada 4 (CMN e BCB): regra por assunto sobre fontes/acervo-bcb.json, sem LLM.

Entra a norma vigente cujo assunto (ementa do BCB) toca mercado de capitais, fundos, securitização,
instrumentos de captação e crédito negociáveis, registro e depósito de ativos e recebíveis,
infraestrutura de liquidação, investidores institucionais (RPPS, EFPC, seguradoras), investidor
não residente, contabilidade de instrumentos financeiros e as instituições do mercado (DTVM,
corretoras, SCD e SEP). Sai o que é de política monetária, câmbio comercial, crédito rural e
programas de governo, meio circulante, pagamentos de varejo, cooperativas e consórcios, leiaute de
documento e prudencial puro (capital, liquidez).

Norma só alteradora ("Altera a Resolução nº X...") não vira arquivo: o texto compilado do BCB
já traz a alteração na norma alterada. Ela fica no índice como verbete da norma que altera.

Uso: python3 scripts/perimetro_camada4.py [--acervo fontes/acervo-bcb.json]
     [--saida fontes/perimetro-camada4.json] [--mostrar entra|fora|alteradora]
"""
import argparse
import json
import re
import sys
import unicodedata
from collections import Counter

ENTRA = [
    ("mercado de capitais", r"mercados? (financeiro e )?de capitais|valores mobiliarios"),
    ("fundos", r"fundos? de investimento|direitos creditorios|fundos? de aplicacao|fiagro|fundo imobiliario"),
    ("securitizacao e cessao", r"securitiza|certificados? de recebiveis|cessao de (creditos?|direitos)|"
                               r"aquisicao de creditos|\bcri\b|\bcra\b"),
    ("instrumentos", r"letras? financeiras?|letras? de credito (imobiliario|do agronegocio)|"
                     r"letras? imobiliarias? garantidas?|cedulas? de credito bancario|"
                     r"certificados? de deposito bancario|debentures?|notas? comerciais?|duplicatas?|"
                     r"operacoes estruturadas|\bcoe\b|depositos? a prazo com garantia especial|"
                     r"letras? de cambio|titulos? de credito|compromissadas?|derivativ|swap|"
                     r"letras? de credito do desenvolvimento|\blcd\b"),
    ("registro e deposito", r"registro (e (o )?deposito centralizado )?de (ativos financeiros|recebiveis|"
                            r"operacoes|gravames)|deposito centralizado|gravames?|onus|"
                            r"ativos financeiros|entidades? registradoras?|recebiveis"),
    ("infraestrutura", r"camaras?|compensacao e (de )?liquidacao|infraestruturas? do mercado|"
                       r"contraparte central|central depositaria"),
    ("investidores institucionais", r"regimes? proprios? de previdencia|previdencia complementar|"
                                    r"reservas tecnicas|recursos garantidores|seguradoras|"
                                    r"resseguradores|capitalizacao"),
    ("investidor nao residente", r"nao residente|capital estrangeiro|investimento estrangeiro"),
    ("contabil instrumentos", r"instrumentos financeiros|contabilidade de hedge|perdas? esperadas?|"
                              r"provisao para (perdas|creditos)|classificacao (de risco )?das operacoes de credito"),
    ("instituicoes do mercado", r"distribuidoras? de titulos|corretoras? de (titulos|valores)|"
                                r"sociedades? de credito direto|sociedades? de emprestimo entre pessoas|"
                                r"bancos? de investimento|custodia|agentes? fiduciari|"
                                r"administracao de carteiras|plataformas? eletronicas"),
]
FORA = [
    ("rural e programas", r"credito rural|proagro|pronaf|pronamp|programa de garantia da atividade|"
                          r"funcafe|manual de credito rural|\bmcr\b|safra|agricultura familiar"),
    ("cambio comercial", r"operacoes de cambio|mercado de cambio(?! .*capitais)|exportacao|importacao"),
    ("monetario", r"recolhimento compulsorio|encaixe|redesconto|meio circulante|cedulas e moedas|"
                  r"numerario|taxa selic"),
    ("pagamentos de varejo", r"\bpix\b|arranjos? de pagamento(?!.*recebiveis)|cartao de credito(?!.*recebiveis)|"
                             r"instituicoes? de pagamento"),
    ("cooperativas e consorcios", r"cooperativas? de credito|consorcios?|administradoras? de consorcio"),
    ("leiaute e documentos", r"leiaute|instrucoes de preenchimento|documento \d{4}|\bscr\b|cadastro de"),
    ("prudencial", r"patrimonio de referencia|basileia|requerimento minimo de capital|indice de liquidez|"
                   r"rwa|parcela .* ativos ponderados|limite de exposicao por cliente"),
]
# Revisão das ementas (Fase 2c, 2026-10-29): exceções à regra, com o motivo. (tipo, número) -> (decisão, motivo)
_FORA_REVISADO = "revisão da ementa: %s"
REVISAO = {
    **{("resolucao-cmn", n): ("fora", _FORA_REVISADO % "crédito rural ou programa de governo")
       for n in (2813, 3440, 3468, 3507, 3523, 3571, 4847)},
    **{("resolucao-cmn", n): ("fora", _FORA_REVISADO % "operação do BCB com bancos centrais")
       for n in (2939, 4202, 5211)},
    ("resolucao-cmn", 1020): ("fora", _FORA_REVISADO % "Sistema Financeiro da Habitação"),
    ("resolucao-cmn", 1764): ("fora", _FORA_REVISADO % "agente fiduciário de empréstimo hipotecário (DL 70)"),
    ("resolucao-cmn", 3516): ("fora", _FORA_REVISADO % "tarifa de liquidação antecipada de crédito"),
    ("circular", 3290): ("fora", _FORA_REVISADO % "registro de cheques"),
    ("carta-circular", 3260): ("fora", _FORA_REVISADO % "registro de cheques"),
    ("circular", 1846): ("fora", _FORA_REVISADO % "câmbio de exportação"),
    ("instrucao-normativa-bcb", 377): ("fora", _FORA_REVISADO % "Open Finance de seguros"),
    ("instrucao-normativa-bcb", 380): ("fora", _FORA_REVISADO % "contas de embaixadas e organismos"),
    ("resolucao-bcb", 273): ("fora", _FORA_REVISADO % "grupo de trabalho interno do BCB"),
    ("carta-circular", 3934): ("entra", "revisão da ementa: registro de recebíveis de arranjo de pagamento"),
    ("circular", 4036): ("entra", "revisão da ementa: escrituração de CCB"),
    ("resolucao-bcb", 122): ("entra", "revisão da ementa: depósito de Letra Financeira"),
    ("resolucao-bcb", 168): ("entra", "revisão da ementa: critérios contábeis de corretoras e distribuidoras"),
    ("resolucao-bcb", 264): ("entra", "revisão da ementa: registro de recebíveis"),
    ("resolucao-bcb", 352): ("entra", "revisão da ementa: contábil de instrumentos financeiros"),
    ("resolucao-bcb", 472): ("entra", "revisão da ementa: entidades registradoras de recebíveis"),
    ("resolucao-bcb", 525): ("entra", "revisão da ementa: operações compromissadas"),
    ("resolucao-cmn", 4948): ("entra", "revisão da ementa: derivativos no exterior"),
    **{("resolucao-cmn", n): ("entra", "revisão da ementa: Letra de Crédito do Agronegócio")
       for n in (4415, 5160, 5210)},
}
ALTERA = re.compile(r"^(altera|revoga|da nova redacao|acrescenta|inclui|prorroga|ajusta|modifica|"
                    r"esclarece acerca|divulga)\b")


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def classificar(n):
    a = sem_acento(n["assunto"])
    temas = [t for t, p in ENTRA if re.search(p, a)]
    fora = [t for t, p in FORA if re.search(p, a)]
    if ALTERA.match(a) and not re.match(r"^(esclarece|divulga)", a):
        alvo = re.findall(r"(resolucao|circular|carta circular|instrucao normativa bcb|resolucao bcb|"
                          r"resolucao cmn)(?: conjunta)? n[ºo°]?\.? ?([\d.]+)", a)
        return "alteradora", temas, fora, [" ".join(x) for x in alvo]
    if temas and not fora:
        return "entra", temas, fora, []
    if temas and fora:
        return "revisar", temas, fora, []
    return "fora", temas, fora, []


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--acervo", default="fontes/acervo-bcb.json")
    ap.add_argument("--saida", default="fontes/perimetro-camada4.json")
    ap.add_argument("--mostrar")
    args = ap.parse_args(argv[1:])
    with open(args.acervo, encoding="utf-8") as f:
        acervo = json.load(f)
    out = []
    for n in acervo["normas"]:
        if n["situacao"] != "vigente":
            continue
        dec, temas, fora, alvo = classificar(n)
        motivo = "regra: " + (", ".join(temas) if dec in ("entra", "revisar") else
                              ", ".join(fora) or "assunto fora do perímetro") if dec != "alteradora" else "só alteradora"
        if (n["tipo"], n["numero"]) in REVISAO:
            dec, motivo = REVISAO[(n["tipo"], n["numero"])]
        elif dec == "revisar":
            dec, motivo = "fora", "revisão da ementa: tema de fora predomina (%s)" % ", ".join(fora)
        out.append({"tipo": n["tipo"], "numero": n["numero"], "data": n["data"], "assunto": n["assunto"],
                    "decisao": dec, "motivo": motivo, "temas": temas, "exclusao": fora, "altera": alvo,
                    "palavras": n.get("palavras", 0), "formato": n.get("formato")})
    with open(args.saida, "w", encoding="utf-8") as f:  # uma norma por linha; a ementa está em acervo-bcb.json
        f.write("[\n" + ",\n".join(json.dumps({k: v for k, v in o.items() if k != "assunto"}, ensure_ascii=False)
                                   for o in out) + "\n]\n")
    c = Counter((o["tipo"], o["decisao"]) for o in out)
    for (t, d), k in sorted(c.items()):
        print("%-26s %-11s %4d" % (t, d, k))
    for d in ("entra", "revisar", "alteradora", "fora"):
        xs = [o for o in out if o["decisao"] == d]
        print("%-11s %4d normas, %8d palavras" % (d, len(xs), sum(o["palavras"] for o in xs)))
    print(Counter(t for o in out if o["decisao"] == "entra" for t in o["temas"]).most_common())
    if args.mostrar:
        for o in out:
            if o["decisao"] == args.mostrar:
                print("%s %s %s | %s | %s" % (o["tipo"], o["numero"], o["data"], ",".join(o["temas"] + o["exclusao"]),
                                              o["assunto"][:150]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
