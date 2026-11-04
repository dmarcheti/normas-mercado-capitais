"""Testes da extração por LLM: sem rede e sem chamar o claude (subprocess falso)."""
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import julgados_comum as jc  # noqa: E402
import julgados_extracao as ex  # noqa: E402


def ler(caminho):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def valores(**kw):
    v = {c: "" for c in jc.CAMPOS}
    v.update({"orgao": "cvm", "data": "2025-09-09", "fonte_original": "https://x",
              "sha256_fonte": "0" * 64, "baixado_em": "2026-10-30",
              "nivel_verificacao": "html-convertido"})
    v.update(kw)
    return v


CORPO = ("# RECURSO CONTRA DECISÃO DA SEP – ACME S.A. – PROC. 19957.000001/2025-01\n\n"
         "## Decisão\n\nO Colegiado, acompanhando o voto do Diretor Fulano Exemplo, negou "
         "provimento ao recurso de Beltrano Exemplar contra a multa.\n")


class Arvore(unittest.TestCase):
    def setUp(self):
        self.raiz = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.raiz)
        self.saida = os.path.join(self.raiz, "dados", "extracao")
        original = ex.Pessoas  # sem ler dados/ (CSV, tabelas, inventário) nos testes
        p = mock.patch.object(ex, "Pessoas",
                              lambda: original(acusados={}, partes_tc={}, descricoes={}))
        p.start()
        self.addCleanup(p.stop)

    def julgado(self, id_, tipo="decisao-colegiado", corpo=CORPO, **kw):
        plug = "julgados-pas" if tipo == "pas" else "julgados-colegiado-2016-2026"
        c = os.path.join(self.raiz, "plugins", plug, "julgados", "cvm", "x", "2025", id_ + ".md")
        os.makedirs(os.path.dirname(c), exist_ok=True)
        ex.gravar(c, valores(id=id_, tipo=tipo, **kw), corpo)
        return c


class RecorteTest(unittest.TestCase):
    def test_extrato_e_sumario(self):
        corpo = ("# PAS 19957.1\n\n## Extrato\n\nExtrato da sessão: multa ao acusado.\n\n"
                 "## Relatório\n\n" + "palavra " * 2000 + "\nSUMÁRIO\nProposta de R$ 100 mil.\n")
        r = ex.recorte(corpo)
        self.assertTrue(r.startswith("PAS 19957.1"))
        self.assertIn("Extrato da sessão", r)
        self.assertNotIn("palavra palavra palavra", r.split("SUMÁRIO")[0])
        self.assertIn("SUMÁRIO: Proposta de R$ 100 mil.", r)

    def test_sem_extrato_inicio_e_fim(self):
        corpo = "# T\n\n## Voto\n\n" + " ".join("p%d" % i for i in range(3000))
        r = ex.recorte(corpo)
        self.assertIn("p0 ", r)
        self.assertIn("p590", r)
        self.assertNotIn("p610 ", r)
        self.assertIn("p2600", r)
        self.assertTrue(r.endswith("p2999"))
        self.assertLess(len(r.split()), 1100)

    def test_deliberacao_do_colegiado_no_meio_entra(self):
        # a deliberação fica no meio da "## Decisão"; o fim do documento é o anexo da área técnica
        corpo = ("# CONSULTA\n\n## Decisão\n\n" + " ".join("d%d" % i for i in range(1500))
                 + "\n\nO Colegiado, por unanimidade, acompanhou as conclusões da área técnica.\n\n"
                 + " ".join("e%d" % i for i in range(800))
                 + "\n\n## Manifestação da área técnica\n\n" + " ".join("m%d" % i for i in range(5000)))
        r = ex.recorte(corpo)
        self.assertIn("O Colegiado, por unanimidade, acompanhou", r)
        self.assertIn("e799", r)  # fim da seção "## Decisão"
        self.assertLess(len(r.split()), 1700)

    def test_temas_iguais_ao_prompt(self):
        with open(ex.PROMPT, encoding="utf-8") as f:
            prompt = f.read()
        self.assertEqual(tuple(re.findall(r"(?m)^\| `([a-z-]+)` \|", prompt)), ex.TEMAS)


class ValidacaoTest(unittest.TestCase):
    LOTE = [{"id": "a", "tipo": "decisao-colegiado", "recorte": CORPO},
            {"id": "b", "tipo": "pas", "recorte": "PAS. A ACME S.A. e JOSÉ DA SILVA EXEMPLO."}]

    def test_id_divergente_nao_reprova_o_lote(self):
        # o modelo trocou o id de "b": "a" é aplicado; "b" vai para a retentativa; "x" é ignorado
        reprovadas = {}
        aprov, erros = ex.validar_saida(self.LOTE, [{"id": "a", "tema": "processual"},
                                                    {"id": "x", "tema": "processual"}],
                                        reprovadas=reprovadas)
        self.assertEqual(aprov, {"a": {"tema": "processual"}})
        self.assertIn("ids faltando: b", erros)
        self.assertIn("ids a mais: x", erros)
        self.assertEqual(reprovadas, {"b": "id ausente na saída"})

    def test_campos_invalidos_saem_do_item(self):
        saida = [{"id": "a", "ementa": "Recurso de Beltrano Exemplar contra multa. Negado.",
                  "tema": "tema-inventado", "resultado": "nao-provido", "relator": "Fulano Exemplo"},
                 {"id": "b", "ementa": " ".join(["palavra"] * 61), "tema": "manipulacao-fraude",
                  "resultado": "aceito"}]
        reprovadas = {}
        aprov, erros = ex.validar_saida(self.LOTE, saida, {"a": ["Beltrano Exemplar"]},
                                        reprovadas)
        self.assertEqual(aprov["a"], {"resultado": "nao-provido", "relator": "Fulano Exemplo"})
        self.assertEqual(aprov["b"], {"tema": "manipulacao-fraude"})
        self.assertEqual(len(erros), 4)
        self.assertEqual(reprovadas, {"a": "ementa com nome de pessoa",
                                      "b": "ementa com mais de 60 palavras"})

    def test_ementa_que_cita_o_recorte_vai_para_a_retentativa(self):
        reprovadas = {}
        aprov, erros = ex.validar_saida(
            self.LOTE[:1], [{"id": "a", "ementa": "Recurso contra multa. O recorte não traz o "
                             "dispositivo do voto.", "resultado": "outro"}], reprovadas=reprovadas)
        self.assertEqual(aprov["a"], {"resultado": "outro"})
        self.assertEqual(reprovadas, {"a": "ementa cita o recorte"})


class PessoasTest(unittest.TestCase):
    """Lista positiva de pessoas físicas por julgado (nomes sintéticos)."""

    def test_nome_completo_nome_e_sobrenome_e_sobrenome_composto(self):
        lista = ["Fulano Beltrano de Tal Exemplar"]
        for ementa in ("Multa a Fulano Beltrano de Tal Exemplar.", "Multa a Fulano Exemplar.",
                       "Multa ao sr. Tal Exemplar.", "Multa a FULANO BELTRANO."):
            self.assertTrue(ex.tem_nome(ementa, lista), ementa)
        for ementa in ("Multa a Fulano, diretor.", "Exemplar Beltrano não é a ordem do nome.",
                       "Multa a fulano exemplar, em minúsculas.", "Multa ao acusado."):
            self.assertFalse(ex.tem_nome(ementa, lista), ementa)

    def test_empresa_nao_entra_na_lista(self):
        for empresa in ("Exemplo Industrial S.A.", "Construtora Exemplar S.A.", "Acme Ltda.",
                        "Exemplo Mineração e Metálicos S.A.", "Boston Exemplo Plus FIA",
                        "Banco Exemplo de Investimentos", "Fulano Participações",
                        "Exemplo Auditores Independentes", "CONTRA DECISÃO DA SEP",
                        "NBC TA 540", "Credenciamento de Administrador de Carteira"):
            self.assertEqual(ex.pessoa(empresa), "", empresa)
        self.assertEqual(ex.pessoa("Sr. Fulano de Tal (“Proponente”)"), "Fulano de Tal")
        self.assertEqual(ex.separar_partes("FULANO DE TAL, ACME S.A. e Beltrano Exemplar"),
                         ["FULANO DE TAL", "Beltrano Exemplar"])

    def test_fontes(self):
        nup = "19957" + "000001" + "2025" + "01"
        p = ex.Pessoas(acusados={nup: ["Acusado Do Csv"]},
                       partes_tc={"19957-000001-2025-01": ["Compromitente Da Tabela"]},
                       descricoes={"cvm-col-1": ("decisao-colegiado",
                                                 "Proposta apresentada por Cicrano Da Silva "
                                                 "(“Proponente”), na qualidade de diretor.")})
        corpo = ("# RECURSO CONTRA DECISÃO DA SEP – PARTE DO TITULO – PROC. 19957.000001/2025-01"
                 "\n\n## Extrato\n\nAcusados:\nPrimeiro Exemplo Extrato\nAcme S.A.\n"
                 "Ementa: multa.\nAcusado: Segundo Exemplo Extrato\n")
        v = {"id": "cvm-col-1", "tipo": "decisao-colegiado",
             "processo": "19957.000001/2025-01", "nup": "19957-000001-2025-01"}
        self.assertEqual(p.do_julgado(v, corpo),
                         ["Acusado Do Csv", "Compromitente Da Tabela", "Cicrano Da Silva",
                          "Primeiro Exemplo Extrato", "Segundo Exemplo Extrato",
                          "PARTE DO TITULO"])
        pas = ex.partes_da_descricao("FULANO DE TAL, ACME S.A. E OUTROS Abuso de poder. Multa.",
                                     "pas")
        self.assertEqual(pas, ["FULANO DE TAL"])

    def test_troca_nomes_da_lista_na_ementa(self):
        lista = ["Fulano Beltrano de Tal Exemplar", "Cicrano J. Exemplo"]
        casos = [
            ("Apurar a responsabilidade de Fulano Beltrano de Tal Exemplar por infração.",
             "Apurar a responsabilidade de [pessoa física] por infração."),
            ("Multa a Fulano Exemplar e a Cicrano J. Exemplo; absolvição de Acme S.A.",
             "Multa a [pessoa física] e a [pessoa física]; absolvição de Acme S.A."),
            ("FULANO BELTRANO DE TAL EXEMPLAR – Uso de informação privilegiada.",
             "[pessoa física] – Uso de informação privilegiada."),
            # ponto final da frase fica; o da inicial sai com o nome
            ("Recurso de Fulano Exemplar. Multa a Cicrano J. Exemplo.",
             "Recurso de [pessoa física]. Multa a [pessoa física]."),
            # sobrenome sozinho, ordem trocada e vírgula no meio não são nome da lista
            ("Multa a Exemplar, diretor; Exemplar Beltrano; Fulano, Exemplar.",
             "Multa a Exemplar, diretor; Exemplar Beltrano; Fulano, Exemplar."),
        ]
        for antes, depois in casos:
            self.assertEqual(ex.trocar_nomes(antes, lista), depois, antes)
        self.assertEqual(ex.trocar_nomes("Sem nome.", []), "Sem nome.")

    def test_ementa_sem_pessoas_no_frontmatter_e_integral_no_corpo(self):
        msg = ("nomes de pessoa física omitidos da ementa do frontmatter; ementa integral na "
               "seção Ementa")
        v = {"id": "cvm-pas-x", "tipo": "pas", "processo": "", "nup": "",
             "ementa": "Apurar a responsabilidade de Fulano Exemplar por infração. Multa.",
             "incerteza": "data aproximada"}
        corpo = "# PAS CVM nº X\n\n## Voto\n\nTexto.\n"
        v2, c2, n = ex.ementa_sem_pessoas(
            v, corpo, ["Fulano Exemplar"],
            publicada="FULANO EXEMPLAR - Apurar a responsabilidade de Fulano Exemplar por "
                      "infração. Multa.")
        self.assertEqual(n, 1)
        self.assertEqual(v2["ementa"], "Apurar a responsabilidade de [pessoa física] por "
                                       "infração. Multa.")
        self.assertEqual(v2["incerteza"], "data aproximada; " + msg)
        self.assertEqual(c2, "# PAS CVM nº X\n\n## Ementa\n\nFULANO EXEMPLAR - Apurar a "
                             "responsabilidade de Fulano Exemplar por infração. Multa.\n\n"
                             "## Voto\n\nTexto.\n")
        self.assertEqual(v["ementa"][:30], "Apurar a responsabilidade de F")  # não muda o original
        # seção Ementa já existe: o corpo fica como está
        corpo_em = "# T\n\n## Ementa\n\nApurar a responsabilidade de Fulano Exemplar.\n"
        _, c3, _ = ex.ementa_sem_pessoas(v, corpo_em, ["Fulano Exemplar"])
        self.assertEqual(c3, corpo_em)
        # sem nome da lista: nada muda
        v4, c4, n4 = ex.ementa_sem_pessoas(dict(v, ementa="Multa."), corpo, ["Fulano Exemplar"])
        self.assertEqual((v4["ementa"], v4["incerteza"], c4, n4), ("Multa.", "data aproximada",
                                                                   corpo, 0))

    def test_caixa_alta_antes_do_travessao_entra_na_lista(self):
        v = {"id": "x", "tipo": "pas", "processo": "", "nup": "", "incerteza": "",
             "ementa": "BELTRANO EXEMPLAR E ACME S.A. – Beltrano Exemplar negociou ações."}
        v2, _, n = ex.ementa_sem_pessoas(v, "# T\n", [])
        self.assertEqual(v2["ementa"], "[pessoa física] E ACME S.A. – [pessoa física] negociou "
                                       "ações.")
        self.assertEqual(n, 2)

    def test_carrega_csv_e_tabelas_de_dados(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        nup = "19957" + "000002" + "2024" + "02"
        csvp = os.path.join(d, "acusados.csv")
        with open(csvp, "w", encoding="latin-1") as f:
            f.write("NUP;Nome_Acusado;Situacao;Data_Situacao\n")
            f.write("%s;JOSÉ EXEMPLO TESTE;Julgado;01/01/2025\n%s;ACME S.A.;Julgado;x\n"
                    % (nup, nup))
        os.makedirs(os.path.join(d, "listagens"))
        with open(os.path.join(d, "listagens", "tc_rejeitados.html"), "w",
                  encoding="utf-8") as f:
            f.write("<table><tr><td>19957.000002/2024-02</td><td>02/12/2025</td>"
                    "<td>Fulana Rejeitada Teste</td><td>x</td></tr></table>")
        p = ex.Pessoas(acusados_csv=csvp, listagens=os.path.join(d, "listagens"),
                       inventario=os.path.join(d, "nada.json"))
        self.assertEqual(p.acusados, {nup: ["JOSÉ EXEMPLO TESTE"]})
        self.assertEqual(p.partes_tc, {"19957-000002-2024-02": ["Fulana Rejeitada Teste"]})
        self.assertEqual(p.descricoes, {})


class ExecucaoTest(Arvore):
    def test_simular_monta_lotes_de_25_sem_modelo(self):
        for i in range(30):
            self.julgado("cvm-col-2025%04d-d%d" % (i, i))
        with mock.patch.object(ex.subprocess, "run") as run, redirect_stdout(io.StringIO()):
            rc = ex.main(["--onda", "1", "--simular", "--raiz", self.raiz, "--saida", self.saida])
        self.assertEqual(rc, 0)
        run.assert_not_called()
        lotes = sorted(os.listdir(self.saida))
        self.assertEqual(len(lotes), 2)
        tamanhos = [len(ler(os.path.join(self.saida, d, "lote.json"))) for d in lotes]
        self.assertEqual(tamanhos, [25, 5])
        item = ler(os.path.join(self.saida, lotes[0], "lote.json"))[0]
        self.assertEqual(set(item), {"id", "tipo", "classe", "processo", "data", "titulo",
                                     "recorte"})

    def test_retomavel_pula_o_que_ja_foi_extraido(self):
        self.julgado("cvm-col-20250001-d1")
        self.julgado("cvm-col-20250002-d2", tema="processual", tema_fonte="extracao",
                     ementa="Recurso negado.", ementa_fonte="extracao")
        with redirect_stdout(io.StringIO()):
            ex.main(["--onda", "1", "--simular", "--raiz", self.raiz, "--saida", self.saida])
        (lote,) = os.listdir(self.saida)
        self.assertEqual([x["id"] for x in ler(os.path.join(self.saida, lote, "lote.json"))],
                         ["cvm-col-20250001-d1"])

    def test_refazer_sobrescreve_ementa_extraida_e_resultado(self):
        c = self.julgado("cvm-col-20250003-d3", tema="processual", tema_fonte="extracao",
                         ementa="Consulta. Sem decisão no recorte.", ementa_fonte="extracao",
                         resultado="indeferido")
        novo = {"ementa": "Consulta; dispensa deferida.", "resultado": "deferido", "tema": "ofertas"}
        self.assertEqual(ex.aplicar(c, novo), [])  # sem refazer, nada muda
        self.assertEqual(sorted(ex.aplicar(c, novo, refazer=True)), ["ementa", "resultado"])
        v, _ = ex.ler_julgado(c)
        self.assertEqual((v["ementa"], v["resultado"], v["tema"]),
                         ("Consulta; dispensa deferida.", "deferido", "processual"))
        # ementa da fonte (cvm) não é tocada nem no refazer
        c2 = self.julgado("cvm-pas-4", tipo="pas", ementa="Ementa da CVM.", ementa_fonte="cvm")
        self.assertNotIn("ementa", ex.aplicar(c2, novo, refazer=True))
        with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
            ex.main(["--refazer", "--onda", "1", "--simular", "--raiz", self.raiz])

    def test_prefixo_do_lote_leva_o_pid(self):
        # duas filas que começam no mesmo segundo não podem escrever nas mesmas pastas
        self.julgado("cvm-col-20250001-d1")
        with mock.patch.object(ex.os, "getpid", return_value=4242), redirect_stdout(io.StringIO()):
            ex.main(["--onda", "1", "--simular", "--raiz", self.raiz, "--saida", self.saida])
        (lote,) = os.listdir(self.saida)
        self.assertRegex(lote, r"-sonnet-\d{6}-4242-001$")  # Sonnet é o padrão desde a 3b

    def test_trabalho_dentro_do_repositorio_e_recusado(self):
        with self.assertRaises(ValueError):
            ex.pasta_de_trabalho(os.path.join(jc.RAIZ, "dados"))

    def test_roda_valida_e_aplica(self):
        c_tit = self.julgado("cvm-col-1", ementa="Recurso contra decisão da SEP.",
                             ementa_fonte="titulo", classe="recurso")
        c_mul = self.julgado("cvm-col-2", ementa="Multa cominatória. Recurso.",
                             ementa_fonte="titulo", classe="multa-cominatoria",
                             resultado="provido")
        c_pas = self.julgado("cvm-pas-3", tipo="pas", ementa="Ementa da CVM.", ementa_fonte="cvm",
                             relator="Diretora Sicrana", tema="opa", tema_fonte="extracao")
        chamadas = []

        def falso(cmd, input, cwd, capture_output, text, timeout):  # noqa: A002
            chamadas.append((cmd, cwd))
            self.assertEqual(sorted(os.listdir(cwd)), ["lote.json"])
            self.assertIn("julgados-extracao", cwd)
            self.assertIn("saida.json", input)
            lote = ler(os.path.join(cwd, "lote.json"))
            saida = [{"id": x["id"], "ementa": "Recurso contra multa por atraso; negado.",
                      "tema": "processual", "resultado": "nao-provido" if x["tipo"] != "pas"
                      else "condenacao", "relator": "SEP"} for x in lote]
            with open(os.path.join(cwd, "saida.json"), "w", encoding="utf-8") as f:
                json.dump(saida, f)
            log = "\n".join([json.dumps({"type": "system"}),
                             json.dumps({"type": "result", "total_cost_usd": 0.0123})])
            return mock.Mock(returncode=0, stdout=log, stderr="")

        trabalho = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, trabalho)
        with mock.patch.object(ex.subprocess, "run", side_effect=falso), \
                redirect_stdout(io.StringIO()) as out:
            rc = ex.main(["--ids", "cvm-col-1,cvm-col-2,cvm-pas-3", "--model", "haiku",
                          "--raiz", self.raiz, "--saida", self.saida, "--trabalho", trabalho])
        self.assertEqual(rc, 0)
        self.assertEqual(len(chamadas), 1)
        cmd = chamadas[0][0]
        for flag in ("--strict-mcp-config", "stream-json", "Read,Write"):
            self.assertIn(flag, cmd)
        self.assertEqual(cmd[cmd.index("--model") + 1], "haiku")
        self.assertIn("custo total: US$ 0.0123", out.getvalue())
        lote = os.path.join(self.saida, os.listdir(self.saida)[0])
        self.assertEqual(ler(os.path.join(lote, "execucao.json"))["total_cost_usd"],
                         0.0123)
        self.assertTrue(os.path.exists(os.path.join(lote, "log.jsonl")))

        v1, _ = ex.ler_julgado(c_tit)
        self.assertEqual((v1["ementa"], v1["ementa_fonte"], v1["tema"], v1["tema_fonte"],
                          v1["resultado"], v1["relator"]),
                         ("Recurso contra multa por atraso; negado.", "extracao", "processual",
                          "extracao", "nao-provido", "SEP"))
        v2, _ = ex.ler_julgado(c_mul)  # rotineira: ementa de modelo fica; resultado já havia
        self.assertEqual((v2["ementa"], v2["ementa_fonte"], v2["resultado"], v2["tema"]),
                         ("Multa cominatória. Recurso.", "titulo", "provido", "processual"))
        v3, corpo3 = ex.ler_julgado(c_pas)  # ementa da CVM, tema e relator já preenchidos
        self.assertEqual((v3["ementa_fonte"], v3["tema"], v3["relator"], v3["resultado"]),
                         ("cvm", "opa", "Diretora Sicrana", "condenacao"))
        self.assertEqual(corpo3, CORPO)
        self.assertEqual(list(v3), list(jc.CAMPOS))

    def test_retentativa_uma_vez_e_ementa_do_titulo_se_falhar(self):
        corpo = CORPO.replace("ACME S.A.", "BELTRANO EXEMPLAR")
        c1 = self.julgado("cvm-col-1", corpo=corpo, ementa="Recurso.", ementa_fonte="titulo")
        c2 = self.julgado("cvm-col-2", ementa="Recurso 2.", ementa_fonte="titulo")
        c3 = self.julgado("cvm-pas-3", tipo="pas", corpo=corpo, ementa="Da CVM.",
                          ementa_fonte="cvm")
        chamadas = []

        def falso(cmd, input, cwd, capture_output, text, timeout):  # noqa: A002
            lote = ler(os.path.join(cwd, "lote.json"))
            retentativa = "## Retentativa" in input
            chamadas.append((retentativa, [(x["id"], x.get("motivo_retentativa")) for x in lote]))
            ementas = {"cvm-col-1": "Recurso de Beltrano Exemplar; negado.",
                       "cvm-col-2": " ".join(["longa"] * 70),
                       "cvm-pas-3": "Multa a Beltrano Exemplar."}
            if retentativa:
                ementas["cvm-col-1"] = "Recurso do acusado; negado."
            saida = [{"id": x["id"], "ementa": ementas[x["id"]], "tema": "processual"}
                     for x in lote]
            with open(os.path.join(cwd, "saida.json"), "w", encoding="utf-8") as f:
                json.dump(saida, f)
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch.object(ex.subprocess, "run", side_effect=falso), \
                redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
            rc = ex.main(["--ids", "cvm-col-1,cvm-col-2,cvm-pas-3", "--raiz", self.raiz,
                          "--saida", self.saida, "--trabalho", tempfile.mkdtemp()])
        self.assertEqual(rc, 0)
        # a PAS com ementa da CVM não volta: a extraída não seria usada
        self.assertEqual(chamadas[1], (True, [("cvm-col-1", "ementa com nome de pessoa"),
                                              ("cvm-col-2", "ementa com mais de 60 palavras")]))
        self.assertEqual(len(chamadas), 2)
        self.assertEqual(ex.ler_julgado(c1)[0]["ementa"], "Recurso do acusado; negado.")
        v2 = ex.ler_julgado(c2)[0]
        self.assertEqual((v2["ementa"], v2["ementa_fonte"], v2["tema"]),
                         ("Recurso 2.", "titulo", "processual"))
        self.assertEqual(ex.ler_julgado(c3)[0]["ementa"], "Da CVM.")
        ret = [d for d in os.listdir(self.saida) if "retentativa" in d]
        self.assertEqual(len(ret), 1)
        val = ler(os.path.join(self.saida, ret[0], "validacao.json"))
        self.assertEqual([os.path.basename(c) for c in val["ementa_do_titulo"]],
                         ["cvm-col-2.md"])
        self.assertIn("1 ficaram com a ementa do título", out.getvalue())
        self.assertNotIn("Beltrano", json.dumps(ler(os.path.join(self.saida, ret[0],
                                                                 "lote.json"))[0]["motivo_retentativa"]))

    def test_saida_ausente_nao_aplica_e_falha(self):
        c = self.julgado("cvm-col-9", ementa_fonte="titulo", ementa="X.")
        with open(c, encoding="utf-8") as f:
            antes = f.read()
        with mock.patch.object(ex.subprocess, "run",
                               return_value=mock.Mock(returncode=1, stdout="", stderr="erro")), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            rc = ex.main(["--ids", "cvm-col-9", "--raiz", self.raiz, "--saida", self.saida,
                          "--trabalho", tempfile.mkdtemp()])
        self.assertEqual(rc, 1)
        with open(c, encoding="utf-8") as f:
            self.assertEqual(f.read(), antes)


# ---------------------------------------------------------------- fase 3b: reextração

PARTICIPANTES = ("**Participantes**\n\n**• FULANO EXEMPLO DA SILVA – PRESIDENTE**\n"
                 "**• BELTRANO EXEMPLAR – DIRETOR**\n\n")


def decisao(*paragrafos, titulo="RECURSO CONTRA DECISÃO DA SEP – ACME S.A. – PROC. 1",
            anexo=""):
    corpo = "# %s\n\n## Decisão\n\n%sReg. nº 1/25\nRelator: SEP\n\n%s\n" % (
        titulo, PARTICIPANTES, "\n\n".join(paragrafos))
    return corpo + ("\n## Manifestação da área técnica\n\n" + anexo + "\n" if anexo else "")


class RecorteDeliberacaoTest(unittest.TestCase):
    def test_deliberacao_no_meio_e_anexo_longo_no_fim(self):
        corpo = decisao(
            "Trata-se de pedido de dispensa de requisitos da ACME S.A.",
            " ".join("c%d" % i for i in range(1500)),
            "A SEP propôs o indeferimento do pedido.",
            "O Colegiado, por unanimidade, deliberou deferir o pedido, nos termos do voto.",
            " ".join("e%d" % i for i in range(300)),
            anexo=(" ".join("m%d" % i for i in range(5000)) + "\n\nDiante do exposto, propomos "
                   "o indeferimento do pedido de dispensa, " + "por razões " * 30 + ".\n\n"
                   "Atenciosamente, Sicrano Exemplo"))
        r = ex.recorte_3b(corpo)
        self.assertTrue(r.startswith("TÍTULO: RECURSO CONTRA DECISÃO DA SEP"))
        i_delib = r.index("DELIBERAÇÃO DO COLEGIADO")
        i_pedido = r.index("PEDIDO E FUNDAMENTOS")
        i_area = r.index("POSIÇÃO DA ÁREA TÉCNICA OU DO COMITÊ")
        self.assertLess(i_delib, i_pedido)
        self.assertLess(i_pedido, i_area)
        self.assertIn("deliberou deferir o pedido", r[i_delib:i_pedido])
        self.assertIn("Trata-se de pedido", r[i_pedido:i_area])
        self.assertIn("A SEP propôs o indeferimento", r[i_pedido:i_area])
        self.assertIn("Diante do exposto, propomos", r[i_area:])
        self.assertNotIn("Atenciosamente", r)
        self.assertNotIn("FULANO EXEMPLO", r)  # sem a lista de participantes
        self.assertNotIn("m100 ", r)  # o miolo do anexo fica de fora
        self.assertNotIn("c800 ", r)  # o miolo do relato também
        self.assertLess(len(r.split()), 1800)

    def test_voto_transcrito_longo_traz_a_conclusao(self):
        # "acompanhou o voto ... a seguir transcrito": o dispositivo está no fim do voto
        corpo = decisao(
            "O Colegiado acompanhou o voto do Diretor-Relator, a seguir transcrito:",
            "RELATÓRIO. Trata-se de pedido de autorização da ACME S.A.",
            " ".join("v%d" % i for i in range(2000)),
            "Diante do exposto, voto pela concessão da autorização pedida.")
        r = ex.recorte_3b(corpo)
        i_delib = r.index("DELIBERAÇÃO DO COLEGIADO")
        i_concl = r.index("CONCLUSÃO DA DECISÃO")
        i_pedido = r.index("PEDIDO E FUNDAMENTOS")
        self.assertLess(i_delib, i_concl)
        self.assertLess(i_concl, i_pedido)
        self.assertIn("voto pela concessão da autorização", r[i_concl:i_pedido])
        self.assertNotIn("v1000 ", r)

    def test_deliberacao_no_fim_nao_repete_a_conclusao(self):
        corpo = decisao(" ".join("c%d" % i for i in range(1500)),
                        "O Colegiado, por unanimidade, deliberou deferir o pedido.")
        self.assertNotIn("CONCLUSÃO DA DECISÃO", ex.recorte_3b(corpo))

    def test_decisao_curta_vai_inteira(self):
        corpo = decisao("Trata-se de recurso contra multa cominatória.",
                        "O Colegiado, acompanhando a SEP, negou provimento ao recurso.")
        r = ex.recorte_3b(corpo)
        self.assertIn("DECISÃO NA ÍNTEGRA", r)
        self.assertIn("Trata-se de recurso", r)
        self.assertNotIn("PEDIDO E FUNDAMENTOS", r)

    def test_data_no_meio_da_frase_nao_esconde_a_deliberacao(self):
        corpo = decisao("Trata-se de consulta.",
                        "Ao apreciar a consulta, o Colegiado, nos termos do voto do Diretor "
                        "Relator, que havia pedido vista em reunião de 20.07.10, concluiu que "
                        "o dispositivo não alcança os créditos.", "Texto final sem verbo.")
        r = ex.recorte_3b(corpo)
        delib = r[r.index("DELIBERAÇÃO DO COLEGIADO"):r.index("DECISÃO NA ÍNTEGRA")]
        self.assertIn("concluiu que o dispositivo", delib)

    def test_sem_decisao_ou_outro_tipo_usa_o_recorte_antigo(self):
        corpo = "# PAS 1\n\n## Extrato\n\nExtrato da sessão: multa ao acusado.\n"
        self.assertEqual(ex.recorte_3b(corpo, "pas"), ex.recorte(corpo))
        corpo = decisao("O Colegiado deliberou aceitar a proposta.")
        self.assertEqual(ex.recorte_3b(corpo, "pas"), ex.recorte(corpo))

    def test_entrada_nova_usa_o_recorte_3b(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        c = os.path.join(d, "x.md")
        ex.gravar(c, valores(id="cvm-col-1", tipo="decisao-colegiado"),
                  decisao("O Colegiado deliberou deferir o pedido."))
        self.assertTrue(ex.entrada(c, novo=True)["recorte"].startswith("TÍTULO:"))
        self.assertFalse(ex.entrada(c)["recorte"].startswith("TÍTULO:"))

    def test_prompt_pede_situacao_e_rotulo(self):
        with open(ex.PROMPT, encoding="utf-8") as f:
            prompt = f.read()
        for s in ex.SITUACOES:
            self.assertIn("`%s`" % s, prompt)
        self.assertIn("DELIBERAÇÃO DO COLEGIADO", prompt)


class SituacaoTest(unittest.TestCase):
    def sit(self, *paragrafos):
        return ex.situacao_deliberacao(decisao(*paragrafos).split("## Decisão", 1)[1])

    def test_pedido_de_vista_no_fim_suspende(self):
        self.assertEqual(self.sit(
            "Trata-se de recurso.", "O Relator votou pelo indeferimento do recurso.",
            "O Colegiado deu início à discussão do assunto, tendo o Diretor Beltrano "
            "solicitado vista do processo."), "suspenso")
        # já havia votos pelo não provimento: continua suspenso
        self.assertEqual(self.sit(
            "Após o Diretor Fulano e o Presidente terem votado pelo não provimento do recurso, "
            "o Diretor Beltrano solicitou vista do processo."), "suspenso")

    def test_adiamento_e_retirada_de_pauta_suspendem(self):
        self.assertEqual(self.sit("O Colegiado deu início à discussão do assunto, tendo ficado "
                                  "adiada sua decisão."), "suspenso")
        self.assertEqual(self.sit("Retirado de pauta, por solicitação da PFE."), "suspenso")
        self.assertEqual(self.sit("O Diretor Fulano solicitou vista dos autos, ficando adiada a "
                                  "decisão."), "suspenso")

    def test_retomada_com_deliberacao_e_decidida(self):
        self.assertEqual(self.sit(
            "O Diretor Beltrano, que havia pedido vista do processo, apresentou seu voto.",
            "O Colegiado, por maioria, deliberou negar provimento ao recurso."), "decidido")
        self.assertEqual(self.sit(
            "Em reunião anterior, o Diretor Beltrano pediu vista do processo.",
            "Retomada a discussão, o Colegiado, por unanimidade, deu provimento ao recurso."),
            "decidido")
        corpo = decisao("O Colegiado acompanhou o voto do relator e indeferiu o pedido.")
        corpo = corpo.replace("Relator: SEP", "Relator: SEP (PEDIDO DE VISTA DO DLA)")
        self.assertEqual(ex.situacao_deliberacao(corpo.split("## Decisão", 1)[1]), "decidido")

    def test_vista_dos_autos_como_objeto_nao_suspende(self):
        self.assertEqual(self.sit(
            "O Colegiado negou provimento ao recurso, mantendo a decisão da SMI que indeferiu "
            "o pedido de vista e cópia integral dos autos."), "decidido")
        self.assertEqual(self.sit(
            "Trata-se de recurso contra decisão que negou vista dos autos do PAS 1.",
            "O Colegiado deliberou dar provimento ao recurso.",
            "O recorrente havia solicitado vista dos autos do Proc. 2 antes do depoimento."),
            "decidido")

    def test_sem_deliberacao_nem_suspensao(self):
        self.assertEqual(self.sit("Trata-se de recurso.", "A SEP opinou pelo indeferimento."),
                         "")


class ReextracaoTest(Arvore):
    """Lista, reextração retomável (sem tocar em plugins/) e aplicação."""

    def setUp(self):
        super().setUp()
        self.saida = os.path.join(self.raiz, "dados", "fase-3b", "extracao")
        self.inventario = os.path.join(self.raiz, "inventario.json")
        with open(self.inventario, "w", encoding="utf-8") as f:
            json.dump({"julgados": [{"id": "cvm-col-tc1", "tipo": "termo-compromisso",
                                     "resultado": "aceito"}]}, f)
        self.respostas, self.chamadas = {}, []
        self.trabalho = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.trabalho)

    def arvore(self):
        self.julgado("cvm-col-a", ementa="Ementa antiga A.", ementa_fonte="extracao",
                     resultado="indeferido", tema="processual", tema_fonte="extracao",
                     relator="SEP", normas_citadas="cvm-res-160", classe="dispensa",
                     corpo=decisao("Trata-se de pedido de dispensa.",
                                   "O Colegiado, por unanimidade, deliberou conceder a dispensa."))
        self.julgado("cvm-col-b", ementa="Recurso.", ementa_fonte="titulo",
                     classe="multa-cominatoria", resultado="indeferido", tema="processual",
                     tema_fonte="script",
                     corpo=decisao("O Relator votou pelo indeferimento.",
                                   "O Colegiado deu início à discussão do assunto, tendo o "
                                   "Diretor Beltrano solicitado vista do processo."))
        self.julgado("cvm-col-tc1", tipo="termo-compromisso", ementa="Ementa TC.",
                     ementa_fonte="extracao", resultado="aceito")
        self.julgado("cvm-col-tc2", tipo="termo-compromisso", ementa="TC.",
                     ementa_fonte="titulo", resultado="aceito")
        self.julgado("cvm-pas-1", tipo="pas", ementa="Ementa PAS.", ementa_fonte="extracao")
        self.julgado("cvm-pas-2", tipo="pas", ementa="Ementa da CVM.", ementa_fonte="cvm")

    def lista(self):
        lista = ex.montar_lista(self.raiz, self.inventario)
        c = os.path.join(self.raiz, "lista.json")
        ex._gravar_json(c, lista)
        return lista, c

    def falso(self, cmd, input, cwd, capture_output, text, timeout):  # noqa: A002
        lote = ler(os.path.join(cwd, "lote.json"))
        self.chamadas.append([x["id"] for x in lote])
        saida = [dict(self.respostas.get(x["id"], {}), id=x["id"]) for x in lote]
        with open(os.path.join(cwd, "saida.json"), "w", encoding="utf-8") as f:
            json.dump(saida, f)
        log = json.dumps({"type": "result", "total_cost_usd": 0.5})
        return mock.Mock(returncode=0, stdout=log, stderr="")

    def rodar(self, *args):
        _, c = self.lista()
        with mock.patch.object(ex.subprocess, "run", side_effect=self.falso), \
                redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
            rc = ex.main(["--reextrair", "--lista", c, "--raiz", self.raiz, "--saida",
                          self.saida, "--trabalho", self.trabalho] + list(args))
        return rc, out.getvalue()

    def aplicar(self, *args):
        _, c = self.lista()
        with redirect_stdout(io.StringIO()):
            ex.main(["--aplicar-reextracao", "--lista", c, "--raiz", self.raiz, "--saida",
                     self.saida] + list(args))
        (rel,) = [x for x in os.listdir(self.saida) if x.startswith("aplicacao-")]
        return ler(os.path.join(self.saida, rel))

    def plugins(self):
        out = {}
        for c in sorted(ex.glob.glob(os.path.join(self.raiz, "plugins", "**", "*.md"),
                                     recursive=True)):
            with open(c, encoding="utf-8") as f:
                out[c] = f.read()
        return out

    def test_lista_por_escopo_e_tipo(self):
        self.arvore()
        lista, _ = self.lista()
        self.assertEqual(lista["itens"], {
            "cvm-col-a": {"tipo": "decisao-colegiado", "classe": "dispensa",
                          "campos": ["ementa", "resultado"]},
            "cvm-col-b": {"tipo": "decisao-colegiado", "classe": "multa-cominatoria",
                          "campos": ["resultado"]},
            "cvm-col-tc1": {"tipo": "termo-compromisso", "classe": "", "campos": ["ementa"]},
            "cvm-col-tc2": {"tipo": "termo-compromisso", "classe": "", "campos": ["resultado"]},
            "cvm-pas-1": {"tipo": "pas", "classe": "", "campos": ["ementa"]}})
        self.assertEqual(lista["contagens"]["decisao-colegiado"],
                         {"itens": 2, "ementa": 1, "resultado": 2, "ementa_e_resultado": 1})
        self.assertEqual(lista["contagens"]["total"]["itens"], 5)

    def test_reextrair_retoma_sem_refazer_e_nao_toca_em_plugins(self):
        self.arvore()
        antes = self.plugins()
        rc, out = self.rodar("--limite", "2", "--model", "sonnet")
        self.assertEqual(rc, 0)
        self.assertEqual(self.chamadas, [["cvm-col-a", "cvm-col-b"]])
        lote = ler(os.path.join(self.saida, sorted(os.listdir(self.saida))[0], "lote.json"))
        self.assertTrue(lote[0]["recorte"].startswith("TÍTULO:"))
        rc, out = self.rodar()  # retoma: só o que falta
        self.assertEqual(self.chamadas[1], ["cvm-col-tc1", "cvm-col-tc2", "cvm-pas-1"])
        rc, out = self.rodar()  # nada pendente
        self.assertEqual(len(self.chamadas), 2)
        self.assertIn("0 de 5", out)
        self.assertEqual(self.plugins(), antes)
        for d in os.listdir(self.saida):
            self.assertEqual(sorted(os.listdir(os.path.join(self.saida, d))),
                             sorted(["caminhos.json", "escopo.json", "execucao.json",
                                     "lote.json", "log.jsonl", "pessoas.json", "saida.json",
                                     "validacao.json"]))

    def test_lote_sem_saida_fica_pendente(self):
        self.arvore()

        def sem_saida(cmd, input, cwd, capture_output, text, timeout):  # noqa: A002
            return mock.Mock(returncode=1, stdout="", stderr="cota")

        _, c = self.lista()
        with mock.patch.object(ex.subprocess, "run", side_effect=sem_saida), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            rc = ex.main(["--reextrair", "--lista", c, "--raiz", self.raiz, "--saida",
                          self.saida, "--trabalho", self.trabalho])
        self.assertEqual(rc, 0)
        self.assertEqual(ex.estado_reextracao(self.saida)["resultados"], {})
        self.rodar()
        self.assertEqual(len(self.chamadas), 1)  # tudo de novo, num lote só

    def test_aplicar_so_os_campos_do_escopo_e_preserva_o_resto(self):
        self.arvore()
        self.respostas = {
            "cvm-col-a": {"situacao": "decidido", "ementa": "O Colegiado concedeu a dispensa.",
                          "tema": "ofertas-publicas", "resultado": "deferido",
                          "relator": "Outro"},
            # o modelo diz decidido, mas o texto termina com pedido de vista: fica vazio
            "cvm-col-b": {"situacao": "decidido", "ementa": "Não entra (fora do escopo).",
                          "tema": "multa-cominatoria-taxa", "resultado": "indeferido"},
            "cvm-col-tc1": {"situacao": "decidido", "ementa": "Nova ementa do TC.",
                            "resultado": "rejeitado"},
            "cvm-col-tc2": {"situacao": "suspenso", "resultado": ""},
            "cvm-pas-1": {"situacao": "decidido", "ementa": "Nova ementa do PAS.",
                          "resultado": "condenacao"}}
        self.rodar()
        antes = self.plugins()
        rel = self.aplicar("--simular")
        self.assertEqual(self.plugins(), antes)  # simulado: nada gravado
        self.assertTrue(rel["simulado"])
        os.remove(os.path.join(self.saida, [x for x in os.listdir(self.saida)
                                            if x.startswith("aplicacao-")][0]))
        rel = self.aplicar()
        depois = self.plugins()
        a = [c for c in depois if c.endswith("cvm-col-a.md")][0]
        v, _ = ex.ler_julgado(a)
        self.assertEqual(v["ementa"], "O Colegiado concedeu a dispensa.")
        self.assertEqual(v["ementa_fonte"], "extracao")
        self.assertEqual(v["resultado"], "deferido")
        self.assertEqual((v["tema"], v["tema_fonte"]), ("ofertas-publicas", "extracao"))
        self.assertEqual(v["relator"], "SEP")  # relator não é reaplicado
        self.assertEqual(v["normas_citadas"], "cvm-res-160")
        # o resto do arquivo fica igual: só as linhas de ementa, resultado e tema mudam
        linhas_antes = antes[a].splitlines()
        linhas_depois = depois[a].splitlines()
        self.assertEqual(len(linhas_antes), len(linhas_depois))
        mudaram = {x.split(":")[0] for x, y in zip(linhas_antes, linhas_depois) if x != y}
        self.assertEqual(mudaram, {"resultado", "ementa", "tema"})
        b = [c for c in depois if c.endswith("cvm-col-b.md")][0]
        vb, _ = ex.ler_julgado(b)
        self.assertEqual(vb["resultado"], "")
        self.assertEqual(vb["ementa"], "Recurso.")  # ementa fora do escopo
        self.assertEqual(vb["tema"], "processual")  # tema do script fica
        self.assertEqual(rel["conflitos_situacao"][0]["id"], "cvm-col-b")
        self.assertEqual(rel["resultado_esvaziado"][0]["antes"], "indeferido")
        tc1 = ex.ler_julgado([c for c in depois if c.endswith("cvm-col-tc1.md")][0])[0]
        self.assertEqual((tc1["ementa"], tc1["resultado"]), ("Nova ementa do TC.", "aceito"))
        tc2 = ex.ler_julgado([c for c in depois if c.endswith("cvm-col-tc2.md")][0])[0]
        self.assertEqual(tc2["resultado"], "")
        pas = ex.ler_julgado([c for c in depois if c.endswith("cvm-pas-1.md")][0])[0]
        self.assertEqual((pas["ementa"], pas["resultado"]), ("Nova ementa do PAS.", ""))
        self.assertEqual(rel["contagens"]["arquivos"], 5)

    def test_ementa_reprovada_duas_vezes_fica_a_do_titulo(self):
        self.arvore()
        self.respostas = {"cvm-col-a": {"situacao": "decidido", "resultado": "deferido",
                                        "ementa": " ".join(["palavra"] * 70)}}
        self.rodar()
        self.assertEqual(self.chamadas[-1], ["cvm-col-a"])  # retentativa só da ementa no escopo
        rel = self.aplicar()
        v, corpo = ex.ler_julgado([c for c in self.plugins() if c.endswith("cvm-col-a.md")][0])
        titulo = re.search(r"(?m)^# (.+)$", corpo).group(1)
        self.assertEqual(v["ementa"], jc.ementa_de_titulo(titulo, "dispensa"))
        self.assertEqual(v["ementa_fonte"], "titulo")
        self.assertEqual(v["resultado"], "deferido")
        self.assertEqual(rel["ementa_do_titulo"], ["cvm-col-a"])


if __name__ == "__main__":
    unittest.main()
