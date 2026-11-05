"""Valida .github/ISSUE_TEMPLATE/*.yml sem dependência externa: um leitor mínimo do subconjunto de
YAML que os formulários usam (mapas, listas de mapas, escalares, lista em linha e bloco `|`)."""
import os
import re
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASTA = os.path.join(RAIZ, ".github", "ISSUE_TEMPLATE")


def escalar(t):
    t = t.strip()
    if t.startswith("[") and t.endswith("]"):
        return [escalar(x) for x in t[1:-1].split(",") if x.strip()]
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
        return t[1:-1]
    if t in ("true", "false"):
        return t == "true"
    return t


def ler_yaml(texto):
    """Subconjunto: indentação por espaços, `chave: valor`, `chave:` com filho, `- item`,
    `- chave: valor` (item mapa), `chave: |` com bloco. Qualquer outra coisa levanta ValueError."""
    linhas = [(len(l) - len(l.lstrip(" ")), l.strip(), n) for n, l in enumerate(texto.split("\n"), 1)]
    pos = [0]

    def vazia(i):
        return not linhas[i][1] or linhas[i][1].startswith("#")

    def proximo():
        while pos[0] < len(linhas) and vazia(pos[0]):
            pos[0] += 1
        return pos[0] if pos[0] < len(linhas) else None

    def bloco(ind_pai):
        partes = []
        brutas = texto.split("\n")
        while pos[0] < len(linhas):
            ind, s, n = linhas[pos[0]]
            if s and ind <= ind_pai:
                break
            partes.append(brutas[pos[0]][ind_pai + 2:] if s else "")
            pos[0] += 1
        return "\n".join(partes).rstrip() + "\n"

    def valor_de(chave_ind, resto):
        if resto == "|":
            return bloco(chave_ind)
        if resto == "":
            i = proximo()
            if i is not None and linhas[i][0] > chave_ind:
                return no(linhas[i][0])
            if i is not None and linhas[i][0] == chave_ind and linhas[i][1].startswith("- "):
                return no(chave_ind)
            return None
        return escalar(resto)

    def no(ind):
        i = proximo()
        if linhas[i][1].startswith("- "):
            lista = []
            while True:
                i = proximo()
                if i is None or linhas[i][0] != ind or not linhas[i][1].startswith("- "):
                    break
                s = linhas[i][1][2:]
                m = re.match(r"^([A-Za-z_][\w-]*):(?: (.*))?$", s)
                if m:
                    # item mapa: o resto da linha vira a 1ª chave; as demais ficam em ind + 2
                    linhas[i] = (ind + 2, s, linhas[i][2])
                    lista.append(no(ind + 2))
                else:
                    lista.append(escalar(s))
                    pos[0] += 1
            return lista
        mapa = {}
        while True:
            i = proximo()
            if i is None or linhas[i][0] != ind:
                if i is not None and linhas[i][0] > ind:
                    raise ValueError("indentação inesperada na linha %d" % linhas[i][2])
                break
            ind_, s, n = linhas[i]
            m = re.match(r"^([A-Za-z_][\w-]*):(?: (.*))?$", s)
            if not m or s.startswith("- "):
                raise ValueError("linha %d fora do subconjunto: %r" % (n, s))
            if m.group(1) in mapa:
                raise ValueError("chave repetida na linha %d" % n)
            pos[0] += 1
            mapa[m.group(1)] = valor_de(ind, (m.group(2) or "").strip())
        return mapa

    i = proximo()
    return no(linhas[i][0]) if i is not None else {}


class TestLeitor(unittest.TestCase):
    def test_leitor_minimo(self):
        d = ler_yaml("a: 1\nb: [x, y]\nc:\n  - k: v\n    z: |\n      linha\n      dois\n  - k: w\n")
        self.assertEqual(d["b"], ["x", "y"])
        self.assertEqual(d["c"], [{"k": "v", "z": "linha\ndois\n"}, {"k": "w"}])

    def test_rejeita_o_que_nao_e_yaml_dos_formularios(self):
        for ruim in ("a: 1\n a: 2\n", "a: 1\na: 2\n", "solto\n"):
            with self.assertRaises(ValueError):
                ler_yaml(ruim)


class TestFormularioRetirada(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(PASTA, "retirada.yml"), encoding="utf-8") as f:
            self.d = ler_yaml(f.read())

    def test_cabecalho(self):
        for chave in ("name", "description", "title", "labels", "body"):
            self.assertIn(chave, self.d)
        self.assertEqual(self.d["labels"], ["retirada"])

    def test_campos(self):
        corpo = self.d["body"]
        self.assertIsInstance(corpo, list)
        self.assertEqual(corpo[0]["type"], "markdown")
        aviso = corpo[0]["attributes"]["value"]
        self.assertIn("Não escreva o dado pessoal", aviso)
        por_id = {c["id"]: c for c in corpo if "id" in c}
        ids = [c["id"] for c in corpo if "id" in c]
        self.assertEqual(len(ids), len(set(ids)))  # id único, exigência do GitHub
        doc = por_id["documento"]
        self.assertEqual(doc["type"], "input")
        self.assertIs(doc["validations"]["required"], True)
        tipo = por_id["tipo"]
        self.assertEqual(tipo["type"], "dropdown")
        self.assertEqual(tipo["attributes"]["options"],
                         ["Dado pessoal em julgado", "Texto da ANBIMA ou da B3 (titular)", "Outro"])
        self.assertEqual(por_id["motivo"]["type"], "textarea")
        for c in corpo:
            self.assertIn(c["type"], ("markdown", "input", "dropdown", "textarea", "checkboxes"))
            self.assertIn("label" if c["type"] != "markdown" else "value", c["attributes"])

    def test_sem_email_nem_dado_pessoal_no_formulario(self):
        with open(os.path.join(PASTA, "retirada.yml"), encoding="utf-8") as f:
            texto = f.read()
        self.assertNotRegex(texto, r"[\w.]+@[\w.]+")
        self.assertNotIn("e-mail", texto.lower())


class TestConfig(unittest.TestCase):
    def test_issues_em_branco_permitidas(self):
        with open(os.path.join(PASTA, "config.yml"), encoding="utf-8") as f:
            d = ler_yaml(f.read())
        self.assertIs(d["blank_issues_enabled"], True)
        self.assertNotIn("contact_links", d)  # nenhum canal fora das issues


if __name__ == "__main__":
    unittest.main()
