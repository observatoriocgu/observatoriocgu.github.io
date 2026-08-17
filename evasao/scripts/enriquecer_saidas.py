#!/usr/bin/env python3
"""
Para cada saída da CGU detectada no SIAPE, busca no DOU o ato que diz POR QUE a
pessoa saiu e, quando dá, PARA ONDE foi.

Entrada : data/dados.csv (as linhas com MES_SAIDA preenchido)
Saída   : data/dou/por_pessoa.csv        — acumulativo, uma linha por PESSOA
          data/dou/atos_saida.csv          — o índice único, uma linha por ATO
          data/dou/atos_saida/*.html     — cópia arquivada do ato

O arquivo de saída é uma camada separada de propósito: `construir_painel.py`
regenera o dados.csv do zero a cada execução, e se este script escrevesse lá
direto, reconstruir o painel apagaria ~50 minutos de crawl.

DUAS SAÍDAS, DUAS CHAVES, E ISSO NÃO É DUPLICAÇÃO. O `por_pessoa.csv` é indexado
por PESSOA e é o que o painel mescla no `dados.csv`. O `atos_saida.csv` é indexado
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
  SIAPE visíveis, e os atos escrevem o SIAPE por extenso.

  ONDE ELA VALE MUDOU EM 16/08/2026 (D25). Em ato de OUTRO órgão, a matrícula que
  conflita continua descartando o ato — lá o homônimo é risco real, e foi assim
  que uma lista do Judiciário virou "destino" de um Auditor. Em ato da PRÓPRIA
  CGU, ela rebaixa em vez de vetar: `dou.identidade_no_ato` aceita a identidade
  provada pela FÓRMULA do ato (nome exato, com terminador), e a exigência do
  cargo fica de pé. Sem isso, quatro saídas ficavam sem ato tendo o ato
  publicado — o DOU erra o nome (Portaria 325/2023: "PAGLIONE" por "PAGLIONI") e
  erra a matrícula (Portarias 1.026/2024, 2.529/2024 e 2.017/2025).

  BUSCAS DE RESERVA. Frase exata falha mais do que parece: o nome inteiro de uma
  Auditora não achava a portaria que declarou vago o cargo dela, e os três
  primeiros nomes acharam. Quando o nome do SIAPE não acha ato de saída, tenta-se
  o nome que a curadoria diz que o DOU usa (`COLUNA_NOME_NO_DOU`) e depois o nome
  encurtado. Isso afrouxa a BUSCA, nunca a IDENTIFICAÇÃO.

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
import json
import sys
from datetime import datetime
from pathlib import Path

import atos
import atos_destino
import dou

RAIZ = Path(__file__).resolve().parent.parent
ARQ_DADOS = RAIZ / "data" / "dados.csv"
ARQ_POR_PESSOA = RAIZ / "data" / "dou" / "por_pessoa.csv"
ARQ_CURADORIA = RAIZ / "data" / "curadoria.csv"
ARQ_RESUMO = RAIZ / "public" / "dou.json"

# Coluna OPCIONAL do `curadoria.csv`: o nome com que o DOU se refere a esta
# pessoa, quando não é o do SIAPE.
#
# O DOU e o Portal da Transparência discordam sobre o nome de gente com mais
# frequência do que se imagina, e nem sempre há como provar de dentro do ato.
# Quando o ato traz a matrícula, `identidade_no_ato` resolve sozinha. Quando não
# traz, não há o que fazer pela máquina — e o silêncio é a resposta certa.
#
# O caso que abriu esta porta: o Portal chama alguém de "LUIZ AUGUSTO GENTILUCCI
# ALVES"; o Edital CGU nº 5/2022 e a Portaria nº 1.968, de 17/08/2022 (exoneração
# a pedido, a partir de 12/08/2022 — o mês exato em que ele some do SIAPE) o
# chamam de "LUIZ AUGUSTO DA SILVA ALVES". Nenhum dos dois atos traz matrícula.
# Dois documentos independentes contra um cadastro não é prova, é indício forte —
# e indício forte sobre pessoa real e nomeada é pauta humana, não automação.
#
# `construir_painel.py` IGNORA esta coluna sem reclamar: `aplicar_curadoria` só
# copia campo que já exista em `pessoa`, e não existe `NOME_NO_DOU` lá. É o mesmo
# caminho por onde passaram VERIFICADO e VERIFICADO_EM.
COLUNA_NOME_NO_DOU = "NOME_NO_DOU"

COLUNAS = (
    "ID_SERVIDOR_PORTAL", "NOME", "SITUACAO",
    "MOTIVO_SAIDA", "FONTE_MOTIVO", "DATA_SAIDA", "DATA_PUBLICACAO_SAIDA",
    "ATO_SAIDA_TITULO", "ATO_SAIDA_URL", "ATO_SAIDA_ARQUIVO",
    "ORGAO_DESTINO", "CARGO_DESTINO", "DATA_DESTINO", "FONTE_DESTINO", "URL_DESTINO",
    # A cópia arquivada do ato de NOMEAÇÃO (D30), irmã de ATO_SAIDA_ARQUIVO. Sem
    # ela o destino — que é inferência, e menos confiável que o motivo — era a
    # única afirmação do site sem lastro próprio: só uma URL que o in.gov.br pode
    # mudar. Vazia para destino que não veio do DOU.
    "ATO_DESTINO_ARQUIVO",
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

# BUSCA DE RESERVA: quantos primeiros nomes usar quando o nome inteiro não acha
# o ato de saída.
#
# A busca do DOU é por frase exata, e a frase inteira falha mais do que parece.
# Caso real: `"DEBORA CRISTINA PASSOS DE SA"` devolve 4 atos e NENHUM da CGU;
# `"DEBORA CRISTINA PASSOS"` devolve 19, entre eles a Portaria nº 2.708, de
# 12/08/2025, que declara vago o cargo dela — ato público, com a matrícula
# batendo, que o observatório simplesmente não tinha ido buscar.
#
# Encurtar afrouxa a busca, não a identificação: quem decide se o ato é da
# pessoa continua sendo `dou.identidade_no_ato`, que exige matrícula compatível
# ou o nome exato lido da fórmula do ato. Trazer mais candidatos só aumenta o
# que se pode CONFERIR.
TOKENS_DA_BUSCA_DE_RESERVA = 3

# Partículas que não podem FECHAR a frase encurtada. `dou.PARTICULAS_DE_NOME` é
# a mesma lista, em minúscula, usada para outra coisa (decidir se um token faz
# parte de um nome); aqui interessa comparar com o nome já normalizado.
PARTICULAS = {p.upper() for p in dou.PARTICULAS_DE_NOME}


# Marca as pessoas que entraram na fila pelo DOU, e não pelo SIAPE. Para elas
# só o DESTINO é gravado — ver `somente_destino`.
CHAVE_SO_DO_DOU = "_SO_DO_DOU"


def saidas_so_do_dou(pessoas: list[dict]) -> list[dict]:
    """
    Quem o DOU já mostrou sair e o SIAPE ainda não (D22), para buscar o DESTINO.

    ESTA FILA FALTAVA, e a falta era invisível. A fila principal é
    `[p for p in pessoas if p.get("MES_SAIDA")]`, e `MES_SAIDA` vem do SIAPE —
    logo, quem saiu depois da última competência do Portal NUNCA teve o destino
    procurado no DOU. Não é que a busca falhava: ela não era feita.

    O caso que revelou isso: três Auditores com vacância publicada em 08/2026 e
    a PORTARIA-TCU nº 117, de 04/08/2026, nomeando os três para o TCU — ato
    público, a uma busca de distância, que o observatório não tinha ido buscar.

    O mês de referência da janela [-6, +6] é o da PUBLICAÇÃO do ato de saída, que
    é o que `mesclarSaidasDoDou` usa como competência no navegador.
    """
    if not ARQ_RESUMO.is_file():
        return []
    try:
        card = json.loads(ARQ_RESUMO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []

    por_id = {p["ID_SERVIDOR_PORTAL"]: p for p in pessoas}
    fila: dict[str, dict] = {}
    for saida in card.get("saidasRecentes", []):
        identificador = saida.get("idServidor")
        publicacao = saida.get("dataPublicacao") or ""
        if not identificador or len(publicacao) < 7:
            continue
        pessoa = por_id.get(identificador)
        # Quem já tem MES_SAIDA entrou pela fila principal, com a competência do
        # cadastro — que é a boa. Aqui só entra quem o SIAPE ainda não mostrou.
        if not pessoa or pessoa.get("MES_SAIDA"):
            continue
        fila[identificador] = {
            **pessoa,
            "MES_SAIDA": publicacao[:4] + publicacao[5:7],
            CHAVE_SO_DO_DOU: True,
        }
    return list(fila.values())


def somente_destino(registro: dict) -> dict:
    """
    Apaga do registro tudo o que não for destino.

    Necessário para quem entrou pela fila do DOU: essa pessoa NÃO tem `MES_SAIDA`
    no `dados.csv`, e gravar ali motivo, situação e ato produziria uma linha que
    afirma que alguém saiu sem dizer quando — o `SITUACAO = VACÂNCIA` de quem a
    interface ainda conta como em exercício. Quem põe motivo e situação nessa
    pessoa é `mesclarSaidasDoDou`, no navegador, a partir do mesmo ato. Aqui só
    entra o que lá não existe: o órgão de chegada.
    """
    preservar = ("ID_SERVIDOR_PORTAL", "NOME",
                 "ORGAO_DESTINO", "CARGO_DESTINO", "DATA_DESTINO",
                 "FONTE_DESTINO", "URL_DESTINO")
    return {campo: (valor if campo in preservar else "") for campo, valor in registro.items()}


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


def nome_encurtado(nome: str) -> str:
    """
    Os primeiros nomes, para a busca de reserva. Vazio se não encurta nada.

    A frase não pode terminar em partícula: `"RAFAEL ROCHA DOS"` é uma busca
    pior que `"RAFAEL ROCHA"` — pede um pedaço de sobrenome que o corte partiu
    ao meio, e a busca do DOU é por frase exata.
    """
    tokens = nome.split()
    if len(tokens) <= TOKENS_DA_BUSCA_DE_RESERVA:
        return ""
    curto = tokens[:TOKENS_DA_BUSCA_DE_RESERVA]
    while len(curto) > 2 and dou.normalizar(curto[-1]) in PARTICULAS:
        curto.pop()
    return " ".join(curto)


def seguir_retificacao(
    texto: str, matricula: str, usar_cache: bool, verboso: bool = False
) -> tuple[str, dict, str] | None:
    """
    O ato ORIGINAL que esta retificação corrige, já classificado. `None` se não há.

    Por que não classificar a própria retificação: ela é um documento pobre e de
    data errada. A de Kranzfeld (01/06/2023) só conserta a grafia do sobrenome e
    não diz o motivo da vacância; a de Angivaldo (10/05/2023) traz o motivo mas
    não o cargo, e sai SEIS MESES depois da saída que descreve. Publicar
    qualquer uma das duas como o ato da saída dataria a saída no dia em que o
    erro foi corrigido.

    O original tem tudo isso certo. O que só a retificação tem é o vínculo com a
    pessoa — e é justamente por isso que ela foi publicada.

    A identidade já foi provada pelo chamador, na retificação. Aqui a única
    guarda é a matrícula do original: se ela CONFLITAR, o ato é de outra pessoa e
    não se aproveita. Não se exige que o original nomeie a pessoa, porque em
    metade dos casos ele não a nomeia — foi essa a falha que a retificação veio
    corrigir.
    """
    for frase in dou.frases_do_ato_retificado(texto):
        for ato in dou.buscar(f'"{frase}"', usar_cache=usar_cache):
            if not dou.e_da_cgu(ato) or not ato.get("urlTitle"):
                continue
            _, original = dou.baixar_ato(ato["urlTitle"], usar_cache=usar_cache)
            if not original or dou.siape_compativel(original, matricula) is False:
                continue
            tipo = dou.classificar(original)
            if tipo:
                if verboso:
                    print(f"      + retificação leva a {frase}: {tipo}")
                return tipo, ato, original
    return None


def procurar_ato_de_saida(
    nomes: list[str], matricula: str, atos_ordenados: list[dict],
    usar_cache: bool, verboso: bool = False
) -> tuple[str, dict, str, str] | None:
    """
    O ato da CGU que diz por que a pessoa saiu. `(tipo, ato, texto, identidade)`.

    `nomes` é o nome do SIAPE e, quando a curadoria souber de outro, o nome com
    que o DOU chama a mesma pessoa (ver `COLUNA_NOME_NO_DOU`). Basta um deles
    provar a identidade.

    A identidade vai junto no resultado porque é o que se registra na observação:
    um ato aceito pelo nome exato, com a matrícula divergindo, é dado bom e
    merece uma segunda leitura humana.
    """
    for ato in atos_ordenados:
        chave = ato.get("urlTitle")
        if not chave or not dou.e_da_cgu(ato):
            continue
        _, texto = dou.baixar_ato(chave, usar_cache=usar_cache)
        if not texto:
            continue

        identidade = next(
            (nivel for nivel in (dou.identidade_no_ato(texto, n, matricula) for n in nomes) if nivel),
            "",
        )
        if not identidade:
            if verboso:
                print(f"      - descartado (não prova ser dela): {ato.get('title', '')[:55]}")
            continue

        # Identidade provada pela matrícula dispensa a prova do cargo: é o que
        # permite ler a demissão disciplinar, cujo texto fala do servidor e da
        # penalidade mas não do cargo de AFFC, e a cessão, que também não o cita.
        # Nos níveis mais fracos a exigência fica de pé.
        tipo = dou.classificar(texto, exigir_cargo=identidade != dou.IDENTIDADE_SIAPE)
        if tipo:
            if verboso:
                print(f"      + motivo {tipo} (por {identidade}): {ato.get('title', '')[:50]}")
            return tipo, ato, texto, identidade

        seguido = seguir_retificacao(texto, matricula, usar_cache, verboso)
        if seguido:
            return (*seguido, identidade)

    return None


def analisar(
    pessoa: dict, indice: dict, indice_destino: dict, usar_cache: bool,
    verboso: bool = False, nome_no_dou: str = ""
) -> dict:
    """Motivo e destino de uma saída, a partir dos atos do DOU que citam a pessoa."""
    nome, mes_saida = pessoa["NOME"], pessoa["MES_SAIDA"]
    matricula = pessoa.get("MATRICULA", "")
    registro = {c: "" for c in COLUNAS}
    registro["ID_SERVIDOR_PORTAL"] = pessoa["ID_SERVIDOR_PORTAL"]
    registro["NOME"] = nome

    # O nome do SIAPE é sempre o primeiro: é a grafia oficial, e é por ela que a
    # busca deve começar. O da curadoria entra em seguida, quando existir.
    nomes = [nome] + ([nome_no_dou] if nome_no_dou and nome_no_dou != nome else [])

    citam_a_pessoa = buscar_atos(nome, usar_cache)

    # Do mais próximo da saída para o mais distante: o ato que interessa é o que
    # está perto do mês em que a pessoa sumiu do SIAPE.
    def por_proximidade(lista: list[dict]) -> list[dict]:
        return sorted(lista, key=lambda a: abs(distancia_meses(dou.data_iso(a), mes_saida)))

    ordenados = por_proximidade(citam_a_pessoa)[:MAX_ATOS_POR_PESSOA]
    melhor_saida = procurar_ato_de_saida(nomes, matricula, ordenados, usar_cache, verboso)

    # Buscas de reserva, em ordem de força da evidência, e só para o ato de
    # SAÍDA: o destino depende de `e_ato_de_nomeacao`, que casa pelo nome inteiro
    # do SIAPE e não teria como aproveitar candidatos a mais.
    #
    #   1. o nome que a curadoria diz que o DOU usa — afirmação humana;
    #   2. os primeiros nomes — afrouxa a busca, não a identificação.
    for alternativo in ([nome_no_dou] if nome_no_dou and nome_no_dou != nome else []) + [
        nome_encurtado(nome)
    ]:
        if melhor_saida is not None:
            break
        if not alternativo:
            continue
        if verboso:
            print(f"      (nada com o nome inteiro — tentando {alternativo!r})")
        reserva = por_proximidade(dou.buscar(f'"{alternativo}"', usar_cache=usar_cache))
        melhor_saida = procurar_ato_de_saida(
            nomes, matricula, reserva[:MAX_ATOS_POR_PESSOA], usar_cache, verboso
        )

    candidatos_destino = []
    for ato in ordenados:
        chave = ato.get("urlTitle")
        if not chave or dou.e_da_cgu(ato):
            continue
        distancia = distancia_meses(dou.data_iso(ato), mes_saida)
        if not MESES_ANTES_DA_SAIDA <= distancia <= MESES_DEPOIS_DA_SAIDA:
            continue
        _, texto = dou.baixar_ato(chave, usar_cache=usar_cache)
        if not texto or not dou.cita_nome(texto, nome):
            continue
        # Fora da CGU o homônimo é risco real (ver o caso do TRE no cabeçalho), e
        # aqui a matrícula que conflita continua VETANDO. É o oposto do que vale
        # para o ato da própria CGU, e de propósito: lá o nome vem da fórmula do
        # ato sobre o cargo de AFFC, aqui vem de uma citação solta num ato de
        # outro órgão, que não sabe nada sobre a carreira desta pessoa.
        if dou.siape_compativel(texto, matricula) is False:
            if verboso:
                print(f"      - descartado (SIAPE não bate): {ato.get('title', '')[:55]}")
            continue
        if dou.e_ato_de_nomeacao(texto, nome):
            candidatos_destino.append((distancia, ato, texto))
            if verboso:
                print(f"      + destino?  {ato.get('hierarchyStr', '')[:50]}")
            # Como `ordenados` vem por proximidade da saída, o primeiro destino
            # já é o mais próximo — continuar só gastaria requisição.
            break

    if melhor_saida:
        tipo, ato, texto, identidade = melhor_saida
        if identidade != dou.IDENTIDADE_SIAPE:
            registro["OBSERVACAO"] = (
                f"identidade do ato provada por {identidade}, não pela matrícula "
                f"(ato: SIAPE {dou.siape_do_ato(texto) or 'ausente'}; "
                f"Portal: {matricula or 'ausente'}) — confira à mão"
            )
        registro["FONTE_MOTIVO"] = "DOU"
        registro["DATA_PUBLICACAO_SAIDA"] = dou.data_iso(ato)

        # O motivo é sempre o real: o dado não mente sobre o que aconteceu, e
        # quem decide o que mostrar é a tela (ver `MOTIVOS_NAO_PUBLICADOS`).
        registro["MOTIVO_SAIDA"] = dou.ROTULOS[tipo]
        registro["SITUACAO"] = dou.SITUACAO_POR_TIPO[tipo]

        # `atos.registrar` devolve None para ato não publicado (D18) e é o único
        # ponto que precisa decidir isso. Aqui basta respeitar: sem linha no
        # índice, sem título, sem URL e sem cópia arquivada — o índice e a pasta
        # `atos_saida/` vão inteiros para repositório público e para o site.
        linha = atos.registrar(
            indice, ato, tipo, texto, atos.FONTE_NOME,
            id_servidor=pessoa["ID_SERVIDOR_PORTAL"],
            nome=nome,
        )
        if linha is not None:
            registro["ATO_SAIDA_TITULO"] = linha["TITULO"]
            registro["ATO_SAIDA_URL"] = linha["URL"]
            registro["ATO_SAIDA_ARQUIVO"] = linha["ARQUIVO"]

    if candidatos_destino:
        # O mais próximo da saída, em qualquer direção. Se a pessoa tomou posse
        # em outro órgão, o ato sai perto da saída — não anos depois.
        _, ato, texto_destino = min(candidatos_destino, key=lambda c: abs(c[0]))
        registro["ORGAO_DESTINO"] = dou.orgao_do_ato(ato)
        registro["DATA_DESTINO"] = dou.data_iso(ato)
        registro["FONTE_DESTINO"] = "DOU"
        registro["URL_DESTINO"] = dou.BASE_ATO + ato["urlTitle"]

        # O ato de chegada vai para o índice PRÓPRIO dele e ganha cópia
        # arquivada (D30). Não custa requisição: o texto já está em mãos, lido
        # nesta mesma busca — antes ele era usado e jogado fora.
        linha_destino = atos_destino.registrar(
            indice_destino, ato, texto_destino,
            id_servidor=pessoa["ID_SERVIDOR_PORTAL"],
            nome=nome,
        )
        if linha_destino is not None:
            registro["ATO_DESTINO_ARQUIVO"] = linha_destino["ARQUIVO"]

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

    ja_feitas = {r["ID_SERVIDOR_PORTAL"]: r for r in ler_csv(ARQ_POR_PESSOA)}

    # Nomes alternativos afirmados à mão. Coluna opcional: se ninguém a criou, o
    # dicionário fica vazio e nada muda.
    nomes_no_dou = {
        c["ID_SERVIDOR_PORTAL"]: c[COLUNA_NOME_NO_DOU]
        for c in ler_csv(ARQ_CURADORIA)
        if c.get("ID_SERVIDOR_PORTAL") and c.get(COLUNA_NOME_NO_DOU)
    }

    # O índice de atos de SAÍDA é compartilhado com a varredura por frase; o de
    # DESTINO (D30) é só deste crawler e do `arquivar_destinos.py`. São dois
    # porque são atos de assuntos diferentes — ver o cabeçalho de `atos_destino`.
    indice = atos.ler()
    indice_destino = atos_destino.ler()

    fila = [p for p in pessoas if p.get("MES_SAIDA")] + saidas_so_do_dou(pessoas)
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
        atos_destino.gravar(indice_destino)
        print("Nada a fazer.")
        return 0
    print(f"Pausa entre requisições: {dou.PAUSA_SEGUNDOS}s | cache: "
          f"{'ligado' if usar_cache else 'DESLIGADO'}")
    print()

    resultados = dict(ja_feitas)
    achou_motivo = achou_destino = 0

    for numero, pessoa in enumerate(fila, start=1):
        print(f"[{numero}/{len(fila)}] {pessoa['NOME'][:44]:<44} saiu em {pessoa['MES_SAIDA']}")
        registro = analisar(
            pessoa, indice, indice_destino, usar_cache, verboso=bool(args.nome),
            nome_no_dou=nomes_no_dou.get(pessoa["ID_SERVIDOR_PORTAL"], ""),
        )
        if pessoa.get(CHAVE_SO_DO_DOU):
            registro = somente_destino(registro)
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
        ARQ_POR_PESSOA.parent.mkdir(parents=True, exist_ok=True)
        with open(ARQ_POR_PESSOA, "w", encoding="utf-8", newline="") as fh:
            escritor = csv.DictWriter(fh, fieldnames=list(COLUNAS), delimiter=";",
                                      extrasaction="ignore")
            escritor.writeheader()
            escritor.writerows(resultados[k] for k in sorted(resultados))
        atos.gravar(indice)
        atos_destino.gravar(indice_destino)

    print()
    print(f"Motivo identificado : {achou_motivo} de {len(fila)}")
    print(f"Destino identificado: {achou_destino} de {len(fila)}")
    print(f"Gravado: {ARQ_POR_PESSOA.relative_to(RAIZ)} ({len(resultados)} linhas)")
    print(f"Gravado: {atos.ARQ_INDICE.relative_to(RAIZ)} ({len(indice)} atos de saída)")
    print(f"Gravado: {atos_destino.ARQ_INDICE.relative_to(RAIZ)} ({len(indice_destino)} atos de destino)")
    print()
    print("CONFIRA À MÃO uma amostra dos atos antes de publicar: abra o ATO_SAIDA_URL,")
    print("veja se cita a pessoa e se o motivo classificado é o que o texto diz.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
