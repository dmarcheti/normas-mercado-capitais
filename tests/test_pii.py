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


class Fase3bTest(unittest.TestCase):
    """Casos da auditoria da Fase 3b: um positivo (sai) e um negativo (fica) por regra. Nomes e
    números fictícios."""

    # --- dado pessoal que ficava
    def test_ci_de_portador_sai(self):
        t = "FULANO DE TAL, portador da C.I n.\nº" + "8765" + "432-1 e portador do CPF"
        self.assertNotIn("8765", pii.limpar(t))

    def test_ci_comunicacao_interna_fica(self):
        t = "conforme a C.I. nº " + "1234" + "/2005 da SEP"
        self.assertEqual(pii.limpar(t), t)

    def test_cedula_rne_sai(self):
        t = "portador da Cédula de Identidade RNE nº W" + "123" + "456K, inscrito"
        self.assertEqual(pii.limpar(t), "portador da Cédula de Identidade RNE nº %s, inscrito" % M)

    def test_rne_sem_numero_fica(self):
        t = "o estrangeiro tem RNE válido, conforme o processo"
        self.assertEqual(pii.limpar(t), t)

    def test_endereco_no_exterior_sai_inteiro(self):
        t = ("BELTRANO EXEMPLAR, domiciliado na Suíça, na Cidade de St. Exemplo, à Rua Exemplostrasse 4, "
             "3rd Flr, CH – 900; CICRANO DA SILVA, brasileiro")
        saida = pii.limpar(t)
        self.assertNotIn("Exemplostrasse", saida)
        self.assertIn("; CICRANO DA SILVA", saida)

    def test_endereco_nacional_com_abreviacao_st_fica_ate_o_fim(self):
        t = "Sede da Companhia na Rua St. Exemplo, 10. O Colegiado decidiu."
        self.assertEqual(pii.limpar(t), t)

    def test_bloco_de_testemunhas_com_resto_na_linha_sai(self):
        t = ("Testemunhas: Wxyz\nNome: FULANO DE TAL Nome:\nCPF: CPF:\nBeltrana Exemplo\n"
             "8º Cartório de Notas da Capital\nReconheço por semelhança a firma de BELTRANA EXEMPLO\n"
             "\n\n\nO Colegiado aprovou a proposta de termo de compromisso apresentada pelos proponentes.")
        saida = pii.limpar(t)
        self.assertNotIn("FULANO", saida)
        self.assertNotIn("Beltrana", saida)
        self.assertNotIn("BELTRANA", saida)  # o carimbo do cartório repete o nome da testemunha
        self.assertTrue(saida.startswith("Testemunhas: " + M))
        self.assertIn("O Colegiado aprovou a proposta", saida)

    def test_testemunhas_em_frase_longa_fica(self):
        t = "Testemunhas: foram ouvidas três pessoas durante a instrução do processo administrativo."
        self.assertEqual(pii.limpar(t), t)

    def test_qualificacao_com_dois_segmentos_sai(self):
        t = "FULANO DE TAL, brasileiro, casado, economista, portador da Cédula"
        self.assertEqual(pii.limpar(t), "FULANO DE TAL, %s, portador da Cédula" % M)
        t = "FULANO DE TAL, brasileiro, estado civil, profissão, portador da Cédula"
        self.assertEqual(pii.limpar(t), "FULANO DE TAL, %s, portador da Cédula" % M)

    def test_separado_judicialmente_sai(self):
        t = "FULANO DE TAL, brasileiro, separado judicialmente, economista, portador da Cédula"
        self.assertEqual(pii.limpar(t), "FULANO DE TAL, %s, portador da Cédula" % M)

    def test_qualificacao_nao_engole_documento_seguinte(self):
        t = ("FULANO DE TAL, brasileiro, economista, portador da\nCédula de Identidade nº " + RG_NUM +
             ", CPF: " + CPF_FMT + ", domiciliado")
        saida = pii.limpar(t)
        self.assertIn("portador da\nCédula de Identidade nº " + M, saida)
        self.assertIn("CPF: " + M, saida)

    # --- corte indevido
    def test_endereco_para_em_tendo_em_vista(self):
        t = ("residente e domiciliado na Rua das Flores, 99, Rio de Janeiro, RJ, tendo em vista a proposta "
             "formulada nos autos do Processo")
        self.assertEqual(pii.limpar(t), "residente e domiciliado %s, tendo em vista a proposta formulada "
                                        "nos autos do Processo" % M)

    def test_endereco_sem_delimitador_continua_cortado(self):
        t = "residente na Rua das Flores, 99, Rio de Janeiro, RJ"
        self.assertEqual(pii.limpar(t), "residente %s" % M)

    def test_endereco_para_no_compromitente_seguinte(self):
        t = "domiciliado na Rua das Flores, 99, São Paulo, SP, e BELTRANO EXEMPLAR, brasileiro"
        self.assertIn(", e BELTRANO EXEMPLAR", pii.limpar(t))
        t = "domiciliado na Rua A, 1, CEP 01000-000 e BELTRANO EXEMPLAR, brasileiro"
        self.assertIn(" e BELTRANO EXEMPLAR", pii.limpar(t))
        t = "domiciliado na Rua A, 1, Botafogo, BELTRANO EXEMPLAR\nDA SILVA, brasileiro"
        self.assertIn("BELTRANO EXEMPLAR\nDA SILVA", pii.limpar(t))

    def test_endereco_e_estado_em_minuscula_continua_cortado(self):
        t = "domiciliado na Rua A, 1, Centro e Rio de Janeiro"
        self.assertNotIn("Rua A", pii.limpar(t))

    def test_endereco_para_em_outra_parte_qualificada(self):
        t = ("residente e domiciliado na Rua A, 1, São Paulo, e EXEMPLO WORLDWIDE\nLTD., pessoa jurídica "
             "de direito privado")
        self.assertIn("e EXEMPLO WORLDWIDE\nLTD., pessoa jurídica", pii.limpar(t))

    def test_endereco_para_em_todos(self):
        t = "domiciliado na Rua A, 1, São Paulo, todos, administradores da Exemplo S/A"
        self.assertIn(", todos, administradores da Exemplo S/A", pii.limpar(t))

    def test_endereco_na_sede_da_empresa_fica(self):
        t = ("FULANO DE TAL, inscrito no CPF sob o nº " + CPF_FMT + ", com endereço na Praça Exemplo, 100, "
             "Torre Sul, Piso Banco Exemplo, São Paulo, SP, tendo em vista")
        saida = pii.limpar(t)
        self.assertIn("com endereço na Praça Exemplo, 100", saida)
        self.assertNotIn(CPF_FMT, saida)

    def test_com_endereco_residencial_sem_empresa_sai(self):
        t = "FULANO DE TAL, com endereço na Praça Exemplo, 100, apto. 12, São Paulo, SP, tendo em vista"
        self.assertNotIn("Praça Exemplo", pii.limpar(t))

    def test_domiciliada_no_exterior_fica(self):
        t = ("a Exemplo Ltd., entidade\ndomiciliada no exterior cujo beneficiário final no Brasil era o "
             "próprio Fulano, realizou 32 operações")
        self.assertEqual(pii.limpar(t), t)

    def test_domiciliado_no_exterior_com_endereco_sai(self):
        t = "FULANO DE TAL, domiciliado no exterior, na Rua Exemplo 4, Zurique; e"
        self.assertNotIn("Rua Exemplo", pii.limpar(t))


class Fase3bVarreduraTest(unittest.TestCase):
    """Resíduos achados na varredura final da Fase 3b."""

    def test_bloco_de_testemunhas_para_em_tabela_retomada(self):
        t = ("Testemunhas:\nFULANA EXEMPLO BELTRANO EXEMPLO\nFundo Alfa FIA 12345 Transferido em\n"
             "4. Reclamante: Empresa Exemplo Ltda.\n5. Reclamante: Outra Exemplo S.A.\n")
        r = pii.limpar(t)
        self.assertNotIn("FULANA", r)
        self.assertIn("Fundo Alfa FIA 12345 Transferido em", r)
        self.assertIn("4. Reclamante: Empresa Exemplo Ltda.", r)

    def test_bloco_de_testemunhas_para_no_titulo_de_anexo(self):
        for titulo in ("Anexo 1", "ANEXO I", "ANEXO II - Declaração"):
            t = ("Testemunhas:\nNome: FULANA EXEMPLO\nCPF:\nNome: BELTRANO EXEMPLO\nCPF:\n"
                 + titulo + "\n\"Na qualidade de ex-diretor, o declarante reconhece o dever.\"\n")
            r = pii.limpar(t)
            self.assertNotIn("FULANA", r)
            self.assertNotIn("BELTRANO", r)
            self.assertIn("\n" + titulo + "\n\"Na qualidade", r)

    def test_bloco_de_testemunhas_segue_no_carimbo_com_ruido(self):
        t = ("Testemunhas:\nNome: FULANA EXEMPLO\n48 x#1\nReconheço por semelhança a firma de\n"
             "BELTRANO EXEMPLO\nEscrevente autorizado\n")
        r = pii.limpar(t)
        self.assertNotIn("FULANA", r)
        self.assertNotIn("BELTRANO", r)

    def test_testemunha_no_singular_em_depoimento_nao_estende(self):
        t = "Testemunha: Sim, confirmo.\nfaça e o efeito seja positivo.\nAdvogado: Uma pergunta.\n"
        r = pii.limpar(t)
        self.assertIn("faça e o efeito seja positivo.", r)
        self.assertIn("Advogado: Uma pergunta.", r)

    def test_identidade_com_n_maiusculo(self):
        t = "portador da carteira de identidade Nº " + "07.140" + ".649-0, emitida pelo IFP e inscrito"
        self.assertEqual(pii.limpar(t), "portador da carteira de identidade Nº %s e inscrito" % M)
        # negativo: "Nº" de norma não é documento
        self.assertEqual(pii.limpar("art. 2º da Lei Nº 6.385, de 1976"), "art. 2º da Lei Nº 6.385, de 1976")

    def test_rne_com_letras_antes_do_numero(self):
        for num in ("RNE-W-" + "208-029-0", "W-" + "476.929-S"):
            t = "portador da Cédula de Identidade nº %s, inscrito" % num
            self.assertEqual(pii.limpar(t), "portador da Cédula de Identidade nº %s, inscrito" % M, num)
        # negativo: sigla com hífen sem rótulo de identidade fica
        self.assertEqual(pii.limpar("operação W-208 na B3, e"), "operação W-208 na B3, e")

    def test_identidade_de_conselho_com_tres_digitos(self):
        t = "portador da cédula de identidade n° " + "83" + "1, emitida pelo 6o CRA (MG), inscrito"
        self.assertEqual(pii.limpar(t), "portador da cédula de identidade n° %s, emitida pelo 6o CRA (MG), inscrito" % M)
        # negativo: 3 dígitos sem rótulo de identidade não bastam
        self.assertEqual(pii.limpar("RG nº 831, e"), "RG nº 831, e")

    def test_cabecalho_de_testemunhas_no_meio_da_linha(self):
        t = ("Jean Exemplo\nPRIMEIRO Testemunhas: PRIMEIRO\nTABELIONATO\nNome: Fulano Exemplo Nome:\n"
             "CPF: %s CPF:\n\n\n\nO Colegiado decidiu." % M)
        saida = pii.limpar(t)
        self.assertNotIn("Fulano", saida)
        self.assertIn("O Colegiado decidiu.", saida)
        # negativo: "provar com testemunhas:" em citação de lei não é bloco de assinatura
        t = "É lícito à parte inocente provar com testemunhas:\nI - nos contratos simulados"
        self.assertEqual(pii.limpar(t), t)


class Fase3bReauditoriaTest(unittest.TestCase):
    """Bloco de assinatura de termo digitalizado por OCR sem o cabeçalho "Testemunhas"."""

    def test_rg_com_virgula_do_ocr_depois_de_rotulo(self):
        t = "RG/SSP/SP n° " + "12,345" + ".678-9\n"
        self.assertEqual(pii.limpar(t), "RG/SSP/SP n° %s\n" % M)
        t = "portador da carteira de identidade nº " + "12,345" + ".678-9, inscrito"
        self.assertEqual(pii.limpar(t), "portador da carteira de identidade nº %s, inscrito" % M)
        # três dígitos antes da vírgula: a vírgula colada não encerra o número
        t = "RG nº " + "123,456" + ".789-0, inscrito"
        self.assertEqual(pii.limpar(t), "RG nº %s, inscrito" % M)

    def test_rg_com_rotulo_trocado_pelo_ocr_antes_de_ssp(self):
        t = "TG/SSP/SP n° " + "12,345" + ".678*9\n"
        self.assertEqual(pii.limpar(t), "TG/SSP/SP n° %s\n" % M)

    def test_valor_com_virgula_sem_rotulo_fica(self):
        self.assertEqual(pii.limpar("multa de R$ " + "98,765" + ".432 e"), "multa de R$ " + "98,765" + ".432 e")
        self.assertEqual(pii.limpar("taxa de " + "12,345" + ".678-9 ao ano"), "taxa de " + "12,345" + ".678-9 ao ano")
        self.assertEqual(pii.limpar("SSP/SP n° " + "12,345" + ".678"), "SSP/SP n° " + "12,345" + ".678")

    def test_nome_de_testemunha_sem_cabecalho_com_rg(self):
        t = ("Rio de Janeiro, 28 de setembro de 2017.\nFULANO COMPROMITENTE\n"
             "Nome: FULANA EXEMPLO DE TAL Nome:\nRG/SSP/SP n° " + RG_NUM + "\nCPF: CPF:\n\nTexto seguinte.")
        r = pii.limpar(t)
        self.assertNotIn("FULANA", r)
        self.assertIn("Nome: %s Nome:" % M, r)
        self.assertIn("FULANO COMPROMITENTE", r)
        self.assertIn("Texto seguinte.", r)

    def test_nome_sem_dois_pontos_do_ocr(self):
        t = "NOme FULANA EXEMPLO DE TAL\nNome:\nRG/SSP/SP n° " + RG_NUM + "\nCPF:\n"
        r = pii.limpar(t)
        self.assertNotIn("FULANA", r)
        self.assertTrue(r.startswith("NOme %s\nNome:\nRG" % M), r)

    def test_nome_na_linha_seguinte_em_duas_colunas(self):
        t = ("Nome: Nome:\nFULANO EXEMPLO DE TAL BELTRANO F. DA SILVA\n"
             "Brasileiro, casado, administrador, CONTADOR\nCPF: CPF:\n"
             "Res. N/ Capital - CPF " + CPF_FMT + " CRC/RS 12.345\nTexto seguinte.")
        r = pii.limpar(t)
        for x in ("FULANO", "BELTRANO", "CONTADOR", "Capital", "12.345", "CRC"):
            self.assertNotIn(x, r, x)
        self.assertIn("Nome: Nome:\n%s\n%s\nCPF: CPF:\n" % (M, M), r)
        self.assertIn("Texto seguinte.", r)

    def test_nome_de_empresa_sem_documento_fica(self):
        t = "Nome: ACME S.A.\nCargo: Diretor\nData: 01/02/2017\nAssinatura: ____\nCPF: " + M
        self.assertEqual(pii.limpar(t), t)
        t = "Nome: ACME S.A.\nEndereço comercial: Av. Exemplo\n"
        self.assertEqual(pii.limpar(t), t)

    def test_nome_no_corpo_sem_rotulo_fica(self):
        t = ("O Diretor FULANO EXEMPLO votou com a relatora.\nNome da companhia: ACME S.A.\n"
             "CPF dos administradores consta do processo.")
        self.assertEqual(pii.limpar(t), t)

    def test_cabecalho_de_tabela_de_cadastro_fica(self):
        t = ("NOME DO CLIENTE IRREGULARIDADES FLS.\nFulano Exemplo Não consta renda mensal; e\n103 e 104\n"
             "Beltrano Exemplo " + "Não possuiu cópia do CPF. Não declarou rendimento mensal. " * 3 + "\n")
        self.assertEqual(pii.limpar(t), t)

    def test_nome_com_acento_e_ruido_de_ocr(self):
        t = "Nóme: Fulana Exemplo Nome: Beltrana A. de 1\nCPF: CPF:\n"
        self.assertEqual(pii.limpar(t), "Nóme: %s Nome: %s\nCPF: CPF:\n" % (M, M))
        t = "Nome: 2ILMA EXEMPLO Nome: Fulana\nCPF: CPF:\n"
        self.assertEqual(pii.limpar(t), "Nome: %s Nome: %s\nCPF: CPF:\n" % (M, M))

    def test_linha_seguinte_com_texto_nao_e_cortada(self):
        t = "Nome:\nRG/SSP/SP n° " + RG_NUM + "\nCPF:\n"
        self.assertEqual(pii.limpar(t), "Nome:\nRG/SSP/SP n° %s\nCPF:\n" % M)


class Fase3bConv6Test(unittest.TestCase):
    """Nome de testemunha cortado no bloco de assinatura sai também no resto do documento."""

    def test_nome_da_testemunha_sai_no_carimbo_com_quebra_de_linha(self):
        # cvm-col-20170829-d0776: o carimbo do cartório repete o nome, quebrado em duas linhas
        t = ("Nome: FULANA EXEMPLO DE TAL Nome:\nRG/SSP/SP n° " + RG_NUM + "\nCPF: CPF:\n\n"
             "SUBDISTRITO\nReconheço por semelhança a firma de IL Fulana Exemplo de\nTal, "
             "com valor econômico.")
        r = pii.limpar(t)
        self.assertNotIn("FULANA", r.upper())
        self.assertIn("firma de IL %s, com valor" % M, r)

    def test_nome_do_bloco_fica_no_texto_corrido(self):
        # cvm-col-20141202-d10: o compromitente assina com "Nome:" no bloco digitalizado; o nome
        # sai do bloco e do carimbo, mas fica no relatório, onde é parte do processo
        relato = ("O proponente Fulano Exemplo Rampon apresentou proposta de termo de compromisso. "
                  * 3)
        t = (relato + "\n" + "Parágrafo do voto sem dados de ninguém. " * 6 + "\n"
             "Nome: FULANO EXEMPLO RAMPON Nome:\nRG/SSP/SP n° " + RG_NUM + "\nCPF: CPF:\n\n"
             "Reconheço por semelhança a firma de Fulano Exemplo\nRampon, com valor econômico.")
        r = pii.limpar(t)
        self.assertEqual(r.count("O proponente Fulano Exemplo Rampon apresentou"), 3)
        self.assertIn("firma de %s, com valor" % M, r)
        self.assertNotIn("FULANO EXEMPLO RAMPON", r)

    def test_nome_da_testemunha_do_cabecalho_e_da_assinatura_eletronica(self):
        t = ("Testemunhas:\nNome: Beltrana Exemplo Silva\nCPF: " + CPF_FMT + "\n\n"
             "Documento assinado eletronicamente por Sicrano Exemplo, Testemunha, em 01/02/2020.\n"
             "Texto: Beltrana Exemplo Silva e Sicrano Exemplo assinam.")
        r = pii.limpar(t)
        self.assertNotIn("Beltrana", r)
        self.assertNotIn("Sicrano", r)
        self.assertIn("Texto: %s e %s assinam." % (M, M), r)

    def test_nome_de_uma_palavra_e_outros_nomes_ficam(self):
        t = ("Nome: FULANA Nome:\nRG/SSP/SP n° " + RG_NUM + "\nCPF: CPF:\n\n"
             "A Fulana Exemplo e FULANA votaram; Beltrano Exemplo também.")
        r = pii.limpar(t)
        self.assertIn("A Fulana Exemplo e FULANA votaram; Beltrano Exemplo também.", r)

class Fase3bReauditoria2Test(unittest.TestCase):
    """Re-auditoria da semente 20261105: passaporte, regime de bens, profissão e "residentes no"."""

    def test_passaporte_e_nacionalidade_saem_escritorio_fica(self):
        t = ("FULANO EXEMPLO, americano,\npassaporte americano nº " + "034768885" +
             ", com escritório na Dayton Avenue, nº 20, Connecticut")
        r = pii.limpar(t)
        self.assertNotIn("034768885", r)
        self.assertNotIn("americano,", r)
        self.assertIn("com escritório na Dayton Avenue", r)

    def test_formatos_de_passaporte(self):
        for t, num in (("portador do passaporte nº CK " + "083355" + ", emitido pelo DPF-RJ", "083355"),
                       ("portadora do Passaporte Espanhol nº XD " + "195931" + ", residente", "195931"),
                       ("portador do Passaporte n° G" + "03962146" + ", e", "03962146"),
                       ("passaporte da Argentina n° 08." + "104.991" + "-M, com", "104.991")):
            self.assertNotIn(num, pii.limpar(t), t)
        for t in ("apresentou cópia de Passaporte Chinês, emitido em 22.05.1997, com validade",
                  "reuniões sobre o passaporte europeu de fundos, realizadas de 22 a 28"):
            self.assertEqual(pii.limpar(t), t)

    def test_regime_de_bens_e_profissao_saem(self):
        for t in ("FULANO DE TAL, brasileiro, casado sob regime de comunhão universal de bens, "
                  "industrial, portador da Cédula de Identidade",
                  "BELTRANO EXEMPLO, brasileiro, casado sob o regime de comunhão parcial de\n"
                  "bens, empresário, portador da Cédula de Identidade"):
            r = pii.limpar(t)
            for fora in ("regime", "bens", "industrial", "empresário"):
                self.assertNotIn(fora, r, t)
            self.assertIn("portador da Cédula de Identidade", r)

    def test_nacionalidade_e_profissao_antes_de_com_escritorio(self):
        t = ("CICRANO EXEMPLO, brasileiro, administrador de empresas com escritório na Rua "
             "Exemplo, nº 78, conj. 91, Cidade Exemplo")
        r = pii.limpar(t)
        self.assertNotIn("brasileiro", r)
        self.assertNotIn("administrador de empresas", r)
        self.assertIn("com escritório na Rua Exemplo, nº 78", r)

    def test_residentes_no_brasil_nao_e_endereco(self):
        for t in ("restrição à negociação por pessoas residentes no Brasil, não tendo sido "
                  "adotados os\ncuidados previstos no PO CVM 33;",
                  "investidores residentes no exterior podem aplicar",
                  "pessoas domiciliadas no país"):
            self.assertEqual(pii.limpar(t), t)


if __name__ == "__main__":
    unittest.main()

class Fase3bReauditoria3Test(unittest.TestCase):
    """Re-auditoria da semente 20261106: RG "expedida pelo IFP sob o nº", ponto do OCR no meio
    do endereço e linha "CPF:" deformada pelo OCR no bloco de assinatura."""

    def test_rg_com_orgao_antes_do_numero(self):
        t = ("FULANO DE TAL, portador da carteira de identidade expedida pelo IFP\nsob o nº "
             + "04625996" + "-6, e do CPF/MF")
        self.assertNotIn("04625996", pii.limpar(t))

    def test_ponto_do_ocr_no_meio_do_logradouro(self):
        t = ("FULANO DE TAL, brasileiro, domiciliado na Rua\nProfessor Exemplo. Menicucci, "
             "111, Mangabeiras, Belo Horizonte, MG, BELTRANO DE TAL, brasileiro")
        r = pii.limpar(t)
        for fora in ("Menicucci", "111", "Mangabeiras"):
            self.assertNotIn(fora, r)
        self.assertIn("BELTRANO DE TAL", r)

    def test_linha_cpf_deformada_pelo_ocr(self):
        t = "(t.:Jltlh} Ji\nCPF: 11 /0· 11'1. -l)o\n11' OFICIO"
        self.assertNotIn("11 /0", pii.limpar(t))
        for t in ("CPF: não informado", "o CPF: documento exigido"):
            self.assertEqual(pii.limpar(t), t)

    def test_rg_com_letra_e_hifen_no_fim_da_linha(self):
        t = "portador da Cédula de Identidade RG nº M-\n" + "1.263" + ".895, emitida pela SSP/DF, inscrito"
        r = pii.limpar(t)
        self.assertNotIn("263", r)
        self.assertIn("inscrito", r)

    def test_nacionalidades_estrangeiras(self):
        for nac in ("norueguês", "guatemalteco", "sueca", "estadunidense"):
            t = "FULANO DE TAL, %s, casado, economista, portador da Cédula" % nac
            r = pii.limpar(t)
            self.assertNotIn(nac, r)
            self.assertNotIn("economista", r)

