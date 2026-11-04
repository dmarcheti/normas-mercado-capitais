"""Testes do reconverter.py: separação por tipo, recusa de id desconhecido, conferência dos
campos extraídos e caminho mudado. Os conversores são falsos (gravam no diretório temporário)."""
import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import julgados_comum as jc  # noqa: E402
import julgados_extracao as je  # noqa: E402
import reconverter as rc  # noqa: E402

COL = "cvm-col-20220222-d2485"
PAS = "cvm-pas-19957-000001-2020-00"
CRS = "crsfn-10372-100333-2019-81"
CONHECIDOS = ({COL, PAS}, {CRS})


def _valores(id_, tipo, data, **kw):
    v = {"id": id_, "orgao": "CVM", "tipo": tipo, "data": data}
    v.update(kw)
    return v


def _gravar(raiz, valores, corpo="Corpo.\n"):
    c = jc.caminho_julgado(valores["tipo"], valores["id"], valores["data"][:4], raiz)
    os.makedirs(os.path.dirname(c), exist_ok=True)
    with open(c, "w", encoding="utf-8") as f:
        f.write(jc.frontmatter(valores) + corpo)
    return c


class Base(unittest.TestCase):
    def setUp(self):
        self.raiz = tempfile.mkdtemp()
        self.chamadas = []

    def tearDown(self):
        shutil.rmtree(self.raiz)

    def falso(self, nome, novos=None):
        """Conversor falso: anota a chamada e grava os valores novos de cada id (sem preservar)."""
        def conv(ids, raiz):
            self.chamadas.append((nome, list(ids)))
            for i in ids:
                if novos and i in novos:
                    _gravar(raiz, novos[i], "Corpo novo.\n")
            return 0
        return conv

    def rodar(self, ids, novos=None):
        return rc.reconverter(ids, self.raiz, converter_cvm=self.falso("cvm", novos),
                              converter_crsfn=self.falso("crsfn", novos), conhecidos_=CONHECIDOS)


class LerIdsTest(unittest.TestCase):
    def test_ids_e_lista(self):
        d = tempfile.mkdtemp()
        try:
            lista = os.path.join(d, "ids.txt")
            with open(lista, "w", encoding="utf-8") as f:
                f.write("# comentario\n%s\n%s, %s  # fim\n\n" % (PAS, CRS, COL))
            self.assertEqual(rc.ler_ids(COL + ", " + PAS + ",", lista), [COL, PAS, CRS])
        finally:
            shutil.rmtree(d)

    def test_vazio(self):
        self.assertEqual(rc.ler_ids("", None), [])


class SepararTest(Base):
    def test_desconhecido_recusa_tudo(self):
        rel = self.rodar([COL, "cvm-col-29990101-d9"])
        self.assertEqual(rel["rc"], 2)
        self.assertEqual(rel["desconhecidos"], ["cvm-col-29990101-d9"])
        self.assertEqual(self.chamadas, [])

    def test_lista_vazia(self):
        self.assertEqual(self.rodar([])["rc"], 2)
        self.assertEqual(self.chamadas, [])

    def test_sem_crsfn_nao_chama_crsfn(self):
        v = _valores(COL, "decisao-colegiado", "2022-02-22")
        _gravar(self.raiz, v)
        rel = self.rodar([COL], {COL: v})
        self.assertEqual(self.chamadas, [("cvm", [COL])])
        self.assertEqual(rel["rc"], 0)

    def test_so_crsfn_nao_chama_cvm(self):
        v = _valores(CRS, "acordao-crsfn", "2019-05-10")
        _gravar(self.raiz, v)
        self.rodar([CRS], {CRS: v})
        self.assertEqual(self.chamadas, [("crsfn", [CRS])])

    def test_mista_separa(self):
        novos = {COL: _valores(COL, "decisao-colegiado", "2022-02-22"),
                 PAS: _valores(PAS, "pas", "2022-03-01"),
                 CRS: _valores(CRS, "acordao-crsfn", "2019-05-10")}
        for v in novos.values():
            _gravar(self.raiz, v)
        rel = self.rodar([CRS, COL, PAS], novos)
        self.assertEqual(self.chamadas, [("cvm", [COL, PAS]), ("crsfn", [CRS])])
        self.assertEqual(rel["rc"], 0)

    def test_ausente_depois(self):
        rel = self.rodar([COL], {})
        self.assertEqual(rel["ausentes"], [COL])
        self.assertEqual(rel["rc"], 1)

    def test_main_id_desconhecido(self):
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            r = rc.main(["--ids", "nao-existe", "--raiz", self.raiz],
                        converter_cvm=self.falso("cvm"), converter_crsfn=self.falso("crsfn"),
                        conhecidos_=CONHECIDOS)
        self.assertEqual(r, 2)
        self.assertIn("id desconhecido: nao-existe", err.getvalue())
        self.assertEqual(self.chamadas, [])


class ConferirExtracaoTest(unittest.TestCase):
    def test_ementa_extraida_perdida(self):
        a = {"ementa_fonte": "extracao", "ementa": "E"}
        self.assertTrue(rc.conferir_extracao(a, {"ementa_fonte": "titulo", "ementa": "T"}))
        self.assertFalse(rc.conferir_extracao(a, {"ementa_fonte": "extracao", "ementa": "E"}))
        self.assertFalse(rc.conferir_extracao(a, {"ementa_fonte": "cvm", "ementa": "C"}))

    def test_tema_resultado_relator(self):
        a = {"tipo": "decisao-colegiado", "tema_fonte": "extracao", "tema": "x",
             "resultado": "deferido", "relator": "Fulano"}
        self.assertEqual(len(rc.conferir_extracao(a, {"tipo": "decisao-colegiado"})), 3)
        self.assertFalse(rc.conferir_extracao(a, dict(a)))

    def test_pas_resultado_vazio_pode_mudar(self):
        self.assertFalse(rc.conferir_extracao({"tipo": "pas", "resultado": ""},
                                              {"tipo": "pas", "resultado": "condenado"}))


class CaminhoMudadoTest(Base):
    def test_preserva_do_antigo_e_relata_orfao(self):
        antigo = _valores(COL, "decisao-colegiado", "2021-12-30", ementa="Ementa extraída.",
                          ementa_fonte="extracao", tema="ofertas", tema_fonte="extracao",
                          resultado="deferido", relator="Diretor Fulano")
        velho = _gravar(self.raiz, antigo)
        # a reconversão leu outra data (outro ano) e não preservou nada
        novo = _valores(COL, "decisao-colegiado", "2022-01-04", ementa="Título",
                        ementa_fonte="titulo")
        rel = self.rodar([COL], {COL: novo})
        self.assertEqual(rel["rc"], 1)
        self.assertEqual(rel["orfaos"], {COL: [velho]})
        self.assertNotIn(COL, rel["problemas"])
        self.assertTrue(os.path.exists(velho))
        v, corpo = je.ler_julgado(jc.caminho_julgado("decisao-colegiado", COL, "2022", self.raiz))
        self.assertEqual((v["ementa"], v["ementa_fonte"]), ("Ementa extraída.", "extracao"))
        self.assertEqual((v["tema"], v["tema_fonte"], v["resultado"], v["relator"]),
                         ("ofertas", "extracao", "deferido", "Diretor Fulano"))
        self.assertIn("Corpo novo.", corpo)

    def test_mesmo_caminho_campo_perdido_e_problema(self):
        _gravar(self.raiz, _valores(COL, "decisao-colegiado", "2022-02-22", resultado="deferido"))
        rel = self.rodar([COL], {COL: _valores(COL, "decisao-colegiado", "2022-02-22")})
        self.assertIn(COL, rel["problemas"])
        self.assertEqual(rel["rc"], 1)


class CorrecaoUmTest(Base):
    """Rodada de correção 1: não regravado, frontmatter ilegível, --so-cache, conversor com erro."""

    def test_conversor_pula_id_sem_erro(self):
        _gravar(self.raiz, _valores(COL, "decisao-colegiado", "2022-02-22"))
        rel = self.rodar([COL], {})  # o falso não grava nada e devolve 0
        self.assertEqual(rel["nao_regravados"], [COL])
        self.assertEqual(rel["rc"], 1)

    def test_antigo_ilegivel_e_problema(self):
        c = jc.caminho_julgado("decisao-colegiado", COL, "2022", self.raiz)
        os.makedirs(os.path.dirname(c))
        with open(c, "w", encoding="utf-8") as f:
            f.write("sem frontmatter\nid: %s\n" % COL)
        rel = self.rodar([COL], {COL: _valores(COL, "decisao-colegiado", "2022-02-22")})
        self.assertIn("frontmatter anterior ilegível", rel["problemas"][COL][0])
        self.assertEqual(rel["rc"], 1)

    def test_conversor_com_erro_sai_1(self):
        v = _valores(COL, "decisao-colegiado", "2022-02-22")
        _gravar(self.raiz, v)

        def falha(ids, raiz):
            _gravar(raiz, v, "Corpo novo.\n")
            return 1
        rel = rc.reconverter([COL], self.raiz, converter_cvm=falha,
                             converter_crsfn=self.falso("crsfn"), conhecidos_=CONHECIDOS)
        self.assertEqual(rel["conversor_rc"], {"cvm": 1})
        self.assertEqual(rel["rc"], 1)

    def test_so_cache_recusa_lote_sem_converter(self):
        rel = rc.reconverter([COL, CRS], self.raiz, converter_cvm=self.falso("cvm"),
                             converter_crsfn=self.falso("crsfn"), conhecidos_=CONHECIDOS,
                             so_cache=True, fora_do_cache_=lambda a, b, raiz: [CRS])
        self.assertEqual((rel["sem_cache"], rel["rc"]), ([CRS], 1))
        self.assertEqual(self.chamadas, [])

    def test_so_cache_passa_ao_crsfn(self):
        v = _valores(CRS, "acordao-crsfn", "2019-05-10")
        _gravar(self.raiz, v)
        visto = {}

        def conv(ids, raiz, so_cache=False):
            visto["so_cache"] = so_cache
            _gravar(raiz, v, "Corpo novo.\n")
            return 0
        rel = rc.reconverter([CRS], self.raiz, converter_crsfn=conv, conhecidos_=CONHECIDOS,
                             so_cache=True, fora_do_cache_=lambda a, b, raiz: [])
        self.assertEqual((visto, rel["rc"]), ({"so_cache": True}, 0))

    def test_fora_do_cache(self):
        import crsfn
        it = {"id": COL, "tipo": "termo-compromisso", "data": "2022-02-22"}
        cache_cvm = os.path.join(self.raiz, "dados", "fase-2d", "cache")
        pasta = os.path.join(cache_cvm, "termo-compromisso", "2022", COL)
        os.makedirs(pasta)
        with open(os.path.join(pasta, "registro.json"), "w", encoding="utf-8") as f:
            f.write('{"arquivos": [{"arquivo": "01-pagina.html"}]}')
        self.assertEqual(rc.fora_do_cache([COL], [CRS], self.raiz, [it]), [COL, CRS])
        open(os.path.join(pasta, "01-pagina.html"), "w").close()
        cache_crs = crsfn.caminhos(self.raiz)["cache"]
        os.makedirs(cache_crs)
        with open(os.path.join(cache_crs, CRS + ".json"), "w", encoding="utf-8") as f:
            f.write('{"arquivo": "%s.pdf"}' % CRS)
        self.assertEqual(rc.fora_do_cache([COL], [CRS], self.raiz, [it]), [CRS])
        open(os.path.join(cache_crs, CRS + ".pdf"), "w").close()
        self.assertEqual(rc.fora_do_cache([COL], [CRS], self.raiz, [it]), [])

    def test_cliente_sem_rede(self):
        with self.assertRaises(RuntimeError):
            rc.ClienteSemRede().get("https://exemplo.invalid/")

    def test_main_lista_ponta_a_ponta(self):
        novos = {COL: _valores(COL, "decisao-colegiado", "2022-02-22", resultado="deferido"),
                 CRS: _valores(CRS, "acordao-crsfn", "2019-05-10")}
        for v in novos.values():
            _gravar(self.raiz, v)
        lista = os.path.join(self.raiz, "ids.txt")
        with open(lista, "w", encoding="utf-8") as f:
            f.write("# lote\n%s\n%s\n" % (COL, CRS))
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            r = rc.main(["--lista", lista, "--raiz", self.raiz],
                        converter_cvm=self.falso("cvm", novos),
                        converter_crsfn=self.falso("crsfn", novos), conhecidos_=CONHECIDOS)
        self.assertEqual(r, 0, err.getvalue())
        self.assertEqual(self.chamadas, [("cvm", [COL]), ("crsfn", [CRS])])
        self.assertIn("1 da CVM, 1 do CRSFN; 0 ausente(s), 0 não regravado(s)", out.getvalue())


if __name__ == "__main__":
    unittest.main()
