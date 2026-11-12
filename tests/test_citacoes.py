"""Testes do extrator de dispositivos citados (sem rede)."""
import os
import sys
import unittest
from unittest import mock

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import citacoes  # noqa: E402
from citacoes import (  # noqa: E402
    dispositivo, extrair_citacoes, formatar_dispositivos_citados, formatar_normas_citadas,
    ler_dispositivo, normas_mencionadas,
)

NORMAS = os.path.join(AQUI, "..", "plugins", "normas", "skills", "consultar-normas", "normas")
# ids do acervo para os testes (independentes do normas.json do repositório)
IDS = frozenset([
    "cvm-res-23", "cvm-res-30", "cvm-res-35", "cvm-res-44", "cvm-res-80", "cvm-res-160", "cvm-res-161",
    "cvm-res-175", "cvm-instr-489", "cvm-po-35", "lei-4595", "lei-6385", "lei-6404", "lei-10406",
    "lei-14430", "cmn-res-4966", "bcb-circ-3553",
])


def disp(texto, **kw):
    return [dispositivo(c) for c in extrair_citacoes(texto, ids=kw.pop("ids", IDS), **kw)]


# Conjunto rotulado à mão: (frase, dispositivos esperados). Frases tiradas do acervo
# (pareceres, ofícios e autorregulação) ou montadas com as variantes do plano.
ROTULADAS = [
    # acórdão do CRSFN (SEI, 2023): "6074/2019" é erro de digitação da fonte para a ICVM 607;
    # ICVM com 4 dígitos não existe: a menção segura o "art. 70" e não vira citação
    ("c/c art. 15 do Código de Processo Civil e do art. 70 da Instrução CVM nº 6074/2019, a exigir "
     "a devolução do prazo recursal",
     ["fora:lei-13105 art. 15"]),
    ("atende aos requisitos estabelecidos no artigo 100, parágrafo 1º, da Lei nº 6.404/76. 67 Vide",
     ["lei-6404 art. 100, § 1º"]),
    ("nos termos do artigo 19 da Resolução CVM nº 44/21, configura infração grave, para os fins previstos "
     "no parágrafo 3º do artigo 11 da Lei nº 6.385/76",
     ["cvm-res-44 art. 19", "lei-6385 art. 11, § 3º"]),
    ("Governança Corporativa – Companhias Abertas (art. 22, inciso XII, da Resolução CVM nº 80). 131",
     ["cvm-res-80 art. 22, inciso XII"]),
    ("De acordo com artigo 133, parágrafo 5º da Lei nº 6.404/76, o emissor está dispensado",
     ["lei-6404 art. 133, § 5º"]),
    ("2. Equivalência Patrimonial O artigo 248 da LEI 6404/76 preconiza o método",
     ["lei-6404 art. 248"]),
    ("previsto no artigo 25 da Resolução CVM nº 80/22, cujo conteúdo reflete o Anexo C da citada Resolução.",
     ["cvm-res-80 art. 25"]),
    ("Nos termos do parágrafo único do artigo 63 da Resolução CVM nº 80/22, a multa não será aplicada",
     ["cvm-res-80 art. 63, parágrafo único"]),
    ("os documentos previstos no artigo 33, incisos XX e XXI, e no artigo 34, inciso XI, da Resolução CVM "
     "nº 80/22, nos prazos assinalados",
     ["cvm-res-80 art. 33, inciso XX", "cvm-res-80 art. 33, inciso XXI", "cvm-res-80 art. 34, inciso XI"]),
    ("O parágrafo único do art. 11 da Resolução CVM n. º 23/2021 procura estabelecer",
     ["cvm-res-23 art. 11, parágrafo único"]),
    ("exercícios anteriores, conforme prevê o artigo 20 da INSTRUÇÃO CVM Nº 191/92. Como o lucro",
     ["fora:icvm-191 art. 20"]),
    ("11 Resolução CVM n° 23/2021, art. 33, §4º. Anexo",
     ["cvm-res-23 art. 33, § 4º"]),
    ("cabíveis, em consonância ao disposto no art. 8º § 5º da RCVM 161. Caso a ANBIMA conclua",
     ["cvm-res-161 art. 8º, § 5º"]),
    ("ofertante, nos termos do inciso XVII do art. 3º da Lei nº 7.940/1989. No caso",
     ["fora:lei-7940 art. 3º, inciso XVII"]),
    ("hipótese prevista na Instrução CVM nº 480/09, artigo 24, parágrafo 3º, inciso I, em razão",
     ["fora:icvm-480 art. 24, § 3º, inciso I"]),
    ("o dever de diligência do art. 155, § 1º, da Lei nº 6.404/76 alcança",
     ["lei-6404 art. 155, § 1º"]),
    ("os deveres dos arts. 153 e 154 da Lei 6.404 aplicam-se",
     ["lei-6404 art. 153", "lei-6404 art. 154"]),
    ("na forma do artigo 90 parágrafo 1º da RCVM 175, o gestor",
     ["cvm-res-175 art. 90, § 1º"]),
    ("observado o art. 9º da Resolução CVM nº 175/22, o regulamento",
     ["cvm-res-175 art. 9º"]),
    ("25. Nos termos do art. 2º, inciso XII, alínea \"d\", do Anexo Normativo II à Resolução CVM nº 175, "
     "as cotas de FIDC",
     ["cvm-res-175 Anexo II art. 2º, inciso XII, alínea d"]),
    ("conforme a Instrução CVM nº 358/02, art. 8º, o administrador",
     ["fora:icvm-358 art. 8º"]),
    ("nos termos do art. 3º da ICVM 358, a companhia",
     ["fora:icvm-358 art. 3º"]),
    ("aplicando-se o art. 2º da Deliberação CVM nº 538, de 2008",
     ["fora:deliberacao-cvm-538 art. 2º"]),
    ("o regime fiduciário da Lei nº 14.430/22, art. 26, III, alcança",
     ["lei-14430 art. 26, inciso III"]),
    ("Por sua vez, o art. 52, III, do Anexo Normativo II à Resolução CVM nº 175 dispõe que a classe",
     ["cvm-res-175 Anexo II art. 52, inciso III"]),
    ("Cabe pontuar que a alínea \"b\" do art. 2º, XII, do Anexo Normativo II, que classifica",
     ["cvm-res-175 Anexo II art. 2º, inciso XII, alínea b"]),
    ("O art. 44 do Anexo Normativo II à Resolução CVM nº 175 e o art. 45 do mesmo Anexo tratam",
     ["cvm-res-175 Anexo II art. 44", "cvm-res-175 Anexo II art. 45"]),
    ("o art. 5º da Resolução CVM nº 160 e o art. 7º da mesma Resolução exigem",
     ["cvm-res-160 art. 5º", "cvm-res-160 art. 7º"]),
    ("nos termos do art. 4º, § 2º, da Resolução CMN nº 4.966, a instituição",
     ["cmn-res-4966 art. 4º, § 2º"]),
    ("conforme o art. 1.368-C do Código Civil, o fundo",
     ["lei-10406 art. 1.368-C"]),
    # "Lei das Estatais" é menção: o "seu artigo 17" não cai na Lei 6.404 citada antes
    ("o artigo 147, §1º, da Lei nº 6.404/1976. Adicionalmente, a Lei das Estatais prescreve em seu artigo 17, §2º, II, que",
     ["lei-6404 art. 147, § 1º", "fora:lei-13303 art. 17, § 2º, inciso II"]),
    ("Segundo o artigo 9º , as ações em tesouraria não podem exceder", []),
    ("CAPÍTULO III: DISPOSIÇÕES FINAIS ## Art. 108º O presente regulamento é aprovado", []),
    ("conforme o art. 4º da Lei nº 4.595/64, compete ao CMN",
     ["lei-4595 art. 4º"]),
    ("Resolução CVM nº 35/21, art. 3º, inciso II, alínea “a”",
     ["cvm-res-35 art. 3º, inciso II, alínea a"]),
    ("nos termos do art. 6º da Lei Complementar nº 105/2001, o sigilo",
     ["fora:lcp-105 art. 6º"]),
    ("o art. 12 da Resolução CVM nº 160/2022 e a observância do presente Ofício-Circular nº 6/2025",
     ["cvm-res-160 art. 12"]),
]


class TestVariantes(unittest.TestCase):
    def test_paragrafo_com_virgulas_e_lei_com_ano(self):
        self.assertEqual(disp("art. 155, § 1º, da Lei nº 6.404/76"), ["lei-6404 art. 155, § 1º"])

    def test_lista_de_artigos(self):
        self.assertEqual(disp("arts. 153 e 154 da Lei 6.404"), ["lei-6404 art. 153", "lei-6404 art. 154"])

    def test_intervalo_de_artigos_e_de_incisos(self):
        self.assertEqual(disp("arts. 9º a 11 da Lei 6.404"),
                         ["lei-6404 art. 9º", "lei-6404 art. 10", "lei-6404 art. 11"])
        self.assertEqual(disp("art. 33, incisos XX a XXII, da Resolução CVM nº 80"),
                         ["cvm-res-80 art. 33, inciso XX", "cvm-res-80 art. 33, inciso XXI",
                          "cvm-res-80 art. 33, inciso XXII"])

    def test_intervalo_acima_de_mil_mantem_ponto(self):
        self.assertEqual(disp("arts. 1.008 a 1.010 da Lei nº 10.406/2002"),
                         ["lei-10406 art. 1.008", "lei-10406 art. 1.009",
                          "lei-10406 art. 1.010"])

    def test_conectivo_colado_no_numero(self):
        # "4ºe 5º" e "132 e133": texto da fonte sem espaço em volta do "e"
        self.assertEqual(disp("os artigos 132 e133 da Lei 6.404"),
                         ["lei-6404 art. 132", "lei-6404 art. 133"])
        self.assertEqual(disp("os artigos 4ºe 5º da Lei 6.385"),
                         ["lei-6385 art. 4º", "lei-6385 art. 5º"])

    def test_artigo_singular_nao_vira_lista(self):
        self.assertEqual(disp("o art. 5º, 30 (trinta) dias depois, da Lei 6.404"), [])

    def test_rcvm_e_resolucao_por_extenso(self):
        self.assertEqual(disp("artigo 90 parágrafo 1º da RCVM 175"), ["cvm-res-175 art. 90, § 1º"])
        self.assertEqual(disp("artigo 90 parágrafo 1º da Resolução CVM nº 175/22"), ["cvm-res-175 art. 90, § 1º"])

    def test_anexo_normativo_vira_parte(self):
        c = extrair_citacoes('art. 2º, inciso XII, alínea "d", do Anexo Normativo II à Resolução CVM 175', ids=IDS)
        self.assertEqual(len(c), 1)
        self.assertEqual((c[0]["norma"], c[0]["parte"], c[0]["artigo"], c[0]["inciso"], c[0]["alinea"]),
                         ("cvm-res-175", "Anexo II", "2º", "XII", "d"))
        self.assertEqual(c[0]["rotulo"], "res-cvm-175")
        self.assertEqual(c[0]["paragrafo"], "")

    def test_instrucao_revogada_fica_fora(self):
        self.assertEqual(disp("art. 2º da Instrução CVM nº 358/02"), ["fora:icvm-358 art. 2º"])
        self.assertEqual(disp("art. 2º da ICVM 358"), ["fora:icvm-358 art. 2º"])
        self.assertEqual(disp("art. 2º da Instrução CVM nº 489"), ["cvm-instr-489 art. 2º"])

    def test_deliberacao_sempre_fora(self):
        self.assertEqual(disp("art. 1º da Deliberação CVM nº 538"), ["fora:deliberacao-cvm-538 art. 1º"])

    def test_norma_antes_do_artigo(self):
        self.assertEqual(disp("Lei nº 14.430/22, art. 26, III"), ["lei-14430 art. 26, inciso III"])

    def test_anaforas(self):
        self.assertEqual(disp("o art. 44 do Anexo Normativo II à Resolução CVM nº 175. Já o art. 2º, inciso XII, "
                              "do referido Anexo"),
                         ["cvm-res-175 Anexo II art. 44", "cvm-res-175 Anexo II art. 2º, inciso XII"])
        self.assertEqual(disp("o art. 1º da Lei 6.385 e o art. 9º da referida Lei"),
                         ["lei-6385 art. 1º", "lei-6385 art. 9º"])
        self.assertEqual(disp("o art. 1º da Resolução CVM 160 e o art. 2º da citada Resolução"),
                         ["cvm-res-160 art. 1º", "cvm-res-160 art. 2º"])

    def test_desta_lei_so_com_documento(self):
        self.assertEqual(disp("observado o disposto no art. 10 desta Lei"), [])
        self.assertEqual(disp("observado o disposto no art. 10 desta Lei", documento="lei-14430"),
                         ["lei-14430 art. 10"])

    def test_paragrafo_do_mesmo_artigo(self):
        self.assertEqual(disp("o artigo 90 parágrafo 1º da RCVM 175 e o parágrafo 2º do mesmo artigo"),
                         ["cvm-res-175 art. 90, § 1º", "cvm-res-175 art. 90, § 2º"])

    def test_artigo_solto_nao_sai(self):
        self.assertEqual(disp("fora do escopo do art. 36 e, portanto, dispensado"), [])

    def test_resolucao_sem_orgao(self):
        self.assertEqual(disp("art. 2º da Resolução nº 175"), ["cvm-res-175 art. 2º"])
        self.assertEqual(disp("art. 14 da Resolução nº 4.966"), ["cmn-res-4966 art. 14"])

    def test_trecho_e_posicao(self):
        texto = "Introdução.\n\nNos termos do art. 26 da Lei n° 14.430/22, o patrimônio separado " + "x" * 300
        c = extrair_citacoes(texto, ids=IDS)[0]
        self.assertEqual(texto[c["posicao"]:c["posicao"] + 7], "art. 26")
        self.assertIn("art. 26 da Lei n° 14.430/22", c["trecho"])
        self.assertLessEqual(len(c["trecho"]), citacoes.TRECHO_MAX)

    def test_quebras_de_linha_do_pdf(self):
        texto = "enquadradas no conceito de que trata o art. 2º, inciso XII, do referido\n\nAnexo."
        prefixo = "nos termos do art. 44 do Anexo Normativo II à Resolução CVM nº 175, "
        self.assertEqual(disp(prefixo + texto)[-1], "cvm-res-175 Anexo II art. 2º, inciso XII")


class TestFormato(unittest.TestCase):
    def test_dispositivo_ida_e_volta(self):
        for s in ("cvm-res-175 Anexo II art. 2º, inciso XII, alínea d", "lei-6404 art. 155, § 1º",
                  "fora:icvm-358 art. 8º", "lei-10406 art. 1.368-C", "cvm-res-80 art. 63, parágrafo único"):
            d = ler_dispositivo(s)
            self.assertIsNotNone(d, s)
            self.assertEqual(dispositivo(d), s)
        self.assertIsNone(ler_dispositivo("cvm-res-175 artigo 2"))
        self.assertIsNone(ler_dispositivo("Res 175 art. 2º"))

    def test_campos_do_julgado(self):
        c = extrair_citacoes("art. 155, § 1º, da Lei 6.404 e art. 155, § 1º, da Lei 6.404; "
                             "art. 2º da ICVM 358", ids=IDS)
        self.assertEqual(formatar_dispositivos_citados(c), "lei-6404 art. 155, § 1º; fora:icvm-358 art. 2º")
        self.assertEqual(formatar_normas_citadas(c), "lei-6404; fora:icvm-358")
        mencionadas = normas_mencionadas("a Resolução CVM nº 175 e a Lei 6.404", ids=IDS)
        self.assertEqual(mencionadas, ["cvm-res-175", "lei-6404"])
        self.assertEqual(formatar_normas_citadas(c, mencionadas), "lei-6404; fora:icvm-358; cvm-res-175")
        # ICVM de 4 dígitos (erro da fonte) não entra nem como norma mencionada
        self.assertEqual(normas_mencionadas("a ICVM 6074/2019 e a Lei 6.404", ids=IDS), ["lei-6404"])

    def test_rotulos_e_ids(self):
        self.assertEqual(citacoes.id_do_rotulo("res-cvm-175"), "cvm-res-175")
        self.assertEqual(citacoes.id_do_rotulo("icvm-358"), "cvm-instr-358")
        self.assertIsNone(citacoes.id_do_rotulo("deliberacao-cvm-538"))
        self.assertEqual(citacoes.rotulo_do_id("cmn-res-4966"), "res-cmn-4966")


class TestConjuntoRotulado(unittest.TestCase):
    def test_precisao_e_cobertura(self):
        acertos = extraidas = esperadas = 0
        erros = []
        for frase, esperado in ROTULADAS:
            obtido = disp(frase)
            extraidas += len(obtido)
            esperadas += len(esperado)
            acertos += len(set(obtido) & set(esperado))
            if obtido != esperado:
                erros.append((frase[:60], obtido, esperado))
        precisao = acertos / extraidas if extraidas else 1.0
        cobertura = acertos / esperadas if esperadas else 1.0
        self.assertGreaterEqual(len(ROTULADAS), 30)
        self.assertGreaterEqual(precisao, 0.95, erros)
        self.assertGreaterEqual(cobertura, 0.90, erros)
        self.assertEqual(erros, [])  # hoje, 100%: qualquer regressão aparece aqui


@unittest.skipUnless(os.path.isdir(NORMAS), "acervo ausente")
class TestTrechosDoAcervo(unittest.TestCase):
    """Os três casos conferidos no plano (P13, P14 e P25), no texto real do acervo."""

    def citacoes_de(self, rel):
        with open(os.path.join(NORMAS, *rel.split("/")), encoding="utf-8") as f:
            return [dispositivo(c) for c in extrair_citacoes(f.read())]

    def test_oc_sse_8_2025_referido_anexo(self):
        c = self.citacoes_de("cvm/oficios-circulares/sse1/oc-sse-0825.md")
        self.assertIn("cvm-res-175 Anexo II art. 2º, inciso XII", c)
        self.assertIn("cvm-res-175 Anexo II art. 2º, inciso XII, alínea d", c)

    def test_alinhamento_act_001_2025_artigo_90(self):
        c = self.citacoes_de("autorregulacao/anbima/alinhamento-act-cvm-anbima-001-2025-enquadramento-fidc.md")
        self.assertIn("cvm-res-175 art. 90, § 1º", c)

    def test_oc_sse_6_2025_lei_14430(self):
        c = self.citacoes_de("cvm/oficios-circulares/sse1/oc-sse-0625.md")
        self.assertIn("lei-14430 art. 26", c)



ANOS = {"cvm-res-17": 2021, "cvm-res-80": 2022, "cvm-res-160": 2022, "lei-6385": 1976, "lei-6404": 1976,
        "lei-9613": 1998, "lei-13506": 2017}
LEIS = frozenset(["lei-6385", "lei-6404", "lei-14430", "lei-9613", "lei-13506"])


@mock.patch.object(citacoes, "carregar_anos", lambda *a: ANOS)
@mock.patch.object(citacoes, "carregar_ids", lambda *a: LEIS)
class TestFase3b(unittest.TestCase):
    """Erros de citação achados na auditoria da Fase 3b."""
    IDS = IDS | {"cvm-res-17", "cvm-res-80", "lei-9613", "lei-13506"}

    def d(self, texto):
        return disp(texto, ids=self.IDS)

    # cvm-col-20161213-d0473 e ~150 julgados: número de lei partido pela fonte virava fora:lei-6
    def test_lei_partida_pelo_ocr_recupera_a_lei_do_acervo(self):
        for frase in ("art. 202, § 4º, da Lei 6 6.404/76 e", "art. 202, § 4º, da Lei 6.4 404/76, a",
                      "art. 202, § 4º, da Lei nº 6. .404/76 e", "art. 202, § 4º, da Lei n° 6.404176 c/c"):
            self.assertEqual(self.d(frase), ["lei-6404 art. 202, § 4º"], frase)
        self.assertEqual(self.d("art. 11 da Lei nO 6.385176, bem"), ["lei-6385 art. 11"])

    def test_lei_partida_sem_lei_do_acervo_fica_como_esta(self):
        self.assertEqual(self.d("art. 3º da Lei 6.04/76, em"), ["fora:lei-6 art. 3º"])
        self.assertEqual(self.d("art. 3º da Lei nº 8.668/93"), ["fora:lei-8668 art. 3º"])

    # cvm-pas-rj2001-4187: Resolução CMN 454 virava fora:res-cvm-454
    def test_resolucao_com_orgao_depois_da_data(self):
        self.assertEqual(self.d("parágrafo único do artigo 14 da Resolução nº 454, de 16.11.77, do Conselho "
                                "Monetário Nacional, prazo"), ["fora:res-cmn-454 art. 14, parágrafo único"])

    def test_resolucoes_com_orgao_coletivo(self):
        self.assertEqual(self.d("por força do art. 4º da Resolução 454/77, com a redação dada pela Resolução "
                                "2.785/00, ambas do Conselho Monetário Nacional."),
                         ["fora:res-cmn-454 art. 4º"])
        self.assertEqual(self.d("art. 4º da Resolução 30/2021, com a redação da Resolução 35. Ambas do CMN"),
                         ["cvm-res-30 art. 4º"])

    # cvm-pas-19957-002296-2020-84 e 19957-001450-2022-62: "Resolução CVM nº 17/2023" virava cvm-res-17
    def test_ano_que_nao_e_o_da_norma_do_acervo_fica_fora(self):
        texto = "art. 2º da Resolução CVM nº 17/2023 e art. 3º da Resolução CVM nº 17/2021"
        self.assertEqual(self.d(texto), ["fora:res-cvm-17-2023 art. 2º", "cvm-res-17 art. 3º"])
        self.assertEqual(normas_mencionadas(texto, ids=self.IDS), ["fora:res-cvm-17-2023", "cvm-res-17"])
        self.assertEqual(self.d("art. 11 da Lei nº 6.385/76"), ["lei-6385 art. 11"])
        self.assertEqual(self.d("art. 11 da Lei nº 6.385/78"), ["fora:lei-6385-1978 art. 11"])
        self.assertEqual(self.d("art. 11 da Lei nº 6.385/7610, e"), ["lei-6385 art. 11"])  # /76 + nota 10

    # ano a 1 de distância do da norma é erro de digitação da fonte: liga à norma do acervo
    def test_ano_a_um_de_distancia_liga_a_norma(self):
        self.assertEqual(self.d("art. 11 da Lei nº 6.385/75, e"), ["lei-6385 art. 11"])
        self.assertEqual(self.d("art. 12 da Lei nº 9.613/99, no"), ["lei-9613 art. 12"])
        self.assertEqual(self.d("art. 2º da Lei nº 13.506/2016, que"), ["lei-13506 art. 2º"])
        self.assertEqual(self.d("art. 61 da Resolução CVM nº 80/2021, o"), ["cvm-res-80 art. 61"])
        self.assertEqual(self.d("art. 2º da Resolução CVM nº 17/2023, e"), ["fora:res-cvm-17-2023 art. 2º"])

    def test_ano_diferente_continua_ligando_a_anafora(self):
        self.assertEqual(self.d("art. 2º da Resolução CVM nº 17/2023 e art. 3º da mesma Resolução"),
                         ["fora:res-cvm-17-2023 art. 2º", "fora:res-cvm-17-2023 art. 3º"])

    # cvm-pas-19957-016206-2023-85: "art. 545 da RCVM nº 160/2022" é erro de digitação da fonte
    # (a Res. CVM 160 não tem art. 545). Exceção registrada: o extrator não corrige a fonte.
    def test_artigo_inexistente_por_erro_da_fonte_fica_como_escrito(self):
        self.assertEqual(self.d("Nos termos do art. 545 da RCVM nº 160/2022, o período vedado"),
                         ["cvm-res-160 art. 545"])


if __name__ == "__main__":
    unittest.main()
