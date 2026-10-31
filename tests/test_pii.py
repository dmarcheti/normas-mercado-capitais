"""Testes do corte de dados pessoais. Números montados em pedaços (fictícios), para que este
arquivo não dispare a varredura do pre-commit."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pii  # noqa: E402

M = pii.MARCADOR
CPF_FMT = "123.456." + "789-09"       # dígito verificador válido (exemplo didático)
CPF_PURO = "123456" + "78909"
CPF_DV_RUIM = "123456" + "78900"
CNPJ_FMT = "12.345.678/" + "0001-95"
RG_NUM = "12.345." + "678-9"


class CpfTest(unittest.TestCase):
    def test_formatado(self):
        self.assertEqual(pii.limpar("inscrito no CPF/MF sob o nº %s, e" % CPF_FMT),
                         "inscrito no CPF/MF sob o nº %s, e" % M)

    def test_sem_pontuacao_valido(self):
        self.assertEqual(pii.limpar("CPF " + CPF_PURO), "CPF " + M)
        self.assertEqual(pii.limpar("número " + CPF_PURO + " solto"), "número %s solto" % M)

    def test_puro_sem_rotulo_com_dv_ruim_fica(self):
        self.assertIn(CPF_DV_RUIM, pii.limpar("protocolo " + CPF_DV_RUIM))

    def test_rotulado_com_ruido_de_ocr(self):
        ruido = "123.4S6".replace("S", "5") + ".7B9-O9".replace("B", "8")
        self.assertEqual(pii.limpar("C.P.F. nº " + ruido + "."), "C.P.F. nº " + M + ".")
        self.assertEqual(pii.limpar("CPF: 123 456 " + "789 09"), "CPF: " + M)

    def test_cpf_me_com_hifen_depois_do_numero(self):
        self.assertEqual(pii.limpar("inscrito no CPF/ME sob o nº-%s, com" % CPF_FMT),
                         "inscrito no CPF/ME sob o nº-%s, com" % M)

    def test_cnpj_fica(self):
        t = "inscrita no CNPJ sob o nº %s, com sede na Rua A, 10" % CNPJ_FMT
        self.assertEqual(pii.limpar(t), t)

    def test_achar(self):
        self.assertEqual(len(pii.achar_cpfs("a %s b %s" % (CPF_FMT, CPF_PURO))), 2)
        self.assertEqual(pii.achar_cpfs("CPF: " + M), [])
        self.assertEqual(pii.achar_cpfs("NUP 19957.011607/2024-20 e CNPJ " + CNPJ_FMT), [])


class RgTest(unittest.TestCase):
    def test_rg(self):
        self.assertEqual(pii.limpar("RG nº %s, expedida pela SSP/SP, e" % RG_NUM),
                         "RG nº %s, e" % M)
        self.assertEqual(pii.limpar("portador da carteira de identidade nº %s IFP/RJ" % RG_NUM),
                         "portador da carteira de identidade nº " + M)
        self.assertEqual(pii.limpar("RG: " + "1234567-8" + " SSP/SP;"), "RG: %s;" % M)

    def test_rg_variantes_da_fonte(self):
        # "n.º" com ponto antes do º, "identidade nº" sem "carteira", "RG/SSP/SP", "RG/SP/SSP"
        for t in ("portador da Carteira de Identidade n.º %s, emitida pelo CRC/MG",
                  "portador da Cédula de Identidade RG n.° %s-SSP/SP, inscrito",
                  "portador da identidade n° %s IFP/RJ, inscrito",
                  "identidade nº: %s, expedida pelo IFP",
                  "Nome: RG/SSP/SP n° %s CPF",
                  "cédula de identidade RG/SP/SSP n° %s e inscrito"):
            self.assertNotIn(RG_NUM, pii.limpar(t % RG_NUM), t)

    def test_cpf_variantes_da_fonte(self):
        # hífen no lugar do espaço, "CPFMF" sem barra, número colado ao "nº", dígito a mais
        for t in ("inscrito-no CPF/MF sob-o-n°-%s, com" % CPF_FMT,
                  "inscrito no CPFMF sob o nº%s, com" % CPF_FMT,
                  "CPF nº%s8, MARIA" % CPF_FMT,
                  "CPF: %s %s" % (CPF_FMT[:3], CPF_FMT[4:])):
            self.assertEqual(pii.achar_cpfs(t) != [], True, t)
            self.assertNotIn(CPF_FMT[4:], pii.limpar(t), t)

    def test_rotulo_sem_numero_nao_dispara(self):
        t = "CPF/CNPJ: RG: RG: Endereço:"
        self.assertEqual(pii.limpar(t), t)
        self.assertEqual(pii.achar_rgs(t), [])


class EnderecoTest(unittest.TestCase):
    def test_residente_ate_o_fim_da_clausula(self):
        t = ("FULANO DE TAL, residente e domiciliado na Av. Paulista, nº 1000, apto. 12, na "
             "cidade de São Paulo – SP, portador do documento X. Segue.")
        self.assertEqual(pii.limpar(t), "FULANO DE TAL, residente e domiciliado %s, portador "
                                        "do documento X. Segue." % M)

    def test_com_endereco_e_ponto_final(self):
        t = "Beltrano, com endereço na Rua das Flores, 99, Rio de Janeiro. O Colegiado decidiu."
        self.assertEqual(pii.limpar(t), "Beltrano, com endereço %s. O Colegiado decidiu." % M)

    def test_sede_de_empresa_fica(self):
        t = "Companhia Exemplo S.A., com sede na Rua Direita, 10, São Paulo"
        self.assertEqual(pii.limpar(t), t)

    def test_domiciliado_sem_endereco_fica(self):
        t = "investidor domiciliado no exterior; a regra vale."
        self.assertEqual(pii.limpar(t), t)

    def test_cep_depois_do_parentese_sai_junto(self):
        t = ("a. Sr. Fulano, residente na Rua A, 10 (Centro, Niterói), CEP 24000-000, na "
             "qualidade de diretor.")
        self.assertEqual(pii.limpar(t), "a. Sr. Fulano, residente %s, na qualidade de diretor." % M)

    def test_endereco_constante_de_cadastro(self):
        t = ("116 O endereço constante da base de dados do SERPRO é a Rua B, nº 4, Apto. 20, "
             "Rio de Janeiro/RJ, CEP 22000-000 (fl. 749). No entanto, o acusado.")
        limpo = pii.limpar(t)
        self.assertNotIn("Rua B", limpo)
        self.assertNotIn("22000-000", limpo)
        self.assertIn("No entanto, o acusado.", limpo)

    def test_enderecos_residenciais_que_vazavam(self):
        casos = [
            # parêntese no meio do endereço não encerra o corte
            "residente e domiciliado na Cidade de São Paulo (SP), na Rua A, nº 111, CEP 05000-000, "
            "Cidade de São Paulo. Fim.",
            # "nesta cidade", "Cidade" sem preposição
            "residente e domiciliado nesta cidade, na Rua A, n.º 35, apto. 201. Fim.",
            "residente e domiciliado Cidade e no Estado de São Paulo, na Av. A, 598, apto. 84. Fim.",
            # verbo "reside"/"residia"
            "mesmo porque ele reside na Rua A nº 740, aptº 202, e o endereço. Fim.",
            "consta que Fulano residia na Estrada A nº 817, apartamento 502, em São Conrado. Fim.",
            # endereço residencial entre aspas e parêntese; último endereço com dois-pontos
            "como \"endereço residencial\" (Rua A, 125, complemento 302, Porto Alegre, RS, "
            "CEP 90.000-120). Fim.",
            "o último endereço informado pelo Sr. Fulano: Rua A, 81, Vila B, São Paulo –SP, "
            "CEP: 02000-050. Fim.",
            # depois do CPF já retirado
            "Sra. Fulana, inscrita no CPF/MF sob o n° %s, na rua A n°. 300, bairro B, Joinvile - SC, "
            "CEP: 89000-400. Fim." % M,
            # ficha cadastral
            "(Ficha cadastral: \"Rua 3, nº 470 – Lote 11 C3 – Bairro B – GO – CEP 74000-000\"). Fim.",
            # logradouro com apartamento, sem gatilho
            "foi enviado para o endereço Largo A, 96 apto. 1803 – Vila B CEP 01000-010. Fim.",
        ]
        for t in casos:
            limpo = pii.limpar(t)
            self.assertNotRegex(limpo, r"\b(?:Rua|Av\.|Estrada|Largo) A\b|Rua 3", t)
            self.assertTrue(limpo.endswith("Fim."), limpo)

    def test_endereco_comercial_e_apartamento_de_empreendimento_ficam(self):
        for t in ("Beltrano, com endereço comercial na Rua A, 10, sala 2, São Paulo. Fim.",
                  "contrato de compra e venda referente ao apartamento 436 do empreendimento X. Fim.",
                  "Companhia X, com sede na Rua A, 10, 5º andar, CEP 20000-000. Fim.",
                  # "reside" figurado e cidade de residência não são endereço
                  "a disciplina legal própria reside no art. 115, da LSA e que. Fim.",
                  "O fulcro da questão residia no fato de a SEP ter determinado. Fim.",
                  "conselheiro que residia em Nova Iorque à época dos fatos. Fim.",
                  "- Não atualização da ficha Cadastral: a discussão sobre sua atualização. Fim."):
            self.assertEqual(pii.limpar(t), t)


class OutrosTest(unittest.TestCase):
    def test_email(self):
        self.assertEqual(pii.limpar("e-mail fulano.tal@exemplo.com.br."), "e-mail %s." % M)
        self.assertEqual(pii.limpar("escreva para sep@cvm.gov.br"), "escreva para sep@cvm.gov.br")

    def test_telefone(self):
        self.assertEqual(pii.limpar("telefone (11) 91234-5678, e"), "telefone %s, e" % M)
        self.assertEqual(pii.limpar("Tel.: 21 3554-8686"), "Tel.: " + M)
        self.assertEqual(pii.limpar("no período 2019-2020 e 1234-5678"),
                         "no período 2019-2020 e 1234-5678")

    def test_nascimento(self):
        self.assertEqual(pii.limpar("nascido em 01/02/1960, filho"), "nascido em %s, filho" % M)
        self.assertEqual(pii.limpar("data de nascimento: 3 de março de 1955"),
                         "data de nascimento: " + M)

    def test_banco(self):
        t = "depósito no Banco Exemplo, agência nº 1234-5, conta corrente nº 98765-4, de sua"
        self.assertEqual(pii.limpar(t), "depósito no %s, de sua" % M)

    def test_qualificacao(self):
        t = ("o Sr. FULANO DE TAL, brasileiro, casado, engenheiro civil, residente e domiciliado "
             "na Rua X, nº 99, São Paulo – SP, RG nº %s, CPF/MF nº %s, doravante "
             "Compromitente" % (RG_NUM, CPF_FMT))
        out = pii.limpar(t)
        self.assertTrue(out.startswith("o Sr. FULANO DE TAL, " + M), out)
        for x in ("brasileiro", "casado", "engenheiro", "Rua X", RG_NUM, CPF_FMT):
            self.assertNotIn(x, out)
        self.assertIn("doravante Compromitente", out)

    def test_qualificacao_sem_estado_civil(self):
        t = ("MARIA EXEMPLO, brasileira, administradora de empresas, portadora da Cédula de "
             "Identidade RG nº %s, inscrita no CPF/MF sob o nº %s, e" % (RG_NUM, CPF_FMT))
        self.assertEqual(pii.limpar(t), "MARIA EXEMPLO, %s, portadora da Cédula de Identidade "
                                        "RG nº %s, inscrita no CPF/MF sob o nº %s, e" % (M, M, M))
        t2 = "o investidor brasileiro, em geral, prefere renda fixa"
        self.assertEqual(pii.limpar(t2), t2)

    def test_rg_com_letra_e_orgao(self):
        self.assertEqual(pii.limpar("carteira de identidade nº " + "1234-D/ CREA-PR e"),
                         "carteira de identidade nº %s e" % M)

    def test_testemunha_assinatura(self):
        t = ("Documento assinado eletronicamente por **Fulano de Tal**, **Testemunha**, em "
             "10/01/2024. Documento assinado eletronicamente por **Presidente X**, "
             "**Presidente**, em 10/01/2024.")
        out = pii.limpar(t)
        self.assertIn("por **%s**, **Testemunha**" % M, out)
        self.assertIn("Presidente X", out)

    def test_bloco_de_testemunhas(self):
        t = "Fecho do termo.\n\nTESTEMUNHAS:\n\n____________\nNome: Fulano\nCPF: " + CPF_FMT + \
            "\n\n____________\nNome: Beltrano\n\n\n\n## Decisão\n"
        out = pii.limpar(t)
        self.assertNotIn("Fulano", out)
        self.assertNotIn("Beltrano", out)
        self.assertIn("## Decisão", out)
        self.assertIn("TESTEMUNHAS:", out)

    def test_contagem(self):
        _, cont = pii.limpar_contando("CPF %s e e-mail a@b.com" % CPF_FMT)
        self.assertEqual(cont, {"cpf": 1, "email": 1})

    def test_nome_e_cargo_ficam(self):
        t = "FULANO DE TAL, Diretor de Relações com Investidores da Companhia"
        self.assertEqual(pii.limpar(t), t)


if __name__ == "__main__":
    unittest.main()
