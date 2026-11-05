"""Testes da varredura do histórico. Repositórios git descartáveis em diretório temporário; CPF, RG e
e-mail fictícios montados em pedaços, para que este arquivo não dispare a varredura do pre-commit."""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pii  # noqa: E402
import varrer_historico as vh  # noqa: E402

M = pii.MARCADOR
CPF_A = "123.456." + "789-09"
CPF_A_PURO = "123456" + "78909"
RG_NUM = "12.345." + "678-9"
EMAIL_PESSOAL = "pessoa" + "@" + "exemplo-pessoal.com"
TERMO = "Termo Proibido Zeta"
RECORTE = "a testemunha " + M + ", brasileiro, casado, engenheiro, residente"
JULGADO = "plugins/julgados-cvm/julgados/2025.md"
NORMA = "plugins/normas/atos/norma-x.md"
CONTROLE_ARQ = "plugins/normas/atos/ctl.md"
APAGADO = "legado/apagado.md"
RECORTE_ARQ = "notas/recorte.md"
BINARIO = "notas/dados-bin.md"
LATERAL = "lateral/x.md"


def _cpf(base9):
    """CPF formatado com dígitos verificadores calculados (fictício)."""
    d = [int(c) for c in base9]
    for n in (9, 10):
        s = sum(d[i] * (n + 1 - i) for i in range(n))
        d.append((s * 10) % 11 % 10)
    t = "".join(map(str, d))
    return "%s.%s.%s-%s" % (t[:3], t[3:6], t[6:9], t[9:])


CPF_B = _cpf("111444" + "777")
CPF_C = _cpf("222333" + "444")


def _env(autor=None):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="Autor Teste", GIT_AUTHOR_EMAIL="autor@exemplo.invalid",
               GIT_COMMITTER_NAME="Autor Teste", GIT_COMMITTER_EMAIL="autor@exemplo.invalid")
    if autor:
        env["GIT_AUTHOR_EMAIL"] = autor
    return env


def git(cwd, *args, env=None):
    r = subprocess.run(["git", "-C", cwd, "-c", "commit.gpgsign=false"] + list(args), check=True,
                       capture_output=True, env=env or _env())
    return r.stdout.decode("utf-8", "replace").strip()


def commitar(repo, arquivos, msg, autor=None):
    """arquivos: caminho -> str | bytes | None (None apaga). Devolve o hash do commit."""
    for caminho, conteudo in arquivos.items():
        destino = os.path.join(repo, caminho)
        if conteudo is None:
            os.remove(destino)
            continue
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "wb") as f:
            f.write(conteudo if isinstance(conteudo, bytes) else conteudo.encode("utf-8"))
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg, env=_env(autor))
    return git(repo, "rev-parse", "HEAD")


def novo_repo(raiz):
    repo = os.path.join(raiz, "repo")
    os.makedirs(repo)
    git(repo, "init", "-q", "-b", "main")
    return repo


def julgado_antigo():
    return "# Julgados 2025\nLinha comum A\nO acusado, CPF %s, compareceu.\nLinha comum B\n" % CPF_A


def julgado_novo():
    return julgado_antigo().replace(CPF_A, M)


def rodar(repo, saida, termos, *extra, base="main", processos="1"):
    """Roda main() em processo; devolve (código, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        codigo = vh.main(["--repo", repo, "--saida", saida, "--termos", termos, "--base", base,
                          "--processos", processos] + list(extra))
    return codigo, out.getvalue(), err.getvalue()


def ler_jsonl(caminho):
    with open(caminho, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def ler_json(caminho):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def escrever_termos(caminho, *termos):
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("# lista de teste\n" + "\n".join(termos) + "\n")


class HistoricoCompletoTest(unittest.TestCase):
    """Um repositório com os seis cenários do brief, varrido uma vez."""

    @classmethod
    def setUpClass(cls):
        cls.raiz = tempfile.mkdtemp()
        cls.repo = novo_repo(cls.raiz)
        cls.termos = os.path.join(cls.raiz, "termos.txt")
        escrever_termos(cls.termos, TERMO)
        cls.c1 = commitar(cls.repo, {
            JULGADO: julgado_antigo(),
            NORMA: "# Norma X\nArt. 1º Texto neutro.\nTexto com %s aqui.\n" % TERMO,
            APAGADO: "Parte: Fulano, CPF %s\nOutra linha comum\n" % CPF_B,
            RECORTE_ARQ: "Cabeçalho\n%s\n" % RECORTE,
            CONTROLE_ARQ: "linha boa\nlinha\x01ruim\n",
            BINARIO: b"\xff\xfe\x00\xc3(",
        }, "grava os julgados")
        git(cls.repo, "checkout", "-q", "-b", "lateral")
        cls.c_lateral = commitar(cls.repo, {LATERAL: "Parte: Beltrano, CPF %s\n" % CPF_C}, "ramo lateral")
        git(cls.repo, "checkout", "-q", "main")
        cls.c2 = commitar(cls.repo, {
            JULGADO: julgado_novo(),
            NORMA: "# Norma X\nArt. 1º Texto neutro.\n",
            APAGADO: None,
            RECORTE_ARQ: "Cabeçalho\n%s\nLinha nova\n" % RECORTE,
            CONTROLE_ARQ: "linha boa\nlinha ruim\n",
        }, "limpa os julgados")
        cls.c3 = commitar(cls.repo, {"notas/nova.md": "ok\n"}, "merge pela interface", autor=EMAIL_PESSOAL)
        cls.c4 = commitar(cls.repo, {BINARIO: None}, "tira o arquivo estranho")
        cls.saida = os.path.join(cls.raiz, "saida")
        cls.codigo, cls.stdout, cls.stderr = rodar(cls.repo, cls.saida, cls.termos)
        cls.achados = ler_jsonl(os.path.join(cls.saida, "achados.jsonl"))
        cls.rel = ler_json(os.path.join(cls.saida, "relatorio.json"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.raiz, ignore_errors=True)

    def blob(self, caminho, regra=None):
        return [a for a in self.achados if a.get("tipo") == "blob" and caminho in a["caminhos"]
                and (regra is None or a["regra"] == regra)]

    def test_precondicoes_do_cenario(self):
        # a linha já limpa que o pii recorta de novo (cenário 5) tem de ser recortada de fato
        self.assertNotEqual(pii.limpar(RECORTE), RECORTE)

    def test_cpf_do_julgado_antigo(self):
        a = self.blob(JULGADO, "pii-cpf")
        self.assertEqual(len(a), 1)
        a = a[0]
        self.assertIn(CPF_A, a["original"])
        self.assertIn(M, a["limpo"])
        self.assertNotIn(CPF_A, a["limpo"])
        self.assertEqual(a["linhas"], [3])
        self.assertTrue(a["publicavel"])
        self.assertEqual(a["primeiro_commit"], self.c1)
        self.assertFalse(a["caminho_fora_da_base"])

    def test_cpf_direto_tambem_aparece(self):
        a = self.blob(JULGADO, "cpf-direto")
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0]["linhas"], [3])

    def test_base_limpa_nao_gera_achado(self):
        for a in self.blob(JULGADO):
            self.assertNotIn("Linha comum", a["original"])
        # a versão da base (c2) é idêntica à da árvore: nada dela entra
        self.assertEqual({a["blob"] for a in self.blob(JULGADO)}, {a["blob"] for a in self.blob(JULGADO, "pii-cpf")})

    def test_termo_de_versao_antiga_da_norma(self):
        a = self.blob(NORMA, "termo")
        self.assertEqual(len(a), 1)
        self.assertIn(TERMO, a[0]["original"])
        self.assertEqual(a[0]["linhas"], [3])
        self.assertTrue(a[0]["publicavel"])

    def test_email_pessoal_nos_metadados(self):
        a = [x for x in self.achados if x["regra"] == "email-metadado"]
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0]["original"], EMAIL_PESSOAL)
        self.assertEqual(a[0]["commits"], [self.c3])
        self.assertEqual(a[0]["papeis"], ["autor"])
        self.assertTrue(a[0]["publicavel"])
        m = self.rel["metadados"]["commits_com_email_fora_da_lista"]
        self.assertEqual(m, {"quantidade": 1, "hashes": [self.c3]})

    def test_email_invalid_e_noreply_nao_contam(self):
        # o autor padrão do cenário é @exemplo.invalid: só o commit c3 aparece
        self.assertEqual(self.rel["metadados"]["commits_lidos"], 5)

    def test_linha_ja_limpa_que_o_pii_recorta_de_novo_fica_fora(self):
        self.assertEqual(self.blob(RECORTE_ARQ), [])

    def test_caminho_apagado_na_base(self):
        a = self.blob(APAGADO, "pii-cpf")
        self.assertEqual(len(a), 1)
        self.assertTrue(a[0]["caminho_fora_da_base"])
        self.assertIn(CPF_B, a[0]["original"])

    def test_caractere_de_controle(self):
        a = self.blob(CONTROLE_ARQ, "controle")
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0]["linhas"], [2])

    def test_blob_que_nao_e_utf8_vira_nao_lido(self):
        self.assertEqual(self.rel["blobs"]["nao_lidos"], 1)
        nl = ler_jsonl(os.path.join(self.saida, "nao-lidos.jsonl"))
        self.assertEqual([n["caminhos"] for n in nl], [[BINARIO]])
        self.assertIn("ATENÇÃO", self.stdout)
        self.assertEqual(self.rel["blobs"]["erros"], 0)

    def test_alcance_do_ramo_lateral(self):
        a = self.blob(LATERAL, "pii-cpf")
        self.assertEqual(len(a), 1)
        self.assertFalse(a[0]["publicavel"])
        self.assertEqual(a[0]["primeiro_commit"], self.c_lateral)
        # a lateral só tem uma versão do caminho, que não existe na base
        self.assertTrue(a[0]["caminho_fora_da_base"])
        pub = self.rel["achados"]["por_publicavel"]
        self.assertGreaterEqual(pub["nao-publicavel"], 2)
        self.assertGreaterEqual(pub["publicavel"], 5)

    def test_substituicoes_com_o_par_do_cpf(self):
        with open(os.path.join(self.saida, "substituicoes.txt"), encoding="utf-8") as f:
            linhas = f.read().splitlines()
        orig = "O acusado, CPF %s, compareceu." % CPF_A
        esperado = "literal:%s==>%s" % (orig, orig.replace(CPF_A, M))
        self.assertIn(esperado, linhas)

    def test_aplicacao_simulada_deixa_o_blob_igual_ao_limpo(self):
        with open(os.path.join(self.saida, "substituicoes.txt"), "rb") as f:
            pares = []
            for linha in f:
                linha = linha.rstrip(b"\r\n")
                padrao, repl = linha.rsplit(b"==>", 1)
                self.assertTrue(padrao.startswith(b"literal:"))
                pares.append((padrao[len(b"literal:"):], repl))
        for rev, caminho in ((self.c1, JULGADO), (self.c1, APAGADO)):
            bruto = subprocess.run(["git", "-C", self.repo, "show", "%s:%s" % (rev, caminho)],
                                   check=True, capture_output=True).stdout
            novo = bruto
            for padrao, repl in pares:
                novo = novo.replace(padrao, repl)
            self.assertNotEqual(novo, bruto)
            self.assertEqual(novo.decode("utf-8"), pii.limpar(bruto.decode("utf-8")))

    def test_nada_sai_nos_arquivos_sem_valores_nem_na_saida(self):
        proibidos = [CPF_A, CPF_A_PURO, CPF_B, CPF_C, EMAIL_PESSOAL, TERMO, "pessoa@", "Fulano", "Beltrano"]
        textos = [self.stdout, self.stderr]
        for nome in ("relatorio.md", "relatorio.json"):
            with open(os.path.join(self.saida, nome), encoding="utf-8") as f:
                textos.append(f.read())
        for t in textos:
            for p in proibidos:
                self.assertNotIn(p, t)
        # e o arquivo com valores, sim, tem
        with open(os.path.join(self.saida, "achados.jsonl"), encoding="utf-8") as f:
            self.assertIn(CPF_A, f.read())

    def test_relatorio_conta_por_regra_e_prefixo(self):
        r = self.rel["achados"]
        self.assertEqual(r["total"], len(self.achados))
        self.assertGreaterEqual(r["por_regra"]["pii-cpf"], 3)
        self.assertEqual(r["por_regra"]["email-metadado"], 1)
        self.assertEqual(r["por_prefixo_de_caminho"]["plugins/julgados-cvm"], 2)
        self.assertEqual(r["por_prefixo_de_caminho"]["legado"], 2)
        self.assertEqual(r["por_prefixo_de_caminho"]["lateral"], 2)
        self.assertFalse([p for p in r["por_prefixo_de_caminho"] if p.endswith(".md")])
        self.assertEqual(self.rel["codigo_de_saida"], 1)

    def test_codigo_de_saida_1_com_achado_publicavel(self):
        self.assertEqual(self.codigo, 1)

    def test_pool_de_processos_da_o_mesmo_resultado(self):
        saida = os.path.join(self.raiz, "saida-pool")
        codigo, _, _ = rodar(self.repo, saida, self.termos, processos="2")
        self.assertEqual(codigo, 1)
        chave = lambda a: json.dumps(a, sort_keys=True)  # noqa: E731
        self.assertEqual(sorted(map(chave, ler_jsonl(os.path.join(saida, "achados.jsonl")))),
                         sorted(map(chave, self.achados)))

    def test_refs_restringe_o_alcance_da_varredura(self):
        saida = os.path.join(self.raiz, "saida-main")
        codigo, _, _ = rodar(self.repo, saida, self.termos, "--refs", "main")
        achados = ler_jsonl(os.path.join(saida, "achados.jsonl"))
        self.assertEqual(codigo, 1)
        self.assertEqual([a for a in achados if a.get("tipo") == "blob" and LATERAL in a["caminhos"]], [])


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.raiz = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.raiz, ignore_errors=True)
        self.repo = novo_repo(self.raiz)
        self.termos = os.path.join(self.raiz, "termos.txt")
        escrever_termos(self.termos, TERMO)
        commitar(self.repo, {JULGADO: julgado_antigo(), NORMA: "a\n"}, "um")
        commitar(self.repo, {JULGADO: julgado_novo(), NORMA: "a\nb\n"}, "dois")
        self.saida = os.path.join(self.raiz, "saida")

    def rel(self):
        return ler_json(os.path.join(self.saida, "relatorio.json"))["blobs"]

    def test_segunda_execucao_nao_reprocessa(self):
        rodar(self.repo, self.saida, self.termos)
        b1 = self.rel()
        self.assertGreater(b1["processados_agora"], 0)
        self.assertEqual(b1["do_cache"], 0)
        antes = ler_jsonl(os.path.join(self.saida, "achados.jsonl"))
        rodar(self.repo, self.saida, self.termos)
        b2 = self.rel()
        self.assertEqual(b2["processados_agora"], 0)
        self.assertEqual(b2["do_cache"], b1["processados_agora"])
        self.assertEqual(ler_jsonl(os.path.join(self.saida, "achados.jsonl")), antes)

    def test_mudar_a_lista_de_termos_invalida(self):
        rodar(self.repo, self.saida, self.termos)
        n = self.rel()["processados_agora"]
        escrever_termos(self.termos, TERMO, "Outro Termo")
        rodar(self.repo, self.saida, self.termos)
        b = self.rel()
        self.assertEqual((b["processados_agora"], b["do_cache"]), (n, 0))

    def test_linha_truncada_no_cache_e_ignorada(self):
        rodar(self.repo, self.saida, self.termos)
        n = self.rel()["processados_agora"]
        with open(os.path.join(self.saida, "cache.jsonl"), "a", encoding="utf-8") as f:
            f.write('{"blob": "abc", "regr')
        rodar(self.repo, self.saida, self.termos)
        self.assertEqual(self.rel()["do_cache"], n)

    def test_base_que_muda_invalida_so_o_blob_afetado(self):
        rodar(self.repo, self.saida, self.termos)
        commitar(self.repo, {NORMA: "a\nb\nc\n"}, "tres")
        rodar(self.repo, self.saida, self.termos)
        b = self.rel()
        # só o blob antigo da norma (cuja base mudou) e o novo da base (idêntico, pulado) mudam
        self.assertLess(b["processados_agora"], b["considerados"])
        self.assertGreater(b["do_cache"], 0)


class CodigoDeSaidaTest(unittest.TestCase):
    def setUp(self):
        self.raiz = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.raiz, ignore_errors=True)
        self.termos = os.path.join(self.raiz, "termos.txt")
        escrever_termos(self.termos, TERMO)
        self.saida = os.path.join(self.raiz, "saida")

    def test_zero_sem_achado(self):
        repo = novo_repo(self.raiz)
        commitar(repo, {"a.md": "texto neutro\n"}, "um")
        commitar(repo, {"a.md": "texto neutro\noutra\n"}, "dois")
        codigo, out, _ = rodar(repo, self.saida, self.termos)
        self.assertEqual(codigo, 0)
        self.assertIn("achados: 0", out)

    def test_zero_com_achado_so_fora_do_alcance_publicavel(self):
        repo = novo_repo(self.raiz)
        commitar(repo, {"a.md": "texto neutro\n"}, "um")
        git(repo, "checkout", "-q", "-b", "lateral")
        commitar(repo, {"b.md": "Parte: Beltrano, CPF %s\n" % CPF_C}, "lateral")
        git(repo, "checkout", "-q", "main")
        codigo, _, _ = rodar(repo, self.saida, self.termos)
        self.assertEqual(codigo, 0)
        rel = ler_json(os.path.join(self.saida, "relatorio.json"))
        self.assertEqual(rel["achados"]["por_publicavel"], {"publicavel": 0, "nao-publicavel": 2})

    def test_tag_torna_o_blob_publicavel(self):
        repo = novo_repo(self.raiz)
        commitar(repo, {"a.md": "texto neutro\n"}, "um")
        git(repo, "checkout", "-q", "-b", "lateral")
        commitar(repo, {"b.md": "Parte: Beltrano, CPF %s\n" % CPF_C}, "lateral")
        git(repo, "tag", "v1")
        git(repo, "checkout", "-q", "main")
        codigo, _, _ = rodar(repo, self.saida, self.termos)
        self.assertEqual(codigo, 1)

    def test_dois_com_repo_invalido(self):
        codigo, out, err = rodar(os.path.join(self.raiz, "nao-existe"), self.saida, self.termos)
        self.assertEqual(codigo, 2)
        self.assertIn("erro de execução", err)

    def test_dois_com_diretorio_que_nao_e_repo(self):
        vazio = os.path.join(self.raiz, "vazio")
        os.makedirs(vazio)
        self.assertEqual(rodar(vazio, self.saida, self.termos)[0], 2)

    def test_dois_com_base_inexistente(self):
        repo = novo_repo(self.raiz)
        commitar(repo, {"a.md": "x\n"}, "um")
        self.assertEqual(rodar(repo, self.saida, self.termos, base="nao-existe")[0], 2)

    def test_dois_sem_lista_de_termos(self):
        repo = novo_repo(self.raiz)
        commitar(repo, {"a.md": "x\n"}, "um")
        self.assertEqual(rodar(repo, self.saida, os.path.join(self.raiz, "sem-lista.txt"))[0], 2)

    def test_dois_quando_a_saida_com_valores_ficaria_fora_de_dados(self):
        repo = novo_repo(self.raiz)
        commitar(repo, {"a.md": "x\n"}, "um")
        self.assertEqual(rodar(repo, os.path.join(repo, "saida"), self.termos)[0], 2)
        self.assertEqual(rodar(repo, os.path.join(repo, "dados", "saida"), self.termos)[0], 0)

    def test_dois_quando_um_blob_da_erro(self):
        repo = novo_repo(self.raiz)
        commitar(repo, {"a.md": "x\n"}, "um")
        commitar(repo, {"a.md": "y\n"}, "dois")
        original = vh.analisar_texto
        vh.analisar_texto = lambda *a, **k: 1 / 0
        try:
            codigo, _, err = rodar(repo, self.saida, self.termos)
        finally:
            vh.analisar_texto = original
        self.assertEqual(codigo, 2)
        self.assertIn("ZeroDivisionError", err)
        self.assertEqual(ler_json(os.path.join(self.saida, "relatorio.json"))["blobs"]["erros"], 1)

    def test_processo_de_verdade_devolve_o_codigo(self):
        repo = novo_repo(self.raiz)
        commitar(repo, {"a.md": "x\n"}, "um")
        script = os.path.join(os.path.dirname(__file__), "..", "scripts", "varrer_historico.py")
        r = subprocess.run([sys.executable, script, "--repo", repo, "--saida", self.saida, "--termos",
                            self.termos, "--processos", "1"], capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run([sys.executable, script, "--repo", os.path.join(self.raiz, "nada"), "--saida",
                            self.saida, "--termos", self.termos], capture_output=True)
        self.assertEqual(r.returncode, 2)


class AnalisarTextoTest(unittest.TestCase):
    def analisar(self, texto, base=(), caminhos=("a.md",), termos=(TERMO,), liberadas=()):
        return vh.analisar_texto(texto, list(caminhos), set(base), list(termos), list(liberadas))

    def test_rg_direto(self):
        a = self.analisar("RG nº %s, expedida pela SSP/SP, e" % RG_NUM)
        self.assertIn("rg-direto", [x["regra"] for x in a])
        self.assertIn("pii-rg", [x["regra"] for x in a])

    def test_regra_multipla(self):
        a = self.analisar("CPF %s e e-mail %s\n" % (CPF_A, EMAIL_PESSOAL))
        self.assertEqual([x["regra"] for x in a if x["regra"].startswith("pii-")], ["pii-multipla"])

    def test_cnpj_fora_de_julgados_e_nao_em_julgados(self):
        cnpj = "12.345.678/" + "0001-95"
        self.assertEqual([x["regra"] for x in self.analisar("CNPJ %s\n" % cnpj)], ["cnpj"])
        self.assertEqual(self.analisar("CNPJ %s\n" % cnpj, caminhos=(JULGADO,)), [])

    def test_expressao_liberada_vale_so_em_julgado(self):
        txt = "O Fundo %s Investimento pagou.\n" % TERMO
        lib = ["Fundo %s Investimento" % TERMO]
        self.assertEqual(self.analisar(txt, caminhos=(JULGADO,), liberadas=lib), [])
        self.assertEqual([x["regra"] for x in self.analisar(txt, liberadas=lib)], ["termo"])

    def test_linha_na_base_nao_conta(self):
        linha = "Parte, CPF %s" % CPF_A
        self.assertEqual(self.analisar(linha + "\n", base={linha, ""}), [])
        self.assertTrue(self.analisar(linha + "\n", base={""}))

    def test_bloco_com_menos_linhas_vai_sem_pares(self):
        txt = "x\ny, brasileiro, casado,\nengenheiro, residente na Rua das Flores, 100, São Paulo, e mais\n"
        a = [x for x in self.analisar(txt) if x["regra"].startswith("pii-")]
        self.assertTrue(a)
        self.assertTrue(any(x["pares"] is None for x in a))

    def test_linha_com_crlf_mantem_o_par_sem_o_cr(self):
        txt = "Parte, CPF %s\r\nfim\r\n" % CPF_A
        a = [x for x in self.analisar(txt) if x["regra"] == "pii-cpf"]
        self.assertEqual(a[0]["pares"], [["Parte, CPF %s" % CPF_A, "Parte, CPF %s" % M]])

    def test_so_linhas_fora_da_base_viram_par(self):
        # duas linhas seguidas mudam; só a que não está na base entra no par
        l1 = "Parte, CPF %s" % CPF_A
        l2 = "Outra, CPF %s" % CPF_B
        a = [x for x in self.analisar(l1 + "\n" + l2 + "\n", base={l1, ""}) if x["regra"] == "pii-cpf"]
        self.assertEqual(len(a), 1)
        self.assertEqual([p[0] for p in a[0]["pares"]], [l2])


class SubstituicoesTest(unittest.TestCase):
    def achado(self, blob, original, limpo, pares, regra="pii-cpf"):
        return {"tipo": "blob", "blob": blob, "caminhos": ["a.md"], "linhas": [1], "regra": regra,
                "original": original, "limpo": limpo, "pares": pares}

    def test_escape(self):
        self.assertEqual(vh.linha_substituicao("a b", "a X"), "literal:a b==>a X")
        self.assertEqual(vh.linha_substituicao("regex:a", "X"), "literal:regex:a==>X")
        self.assertEqual(vh.linha_substituicao("glob:a", "X"), "literal:glob:a==>X")
        self.assertIsNone(vh.linha_substituicao("a ==> b", "X"))
        self.assertIsNone(vh.linha_substituicao("a", "X ==> b"))
        self.assertIsNone(vh.linha_substituicao("a", "a"))
        self.assertIsNone(vh.linha_substituicao("", "a"))

    def test_par_comum_e_dedup(self):
        a = [self.achado("b1", "o", "l", [["o", "l"]]), self.achado("b2", "o", "l", [["o", "l"]])]
        linhas, manuais, conflitos = vh.montar_substituicoes(a)
        self.assertEqual((linhas, manuais, conflitos), (["literal:o==>l"], [], []))

    def test_conflito_nao_grava_o_par(self):
        a = [self.achado("b1", "o", "l1", [["o", "l1"]]), self.achado("b2", "o", "l2", [["o", "l2"]])]
        linhas, manuais, conflitos = vh.montar_substituicoes(a)
        self.assertEqual(linhas, [])
        self.assertEqual(conflitos, [{"original": "o", "limpas": ["l1", "l2"], "blobs": ["b1", "b2"]}])

    def test_bloco_de_tamanho_diferente_vai_para_manuais(self):
        a = [self.achado("b1", "o1\no2", "l", None)]
        linhas, manuais, _ = vh.montar_substituicoes(a)
        self.assertEqual(linhas, [])
        self.assertEqual(manuais[0]["motivo"], "numero-de-linhas-diferente")

    def test_par_nao_escapavel_vai_para_manuais(self):
        a = [self.achado("b1", "a ==> b", "l", [["a ==> b", "l"]])]
        linhas, manuais, _ = vh.montar_substituicoes(a)
        self.assertEqual((linhas, manuais[0]["motivo"]), ([], "nao-escapavel"))

    def test_so_regras_pii_geram_par(self):
        a = [self.achado("b1", "o", "l", [["o", "l"]], regra="termo"),
             self.achado("b1", "o", "l", [["o", "l"]], regra="cpf-direto")]
        self.assertEqual(vh.montar_substituicoes(a), ([], [], []))

    def test_linha_mais_longa_vem_primeiro(self):
        a = [self.achado("b1", "abc", "X", [["abc", "X"]]), self.achado("b2", "abcdef", "Y", [["abcdef", "Y"]])]
        linhas, _, _ = vh.montar_substituicoes(a)
        self.assertEqual(linhas, ["literal:abcdef==>Y", "literal:abc==>X"])


class BlocosTest(unittest.TestCase):
    def test_mesmo_tamanho_alinha_por_indice(self):
        self.assertEqual(vh._blocos(["a", "b", "c", "d"], ["a", "B", "C", "d"]), [(1, 3, 1, 3)])

    def test_menos_linhas_usa_diff(self):
        self.assertEqual(vh._blocos(["a", "b", "c", "d"], ["a", "X", "d"]), [(1, 3, 1, 2)])


if __name__ == "__main__":
    unittest.main()
