#!/usr/bin/env python3
"""Normalização de texto para comparar norma, ato e consolidado.

normalizar_texto(md) -> str, linha a linha:
- remove a redação antiga tachada (`~~...~~`, como o DOCX da CVM mantém);
- unifica espaços, aspas e travessões;
- remove notas de alteração: "(Redação dada pela...)", "(Incluído pela...)",
  "(NR)" e as notas em parágrafo próprio do consolidado ("Caput com redação
  dada pela Resolução CVM nº ...", "Inciso II revogado pela ...",
  "Art. 73-A incluído pela ...");
- unifica a marca de revogação: "REVOGADO", "(Revogado)" e "(Revogado pela
  ...)" viram "(Revogado)"; o consolidado ainda separa o dispositivo da marca
  por travessão ("§ 4º - REVOGADO", "Seção I - REVOGADA", "CAPÍTULO III -
  REVOGADO", "SUPLEMENTO H - REVOGADO", "- REVOGADO" depois de "Art. N"). A marca
  fica: o que se compara é a revogação, não a ausência do texto.
"""
import re

_TACHADO = re.compile(r"~~.*?~~")
_NOTA_INLINE = re.compile(
    r"\s*\((?:redação\s+dada|incluíd[oa]s?|acrescid[oa]s?|renumerad[oa]s?)\b[^)]*\)", re.I
)
_NR = re.compile(r"\s*\(NR\)", re.I)
_ATOS = r"(?:Resolu|Instru|Lei\b|Delibera|Portaria|Decreto|Medida|Parecer|Ato\b)"
# Nota em parágrafo próprio: prefixo curto (dispositivo) + verbo + "pela <ato>".
_NOTA_LINHA = re.compile(
    r"^(?:[^;:,]{1,40}?\s)?"
    r"(?:com\s+(?:a\s+)?redação\s+dada|incluíd[oa]s?|revogad[oa]s?|acrescentad[oa]s?|renumerad[oa]s?)"
    r"\s+pel[ao]s?\s+" + _ATOS + r".{0,150}$",
    re.I,
)
_PREFIXO_DISPOSITIVO = (
    r"(?:Art\.?\s*\S+|§+\s*\S+|Parágrafo único\.?|[IVXLCDM]+(?:-[A-Z]{1,2})?\s*-|\"?[a-z]\"?\)|\d+\s*[-.)]"
    r"|(?:Seção|CAPÍTULO|SUPLEMENTO)\s+\S+)"
)
_REVOGADO = re.compile(
    r"^(?P<pre>" + _PREFIXO_DISPOSITIVO + r")?\s*(?:-\s*)?\(?\s*revogad[oa]s?"
    r"(?:\s+pel[ao]s?\s+[^)]*)?\)?\.?$",
    re.I,
)
_CARACTERES = str.maketrans({
    "“": '"', "”": '"', "„": '"', "«": '"', "»": '"',
    "‘": "'", "’": "'",
    "–": "-", "—": "-", "−": "-", "‒": "-",
    " ": " ", "°": "º", "­": None,
})


def _linha(linha):
    linha = _TACHADO.sub("", linha).translate(_CARACTERES)
    linha = _NOTA_INLINE.sub("", linha)
    linha = _NR.sub("", linha)
    linha = " ".join(linha.split())
    if _NOTA_LINHA.match(linha):
        return ""
    m = _REVOGADO.match(linha)
    if m:
        pre = (m.group("pre") or "").strip()
        if pre.endswith("."):
            pre = pre[:-1]
        return (pre + " " if pre else "") + "(Revogado)"
    return linha


def normalizar_texto(md):
    return "\n".join(_linha(l) for l in md.split("\n"))
