#!/usr/bin/env python3
"""
As chaves de API que o observatório usa — lidas do ambiente ou do `.env`.

STDLIB ONLY, como todo o resto de `scripts/`: o CI não roda `pip install`, então
não há `python-dotenv` aqui. O formato aceito é o mínimo (`CHAVE=valor`, uma por
linha, `#` comenta), porque o arquivo é escrito à mão por uma pessoa e não
precisa de mais que isso.

A ORDEM IMPORTA: variável de ambiente vence o arquivo. É o que faz o mesmo
código servir aos dois lugares — na máquina de casa a chave está no `.env`, e no
GitHub Actions ela entra como *repository secret*, que chega como variável de
ambiente. Se o arquivo vencesse, um `.env` esquecido no runner (ou um valor
velho) sobreporia o segredo do repositório em silêncio.

E TUDO É OPCIONAL. Sem chave nenhuma, `chave_de_busca_web()` devolve
`(None, "")` e quem chama pula a etapa. Nenhuma fonte aberta do observatório —
DOU, Portal da Transparência, rankingdosconcursos, Querido Diário — depende
disto. A busca web existe só para alcançar diário ESTADUAL.
"""

from __future__ import annotations

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQ_ENV = RAIZ / ".env"

# Os serviços de busca web que o observatório sabe usar, na ordem de preferência.
# O Serper vem primeiro porque é o mais barato por consulta (US$ 0,30 a 1,00 por
# mil, contra US$ 9 a 25 do SerpApi) — ver a D28.
SERVICOS_DE_BUSCA = (
    ("serper", "SERPER_API_KEY"),
    ("serpapi", "SERPAPI_API_KEY"),
)


def _do_arquivo() -> dict[str, str]:
    """O `.env`, se existir. Linha malformada é ignorada, não explode."""
    if not ARQ_ENV.is_file():
        return {}
    valores: dict[str, str] = {}
    for linha in ARQ_ENV.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        # Aspas são um engano comum ao colar chave; tirá-las evita um erro de
        # autenticação que não diz o que houve.
        valores[chave.strip()] = valor.strip().strip("'\"")
    return valores


def ler(nome: str) -> str:
    """O valor de um segredo. `""` quando não há — nunca `None`, nunca erro."""
    do_ambiente = os.environ.get(nome, "").strip()
    return do_ambiente or _do_arquivo().get(nome, "").strip()


def chave_de_busca_web() -> tuple[str | None, str]:
    """
    `(servico, chave)` do primeiro serviço de busca configurado.

    `(None, "")` quando não há nenhum — e esse é um estado NORMAL, não um erro:
    quem chama pula a etapa e o resto do observatório segue igual.
    """
    for servico, nome_da_variavel in SERVICOS_DE_BUSCA:
        chave = ler(nome_da_variavel)
        if chave:
            return servico, chave
    return None, ""


if __name__ == "__main__":
    # Diz o que está configurado SEM imprimir a chave: este script é rodado à
    # mão para conferir o `.env`, e a saída pode acabar num log ou num print.
    servico, chave = chave_de_busca_web()
    if servico:
        print(f"busca web: {servico} configurado ({len(chave)} caracteres)")
    else:
        print("busca web: nenhuma chave configurada — a etapa fica desligada")
        print(f"           preencha {ARQ_ENV}")
