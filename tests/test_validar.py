"""Testes do validador de frontmatter (sem rede)."""
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

from validar import CAMPOS, arquivos_de_normas, partes_da_norma, validar_norma  # noqa: E402

VALORES = {
    "id": "cvm-res-17",
    "orgao": "cvm",
    "tipo": "resolucao",
    "numero": "17",
    "data": "2021-02-09",
    "publicacao_dou": "2021-02-10",
    "ementa": "Dispõe sobre o exercício da função de agente fiduciário.",
    "situacao": "vigente",
    "versao_texto": "consolidado",
    "vigente_ate_ato": "226",
    "aguarda_consolidado_oficial": "false",
    "historico_parcial": "false",
    "fonte_original": "https://exemplo.invalid/original",
    "fonte_consolidada": "https://exemplo.invalid/consolidado",
    "sha256_fonte": "a" * 64,
    "baixado_em": "2026-10-28",
    "verificado_em": "2026-10-28",
    "incerteza": "",
}
CORPO = "\n# Resolução CVM 17\n\n## Art. 1º\n\nTexto.\n"


def montar(valores=None, ordem=None, extra=(), corpo=CORPO):
    v = dict(VALORES)
    v.update(valores or {})
    chaves = ordem or list(CAMPOS)
    linhas = ["---"]
    for k in chaves:
        if k in v:
            linhas.append("%s: %s" % (k, v[k]) if v[k] != "" else "%s:" % k)
    linhas += list(extra)
    linhas.append("---")
    return "\n".join(linhas) + "\n" + corpo


class Base(unittest.TestCase):
    def erros(self, texto, nome="0017.md"):
        d = tempfile.mkdtemp()
        caminho = os.path.join(d, nome)
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(texto)
        self.addCleanup(lambda: (os.remove(caminho), os.rmdir(d)))
        return validar_norma(caminho)


class TestValidarNorma(Base):
    def test_arquivo_valido(self):
        self.assertEqual(self.erros(montar()), [])

    def test_campos_obrigatorios_na_ordem_do_plano(self):
        self.assertEqual(CAMPOS[:3], ["id", "orgao", "tipo"])
        self.assertEqual(CAMPOS[-1], "incerteza")
        self.assertEqual(len(CAMPOS), 18)

    def test_campo_faltando(self):
        ordem = [c for c in CAMPOS if c != "ementa"]
        erros = self.erros(montar(ordem=ordem))
        self.assertTrue(any("ementa" in e for e in erros), erros)

    def test_ordem_trocada(self):
        ordem = list(CAMPOS)
        ordem[3], ordem[4] = ordem[4], ordem[3]
        erros = self.erros(montar(ordem=ordem))
        self.assertTrue(any("ordem" in e for e in erros), erros)

    def test_situacao_fora_da_lista(self):
        erros = self.erros(montar({"situacao": "em-vigor"}))
        self.assertTrue(any("situacao" in e for e in erros), erros)

    def test_situacoes_aceitas(self):
        for s in ("vigente", "revogada", "parcialmente-revogada"):
            self.assertEqual(self.erros(montar({"situacao": s})), [], s)

    def test_versao_texto_fora_da_lista(self):
        erros = self.erros(montar({"versao_texto": "atualizado"}))
        self.assertTrue(any("versao_texto" in e for e in erros), erros)

    def test_data_invalida(self):
        erros = self.erros(montar({"data": "09/02/2021"}))
        self.assertTrue(any("data" in e for e in erros), erros)
        erros = self.erros(montar({"baixado_em": "2026-02-30"}))
        self.assertTrue(any("baixado_em" in e for e in erros), erros)

    def test_booleano_invalido(self):
        erros = self.erros(montar({"historico_parcial": "talvez"}))
        self.assertTrue(any("historico_parcial" in e for e in erros), erros)

    def test_numero_nao_inteiro(self):
        erros = self.erros(montar({"numero": "17A"}))
        self.assertTrue(any("numero" in e for e in erros), erros)

    def test_vigente_ate_ato_vazio_so_no_texto_original(self):
        self.assertEqual(self.erros(montar({"vigente_ate_ato": "", "versao_texto": "original"})), [])
        erros = self.erros(montar({"vigente_ate_ato": "226/25"}))
        self.assertTrue(any("vigente_ate_ato" in e for e in erros), erros)

    def test_id_incoerente_com_numero(self):
        erros = self.erros(montar({"id": "cvm-res-18"}))
        self.assertTrue(any("id" in e for e in erros), erros)

    def test_nome_do_arquivo_com_quatro_digitos(self):
        erros = self.erros(montar(), nome="17.md")
        self.assertTrue(any("arquivo" in e for e in erros), erros)

    def test_campo_desconhecido(self):
        erros = self.erros(montar(extra=["inventado: x"]))
        self.assertTrue(any("inventado" in e for e in erros), erros)

    def test_sem_frontmatter(self):
        erros = self.erros("# Só texto\n")
        self.assertTrue(any("frontmatter" in e for e in erros), erros)

    def test_frontmatter_nao_fechado(self):
        erros = self.erros("---\nid: cvm-res-17\n")
        self.assertTrue(any("frontmatter" in e for e in erros), erros)


class TestVigenciaDiferida(Base):
    BLOCO = (
        "\n## Art. 5º\n\nRedação atual.\n\n"
        "Vigente a partir de 2027-03-01:\n\nRedação futura.\n"
    )

    def test_bloco_sem_vigencia_inicio_e_rejeitado(self):
        erros = self.erros(montar(corpo=self.BLOCO))
        self.assertTrue(any("vigencia_inicio" in e for e in erros), erros)

    def test_bloco_com_vigencia_inicio_e_aceito(self):
        texto = montar(corpo=self.BLOCO, extra=["vigencia_inicio: 2027-03-01"])
        self.assertEqual(self.erros(texto), [])

    def test_vigencia_inicio_vazia_ou_invalida_e_rejeitada(self):
        for valor in ("", "março de 2027"):
            texto = montar(corpo=self.BLOCO, extra=["vigencia_inicio: " + valor])
            erros = self.erros(texto)
            self.assertTrue(any("vigencia_inicio" in e for e in erros), (valor, erros))

    def test_bloco_em_citacao_tambem_conta(self):
        corpo = "\n## Art. 5º\n\n> Vigente a partir de 2027-03-01\n"
        erros = self.erros(montar(corpo=corpo))
        self.assertTrue(any("vigencia_inicio" in e for e in erros), erros)

    def test_vigencia_inicio_antes_de_incerteza_e_rejeitada(self):
        # o opcional vem depois de `incerteza`
        ordem = list(CAMPOS[:-1]) + ["vigencia_inicio", "incerteza"]
        texto = montar({"vigencia_inicio": "2027-03-01"}, ordem=ordem, corpo=self.BLOCO)
        erros = self.erros(texto)
        self.assertTrue(any("ordem" in e for e in erros), erros)


class TestNormaEmPartes(unittest.TestCase):
    """`NNNN/index.md` com `## Partes`; partes sem frontmatter, abertas por `# título`."""

    PARTES = "\n# Resolução CVM 175\n\n## Partes\n\n- parte-geral.md\n- anexo-01.md\n"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = os.path.join(self._tmp.name, "0175")
        os.makedirs(self.pasta)
        self.gravar("index.md", montar({"id": "cvm-res-175", "numero": "175"}, corpo=self.PARTES))
        self.gravar("parte-geral.md", "# Parte geral\n\n## Art. 1º\n\nTexto.\n")
        self.gravar("anexo-01.md", "# Anexo Normativo I\n\n## Art. 1º\n\nTexto.\n")

    def gravar(self, nome, texto):
        with open(os.path.join(self.pasta, nome), "w", encoding="utf-8") as f:
            f.write(texto)

    def erros(self):
        return validar_norma(os.path.join(self.pasta, "index.md"))

    def test_norma_em_partes_valida(self):
        self.assertEqual(self.erros(), [])

    def test_partes_na_ordem_da_secao(self):
        nomes = [os.path.basename(p) for p in partes_da_norma(os.path.join(self.pasta, "index.md"))]
        self.assertEqual(nomes, ["parte-geral.md", "anexo-01.md"])

    def test_parte_fora_da_lista_e_erro(self):
        self.gravar("anexo-02.md", "# Anexo II\n\n## Art. 1º\n\nTexto.\n")
        erros = self.erros()
        self.assertEqual(len(erros), 1, erros)
        self.assertIn("anexo-02.md", erros[0])

    def test_parte_listada_que_nao_existe_e_erro(self):
        self.gravar("index.md", montar({"id": "cvm-res-175", "numero": "175"}, corpo=self.PARTES + "- anexo-09.md\n"))
        erros = self.erros()
        self.assertEqual(len(erros), 1, erros)
        self.assertIn("anexo-09.md", erros[0])

    def test_parte_listada_duas_vezes_e_erro(self):
        self.gravar("index.md", montar({"id": "cvm-res-175", "numero": "175"}, corpo=self.PARTES + "- anexo-01.md\n"))
        self.assertTrue(any("duplicad" in e for e in self.erros()))

    def test_index_sem_secao_partes_e_erro(self):
        self.gravar("index.md", montar({"id": "cvm-res-175", "numero": "175"}, corpo="\n# Resolução CVM 175\n"))
        self.assertTrue(any("Partes" in e for e in self.erros()))

    def test_parte_com_frontmatter_ou_sem_titulo_e_erro(self):
        self.gravar("anexo-01.md", "---\nid: x\n---\n\n# Anexo\n")
        self.assertTrue(any("anexo-01.md" in e and "frontmatter" in e for e in self.erros()))
        self.gravar("anexo-01.md", "## Art. 1º\n\nTexto.\n")
        self.assertTrue(any("anexo-01.md" in e and "título" in e for e in self.erros()))

    def test_index_precisa_estar_em_pasta_com_o_numero_da_norma(self):
        pasta = os.path.join(self._tmp.name, "0176")
        os.makedirs(pasta)
        with open(os.path.join(pasta, "index.md"), "w", encoding="utf-8") as f:
            f.write(montar({"id": "cvm-res-175", "numero": "175"}, corpo=self.PARTES))
        self.assertTrue(any("0175" in e for e in validar_norma(os.path.join(pasta, "index.md"))))

    def test_vigencia_diferida_numa_parte_exige_vigencia_inicio(self):
        self.gravar("anexo-01.md", "# Anexo\n\n## Art. 1º\n\nAtual.\n\nVigente a partir de 2027-03-01:\n\nFutura.\n")
        self.assertTrue(any("vigencia_inicio" in e for e in self.erros()))

    def test_arquivos_de_normas_acha_arquivo_unico_e_index_de_partes(self):
        raiz = self._tmp.name
        resol = os.path.join(raiz, "cvm", "resolucoes")
        os.makedirs(os.path.join(resol, "0175"))
        with open(os.path.join(resol, "0017.md"), "w") as f:
            f.write("x")
        with open(os.path.join(resol, "0175", "index.md"), "w") as f:
            f.write("x")
        with open(os.path.join(resol, "0175", "anexo-01.md"), "w") as f:
            f.write("x")
        achados = [os.path.relpath(c, raiz).replace(os.sep, "/") for c in arquivos_de_normas(raiz)]
        self.assertEqual(achados, ["cvm/resolucoes/0017.md", "cvm/resolucoes/0175/index.md"])


LEI = {"orgao": "federal", "vigente_ate_ato": "", "historico_parcial": "true",
       "aguarda_consolidado_oficial": "false"}


class TestTiposV030(Base):
    """SPEC v0.3.0: instrução, parecer, ofício-circular, decreto e lei complementar."""

    def test_um_arquivo_valido_de_cada_tipo_novo(self):
        casos = [
            ({"id": "cvm-instr-489", "tipo": "instrucao", "numero": "489"}, "0489.md"),
            ({"id": "cvm-po-35", "tipo": "parecer-orientacao", "numero": "35",
              "situacao": "nao-informada", "vigente_ate_ato": ""}, "0035.md"),
            ({"id": "cvm-oc-sse-0326", "tipo": "oficio-circular", "numero": "3",
              "situacao": "nao-informada", "vigente_ate_ato": ""}, "oc-sse-0326.md"),
            ({"id": "cvm-occ-sin-sse-0125", "tipo": "oficio-circular", "numero": "1",
              "situacao": "nao-informada", "vigente_ate_ato": ""}, "occ-sin-sse-0125.md"),
            ({"id": "cvm-oc-anual-2026-sre", "tipo": "oficio-circular", "numero": "1",
              "situacao": "vigente", "vigente_ate_ato": ""}, "oc-anual-2026-sre.md"),
            (dict(LEI, id="decreto-11415", tipo="decreto", numero="11415"), "decreto-11415.md"),
            (dict(LEI, id="lcp-105", tipo="lei-complementar", numero="105"), "lcp-105.md"),
        ]
        for valores, nome in casos:
            # parecer e ofício não têm artigos: o corpo sem `## Art.` é aceito
            corpo = "\n# Texto\n\nSem artigos.\n"
            self.assertEqual(self.erros(montar(valores, corpo=corpo), nome=nome), [], nome)

    def test_tipo_desconhecido_lista_os_aceitos(self):
        erros = self.erros(montar({"tipo": "deliberacao"}))
        msg = next(e for e in erros if "tipo" in e)
        for t in ("resolucao", "instrucao", "parecer-orientacao", "oficio-circular",
                  "lei", "decreto", "lei-complementar"):
            self.assertIn(t, msg)

    def test_nao_informada_so_em_parecer_e_oficio(self):
        erros = self.erros(montar({"situacao": "nao-informada"}))
        self.assertTrue(any("situacao" in e for e in erros), erros)
        erros = self.erros(montar({"id": "cvm-instr-489", "tipo": "instrucao", "numero": "489",
                                   "situacao": "nao-informada"}), nome="0489.md")
        self.assertTrue(any("situacao" in e for e in erros), erros)

    def test_id_e_arquivo_dos_tipos_novos(self):
        erros = self.erros(montar({"id": "cvm-res-489", "tipo": "instrucao", "numero": "489"}), nome="0489.md")
        self.assertTrue(any("id" in e for e in erros), erros)
        erros = self.erros(montar(dict(LEI, id="lcp-105", tipo="lei-complementar", numero="105")), nome="lcp-0105.md")
        self.assertTrue(any("arquivo" in e for e in erros), erros)
        erros = self.erros(montar(dict(LEI, id="decreto-11415", tipo="decreto", numero="11415", orgao="cvm")),
                           nome="decreto-11415.md")
        self.assertTrue(any("orgao" in e for e in erros), erros)

    def test_oficio_com_id_incoerente_com_o_nome_do_arquivo(self):
        valores = {"id": "cvm-oc-sse-0425", "tipo": "oficio-circular", "numero": "3",
                   "situacao": "nao-informada", "vigente_ate_ato": ""}
        erros = self.erros(montar(valores), nome="oc-sse-0326.md")
        self.assertTrue(any("id" in e for e in erros), erros)

    def test_oficio_com_nome_fora_do_padrao(self):
        valores = {"id": "cvm-OC_SSE", "tipo": "oficio-circular", "numero": "3",
                   "situacao": "nao-informada", "vigente_ate_ato": ""}
        erros = self.erros(montar(valores), nome="OC_SSE.md")
        self.assertTrue(any("arquivo" in e for e in erros), erros)

    def test_regras_de_lei_valem_para_decreto_e_lcp(self):
        base = dict(LEI, id="decreto-11415", tipo="decreto", numero="11415")
        for campo, valor in (("vigente_ate_ato", "12"), ("historico_parcial", "false"),
                             ("aguarda_consolidado_oficial", "true")):
            erros = self.erros(montar(dict(base, **{campo: valor})), nome="decreto-11415.md")
            self.assertTrue(any(campo in e for e in erros), (campo, erros))

    def test_vigente_ate_ato_inteiro_ou_vazio_em_tipo_da_cvm(self):
        valores = {"id": "cvm-po-35", "tipo": "parecer-orientacao", "numero": "35",
                   "situacao": "nao-informada", "vigente_ate_ato": "x"}
        erros = self.erros(montar(valores), nome="0035.md")
        self.assertTrue(any("vigente_ate_ato" in e for e in erros), erros)


class TestNivelVerificacao(Base):
    VALORES = ("historico-conferido", "consolidado-convertido", "ato-convertido",
               "pdf-extraido", "ocr", "compilado-planalto")

    def test_valores_aceitos(self):
        for valor in self.VALORES:
            texto = montar(extra=["nivel_verificacao: " + valor])
            self.assertEqual(self.erros(texto), [], valor)

    def test_valor_invalido_ou_vazio(self):
        for valor in ("conferido", "", "OCR", "ocr-vision"):
            erros = self.erros(montar(extra=["nivel_verificacao: " + valor]))
            self.assertTrue(any("nivel_verificacao" in e for e in erros), (valor, erros))

    def test_depois_de_vigencia_inicio(self):
        corpo = TestVigenciaDiferida.BLOCO
        certo = montar(corpo=corpo, extra=["vigencia_inicio: 2027-03-01", "nivel_verificacao: ato-convertido"])
        self.assertEqual(self.erros(certo), [])
        errado = montar(corpo=corpo, extra=["nivel_verificacao: ato-convertido", "vigencia_inicio: 2027-03-01"])
        self.assertTrue(any("ordem" in e for e in self.erros(errado)))

    def test_antes_de_incerteza_e_erro(self):
        ordem = list(CAMPOS[:-1]) + ["nivel_verificacao", "incerteza"]
        erros = self.erros(montar({"nivel_verificacao": "ato-convertido"}, ordem=ordem))
        self.assertTrue(any("ordem" in e for e in erros), erros)


class TestArquivosDeNormasV030(unittest.TestCase):
    def test_acha_tipos_novos_e_oficio_em_subpasta(self):
        with tempfile.TemporaryDirectory() as raiz:
            rels = [
                "cvm/resolucoes/0017.md",
                "cvm/instrucoes/0489.md",
                "cvm/pareceres-orientacao/0035.md",
                "cvm/oficios-circulares/sse1/oc-sse-0326.md",
                "cvm/oficios-circulares/smi-sin/occ-smi-sin-0124/index.md",
                "cvm/oficios-circulares/smi-sin/occ-smi-sin-0124/anexo-01.md",
                "cvm/alteradoras/0226.md",
                "leis/decreto-11415.md",
                "leis/lcp-105.md",
                "indice.md",
                "indices/resolucoes.md",
            ]
            for rel in rels:
                caminho = os.path.join(raiz, *rel.split("/"))
                os.makedirs(os.path.dirname(caminho), exist_ok=True)
                with open(caminho, "w") as f:
                    f.write("x")
            achados = sorted(os.path.relpath(c, raiz).replace(os.sep, "/") for c in arquivos_de_normas(raiz))
            self.assertEqual(achados, sorted([
                "cvm/resolucoes/0017.md",
                "cvm/instrucoes/0489.md",
                "cvm/pareceres-orientacao/0035.md",
                "cvm/oficios-circulares/sse1/oc-sse-0326.md",
                "cvm/oficios-circulares/smi-sin/occ-smi-sin-0124/index.md",
                "leis/decreto-11415.md",
                "leis/lcp-105.md",
            ]))


if __name__ == "__main__":
    unittest.main()
