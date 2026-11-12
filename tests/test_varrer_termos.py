"""Testes da varredura de termos proibidos (CNPJ e lista de nomes)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from varrer_termos import carregar_termos, varrer  # noqa: E402

TERMOS = ["Fundo Exemplo Alfa", "Gestora Exemplo"]
# CNPJ fictício montado em pedaços, para que este arquivo não dispare o próprio hook.
CNPJ_FORMATADO = "12.345.678/" + "0001-95"
CNPJ_PURO = "12345678" + "000195"


class TestVarrer(unittest.TestCase):
    def test_cnpj_formatado_e_achado(self):
        achados = varrer({"a.md": "Inscrito no CNPJ " + CNPJ_FORMATADO + "."}, TERMOS)
        self.assertEqual(len(achados), 1)
        self.assertTrue(achados[0].startswith("a.md: "))

    def test_cnpj_sem_pontuacao_e_achado(self):
        achados = varrer({"a.md": "cnpj " + CNPJ_PURO}, [])
        self.assertEqual(len(achados), 1)

    def test_termo_da_lista_sem_diferenciar_maiusculas(self):
        achados = varrer({"b.md": "O FUNDO EXEMPLO ALFA pagou."}, TERMOS)
        self.assertEqual(achados, ["b.md: Fundo Exemplo Alfa"])

    def test_termo_nao_casa_no_meio_de_palavra(self):
        achados = varrer({"c.md": "Um contraexemplo qualquer"}, ["exemplo"])
        self.assertEqual(achados, [])

    def test_texto_limpo_passa(self):
        achados = varrer({"d.md": "Art. 1º Esta Resolução dispõe sobre fundos."}, TERMOS)
        self.assertEqual(achados, [])

    def test_varios_arquivos_e_ordem_estavel(self):
        achados = varrer(
            {"z.md": "Gestora Exemplo", "a.md": "Fundo Exemplo Alfa"}, TERMOS
        )
        self.assertEqual(achados, ["a.md: Fundo Exemplo Alfa", "z.md: Gestora Exemplo"])

    def test_numero_longo_que_nao_e_cnpj(self):
        # Número de processo/ato com formato diferente não deve disparar.
        achados = varrer({"e.md": "Processo SEI 19957.001234/2023-10"}, [])
        self.assertEqual(achados, [])


class TestCarregarTermos(unittest.TestCase):
    def test_ignora_comentarios_e_linhas_vazias(self):
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("# comentário\n\nFundo Exemplo Alfa\n  Gestora Exemplo  \n")
            caminho = f.name
        try:
            self.assertEqual(carregar_termos(caminho), ["Fundo Exemplo Alfa", "Gestora Exemplo"])
        finally:
            os.unlink(caminho)

    def test_arquivo_ausente_devolve_none(self):
        self.assertIsNone(carregar_termos("/caminho/que/nao/existe.txt"))


if __name__ == "__main__":
    unittest.main()


class TestCnpjDentroDeHash(unittest.TestCase):
    def test_hash_hexadecimal_nao_e_cnpj(self):
        from varrer_termos import varrer
        texto = "sha256_fonte: 29653ca2f0300a653b7cf646db92a1f9cf6794a72540926012984b67b7c62e73"
        self.assertEqual(varrer({"a.md": texto}, []), [])

    def test_cnpj_solto_continua_bloqueado(self):
        from varrer_termos import varrer
        self.assertEqual(varrer({"a.md": "CNPJ %s." % CNPJ_PURO}, []), ["a.md: " + CNPJ_PURO])


class TestCnpjDeDigitoRepetido(unittest.TestCase):
    def test_sequencia_de_um_digito_nao_e_cnpj(self):
        from varrer_termos import varrer
        self.assertEqual(varrer({"a.md": "repetidos (p.ex., " + "9" * 14 + ")"}, []), [])


class TestCnpjsPublicos(unittest.TestCase):
    def test_cnpj_da_lista_passa(self):
        self.assertEqual(varrer({"a.md": "Banco B3 S.A. CNPJ: 00.997.185/0001-50"}, []), [])

    def test_outro_cnpj_continua_bloqueado(self):
        outro = "11.222." + "333/0001-81"  # montado aqui para a varredura não barrar este arquivo
        self.assertEqual(varrer({"a.md": "CNPJ: " + outro}, []), ["a.md: " + outro])


class TestCpfERg(unittest.TestCase):
    # Números fictícios montados em pedaços, para a varredura não barrar este arquivo.
    CPF = "123.456." + "789-09"
    RG = "12.345." + "678-9"

    def test_cpf_e_achado_sem_mostrar_o_numero(self):
        achados = varrer({"a.md": "linha 1\nCPF nº %s." % self.CPF}, [])
        self.assertEqual(achados, ["a.md: CPF na linha 2"])

    def test_cpf_sem_pontuacao_valido(self):
        self.assertEqual(varrer({"a.md": "x " + self.CPF.replace(".", "").replace("-", "")}, []),
                         ["a.md: CPF na linha 1"])

    def test_rg_e_achado(self):
        self.assertEqual(varrer({"a.md": "RG nº %s, e" % self.RG}, []), ["a.md: RG na linha 1"])

    def test_ja_cortado_passa(self):
        t = "inscrito no CPF sob o nº [dado pessoal retirado], RG nº [dado pessoal retirado]"
        self.assertEqual(varrer({"a.md": t}, []), [])

    def test_rotulo_de_formulario_passa(self):
        self.assertEqual(varrer({"a.md": "CPF/CNPJ: RG: RG: Endereço:"}, []), [])


NORMA_X = "plugins/normas/skills/consultar-normas/normas/x.md"


class TestJulgados(unittest.TestCase):
    def test_cnpj_liberado_so_nos_julgados(self):
        cnpj = "60.701.190/" + "0001-04"
        txt = "Banco X, CNPJ " + cnpj
        self.assertEqual(varrer({"julgados/cvm/pas/2023/x.md": txt}, []), [])
        self.assertEqual(varrer({NORMA_X: txt}, []), [NORMA_X + ": " + cnpj])

    def test_layout_antigo_do_historico_continua_valendo(self):
        cnpj = "60.701.190/" + "0001-04"
        txt = "Banco X, CNPJ " + cnpj
        self.assertEqual(varrer({"plugins/julgados-pas/julgados/cvm/pas/2023/x.md": txt}, []), [])

    def test_indices_e_fichas_dos_julgados_na_skill_valem_como_julgados(self):
        cnpj = "60.701.190/" + "0001-04"
        for arq in ("plugins/normas/skills/consultar-normas/julgados/indices/pas-2023.md",
                    "plugins/normas/skills/consultar-normas/julgados/fichas/pas/2023.md"):
            self.assertEqual(varrer({arq: "CNPJ " + cnpj}, []), [])
            self.assertEqual(varrer({arq: "caso da Fulana Ltda"}, ["Fulana"]), [arq + ": Fulana"])

    def test_normas_da_skill_nao_valem_como_julgados(self):
        cnpj = "60.701.190/" + "0001-04"
        self.assertEqual(varrer({NORMA_X: "CNPJ " + cnpj}, []), [NORMA_X + ": " + cnpj])

    def test_termo_e_cpf_continuam_nos_julgados(self):
        arq = "julgados/cvm/pas/2023/x.md"
        self.assertEqual(varrer({arq: "caso da Fulana Ltda"}, ["Fulana"]), [arq + ": Fulana"])



class TestExpressoesLiberadas(unittest.TestCase):
    ARQ = "julgados/cvm/pas/2023/x.md"

    def test_expressao_liberada_passa_so_nos_julgados(self):
        txt = "a administradora do Fundo Alfa Credito respondeu"
        self.assertEqual(varrer({self.ARQ: txt}, ["Alfa"], ["Fundo Alfa"]), [])
        self.assertEqual(varrer({NORMA_X: txt}, ["Alfa"], ["Fundo Alfa"]),
                         [NORMA_X + ": Alfa"])

    def test_termo_fora_da_expressao_continua_barrando(self):
        txt = "o Fundo Alfa e a Alfa Gestora"
        self.assertEqual(varrer({self.ARQ: txt}, ["Alfa"], ["Fundo Alfa"]), [self.ARQ + ": Alfa"])

    def test_espaco_quebra_hifen_e_maiusculas(self):
        txt = "do fundo\nALFA, do Alfa FIDC- NP e da Alfa Fundo de Investimentos"
        lib = ["Fundo Alfa", "Alfa FIDC-NP", "Alfa Fundo de Investimento"]
        self.assertEqual(varrer({self.ARQ: txt}, ["Alfa"], lib), [])


class TestCarregarLiberadas(unittest.TestCase):
    def test_linhas_com_mais_viram_liberadas_e_saem_dos_termos(self):
        import tempfile
        from varrer_termos import carregar_liberadas

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("# c\nAlfa\n+ Fundo Alfa\n+Alfa FIDC-NP\n+\n")
            caminho = f.name
        try:
            self.assertEqual(carregar_termos(caminho), ["Alfa"])
            self.assertEqual(carregar_liberadas(caminho), ["Fundo Alfa", "Alfa FIDC-NP"])
        finally:
            os.unlink(caminho)
        self.assertEqual(carregar_liberadas("/caminho/que/nao/existe.txt"), [])
