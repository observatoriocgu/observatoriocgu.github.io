#!/usr/bin/env python3
"""
Para cada saída da CGU detectada no SIAPE, busca no DOU o ato que diz POR QUE a
pessoa saiu e, quando dá, PARA ONDE foi.

Entrada : data/dados.csv (as linhas com MES_SAIDA preenchido)
Saída   : data/saidas_dou.csv        — acumulativo, uma linha por PESSOA
          data/atos_dou.csv          — o índice único, uma linha por ATO
          data/saidas_dou/*.html     — cópia arquivada do ato

O arquivo de saída é uma camada separada de propósito: `construir_painel.py`
regenera o dados.csv do zero a cada execução, e se este script escrevesse lá
direto, reconstruir o painel apagaria ~50 minutos de crawl.

DUAS SAÍDAS, DUAS CHAVES, E ISSO NÃO É DUPLICAÇÃO. O `saidas_dou.csv` é indexado
por PESSOA e é o que o painel mescla no `dados.csv`. O `atos_dou.csv` é indexado
por ATO e é o que o card lê — e é o mesmo índice que a varredura por frase
(`varrer_dou.py`) alimenta, que é como o card enxerga o que o SIAPE ainda não
mostrou. Este script preenche o `ID_SERVIDOR_PORTAL` da linha do índice: é o
momento em que "houve uma vacância em 11/08" vira "foi fulano quem saiu".

ESTRATÉGIA DE BUSCA — uma requisição por pessoa, sem janelamento. Um nome não
chega perto do teto de 50 resultados por resposta (o caso testado devolveu 20
atos na vida inteira). Se vier cheio, aí sim refaz por janelas de data — é o
único jeito, porque a paginação do DOU não funciona.

`s=todos` é obrigatório: atos de pessoal saem na Seção 2, e buscar só na Seção 1
não devolve nenhum deles.

DUAS DEFESAS CONTRA AFIRMAR COISA ERRADA SOBRE PESSOA REAL:

  Homônimo. A busca do DOU ignora acento e gênero, então nome casa demais. O
  Portal mascara a matrícula como "166****", deixando os 3 primeiros dígitos do
  SIAPE visíveis, e os atos escrevem o SIAPE por extenso. Quando o ato traz
  matrícula e ela CONFLITA com a do Portal, o ato é descartado.

  Destino. Um ato posterior à saída que cita a pessoa não é, por si, prova de
  destino. Caso real: alguém saiu da CGU em 2022, e o único ato posterior que o
  cita é uma portaria do TRE-MG de 2025 — que trata da vacância do cargo que ele
  deixou no TRE em 2022, ANTES de entrar na CGU. A regra ingênua publicaria
  "foi para o TRE-MG em 2025", que é falso. Por isso o destino exige ato de
  nomeação/posse, sem verbo de desligamento, dentro de 24 meses da saída.

Uso:
    python enriquecer_saidas.py                  # processa quem ainda não tem motivo
    python enriquecer_saidas.py --limite 10      # só os 10 primeiros (teste)
    python enriquecer_saidas.py --refazer        # reprocessa todo mundo
    python enriquecer_saidas.py --nome "FULANO"  # uma pessoa só, com detalhe
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

import atos
import dou

RAIZ = Path(__file__).resolve().parent.parent
ARQ_DADOS = RAIZ / "data" / "dados.csv"
ARQ_SAIDAS = RAIZ / "data" / "saidas_dou.csv"

COLUNAS = (
    "ID_SERVIDOR_PORTAL", "NOME", "SITUACAO",
    "MOTIVO_SAIDA", "FONTE_MOTIVO", "DATA_SAIDA", "DATA_PUBLICACAO_SAIDA",
    "ATO_SAIDA_TITULO", "ATO_SAIDA_URL", "ATO_SAIDA_ARQUIVO",
    "ORGAO_DESTINO", "CARGO_DESTINO", "DATA_DESTINO", "FONTE_DESTINO", "URL_DESTINO",
    "OBSERVACAO",
)

# Janela em que um ato de nomeação vale como destino, em meses relativos ao mês
# da saída do SIAPE.
#
# O limite superior existe porque um ato de nomeação anos depois da saída não é
# evidência de destino, é outra coisa na vida da pessoa — foi ele que barrou o
# ato do TRE de 2025 sobre uma saída de 2022.
#
# O limite INFERIOR é negativo porque a posse no novo órgão costuma vir ANTES de
# a CGU declarar o cargo vago: a pessoa toma posse no TCU em outubro, a CGU
# publica a vacância em dezembro, e o SIAPE só deixa de listá-la depois. Exigir
# ato posterior perdia justamente os destinos mais bem documentados.
#
# O +24 inicial foi APERTADO PARA +6 depois de medir os 95 destinos do backfill:
# 90 deles caem entre -4 e +4 meses (pico em -1 e -2), e existe um vazio limpo
# entre +4 e +13. Os 5 do outro lado do vazio foram conferidos à mão e não se
# sustentam — são nomeação para cargo comissionado, ato-lista de concurso, ou
# uma mudança POSTERIOR de emprego que não é o destino de quem saiu da CGU.
# O corte em +6 fica dentro do vazio: mantém todo o sinal e descarta o ruído.
MESES_ANTES_DA_SAIDA = -6
MESES_DEPOIS_DA_SAIDA = 6

# Quantos atos do DOU baixar por pessoa. A busca devolve no máximo 50; abrir
# todos custaria caro e os mais relevantes vêm primeiro.
MAX_ATOS_POR_PESSOA = 14


def ler_csv(caminho: Path) -> list[dict]:
    if not caminho.is_file():
        return []
    with open(caminho, encoding="utf-8-sig", newline="") as fh:
        return [
            {(k or "").strip(): (v or "").strip() for k, v in linha.items()}
            for linha in csv.DictReader(fh, delimiter=";")
        ]


def mes_para_data(mes: str) -> datetime:
    return datetime(int(mes[:4]), int(mes[4:]), 1)


def distancia_meses(iso: str, mes_referencia: str) -> float:
    """Meses entre a data de um ato (AAAA-MM-DD) e o mês de saída. `inf` se não der."""
    try:
        data = datetime.strptime(iso, "%Y-%m-%d")
    except (TypeError, ValueError):
        return float("inf")
    referencia = mes_para_data(mes_referencia)
    return (data.year - referencia.year) * 12 + (data.month - referencia.month)


def buscar_atos(nome: str, usar_cache: bool) -> list[dict]:
    """Todos os atos do DOU que citam o nome, do mais recente para o mais antigo."""
    resultados = dou.buscar(f'"{nome}"', usar_cache=usar_cache)
    if dou.busca_estourou_teto(resultados):
        # Resposta cheia = possivelmente truncada, e não há paginação. Refaz em
        # fatias anuais para não perder ato em silêncio.
        print("      (resposta cheia — refazendo por janelas anuais)")
        vistos, completos = set(), []
        for ano in range(2021, datetime.now().year + 1):
            for pedaco in dou.buscar(
                f'"{nome}"',
                inicio=datetime(ano, 1, 1).date(),
                fim=datetime(ano, 12, 31).date(),
                usar_cache=usar_cache,
            ):
                chave = pedaco.get("urlTitle")
                if chave and chave not in vistos:
                    vistos.add(chave)
                    completos.append(pedaco)
        return completos
    return resultados


def analisar(pessoa: dict, indice: dict, usar_cache: bool, verboso: bool = False) -> dict:
    """Motivo e destino de uma saída, a partir dos atos do DOU que citam a pessoa."""
    nome, mes_saida = pessoa["NOME"], pessoa["MES_SAIDA"]
    matricula = pessoa.get("MATRICULA", "")
    registro = {c: "" for c in COLUNAS}
    registro["ID_SERVIDOR_PORTAL"] = pessoa["ID_SERVIDOR_PORTAL"]
    registro["NOME"] = nome

    citam_a_pessoa = buscar_atos(nome, usar_cache)
    if not citam_a_pessoa:
        return registro

    # Do mais próximo da saída para o mais distante: o ato que interessa é o que
    # está perto do mês em que a pessoa sumiu do SIAPE.
    ordenados = sorted(
        citam_a_pessoa, key=lambda a: abs(distancia_meses(dou.data_iso(a), mes_saida))
    )

    melhor_saida = None
    candidatos_destino = []

    for ato in ordenados[:MAX_ATOS_POR_PESSOA]:
        chave = ato.get("urlTitle")
        if not chave:
            continue
        _, texto = dou.baixar_ato(chave, usar_cache=usar_cache)
        if not texto or not dou.cita_nome(texto, nome):
            continue

        # Matrícula que conflita = outra pessoa com o mesmo nome. `None` (ato sem
        # matrícula) não elimina: seria jogar fora a maioria dos atos.
        matricula_confere = dou.siape_compativel(texto, matricula)
        if matricula_confere is False:
            if verboso:
                print(f"      - descartado (SIAPE não bate): {ato.get('title', '')[:60]}")
            continue

        distancia = distancia_meses(dou.data_iso(ato), mes_saida)

        if dou.e_da_cgu(ato) and melhor_saida is None:
            # Quando a matrícula bate, a identidade já está provada e não é
            # preciso o ato citar o cargo. Isso é o que permite reconhecer a
            # demissão disciplinar, cujo texto fala do servidor e da penalidade
            # mas não do cargo de AFFC. Sem prova de matrícula, mantém-se a
            # exigência do cargo — nome sozinho casa homônimo.
            tipo = dou.classificar(texto, exigir_cargo=not matricula_confere)
            if tipo:
                melhor_saida = (tipo, ato, texto)
                if verboso:
                    print(f"      + motivo {tipo}: {ato.get('title', '')[:60]}")
                continue

        if not dou.e_da_cgu(ato) and MESES_ANTES_DA_SAIDA <= distancia <= MESES_DEPOIS_DA_SAIDA:
            if dou.e_ato_de_nomeacao(texto, nome):
                candidatos_destino.append((distancia, ato, texto))
                if verboso:
                    print(f"      + destino?  {ato.get('hierarchyStr', '')[:50]}")

        # Achou os dois: pode parar. Como `ordenados` vem por proximidade da
        # saída, o primeiro destino encontrado já é o mais próximo — continuar
        # só gastaria requisição sem poder melhorar a resposta.
        if melhor_saida and candidatos_destino:
            break

    if melhor_saida:
        tipo, ato, texto = melhor_saida
        registro["FONTE_MOTIVO"] = "DOU"
        registro["DATA_PUBLICACAO_SAIDA"] = dou.data_iso(ato)

        # `atos.registrar` devolve None para motivo não publicado (D18) e é o
        # único ponto que precisa decidir isso. Aqui basta respeitar: sem linha
        # no índice, sem título, sem URL e sem cópia arquivada — o índice e a
        # pasta `saidas_dou/` vão inteiros para repositório público e para o site.
        linha = atos.registrar(
            indice, ato, tipo, texto, atos.FONTE_NOME,
            id_servidor=pessoa["ID_SERVIDOR_PORTAL"],
        )
        if linha is None:
            registro["MOTIVO_SAIDA"] = dou.ROTULO_NAO_PUBLICADO
            registro["SITUACAO"] = dou.SITUACAO_NAO_PUBLICADA
        else:
            registro["MOTIVO_SAIDA"] = dou.ROTULOS[tipo]
            registro["SITUACAO"] = dou.SITUACAO_POR_TIPO[tipo]
            registro["ATO_SAIDA_TITULO"] = linha["TITULO"]
            registro["ATO_SAIDA_URL"] = linha["URL"]
            registro["ATO_SAIDA_ARQUIVO"] = linha["ARQUIVO"]

    if candidatos_destino:
        # O mais próximo da saída, em qualquer direção. Se a pessoa tomou posse
        # em outro órgão, o ato sai perto da saída — não anos depois.
        _, ato, _ = min(candidatos_destino, key=lambda c: abs(c[0]))
        registro["ORGAO_DESTINO"] = dou.orgao_do_ato(ato)
        registro["DATA_DESTINO"] = dou.data_iso(ato)
        registro["FONTE_DESTINO"] = "DOU"
        registro["URL_DESTINO"] = dou.BASE_ATO + ato["urlTitle"]

    return registro


def main() -> int:
    parser = argparse.ArgumentParser(description="Busca no DOU o motivo e o destino de cada saída.")
    parser.add_argument("--limite", type=int, help="Processa no máximo N pessoas.")
    parser.add_argument("--refazer", action="store_true", help="Reprocessa quem já tem resultado.")
    parser.add_argument("--nome", help="Processa só quem tiver este trecho no nome, com detalhe.")
    parser.add_argument("--sem-cache", action="store_true", help="Ignora o cache do DOU.")
    args = parser.parse_args()
    usar_cache = not args.sem_cache

    pessoas = ler_csv(ARQ_DADOS)
    if not pessoas:
        print(f"{ARQ_DADOS} não existe. Rode `python construir_painel.py` antes.", file=sys.stderr)
        return 1

    ja_feitas = {r["ID_SERVIDOR_PORTAL"]: r for r in ler_csv(ARQ_SAIDAS)}

    # O índice de atos é compartilhado com a varredura por frase. Ler antes e
    # reconciliar com o que já está no saidas_dou.csv mantém as duas metades
    # coerentes mesmo quando só um dos crawlers roda.
    indice = atos.ler()
    atos.importar_de_saidas_dou(indice)

    fila = [p for p in pessoas if p.get("MES_SAIDA")]
    if args.nome:
        alvo = dou.normalizar(args.nome)
        fila = [p for p in fila if alvo in dou.normalizar(p["NOME"])]
    elif not args.refazer:
        fila = [p for p in fila if p["ID_SERVIDOR_PORTAL"] not in ja_feitas]

    # A saída provisória tem um mês só de ausência observada — pode ser a
    # ressurreição da vez. Não vale gastar requisição nem publicar ato sobre ela.
    provisorias = [p for p in fila if p.get("SAIDA_PROVISORIA") == "SIM"]
    fila = [p for p in fila if p.get("SAIDA_PROVISORIA") != "SIM"]

    if args.limite:
        fila = fila[: args.limite]

    print(f"Saídas a processar: {len(fila)}  (já feitas: {len(ja_feitas)}"
          f"{f', {len(provisorias)} provisória(s) adiada(s)' if provisorias else ''})")
    if not fila:
        # Nada a buscar não quer dizer nada a gravar: a reconciliação acima pode
        # ter trazido atos que faltavam ao índice.
        atos.gravar(indice)
        print("Nada a fazer.")
        return 0
    print(f"Pausa entre requisições: {dou.PAUSA_SEGUNDOS}s | cache: "
          f"{'ligado' if usar_cache else 'DESLIGADO'}")
    print()

    resultados = dict(ja_feitas)
    achou_motivo = achou_destino = 0

    for numero, pessoa in enumerate(fila, start=1):
        print(f"[{numero}/{len(fila)}] {pessoa['NOME'][:44]:<44} saiu em {pessoa['MES_SAIDA']}")
        registro = analisar(pessoa, indice, usar_cache, verboso=bool(args.nome))
        resultados[registro["ID_SERVIDOR_PORTAL"]] = registro

        if registro["MOTIVO_SAIDA"]:
            achou_motivo += 1
            print(f"      motivo : {registro['MOTIVO_SAIDA']} "
                  f"({registro['DATA_PUBLICACAO_SAIDA']})")
        else:
            print("      motivo : não identificado")
        if registro["ORGAO_DESTINO"]:
            achou_destino += 1
            print(f"      destino: {registro['ORGAO_DESTINO'][:60]} "
                  f"({registro['DATA_DESTINO']})")

        # Grava a cada pessoa: uma interrupção no meio de 268 nomes não pode
        # jogar fora o que já foi baixado. O índice de atos vai junto, pelo
        # mesmo motivo — e para os dois arquivos nunca discordarem.
        ARQ_SAIDAS.parent.mkdir(parents=True, exist_ok=True)
        with open(ARQ_SAIDAS, "w", encoding="utf-8", newline="") as fh:
            escritor = csv.DictWriter(fh, fieldnames=list(COLUNAS), delimiter=";",
                                      extrasaction="ignore")
            escritor.writeheader()
            escritor.writerows(resultados[k] for k in sorted(resultados))
        atos.gravar(indice)

    print()
    print(f"Motivo identificado : {achou_motivo} de {len(fila)}")
    print(f"Destino identificado: {achou_destino} de {len(fila)}")
    print(f"Gravado: {ARQ_SAIDAS.relative_to(RAIZ)} ({len(resultados)} linhas)")
    print(f"Gravado: {atos.ARQ_INDICE.relative_to(RAIZ)} ({len(indice)} atos)")
    print()
    print("CONFIRA À MÃO uma amostra dos atos antes de publicar: abra o ATO_SAIDA_URL,")
    print("veja se cita a pessoa e se o motivo classificado é o que o texto diz.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
