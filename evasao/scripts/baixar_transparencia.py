#!/usr/bin/env python3
"""
Baixa do Portal da Transparência os snapshots mensais que ainda faltam.

Automatiza os passos 1 e 2 da ROTINA MENSAL do `atualizar.py`: pegar o ZIP do
mês em portaldatransparencia.gov.br/download-de-dados/servidores e descompactar
o `AAAAMM_Cadastro.csv` em `evasao/data/historico_transparencia_cgu/`.

O que ele faz:
  1. olha os snapshots VERSIONADOS (`data/siape/AAAAMM.csv.gz`) e vê quais
     competências de 202206 até o mês atual faltam — a pergunta é respondida
     pelo repositório, não pela pasta de trabalho local (D32);
  2. baixa o ZIP de cada uma que falta (equivale a marcar "exercício atual",
     "mês atual" e "planilha Servidores_SIAPE" na tela do portal);
  3. extrai só o `AAAAMM_Cadastro.csv` — os outros três membros do ZIP
     (Remuneração, Afastamentos, Observações) são descartados;
  4. chama o `filtrar_affc.py`, que reduz o bruto (~420 MB) aos AFFC e às 16
     colunas que a derivação lê, e grava `data/siape/AAAAMM.csv.gz` (~89 KB).

O caso de uso normal é o mês novo: com a série em dia, sobra uma competência ou
nenhuma. Com a pasta vazia, ele faz o backfill inteiro — ~4 GB de download.

RODA IGUAL NA MÁQUINA E NO CI. O que ele grava são os ~89 KB do snapshot; o ZIP e
o CSV de 420 MB são efêmeros nos dois lugares. É o que permite ao workflow mensal
fazer a rotina inteira sem que ninguém baixe nada à mão.

O PORTAL ATRASA. Em agosto/2026 a competência mais recente publicada era
junho/2026: os dois últimos meses do intervalo esperado normalmente ainda não
existem no servidor. Isso NÃO é erro — o script chama de "aguardando publicação"
e sai com código 0. Só devolve código 1 quando um mês publicado não pôde ser
baixado, ou quando sobra um buraco no meio da série.

URL (verificada em 14/08/2026): a página do portal manda um 302 para o S3 da
CGU, e é o S3 que responde 403 quando a competência ainda não saiu — não 404.
Por isso 403 e 404 valem a mesma coisa aqui: "ainda não publicado".

Uso (de qualquer diretório):
    python baixar_transparencia.py                  # baixa e filtra o que falta
    python baixar_transparencia.py --dry-run        # só relatório, nada gravado
    python baixar_transparencia.py --limite 3       # no máximo 3 meses por vez
    python baixar_transparencia.py --refazer 202605 # rebaixa uma retificação
    python baixar_transparencia.py --sem-filtrar    # deixa o bruto sem filtrar
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

AQUI = Path(__file__).resolve().parent
if str(AQUI) not in sys.path:
    sys.path.insert(0, str(AQUI))

import filtrar_affc  # noqa: E402  (só resolve depois de ajustar o sys.path)
import painel  # noqa: E402

RAIZ = AQUI.parent
PASTA_PADRAO = RAIZ / "data" / "historico_transparencia_cgu"

# Homologação do concurso: 14/06/2022. A série começa na competência do mês.
COMPETENCIA_INICIAL = "202206"

BASE_DOWNLOAD = "https://portaldatransparencia.gov.br/download-de-dados/servidores"

CABECALHOS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/zip,application/octet-stream,*/*",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

# Segundos entre duas requisições, para não martelar o portal num backfill.
PAUSA_SEGUNDOS = 1.0

# Um mês custa ~85 MB de ZIP mais ~450 MB de CSV bruto, e os dois convivem no
# disco até a extração terminar. Abaixo disso o backfill morre no meio.
ESPACO_MINIMO_BYTES = 1_500_000_000

BLOCO = 1 << 20  # 1 MB

# Estados possíveis de uma competência na pasta local.
FILTRADO = "filtrado"   # nada a fazer
BRUTO = "bruto"         # baixado, mas ainda não filtrado
AUSENTE = "ausente"     # precisa baixar

# Resultados possíveis de uma tentativa de download.
OK = "ok"
NAO_PUBLICADO = "nao_publicado"
FALHA = "falha"


# ------------------------------------------------------------------ utilidades

def formatar_bytes(n: float) -> str:
    for unidade in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidade == "GB":
            return f"{n:.1f} {unidade}"
        n /= 1024
    return f"{n:.1f} GB"


def competencia_valida(texto: str) -> str:
    if not re.fullmatch(r"\d{4}(0[1-9]|1[0-2])", texto):
        raise argparse.ArgumentTypeError(f"competência inválida: {texto} (esperado AAAAMM)")
    return texto


def competencia_atual() -> str:
    hoje = date.today()
    return f"{hoje.year}{hoje.month:02d}"


def intervalo(inicio: str, fim: str) -> list[str]:
    """Competências de `inicio` a `fim`, inclusive. AAAAMM com zero à esquerda
    compara certo como string, então a parada é uma comparação simples."""
    ano, mes = int(inicio[:4]), int(inicio[4:])
    saida = []
    while f"{ano}{mes:02d}" <= fim:
        saida.append(f"{ano}{mes:02d}")
        mes += 1
        if mes == 13:
            ano, mes = ano + 1, 1
    return saida


def caminho_filtrado(pasta: Path, comp: str) -> Path:
    """
    O snapshot VERSIONADO da competência — e repare que ele não depende de
    `pasta` (D32).

    É de propósito: a pergunta "o que já foi carregado?" tem de ser respondida
    pelo que está no repositório, não pelo que sobrou na pasta de trabalho de
    quem roda. Assim a resposta é a mesma na sua máquina e no CI, e um bruto
    esquecido no disco não faz o script pular uma competência que o projeto
    ainda não tem.
    """
    return painel.PASTA_SNAPSHOTS / f"{comp}.csv.gz"


def caminho_bruto(pasta: Path, comp: str) -> Path:
    return pasta / f"{comp}_Cadastro.csv"


def estado(pasta: Path, comp: str) -> str:
    if caminho_filtrado(pasta, comp).is_file():
        return FILTRADO
    if caminho_bruto(pasta, comp).is_file():
        return BRUTO
    return AUSENTE


def url_do_mes(comp: str) -> str:
    return f"{BASE_DOWNLOAD}/{comp}_Servidores_SIAPE"


def buracos(pasta: Path, esperadas: list[str]) -> list[str]:
    """Competências que faltam ANTES da última que existe.

    O que falta no fim da série é o atraso do portal, e passa. O que falta no
    meio é dado sumido: o painel calcula saída por ausência (D13), então um mês
    vazio no miolo vira uma leva de saídas falsas. Isso tem de gritar.
    """
    completas = [c for c in esperadas if estado(pasta, c) == FILTRADO]
    if not completas:
        return []
    ultima = completas[-1]
    return [c for c in esperadas if c < ultima and estado(pasta, c) != FILTRADO]


_ultima_requisicao = 0.0


def _respeitar_pausa() -> None:
    global _ultima_requisicao
    espera = PAUSA_SEGUNDOS - (time.monotonic() - _ultima_requisicao)
    if espera > 0:
        time.sleep(espera)
    _ultima_requisicao = time.monotonic()


# ------------------------------------------------------------------------ rede

def consultar(comp: str) -> tuple[str, int]:
    """Só olha se a competência existe no servidor, sem baixar o corpo.

    Devolve (OK|NAO_PUBLICADO|FALHA, tamanho_em_bytes). O tamanho vem do
    Content-Length e é 0 quando o servidor não informa.
    """
    url = url_do_mes(comp)
    _respeitar_pausa()
    try:
        req = urllib.request.Request(url, headers=CABECALHOS, method="HEAD")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return OK, int(resp.headers.get("Content-Length") or 0)
    except urllib.error.HTTPError as erro:
        if erro.code in (403, 404):
            return NAO_PUBLICADO, 0
        # Outro código HTTP pode ser bloqueio de User-Agent — o curl costuma passar.
    except Exception:
        pass

    try:
        proc = subprocess.run(
            ["curl", "-sS", "-I", "-L", "-m", "60", "-A", CABECALHOS["User-Agent"],
             "-o", os.devnull, "-w", "%{http_code} %{size_download} %{header_json}", url],
            capture_output=True,
            timeout=90,
        )
    except Exception as erro:
        print(f"  ! não consegui consultar {comp}: {erro}", file=sys.stderr)
        return FALHA, 0

    saida = proc.stdout.decode("utf-8", errors="replace")
    codigo = saida.split(" ", 1)[0].strip()
    if codigo.startswith("2"):
        achado = re.search(r'"content-length":\s*\["?(\d+)', saida)
        return OK, int(achado.group(1)) if achado else 0
    if codigo in ("403", "404"):
        return NAO_PUBLICADO, 0
    print(f"  ! consulta a {comp} devolveu HTTP {codigo or '?'}", file=sys.stderr)
    return FALHA, 0


def _progresso(baixado: int, total: int) -> None:
    if total:
        pct = 100.0 * baixado / total
        print(f"\r    {formatar_bytes(baixado)} de {formatar_bytes(total)} ({pct:.0f}%)",
              end="", flush=True)
    else:
        print(f"\r    {formatar_bytes(baixado)}", end="", flush=True)


def baixar_zip(comp: str, destino: Path, timeout: int = 900) -> str:
    """Baixa o ZIP do mês para `destino`. Devolve OK, NAO_PUBLICADO ou FALHA.

    Grava num `.parcial` e só renomeia no fim, para que uma interrupção não
    deixe um ZIP truncado parecendo completo.
    """
    url = url_do_mes(comp)
    parcial = destino.with_suffix(destino.suffix + ".parcial")
    parcial.unlink(missing_ok=True)

    _respeitar_pausa()
    try:
        req = urllib.request.Request(url, headers=CABECALHOS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            baixado = 0
            with open(parcial, "wb") as fh:
                while True:
                    bloco = resp.read(BLOCO)
                    if not bloco:
                        break
                    fh.write(bloco)
                    baixado += len(bloco)
                    _progresso(baixado, total)
            print()
        # Content-Length menor que o arquivo significa conexão cortada no meio.
        if total and baixado != total:
            print(f"  ! download incompleto: {baixado} de {total} bytes.", file=sys.stderr)
            parcial.unlink(missing_ok=True)
            return FALHA
        os.replace(parcial, destino)
        return OK
    except urllib.error.HTTPError as erro:
        parcial.unlink(missing_ok=True)
        if erro.code in (403, 404):
            return NAO_PUBLICADO
    except Exception:
        parcial.unlink(missing_ok=True)

    # Mesmo fallback do dou.py: alguns proxies barram o urllib e deixam o curl.
    print("    urllib não deu conta — tentando pelo curl...")
    try:
        proc = subprocess.run(
            ["curl", "-fL", "--retry", "2", "-m", str(timeout),
             "-A", CABECALHOS["User-Agent"], "-w", "%{http_code}",
             "-o", str(parcial), url],
            capture_output=True,
            timeout=timeout + 120,
        )
    except Exception as erro:
        parcial.unlink(missing_ok=True)
        print(f"  ! curl falhou em {comp}: {erro}", file=sys.stderr)
        return FALHA

    codigo = proc.stdout.decode("utf-8", errors="replace").strip()[-3:]
    if proc.returncode == 0 and parcial.is_file() and parcial.stat().st_size > 0:
        os.replace(parcial, destino)
        return OK

    parcial.unlink(missing_ok=True)
    if codigo in ("403", "404"):
        return NAO_PUBLICADO
    erro_curl = proc.stderr.decode("utf-8", errors="replace").strip()
    print(f"  ! curl devolveu HTTP {codigo or '?'} em {comp}: {erro_curl[:200]}", file=sys.stderr)
    return FALHA


# ------------------------------------------------------------------- descompac

def extrair_cadastro(caminho_zip: Path, comp: str, pasta: Path) -> Path | None:
    """Tira do ZIP só o membro de Cadastro. Devolve o caminho gravado."""
    if not zipfile.is_zipfile(caminho_zip):
        print(f"  ! {caminho_zip.name} não é um ZIP válido.", file=sys.stderr)
        return None

    destino = caminho_bruto(pasta, comp)
    parcial = destino.with_suffix(destino.suffix + ".parcial")

    with zipfile.ZipFile(caminho_zip) as arquivo:
        nomes = arquivo.namelist()
        # O ZIP traz quatro membros: Cadastro, Remuneração, Afastamentos e
        # Observações. Só o Cadastro interessa — os outros somam centenas de MB.
        alvo = next(
            (n for n in nomes if re.fullmatch(r"\d{6}_Cadastro\.csv", n.rsplit("/", 1)[-1], re.I)),
            None,
        )
        if alvo is None:
            alvo = next(
                (n for n in nomes
                 if n.lower().endswith(".csv") and "cadastro" in n.rsplit("/", 1)[-1].lower()),
                None,
            )
        if alvo is None:
            print(f"  ! nenhum membro de Cadastro em {caminho_zip.name}: {nomes}", file=sys.stderr)
            return None

        with arquivo.open(alvo) as origem, open(parcial, "wb") as fh:
            shutil.copyfileobj(origem, fh, BLOCO)

    os.replace(parcial, destino)
    print(f"    extraído {alvo} -> {destino.name} ({formatar_bytes(destino.stat().st_size)})")
    return destino


# ------------------------------------------------------------------- orquestra

def processar(comp: str, pasta: Path, filtrar: bool, manter_zip: bool) -> str:
    """Baixa, extrai e filtra uma competência. Devolve OK, NAO_PUBLICADO ou FALHA."""
    bruto = caminho_bruto(pasta, comp)

    if bruto.is_file():
        print(f"  {comp}: bruto já está na pasta — pulando o download.")
    else:
        livre = shutil.disk_usage(pasta).free
        if livre < ESPACO_MINIMO_BYTES:
            print(f"  ! só há {formatar_bytes(livre)} livres no disco; são precisos "
                  f"~{formatar_bytes(ESPACO_MINIMO_BYTES)} por mês.", file=sys.stderr)
            return FALHA

        caminho_zip = pasta / f"{comp}_Servidores_SIAPE.zip"
        print(f"  {comp}: baixando {url_do_mes(comp)}")
        resultado = baixar_zip(comp, caminho_zip)
        if resultado != OK:
            return resultado

        try:
            if extrair_cadastro(caminho_zip, comp, pasta) is None:
                return FALHA
        finally:
            if manter_zip:
                print(f"    ZIP conservado: {caminho_zip.name}")
            else:
                caminho_zip.unlink(missing_ok=True)

    if not filtrar:
        print(f"    {bruto.name} pronto para o filtrar_affc.py.")
        return OK

    filtrar_affc.filtrar_arquivo(bruto, dry_run=False, manter_original=False)
    if not caminho_filtrado(pasta, comp).is_file():
        print(f"  ! o filtro não gerou saída para {comp}.", file=sys.stderr)
        return FALHA
    return OK


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Baixa do Portal da Transparência os snapshots mensais que faltam."
    )
    parser.add_argument("--pasta", type=Path, default=PASTA_PADRAO,
                        help=f"Pasta dos snapshots (padrão: data/{PASTA_PADRAO.name}).")
    parser.add_argument("--desde", type=competencia_valida, default=COMPETENCIA_INICIAL,
                        help=f"Primeira competência AAAAMM (padrão: {COMPETENCIA_INICIAL}).")
    parser.add_argument("--ate", type=competencia_valida, default=None,
                        help="Última competência AAAAMM (padrão: o mês atual).")
    parser.add_argument("--refazer", type=competencia_valida, nargs="+", metavar="AAAAMM",
                        help="Rebaixa estas competências mesmo já filtradas (retificação).")
    parser.add_argument("--limite", type=int,
                        help="Baixa no máximo N competências nesta execução.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Só relata o que falta e se o portal já publicou; não baixa nada.")
    parser.add_argument("--sem-filtrar", action="store_true",
                        help="Deixa o AAAAMM_Cadastro.csv bruto, sem chamar o filtrar_affc.")
    parser.add_argument("--manter-zip", action="store_true",
                        help="Não apaga o ZIP depois de extrair o Cadastro.")
    args = parser.parse_args()

    # Mesmo motivo do filtrar_affc: o limite padrão do csv é baixo para estes
    # arquivos, e uma linha malformada derrubaria a execução.
    csv.field_size_limit(10 * 1024 * 1024)

    pasta = args.pasta.resolve()
    pasta.mkdir(parents=True, exist_ok=True)

    fim = args.ate or competencia_atual()
    if fim < args.desde:
        sys.exit(f"Intervalo vazio: --ate {fim} é anterior a --desde {args.desde}.")

    esperadas = intervalo(args.desde, fim)
    situacao = {comp: estado(pasta, comp) for comp in esperadas}

    # Antes de aplicar o --refazer: um mês que o usuário mandou rebaixar de
    # propósito não é buraco.
    buracos_iniciais = buracos(pasta, esperadas)

    refazer = sorted(set(args.refazer or []))
    fora = [c for c in refazer if c not in situacao]
    if fora:
        sys.exit("--refazer fora do intervalo " + f"{args.desde}-{fim}: " + ", ".join(fora))
    for comp in refazer:
        situacao[comp] = AUSENTE

    completas = [c for c in esperadas if situacao[c] == FILTRADO]
    pendentes = [c for c in esperadas if situacao[c] != FILTRADO]

    print(f"Pasta     : {pasta}")
    print(f"Intervalo : {args.desde} a {fim} ({len(esperadas)} competências)")
    print(f"Completas : {len(completas)}")
    print(f"Pendentes : {len(pendentes)}"
          + (" — " + ", ".join(pendentes) if pendentes else ""))
    if refazer:
        print(f"Refazendo : {', '.join(refazer)}")
    if buracos_iniciais:
        print(f"! BURACO NA SÉRIE: faltam {', '.join(buracos_iniciais)} no meio do intervalo.")
    print()

    if not pendentes:
        print("Nada a fazer: a série está completa até o mês atual.")
        return 0

    if args.limite and args.limite < len(pendentes):
        # Ordem cronológica: um backfill interrompido deixa a série contígua.
        print(f"--limite {args.limite}: das {len(pendentes)} pendentes, "
              f"as {len(pendentes) - args.limite} mais recentes ficam para a próxima execução.")
        pendentes = pendentes[: args.limite]
        print()

    if args.dry_run:
        print("SIMULAÇÃO — nada será baixado.")
        aguardando, disponiveis, indisponiveis = [], [], []
        for comp in pendentes:
            if situacao[comp] == BRUTO:
                print(f"  {comp}: bruto na pasta, falta filtrar.")
                disponiveis.append(comp)
                continue
            resultado, tamanho = consultar(comp)
            if resultado == OK:
                print(f"  {comp}: publicado ({formatar_bytes(tamanho)}) — seria baixado.")
                disponiveis.append(comp)
            elif resultado == NAO_PUBLICADO:
                print(f"  {comp}: ainda não publicado no portal.")
                aguardando.append(comp)
            else:
                print(f"  {comp}: não deu para consultar.")
                indisponiveis.append(comp)
        print()
        # Esta linha é CONTRATO: o atualizar-siape.yml faz grep em
        # "A baixar: 0 |" para decidir se pula o resto do job (janela 15-28).
        # Mudar o texto sem mudar o grep faria o CI rodar o ciclo inteiro todo
        # dia, em silêncio.
        print(f"A baixar: {len(disponiveis)} | Aguardando publicação: {len(aguardando)} "
              f"| Sem resposta: {len(indisponiveis)}")
        # Um buraco que o portal diz não ter publicado não se resolve esperando.
        insanaveis = indisponiveis + [c for c in aguardando if c in buracos_iniciais]
        return 1 if insanaveis else 0

    baixadas, aguardando, falhas = [], [], []
    for indice, comp in enumerate(pendentes, start=1):
        print(f"[{indice}/{len(pendentes)}] {comp}")
        resultado = processar(comp, pasta, not args.sem_filtrar, args.manter_zip)
        if resultado == OK:
            baixadas.append(comp)
        elif resultado == NAO_PUBLICADO:
            print(f"  {comp}: ainda não publicado no portal.")
            aguardando.append(comp)
        else:
            falhas.append(comp)
        print()

    print(f"Baixadas             : {len(baixadas)}"
          + (" — " + ", ".join(baixadas) if baixadas else ""))
    if aguardando:
        print(f"Aguardando publicação: {', '.join(aguardando)}")
    if falhas:
        print(f"Falharam             : {', '.join(falhas)}")

    buracos_finais = buracos(pasta, esperadas)
    if buracos_finais:
        print()
        print(f"! BURACO NA SÉRIE: ainda faltam {', '.join(buracos_finais)} no meio do intervalo.",
              file=sys.stderr)

    if baixadas and not args.sem_filtrar:
        print()
        print("Snapshots novos na pasta. Agora rode: python atualizar.py")

    return 1 if (falhas or buracos_finais) else 0


if __name__ == "__main__":
    raise SystemExit(main())
