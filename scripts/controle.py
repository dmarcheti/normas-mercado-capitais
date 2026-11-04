"""Caractere de controle no texto gravado (normas e julgados), só com a biblioteca padrão.

A extração de PDF deixa caractere de controle no lugar de um glifo que ela não leu (ligadura,
acento combinante, marcador, travessão). Com NUL no arquivo, o grep e o git o tratam como
binário e a busca não o vê.

- CONTROLE: o conjunto reprovado (\\x00-\\x08, \\x0b, \\x0c, \\x0e-\\x1f, \\x7f); \\t, \\n e \\r ficam.
- sem_controle(texto): o NUL vira "\\ufffd" (visível e buscável), o STX, que o SEI põe no hífen
  ("sexta-feira"), vira "-", e os demais saem.
- contar_controle(texto): quantos caracteres de controle há no texto.
"""

import re

CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TROCA = {"\x00": "�", "\x02": "-"}


def sem_controle(texto):
    return CONTROLE.sub(lambda m: _TROCA.get(m.group(0), ""), texto)


def contar_controle(texto):
    return len(CONTROLE.findall(texto))
