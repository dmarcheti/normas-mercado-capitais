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

    def test_nome_da_testemunha_sem_acento_no_carimbo(self):
        t = ("Cláusula final do termo, com João Exemplo Fictício Teste citado no mérito.\n"
             "JOAO EXEMPLO FICTICIO TESTE.. Reconheço a(s) firma(s) de por SEMELHANCA:")
        spans = pii._outras_ocorrencias(t, ["João Exemplo Fictício Teste"])
        self.assertEqual([t[a:b] for a, b in spans], ["JOAO EXEMPLO FICTICIO TESTE"])

    def test_nome_abreviado_no_bloco_por_extenso_no_carimbo(self):
        t = ("O termo foi assinado.\n"
             "Reconheço a(s) firma(s) de por SEMELHANÇA\nJOAO PEDRO MARTINS DO EXEMPLO DE FICTICIO\n")
        spans = pii._outras_ocorrencias(t, ["João P. M Fictício"])
        self.assertEqual([t[a:b] for a, b in spans], ["JOAO PEDRO MARTINS DO EXEMPLO DE FICTICIO"])


    def test_compromitente_seguido_de_cpf_fica(self):
        # o "Nome:" do bloco digitalizado traz o compromitente; na qualificação ele é parte e fica
        t = ("outro, o doravante denominado COMPROMITENTE, FULANO EXEMPLO, inscrito no CPF/MF\n"
             "sob o nº X, com endereço Y.")
        self.assertEqual(pii._outras_ocorrencias(t, ["Fulano Exemplo"]), [])

    def test_cpf_com_dois_pontos_do_ocr(self):
        t = "Nome: Fulano Nome: Beltrano\nCPF: 123: 456" + ".789-09 CPF: 987.654" + ".321-00\nFeconheço"
        r = pii.limpar(t)
        self.assertNotIn("456.789", r)
        self.assertNotIn("654.321", r)


class Fase4FraseTestemunhasTest(unittest.TestCase):
    """Task 1b: "Na qualidade de testemunhas, assinaram <nome> e <nome>" no fecho das decisões do
    Colegiado sobre termo de compromisso (cvm-col-20220222-d2485)."""

    def test_frase_com_dois_nomes(self):
        t = "*Na qualidade de testemunhas, assinaram Fulana Exemplo de Tal e Beltrano Exemplo Silva*"
        self.assertEqual(pii.limpar(t),
                         "*Na qualidade de testemunhas, assinaram %s e %s*" % (M, M))

    def test_italico_quebrado_no_primeiro_nome(self):
        # cvm-col-20250401-d3245: o HTML fecha o itálico depois da primeira letra do nome
        t = "*Na qualidade de testemunhas, assinaram* F*ulana Exemplo de Tal e Beltrano Exemplo*"
        self.assertEqual(pii.limpar(t),
                         "*Na qualidade de testemunhas, assinaram* %s e %s*" % (M, M))

    def test_tres_nomes_e_ponto_final(self):
        t = ("Na qualidade de testemunhas, assinaram Fulana Exemplo, Beltrano Exemplo e "
             "Sicrana Exemplo Teste.")
        self.assertEqual(pii.limpar(t),
                         "Na qualidade de testemunhas, assinaram %s, %s e %s." % (M, M, M))

    def test_diretores_na_mesma_frase_ficam(self):
        # cvm-col-20210608-d2058: diretores assinam o original; só as testemunhas saem
        t = ("*Original assinado por Diretor Exemplo Um, Diretora Exemplo Dois e Diretor Exemplo "
             "Tres. Na qualidade de testemunhas, assinaram Fulana Exemplo e Beltrano Exemplo.*")
        r = pii.limpar(t)
        self.assertIn("Original assinado por Diretor Exemplo Um, Diretora Exemplo Dois e "
                      "Diretor Exemplo Tres.", r)
        self.assertIn("assinaram %s e %s.*" % (M, M), r)

    def test_variantes(self):
        casos = {
            "Na qualidade de testemunha, assinou Fulana Exemplo.":
                "Na qualidade de testemunha, assinou %s." % M,
            "Como testemunhas, assinaram Fulana Exemplo e Beltrano Exemplo.":
                "Como testemunhas, assinaram %s e %s." % (M, M),
            "Assinaram, na qualidade de testemunhas, Fulana Exemplo e Beltrano Exemplo.":
                "Assinaram, na qualidade de testemunhas, %s e %s." % (M, M),
            "Na qualidade de testemunhas, assinaram\nFulana Exemplo e Beltrano Exemplo\n":
                "Na qualidade de testemunhas, assinaram\n%s e %s\n" % (M, M),
        }
        for t, esperado in casos.items():
            self.assertEqual(pii.limpar(t), esperado, t)

    def test_nome_da_frase_sai_no_carimbo(self):
        t = ("Termo assinado.\n" + "Parágrafo sem dados de ninguém. " * 6 + "\n"
             "Reconheço por semelhança a firma de FULANA EXEMPLO DE TAL.\n"
             + "Outro parágrafo sem dados de ninguém. " * 6 + "\n"
             "Na qualidade de testemunhas, assinaram Fulana Exemplo de Tal e Beltrano Exemplo.")
        r = pii.limpar(t)
        self.assertNotIn("FULANA", r)
        self.assertIn("firma de %s." % M, r)

    def test_parte_que_assinou_como_testemunha_fica(self):
        # cvm-pas-19957-004416-2016-00 e crsfn-10372-100118-2023-67: o fato do processo
        casos = [
            "Como testemunhas, assinaram os conselheiros de administração Fulano Exemplo "
            "(indicado pelo grupo Alfa) e Beltrano Exemplo (grupo Beta).",
            "Fulano Exemplo e Beltrano Exemplo assinaram esses documentos na qualidade de "
            "testemunhas. Em manifestações apresentadas à CVM, ambos reconheceram a assinatura.",
            "Fulano Exemplo e Beltrano Exemplo voltaram a subscrever, como testemunhas, o Aditivo "
            "Contratual relativo a Sicrano Exemplo.",
            "Na qualidade de testemunhas, assinaram Fulano Exemplo e Beltrano Exemplo o contrato "
            "de mútuo, sem poderes de representação.",
        ]
        for t in casos:
            self.assertEqual(pii.limpar(t), t)

    def test_testemunhas_do_processo_ficam(self):
        casos = [
            "É lícito à parte inocente provar com testemunhas a simulação.",
            "O acusado requereu a oitiva de testemunhas, indeferida pelo Relator.",
            "As testemunhas de defesa arroladas por Fulano Exemplo foram ouvidas.",
            "Nos termos do art. 447 do CPC, podem depor como testemunhas todas as pessoas, "
            "exceto as incapazes, impedidas ou suspeitas.",
            "o documento foi assinado por duas testemunhas, com firma reconhecida.",
        ]
        for t in casos:
            self.assertEqual(pii.limpar(t), t)

    def test_nome_de_diretor_fica_mesmo_perto_da_frase(self):
        t = ("O Diretor Fulano Exemplo acompanhou o voto.\n"
             "*Original assinado por Fulano Exemplo e Beltrana Exemplo*\n\n"
             "*Na qualidade de testemunhas, assinaram Sicrano Teste e Sicrana Teste*")
        r = pii.limpar(t)
        self.assertEqual(r.count("Fulano Exemplo"), 2)
        self.assertIn("Beltrana Exemplo", r)
        self.assertNotIn("Sicran", r)


class Fase5TestemunhaNoTextoCorridoTest(unittest.TestCase):
    """T2 da Fase 5 (D2): sai o nome de quem aparece só como testemunha ou informante no texto
    corrido; fica o papel. Nomes fictícios; os padrões vêm do levantamento do acervo."""

    def _confere(self, casos):
        for t, esperado in casos.items():
            self.assertEqual(pii.limpar(t), esperado, t)

    def test_gatilho_seguido_do_nome(self):
        self._confere({
            "a oitiva da testemunha Fulano Exemplo de Tal, arrolada pela defesa.":
                "a oitiva da testemunha %s, arrolada pela defesa." % M,
            "o depoimento da testemunha Fulano Exemplo, operador da corretora Alfa, no sentido de":
                "o depoimento da testemunha %s, operador da corretora Alfa, no sentido de" % M,
            "Também a testemunha Fulano Exemplo solicitou e obteve a transferência.":
                "Também a testemunha %s solicitou e obteve a transferência." % M,
            "a prova oral trazida por Fulano Exemplo Silva, testemunha dos Reclamantes, de que":
                "a prova oral trazida por %s, testemunha dos Reclamantes, de que" % M,
            "o pedido de oitiva da testemunha Sr. Fulano Exemplo, arquiteto responsável":
                "o pedido de oitiva da testemunha Sr. %s, arquiteto responsável" % M,
            "o informante Fulano Exemplo afirmou que não sabia.":
                "o informante %s afirmou que não sabia." % M,
            "uma única testemunha, Fulano Exemplo de Tal, de modo que":
                "uma única testemunha, %s, de modo que" % M,
            "a testemunha por ele arrolada, Fulano Exemplo, designando o dia":
                "a testemunha por ele arrolada, %s, designando o dia" % M,
        })

    def test_nome_com_caixa_alta(self):
        self._confere({
            "a testemunha FULANO EXEMPLO DE TAL respondeu que não.":
                "a testemunha %s respondeu que não." % M,
        })

    def test_na_qualidade_de_testemunha(self):
        self._confere({
            "o indeferimento do pedido de oitiva de Fulano Exemplo, na qualidade de testemunha;":
                "o indeferimento do pedido de oitiva de %s, na qualidade de testemunha;" % M,
            "documentos encaminhados por Fulano Exemplo, na qualidade de testemunha, e anexados":
                "documentos encaminhados por %s, na qualidade de testemunha, e anexados" % M,
            "e (ii) oitiva de Fulano Exemplo Silva, este na qualidade de testemunha. Vale":
                "e (ii) oitiva de %s, este na qualidade de testemunha. Vale" % M,
        })

    def test_lista_corta_cada_nome(self):
        self._confere({
            "a oitiva das testemunhas Fulano Exemplo, Beltrano Exemplo dos Reis e Sicrano Exemplo.":
                "a oitiva das testemunhas %s, %s e %s." % (M, M, M),
            "requereu a oitiva, na condição de testemunhas, de Fulano Exemplo, Beltrano Exemplo "
            "dos Reis e Sicrano Exemplo, pedido que denego":
                "requereu a oitiva, na condição de testemunhas, de %s, %s e %s, pedido que denego"
                % (M, M, M),
            "decidi pela oitiva das testemunhas listadas (Fulano Exemplo, Beltrano Exemplo,\n"
            "Sicrano Exemplo, Fulana Exemplo e Beltrana Exemplo), intimando":
                "decidi pela oitiva das testemunhas listadas (%s, %s,\n%s, %s e %s), intimando"
                % (M, M, M, M, M),
        })

    def test_lista_com_aposto_depois_do_nome(self):
        self._confere({
            "dos depoimentos das testemunhas Fulana Exemplo, ex-funcionária da Alfa, e "
            "Beltrano Exemplo, operador da corretora Beta; k. tanto":
                "dos depoimentos das testemunhas %s, ex-funcionária da Alfa, e %s, operador da "
                "corretora Beta; k. tanto" % (M, M),
        })

    def test_titulo_depois_da_virgula_e_quebra_de_linha(self):
        self._confere({
            "Cita como testemunha de tal fato o seu agente\nautônomo, Sr. Fulano Exemplo, e acrescenta":
                "Cita como testemunha de tal fato o seu agente\nautônomo, Sr. %s, e acrescenta" % M,
        })

    def test_nome_quebrado_por_linha_em_branco(self):
        self._confere({
            "a desistência da oitiva da sua testemunha, Fulano Exemplo\n\nde Tal. Na oportunidade":
                "a desistência da oitiva da sua testemunha, %s. Na oportunidade" % M,
        })

    def test_paragrafo_novo_nao_entra_no_nome(self):
        t = "a oitiva da testemunha Fulano Exemplo\n\nAssim, concluo que"
        self.assertEqual(pii.limpar(t), "a oitiva da testemunha %s\n\nAssim, concluo que" % M)

    def test_nome_cortado_entra_na_lista_de_outras_ocorrencias(self):
        # o nome cortado vale também para o carimbo de firma no mesmo julgado
        t = ("A testemunha Fulano Exemplo de Tal depôs.\n" + "Parágrafo sem dados de ninguém. " * 6
             + "\nReconheço por semelhança a firma de FULANO EXEMPLO DE TAL.")
        r = pii.limpar(t)
        self.assertNotIn("FULANO", r)
        self.assertNotIn("Fulano", r)

    def test_negativos(self):
        casos = [
            "A prova testemunhal produzida não convenceu o Colegiado.",
            "o indeferimento da prova testemunhal requerida por Fulano Exemplo.",
            "o pedido de oitiva das testemunhas arroladas pela defesa foi indeferido.",
            "Foram ouvidas as testemunhas arroladas pela defesa, que confirmaram os fatos.",
            "a testemunha da Acusação afirmou que não presenciou os fatos.",
            "tendo a testemunha composto o Conselho de Administração, poderá atestar.",
            "a testemunha Beta Participações S.A. juntou documentos.",
            "o depoimento da testemunha Diretor Relator foi tomado em sessão.",
            # nome de parte que depôs: sem o gatilho colado, fica
            "O pedido de oitiva de outro acusado como testemunha. Fulano Exemplo interpôs recurso.",
            "Fulano Exemplo, depoente nos autos, afirmou que as ordens partiam do cliente.",
            "Fulano Exemplo e Beltrano Exemplo voltaram a subscrever, como testemunhas, o Aditivo "
            "Contratual relativo a Sicrano Exemplo.",
            "Como testemunhas, assinaram os conselheiros de administração Fulano Exemplo "
            "(indicado pelo grupo Alfa) e Beltrano Exemplo (grupo Beta).",
            "o cliente Fulano Exemplo assinou como testemunha no contrato social da DTVM.",
            # ato das partes (assinatura de contrato): "como testemunha Nome" fica
            "os documentos eram assinados por Fulano Exemplo e tinham como testemunha Beltrano "
            "Exemplo dos Santos, que é um dos proponentes.",
        ]
        for t in casos:
            self.assertEqual(pii.limpar(t), t, t)

    def test_mesmo_nome_em_outro_ponto_do_julgado_sai_tambem(self):
        neutro = "Parágrafo sem dados de ninguém. " * 8
        t = ("o indeferimento da oitiva de Fulano Exemplo, na qualidade de testemunha.\n" + neutro
             + "\nPrejudicado o pedido de depoimento de Fulano Exemplo, o Relator decidiu.\n" + neutro
             + "\nFULANO\nEXEMPLO não foi ouvido.\n" + neutro
             + "\nFulano Exemplo Santos é outra pessoa, e Fulano Exemplo de Tal também.")
        r = pii.limpar(t)
        self.assertEqual(r.count(M), 3)
        self.assertNotIn("depoimento de Fulano", r)
        self.assertIn("Fulano Exemplo Santos é outra pessoa", r)
        self.assertIn("Fulano Exemplo de Tal também", r)

    def test_enumeracao_com_membro_cortado_leva_os_outros_nomes(self):
        neutro = "Parágrafo sem dados de ninguém. " * 8
        t = ("a oitiva da testemunha Ana Exemplo, arrolada pela defesa.\n" + neutro
             + "\n212. Compareceram à CVM Ana Exemplo, Beto Exemplo, Caio\nExemplo e Davi Exemplo "
             "Silva. Este último substituiu, a pedido da Defesa, Eva Exemplo (fls. 2).\n")
        r = pii.limpar(t)
        self.assertIn("Compareceram à CVM %s, %s, %s e %s. Este último" % (M, M, M, M), r)
        self.assertIn("a pedido da Defesa, Eva Exemplo (fls. 2)", r)  # fora da enumeração: fica

    def test_enumeracao_com_marcador_no_meio_e_quebra_de_linha(self):
        t = ("a testemunha Ana Exemplo foi ouvida.\n"
             "Foram ouvidas Beto Exemplo,\nAna Exemplo e Caio Exemplo, que confirmaram.")
        r = pii.limpar(t)
        self.assertIn("Foram ouvidas %s,\n%s e %s, que confirmaram." % (M, M, M), r)

    def test_oitivas_no_plural_com_lista_de_nomes(self):
        self._confere({
            "- Oitivas de Ana Exemplo e Davi Exemplo Silva, para demonstrar a adequação do projeto":
                "- Oitivas de %s e %s, para demonstrar a adequação do projeto" % (M, M),
            "não seriam úteis as oitivas de Ana Exemplo, Beto Exemplo e Caio Exemplo, já que":
                "não seriam úteis as oitivas de %s, %s e %s, já que" % (M, M, M),
        })

    def test_enumeracao_e_oitiva_negativos(self):
        casos = [
            # singular: costuma ser a oitiva de um acusado
            "- Oitiva de Ana Exemplo, para demonstrar a adequação do projeto.",
            "o deferimento da oitiva de Ana Exemplo e de Beto Exemplo, acusados.",
            # lista de acusados sem nenhuma testemunha cortada
            "Participaram da operação os acusados Ana Exemplo, Beto Exemplo e Caio Exemplo.",
            # plural sem lista de nomes
            "Indeferidas as oitivas de Ana Exemplo, por desnecessárias.",
        ]
        for t in casos:
            self.assertEqual(pii.limpar(t), t, t)
        # verbo entre os membros: não é enumeração contígua; só a testemunha sai
        self.assertEqual(pii.limpar("Ana Exemplo interpôs recurso e a testemunha Beto Exemplo depôs."),
                         "Ana Exemplo interpôs recurso e a testemunha %s depôs." % M)

    def test_pedido_de_oitiva_de_parte_e_da_testemunha(self):
        t = ("deferi o pedido de oitiva de Ana Exemplo e da testemunha por ele arrolada, "
             "Beto Exemplo, designando o dia 14.9.2016")
        self.assertEqual(pii.limpar(t),
                         "deferi o pedido de oitiva de Ana Exemplo e da testemunha por ele arrolada, "
                         "%s, designando o dia 14.9.2016" % M)

    def test_oitivas_de_co_acusados_ficam(self):
        # o próprio julgado chama os nomes de acusados: ficam, em todas as menções da lista
        t = ("Indeferidas as oitivas de Ana Exemplo e Beto Exemplo, haja vista que ambos são também "
             "acusados no PAS. A defesa pediu as oitivas de Ana Exemplo e Beto Exemplo para provar o fato.")
        self.assertEqual(pii.limpar(t), t)

    def test_oitivas_de_iniciais_ficam(self):
        t = "A defesa pediu as oitivas de A. B. C., D. E. de F. e G. H. I. para provar o fato."
        self.assertEqual(pii.limpar(t), t)

    def test_enumeracao_nao_leva_sigla_nem_grupo(self):
        # só nome de pessoa entra na enumeração: nome de grupo fica
        out = pii.limpar("a testemunha Beto Exemplo, Grupo ZZX, disse que sim.")
        self.assertNotIn("Exemplo", out)
        self.assertIn("Grupo ZZX", out)

    def test_dirigente_ouvido_como_testemunha_fica_em_todas_as_ocorrencias(self):
        t = ("A defesa arrolou a testemunha Beto Exemplo. Depois, Beto Exemplo, CEO da Alfa, "
             "confirmou os fatos. Diretora Financeira, Sra. Dora Exemplo, a testemunha Dora Exemplo "
             "também depôs. O ex-presidente da Beta, Sr. Caio Exemplo, e a testemunha Caio Exemplo "
             "concordaram. A testemunha Eva Exemplo, ex-gerente de investimentos, falou. "
             "A testemunha Fábio Exemplo, diretor da Gama, falou.")
        self.assertEqual(pii.limpar(t), t)

    def test_dirigente_em_lista_mista_so_o_empregado_sai(self):
        t = ("Oitivas de Ana Exemplo e Beto Exemplo, geólogos responsáveis pela avaliação, "
             "e Caio Exemplo, CEO da Alfa, para esclarecer os fatos.")
        out = pii.limpar(t)
        self.assertNotIn("Ana Exemplo", out)
        self.assertNotIn("Beto Exemplo", out)
        self.assertIn("Caio Exemplo, CEO da Alfa", out)

    def test_nao_dirigente_continua_saindo(self):
        for t in ("a testemunha Ana Exemplo, operador da corretora Alfa, disse que sim.",
                  "a testemunha Ana Exemplo, ex-funcionária da Alfa, disse que sim.",
                  "a testemunha Ana Exemplo, geólogo responsável pelo laudo, disse que sim.",
                  "o perito da Alfa informou que a testemunha Ana Exemplo disse que sim."):
            self.assertNotIn("Exemplo", pii.limpar(t), t)

    def test_nome_abreviado_sem_o_ultimo_sobrenome(self):
        t = ("a testemunha Carla Beatriz Exemplo de Tal depôs. Ana Exemplo falou antes. "
             "Depois, Carla Beatriz Exemplo foi citada no pedido.")
        out = pii.limpar(t)
        self.assertNotIn("Carla", out)
        self.assertIn("Ana Exemplo", out)

    def test_qualidade_de_testemunha_depois_de_parentese(self):
        t = ("considerou necessária a oitiva pessoal do Sr. Ana Exemplo (realizada em 25.04.2013, "
             "fls. 4.321/4.323), na qualidade de testemunha, tendo em vista as defesas. "
             "Após o depoimento do Sr. Ana Exemplo, a parte peticionou.")
        out = pii.limpar(t)
        self.assertNotIn("Exemplo", out)
        self.assertIn("(realizada em 25.04.2013, fls. 4.321/4.323)", out)

    def test_nome_com_um_sobrenome_a_mais(self):
        t = ("a testemunha Ana Maria Exemplo depôs. Depois, Ana Maria Exemplo Lima confirmou. "
             "Ana Exemplo Lima é outra pessoa.")
        out = pii.limpar(t)
        self.assertNotIn("Lima confirmou", out)
        self.assertNotIn("Maria", out)
        self.assertIn("Ana Exemplo Lima é outra pessoa", out)

    def test_idempotencia_relativa(self):
        # rodar a regra sobre o texto já limpo não corta mais nada
        t = "a testemunha %s, ex-funcionária, e a testemunha %s depuseram." % (M, M)
        self.assertEqual(pii._testemunhas_corrido(t), [])
        self.assertEqual(pii.limpar(t), t)
        t2 = pii.limpar("a oitiva da testemunha Fulano Exemplo de Tal, arrolada pela defesa.")
        self.assertEqual(pii._testemunhas_corrido(t2), [])
        self.assertEqual(pii.limpar(t2), t2)
