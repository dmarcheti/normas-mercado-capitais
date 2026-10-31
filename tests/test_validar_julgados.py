"""Testes do validador dos julgados (SPEC v0.5.0), sem rede."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import validar  # noqa: E402

IDS = frozenset(["cvm-res-175", "lei-6404", "lei-6385", "cvm-instr-489"])

BASE = {
    "id": "cvm-pas-19957-011607-2024-20",
    "orgao": "cvm",
    "tipo": "pas",
    "classe": "",
    "processo": "19957.011607/2024-20",
    "nup": "19957-011607-2024-20",
    "rito": "ordinario",
    "data": "2025-05-27",
    "relator": "Dir. Fulano",
    "resultado": "condenacao",
    "ementa": "PAS. Dever de diligência de administradores. Multa.",
    "ementa_fonte": "cvm",
    "tema": "deveres-administradores",
    "tema_fonte": "script",
    "normas_citadas": "lei-6404; fora:icvm-358",
    "dispositivos_citados": "lei-6404 art. 155, § 1º; fora:icvm-358 art. 3º",
    "fonte_original": "https://conteudo.cvm.gov.br/sancionadores/sancionador/2025/x.html",
    "sha256_fonte": "a" * 64,
    "baixado_em": "2026-10-30",
    "nivel_verificacao": "html-convertido",
    "incerteza": "",
}
ORDEM = list(BASE)
CORPO = "# PAS CVM nº 19957.011607/2024-20\n\n## Relatório\n\nTexto.\n\n## Voto\n\nTexto.\n"


def montar(valores, corpo=CORPO, ordem=None):
    linhas = ["---"]
    for c in ordem or ORDEM:
        if c in valores:
            linhas.append("%s: %s" % (c, valores[c]) if valores[c] else "%s:" % c)
    return "\n".join(linhas + ["---", "", corpo])


class TestValidarJulgado(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = os.path.join(self.tmp.name, "plugins", "julgados-pas", "julgados")

    def tearDown(self):
        self.tmp.cleanup()

    def gravar(self, rel, texto):
        p = os.path.join(self.raiz, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(texto)
        return p

    def erros(self, mudancas=None, rel="cvm/pas/2025/19957-011607-2024-20.md", corpo=CORPO, ordem=None,
              ids=IDS):
        v = dict(BASE, **(mudancas or {}))
        v = {k: x for k, x in v.items() if x is not None}
        return validar.validar_julgado(self.gravar(rel, montar(v, corpo, ordem)), ids)

    def test_pas_valido(self):
        self.assertEqual(self.erros(), [])

    def test_colegiado_tc_antiga_crsfn_validos(self):
        col = {"id": "cvm-col-20251202-d3228", "tipo": "decisao-colegiado", "classe": "recurso",
               "data": "2025-12-02", "resultado": "nao-provido", "rito": "", "nup": "", "ementa_fonte": "extracao"}
        self.assertEqual(self.erros(col, "cvm/colegiado/2025/col-20251202-d3228.md"), [])
        # matéria institucional (agenda regulatória, PAINT): a CVM não publica número de processo
        self.assertEqual(self.erros(dict(col, processo=""), "cvm/colegiado/2025/col-20251202-d3228.md"), [])
        tc = dict(col, id="cvm-tc-19957-011607-2024-20-20250603", tipo="termo-compromisso", classe="",
                  data="2025-06-03", resultado="aceito")
        self.assertEqual(self.erros(tc, "cvm/colegiado/2025/tc-19957-011607-2024-20-20250603.md"), [])
        # TC de item do Colegiado sem número publicado ("ALTERAÇÃO DA DELIBERAÇÃO 390/01 - TERMO
        # DE COMPROMISSO"); o TC da listagem, que nasce do processo, continua exigindo o número
        tc_col = dict(col, tipo="termo-compromisso", classe="", resultado="aceito", processo="")
        self.assertEqual(self.erros(tc_col, "cvm/colegiado/2025/col-20251202-d3228.md"), [])
        self.assertIn("processo vazio", self.erros(
            dict(tc, processo=""), "cvm/colegiado/2025/tc-19957-011607-2024-20-20250603.md"))
        antiga = dict(col, id="cvm-dec-1995-012", tipo="decisao-antiga", classe="", processo="",
                      data="1995-03-10", resultado="", ementa_fonte="titulo", nivel_verificacao="ocr")
        self.assertEqual(self.erros(antiga, "cvm/decisoes-antigas/1995-012.md"), [])
        crsfn = dict(BASE, id="crsfn-10372-000123-2019-11", orgao="crsfn", tipo="acordao-crsfn",
                     data="2021-04-15", resultado="parcial", ementa_fonte="crsfn", nivel_verificacao="pdf-extraido")
        self.assertEqual(self.erros(crsfn, "crsfn/2021/10372-000123-2019-11.md"), [])

    def test_ordem_e_conjunto_de_chaves(self):
        ordem = list(ORDEM)
        ordem[0], ordem[1] = ordem[1], ordem[0]
        self.assertTrue(any("fora da ordem" in e for e in self.erros(ordem=ordem)))
        self.assertIn("campo obrigatório ausente: rito", self.erros({"rito": None}))
        texto = montar(BASE).replace("incerteza:\n", "incerteza:\nacusados: X\n")
        p = self.gravar("cvm/pas/2025/19957-011607-2024-20.md", texto)
        self.assertIn("campo desconhecido: acusados", validar.validar_julgado(p, IDS))

    def test_vazios(self):
        self.assertIn("ementa vazio", self.erros({"ementa": ""}))
        self.assertIn("processo vazio", self.erros({"processo": ""}))
        self.assertEqual(self.erros({"relator": "", "resultado": "", "nup": "", "rito": "", "incerteza": "",
                                     "normas_citadas": "", "dispositivos_citados": "",
                                     "tema": "", "tema_fonte": ""}), [])

    def test_coerencia_tipo_orgao_id_caminho(self):
        self.assertTrue(any("orgao deve ser" in e for e in self.erros({"orgao": "crsfn"})))
        self.assertTrue(any("tipo" in e and "desconhecido" in e for e in self.erros({"tipo": "acordao"})))
        self.assertTrue(any("fora do padrão" in e for e in self.erros({"id": "cvm-col-20250527-d1"})))
        self.assertTrue(any("caminho" in e for e in self.erros(rel="cvm/pas/2024/19957-011607-2024-20.md")))
        self.assertTrue(any("caminho" in e for e in self.erros(rel="cvm/pas/2025/outro.md")))
        e = self.erros({"id": "cvm-dec-1994", "tipo": "decisao-antiga", "data": "1995-01-01", "processo": "",
                        "resultado": ""}, "cvm/decisoes-antigas/1994.md")
        self.assertTrue(any("ano do id" in x for x in e))

    def test_datas_e_listas_fechadas(self):
        self.assertTrue(any("data deve ser" in e for e in self.erros({"data": "2025-02-30"})))
        self.assertTrue(any("resultado" in e for e in self.erros({"resultado": "aceito"})))
        self.assertTrue(any("ementa_fonte" in e for e in self.erros({"ementa_fonte": "llm"})))
        self.assertTrue(any("tema_fonte" in e for e in self.erros({"tema_fonte": "manual"})))
        self.assertTrue(any("nivel_verificacao" in e for e in self.erros({"nivel_verificacao": "compilado-planalto"})))
        self.assertTrue(any("rito" in e for e in self.erros({"rito": "sumario"})))
        self.assertTrue(any("classe" in e for e in self.erros({"classe": "Recurso"})))
        self.assertTrue(any("nup" in e for e in self.erros({"nup": "19957.011607/2024-20"})))
        self.assertTrue(any("sha256" in e for e in self.erros({"sha256_fonte": "abc"})))
        self.assertIn("tema preenchido sem tema_fonte", self.erros({"tema_fonte": ""}))

    def test_classe_obrigatoria_no_colegiado(self):
        col = {"id": "cvm-col-20251202-d3228", "tipo": "decisao-colegiado", "classe": "",
               "data": "2025-12-02", "resultado": "deferido"}
        self.assertTrue(any("classe vazia" in e for e in self.erros(col, "cvm/colegiado/2025/col-20251202-d3228.md")))

    def test_citacoes(self):
        self.assertTrue(any("não está no normas.json" in e for e in self.erros({"normas_citadas": "cvm-res-999"})))
        self.assertTrue(any("está no acervo" in e for e in self.erros({"normas_citadas": "fora:res-cvm-175"})))
        self.assertTrue(any("fora do formato" in e
                            for e in self.erros({"dispositivos_citados": "lei-6404 artigo 155"})))
        self.assertTrue(any("não está no normas.json" in e
                            for e in self.erros({"dispositivos_citados": "lei-9999 art. 1º"})))
        self.assertTrue(any("repetido" in e for e in self.erros({"normas_citadas": "lei-6404; lei-6404"})))
        # sem normas.json: só o formato
        self.assertEqual(self.erros({"normas_citadas": "cvm-res-999"}, ids=frozenset()), [])

    def test_corpo(self):
        self.assertTrue(any("'# <título>'" in e for e in self.erros(corpo="## Relatório\n\nx\n")))
        self.assertTrue(any("seção '## '" in e for e in self.erros(corpo="# Título\n\nsó texto\n")))


class TestMainJulgados(unittest.TestCase):
    def rodar(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = validar.main(argv)
        return rc, out.getvalue()

    def test_raiz_inexistente_passa(self):
        rc, _ = self.rodar(["validar.py", "/nao/existe/plugins/julgados-x/julgados"])
        self.assertEqual(rc, 0)

    def test_raiz_julgados_valida_e_pula_indices(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = os.path.join(tmp, "julgados")
            os.makedirs(os.path.join(raiz, "indices"))
            os.makedirs(os.path.join(raiz, "cvm", "pas", "2025"))
            for rel in ("indice.md", "indices/pas-2025.md"):
                with open(os.path.join(raiz, rel), "w", encoding="utf-8") as f:
                    f.write("# Índice\n")
            with open(os.path.join(raiz, "cvm", "pas", "2025", "19957-011607-2024-20.md"), "w",
                      encoding="utf-8") as f:
                f.write(montar(BASE))
            nj = os.path.join(tmp, "normas.json")
            with open(nj, "w", encoding="utf-8") as f:
                json.dump([{"id": i} for i in sorted(IDS)], f)
            rc, out = self.rodar(["validar.py", raiz, "--normas-json", nj])
            self.assertEqual(rc, 0, out)
            self.assertIn("1 julgado(s), 0 erro(s)", out)
            with open(os.path.join(raiz, "cvm", "pas", "2025", "19957-011607-2024-20.md"), "w",
                      encoding="utf-8") as f:
                f.write(montar(dict(BASE, resultado="aceito")))
            rc, out = self.rodar(["validar.py", raiz, "--normas-json", nj])
            self.assertEqual(rc, 1)

    def test_opcao_julgados_e_uso(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = self.rodar(["validar.py", tmp, "--julgados"])
            self.assertEqual(rc, 0)
            self.assertIn("nenhum julgado", out)
        self.assertEqual(self.rodar(["validar.py"])[0], 2)
        self.assertEqual(self.rodar(["validar.py", "x", "--normas-json"])[0], 2)


if __name__ == "__main__":
    unittest.main()
