#!/usr/bin/env python3
"""
Extrai o resultado final de um concurso da CGU a partir do ato publicado no DOU.

D17 do PLANO.md: a área de especialização (Auditoria e Fiscalização, TI,
Contabilidade Pública e Finanças, Correição e Combate à Corrupção) NÃO existe no
Portal da Transparência. Ela está no edital de homologação, junto com inscrição,
nota, classificação e modalidade — tudo numa página só, sem crawler de banca.

Uso:
    python concurso.py                    # CGU-2021, grava data/concurso_2021.csv
    python concurso.py --diagnostico      # só mostra o que achou
    python concurso.py --ato <urlTitle> --id CGU-2026 --saida concurso_2026.csv

ESTRUTURA DO ATO (verificada em 14/08/2026 no Edital CGU nº 5):

    II.1 RESULTADO FINAL DE APROVADOS - AMPLA CONCORRENCIA, ...
      1. AUDITOR FEDERAL DE FINANCAS E CONTROLE - AUDITORIA E FISCALIZACAO
        1.1. AC - REGIAO NORTE - ACRE
          206081364, MAUREEN DA SILVA BRANDAO, 123.5, 1O / 206072821, JAIDIR ...
      5. TECNICO FEDERAL DE FINANCAS E CONTROLE       <- descartado (D7)
    II.2 ... - CANDIDATOS NEGROS ...
    II.3 ... - PESSOA COM DEFICIENCIA ...

Três armadilhas do texto, todas encontradas na marra:

  1. O EDITAL TEM ERRO DE DIGITAÇÃO. Um dos blocos diz "AUDITOR FEDERAL DE
     FINANCAAS E CONTROLE" (dois "A"). Um padrão exato perde esse bloco inteiro
     — que é a Contabilidade Pública da ampla concorrência — e subconta a área
     sem dar nenhum erro. Por isso PADRAO_CARGO_AFFC aceita a letra repetida.
  2. O nome do candidato pode conter qualquer coisa menos vírgula (apóstrofo,
     hífen). Casar `[A-Z ]+` perderia gente.
  3. O sub-bloco começa pela UF DA VAGA ("AC - REGIAO NORTE - ACRE"), que não é
     onde a pessoa foi lotada depois — é a vaga a que concorreu.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import dou

RAIZ = Path(__file__).resolve().parent.parent

ATO_CGU_2021 = "edital-cgu-n-5-de-13-de-junho-de-2022-407806622"

CABECALHOS = (
    "INSCRICAO",
    "NOME",
    "AREA",
    "NOTA",
    "POSICAO_CONCURSO",
    "MODALIDADE",
    "UF_VAGA",
)

# "FINANCA+S" tolera o "FINANCAAS" do original. Ver armadilha 1 no cabeçalho.
PADRAO_CARGO_AFFC = r"AUDITOR[A]?\s+FEDERAL\s+DE\s+FINANCA+S\s+E\s+CONTROLE"
PADRAO_CARGO_TFFC = r"TECNICO\s+FEDERAL\s+DE\s+FINANCA+S\s+E\s+CONTROLE"

PADRAO_SECAO = re.compile(r"II\.(\d+)\s+RESULTADO\s+FINAL\s+DE\s+APROVADOS\s*-\s*([A-Z\s]+?),")
PADRAO_BLOCO_CARGO = re.compile(
    rf"(?:^|\s)\d+\.\s+((?:{PADRAO_CARGO_AFFC}|{PADRAO_CARGO_TFFC})[A-Z\s\-]*?)(?=\s+\d+\.\d+\.)"
)
PADRAO_SUBBLOCO = re.compile(r"\d+\.\d+\.\s+([A-Z]{2})\s*-\s*[A-Z0-9\s\-/]{3,50}?(?=\s+\d{9},)")
# Nome = tudo menos vírgula. Ver armadilha 2.
PADRAO_REGISTRO = re.compile(r"(\d{6,10}),\s*([^,]+?),\s*([\d.]+),\s*(\d+)\s*[O°º]")

MODALIDADES = {
    "AMPLA CONCORRENCIA": "Ampla Concorrência",
    "CANDIDATOS NEGROS": "Negros",
    "PESSOA COM DEFICIENCIA": "PcD",
}

# Rótulo de exibição das áreas. O texto do DOU vem sem acento e em caixa alta;
# estes são os nomes que o CLAUDE.md usa e que a interface mostra.
AREAS = {
    "AUDITORIA E FISCALIZACAO": "Auditoria e Fiscalização",
    "CONTABILIDADE PUBLICA E FINANCAS": "Contabilidade Pública e Finanças",
    "CORREICAO E COMBATE A CORRUPCAO": "Correição e Combate à Corrupção",
    "TECNOLOGIA DA INFORMACAO": "TI",
}


def _fatias(texto: str, marcadores: list[tuple[int, str]]) -> list[tuple[str, str]]:
    """(rótulo, trecho) para cada marcador, até o marcador seguinte."""
    fatias = []
    for indice, (posicao, rotulo) in enumerate(marcadores):
        fim = marcadores[indice + 1][0] if indice + 1 < len(marcadores) else len(texto)
        fatias.append((rotulo, texto[posicao:fim]))
    return fatias


def extrair(texto_normalizado: str) -> tuple[list[dict], dict]:
    """Devolve (registros AFFC, relatório de conferência)."""
    secoes = [(m.start(), m.group(2).strip()) for m in PADRAO_SECAO.finditer(texto_normalizado)]
    if not secoes:
        raise SystemExit("Nenhuma seção 'II.N RESULTADO FINAL DE APROVADOS' no ato.")

    registros: list[dict] = []
    relatorio = {"secoes": [], "blocos_affc": 0, "blocos_tffc": 0, "descartados_tffc": 0}

    for rotulo_secao, trecho_secao in _fatias(texto_normalizado, secoes):
        modalidade = MODALIDADES.get(rotulo_secao, rotulo_secao.title())
        relatorio["secoes"].append(rotulo_secao)

        blocos = [(m.start(), m.group(1).strip()) for m in PADRAO_BLOCO_CARGO.finditer(trecho_secao)]
        for cabecalho, trecho_bloco in _fatias(trecho_secao, blocos):
            if re.match(PADRAO_CARGO_TFFC, cabecalho):
                relatorio["blocos_tffc"] += 1
                relatorio["descartados_tffc"] += len(PADRAO_REGISTRO.findall(trecho_bloco))
                continue  # TFFC está fora do observatório (D7)
            if not re.match(PADRAO_CARGO_AFFC, cabecalho):
                continue

            relatorio["blocos_affc"] += 1
            partes = cabecalho.split("-", 1)
            area_bruta = partes[1].strip() if len(partes) > 1 else ""
            area = AREAS.get(area_bruta, area_bruta.title())

            subblocos = [(m.start(), m.group(1)) for m in PADRAO_SUBBLOCO.finditer(trecho_bloco)]
            if not subblocos:
                subblocos = [(0, "")]

            for uf_vaga, trecho_sub in _fatias(trecho_bloco, subblocos):
                for inscricao, nome, nota, posicao in PADRAO_REGISTRO.findall(trecho_sub):
                    registros.append(
                        {
                            "INSCRICAO": inscricao,
                            "NOME": " ".join(nome.split()),
                            "AREA": area,
                            "NOTA": nota,
                            "POSICAO_CONCURSO": posicao,
                            "MODALIDADE": modalidade,
                            "UF_VAGA": uf_vaga,
                        }
                    )

    return registros, relatorio


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extrai o resultado final de um concurso da CGU publicado no DOU."
    )
    parser.add_argument("--ato", default=ATO_CGU_2021, help="urlTitle do ato no in.gov.br.")
    parser.add_argument("--saida", default="concurso_2021.csv", help="Arquivo em evasao/data/.")
    parser.add_argument("--diagnostico", action="store_true", help="Não grava, só relata.")
    parser.add_argument("--sem-cache", action="store_true", help="Rebaixa o ato do in.gov.br.")
    args = parser.parse_args()

    print(f"Ato: {dou.BASE_ATO}{args.ato}")
    _, texto = dou.baixar_ato(args.ato, timeout=90, usar_cache=not args.sem_cache)
    if not texto:
        print("Não foi possível baixar o ato.", file=sys.stderr)
        return 1
    print(f"Texto: {len(texto):,} caracteres")

    registros, relatorio = extrair(dou.normalizar(texto))
    if not registros:
        print("Nenhum registro AFFC extraído — o formato do ato pode ter mudado.", file=sys.stderr)
        return 1

    print()
    print(f"Seções            : {', '.join(relatorio['secoes'])}")
    print(f"Blocos AFFC       : {relatorio['blocos_affc']}")
    print(f"Blocos TFFC       : {relatorio['blocos_tffc']} "
          f"({relatorio['descartados_tffc']} registros descartados — D7)")
    print(f"Aprovados AFFC    : {len(registros)}")

    print()
    print("Por área:")
    for area in sorted({r["AREA"] for r in registros}):
        total = sum(1 for r in registros if r["AREA"] == area)
        print(f"   {total:4d}  {area}")
    print("Por modalidade:")
    for modalidade in sorted({r["MODALIDADE"] for r in registros}):
        total = sum(1 for r in registros if r["MODALIDADE"] == modalidade)
        print(f"   {total:4d}  {modalidade}")

    inscricoes = [r["INSCRICAO"] for r in registros]
    if len(set(inscricoes)) != len(inscricoes):
        print(f"\n! {len(inscricoes) - len(set(inscricoes))} inscrição(ões) repetida(s) — "
              f"esperado: quem concorre por cota aparece na ampla e na cota.")

    if args.diagnostico:
        print("\nModo diagnóstico — nada gravado.")
        return 0

    destino = RAIZ / "data" / args.saida
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=CABECALHOS, delimiter=";")
        escritor.writeheader()
        escritor.writerows(registros)
    print(f"\nGravado: {destino.relative_to(RAIZ)} ({len(registros)} linhas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
