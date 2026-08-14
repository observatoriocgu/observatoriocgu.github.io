#!/usr/bin/env python3
"""
Busca no Diário Oficial da União as saídas mais recentes de Auditores Federais
de Finanças e Controle (AFFC) da CGU e alimenta o card "dias sem perder um Auditor".

Três tipos de saída são rastreados, cada um com o seu ato mais recente:
  - vacancia      : vacância do cargo por posse em outro cargo inacumulável
  - aposentadoria : concessão de aposentadoria
  - exoneracao    : exoneração do cargo efetivo de AFFC

Saídas do script:
  - evasao/public/dias_sem_perder_affc.json      -> lido pela interface
  - evasao/data/dias_sem_perder_AFFC/*.html      -> o trecho do DOU de cada ato

O JSON guarda DATAS, nunca a contagem de dias: quem calcula "faz N dias" é o
navegador, na hora de renderizar. Assim o card não congela no dia em que o
crawler rodou.

Como a busca do DOU se comporta (verificado em 13/08/2026):
  - endpoint público, sem autenticação: /consulta/-/buscar/dou
  - o JSON dos resultados vem embutido num <script id="..._BuscaDouPortlet_params">
  - aceita UMA frase entre aspas; frase + termo solto devolve ZERO resultados,
    e termos soltos viram OU (centenas de milhares de resultados)
  - `delta` funciona até 50; acima disso o servidor volta a 20
  - não há parâmetro de paginação que funcione (currentPage/pagina/_cur foram
    testados e devolvem sempre a primeira página)
  => por isso a varredura é feita por JANELAS DE DATA, andando para trás.

Uso:
    python dou_saidas_affc.py --diagnostico   # mostra o que achou, não grava
    python dou_saidas_affc.py                 # grava JSON + HTMLs
    python dou_saidas_affc.py --meses 24      # varre mais fundo
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import subprocess
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_ATOS = RAIZ / "data" / "dias_sem_perder_AFFC"
ARQUIVO_JSON = RAIZ / "public" / "dias_sem_perder_affc.json"

BASE_BUSCA = "https://www.in.gov.br/consulta/-/buscar/dou"
BASE_ATO = "https://www.in.gov.br/web/dou/-/"

# Uma frase só — ver nota no cabeçalho. A busca do DOU ignora acento e gênero,
# então esta frase também traz "Auditora Federal de Finanças e Controle".
FRASE_BUSCA = '"Auditor Federal de Finanças e Controle"'

ORGAO_CGU = "CONTROLADORIA-GERAL DA UNIAO"

# Janela de 15 dias: em janelas mensais alguns meses passam de 50 atos, que é o
# teto por resposta, e atos seriam perdidos silenciosamente.
DIAS_POR_JANELA = 15

TIPOS = ("vacancia", "aposentadoria", "exoneracao")

ROTULOS = {
    "vacancia": "Vacância (posse em outro cargo)",
    "aposentadoria": "Aposentadoria",
    "exoneracao": "Exoneração",
}

# Exoneração de cargo em comissão / função não é saída da CGU: o servidor deixa
# a chefia e continua Auditor. Sem este recorte, o card contaria troca de chefia
# como evasão — foi um falso positivo real na validação de 13/08/2026:
# "EXONERAR [...], Auditor Federal de Finanças e Controle, do Cargo Comissionado
#  Executivo de Chefe de Setor, código CCE 1.02".
# Padrões já normalizados (caixa alta, sem acento) — não passar por normalizar().
PADROES_NAO_E_SAIDA = (
    r"CARGO\s+EM\s+COMISS",
    r"CARGO\s+COMISSIONADO",
    r"FUN[CG][AO]O\s+COMISSIONADA",
    r"FUNCAO\s+DE\s+CONFIAN",
    r"\bFCPE\b",
    r"\bCCE\b",
    r"\bFCE\b",
    r"\bCCE\s*\d",
    r"\bDAS[\s-]?\d",
    r"CODIGO\s+DAS",
)

# Não basta ausência de marcador de chefia: a exoneração precisa ser DO CARGO de
# AFFC. Um ato que só cita o cargo de passagem ("Fulano, Auditor Federal...,
# exonerado de X") não conta.
PADRAO_EXONERACAO_EFETIVA = (
    r"EXONERA(?:R|CAO)[^.]{0,200}?"
    r"DO\s+CARGO(?:\s+EFETIVO)?\s+DE\s+AUDITOR[A]?\s+FEDERAL\s+DE\s+FINANCAS\s+E\s+CONTROLE"
)

# Padrões já normalizados (caixa alta, sem acento) — ver nota em PADRAO_CARGO.
#
# Vacância: o DOU NÃO usa a palavra "vacância" nesses atos. A redação real é
# "Declarar vago o cargo de Auditor Federal [...] por motivo de posse em outro
# cargo inacumulável" (art. 33, VIII, da Lei 8.112/90). Procurar por "VACANCIA"
# fazia o crawler perder todos eles em silêncio.
PADROES = {
    "vacancia": (
        r"DECLARAR\s+VAG[OA]",
        r"DECLARAR\s+A\s+VACANCIA",
        r"VACANCIA\s+DO\s+CARGO",
    ),
    "aposentadoria": (r"APOSENTADORIA", r"\bAPOSENTAR\b"),
    "exoneracao": (r"EXONERACAO", r"\bEXONERAR\b"),
}

# A vacância só conta como saída quando o motivo é posse em outro cargo — que é
# o recorte pedido. O art. 33 lista outros motivos (promoção, readaptação) que
# são movimentação interna, não saída da CGU.
#
# Este é também o desempate contra a exoneração a pedido, cuja redação traz
# "ficando vago o cargo que atualmente ocupa" — texto que casaria com um padrão
# frouxo tipo "VAGO O CARGO", mas não com "DECLARAR VAGO".
PADRAO_VACANCIA_MOTIVO = r"POSSE\s+EM\s+OUTRO\s+CARGO"

# Só conta se o ato realmente falar do cargo efetivo de AFFC.
# ATENÇÃO: já está na forma normalizada (caixa alta, sem acento). NÃO passar por
# `normalizar()` — o .upper() converteria \s em \S e o padrão nunca casaria.
PADRAO_CARGO = r"AUDITOR[A]?\s+FEDERAL\s+DE\s+FINANCAS\s+E\s+CONTROLE"


def normalizar(texto: str) -> str:
    """Caixa alta, sem acentos, espaços colapsados — para comparar com segurança."""
    decomposto = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_acento.upper().split())


def baixar(url: str, timeout: int = 90) -> str:
    """
    Baixa uma URL como texto.

    Tenta urllib e cai para o curl se levar 403 — alguns proxies bloqueiam o
    User-Agent do urllib mas deixam o curl passar.
    """
    cabecalhos = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "pt-BR,pt;q=0.9",
    }
    try:
        req = urllib.request.Request(url, headers=cabecalhos)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        pass

    try:
        proc = subprocess.run(
            ["curl", "-sS", "-m", str(timeout), "-A", cabecalhos["User-Agent"], url],
            capture_output=True,
            check=True,
        )
        return proc.stdout.decode("utf-8", errors="replace")
    except Exception as erro:
        print(f"    ! falha ao baixar {url[:80]}: {erro}", file=sys.stderr)
        return ""


def buscar_janela(inicio: date, fim: date) -> list[dict]:
    """Resultados da busca numa janela de datas, do mais recente para o mais antigo."""
    url = BASE_BUSCA + "?" + urllib.parse.urlencode(
        {
            "q": FRASE_BUSCA,
            "s": "todos",
            "sortType": "0",
            "delta": "50",
            "exactDate": "personalizado",
            "publishFrom": inicio.strftime("%d-%m-%Y"),
            "publishTo": fim.strftime("%d-%m-%Y"),
        }
    )
    pagina = baixar(url)
    if not pagina:
        return []

    achado = re.search(
        r'BuscaDouPortlet_params"[^>]*>(.*?)</script>', pagina, re.S
    )
    if not achado:
        return []

    try:
        dados = json.loads(html_mod.unescape(achado.group(1).strip()))
    except json.JSONDecodeError:
        return []

    return dados.get("jsonArray", []) or []


def e_da_cgu(resultado: dict) -> bool:
    hierarquia = resultado.get("hierarchyList") or []
    return any(ORGAO_CGU in normalizar(nivel) for nivel in hierarquia)


def extrair_texto(pagina_html: str) -> str:
    """Texto corrido do ato, a partir da div .texto-dou da página do DOU."""
    achado = re.search(
        r'<div[^>]*class="[^"]*texto-dou[^"]*"[^>]*>(.*?)</div>\s*(?:<div|</section|</article)',
        pagina_html,
        re.S,
    )
    bruto = achado.group(1) if achado else pagina_html
    sem_tag = re.sub(r"<[^>]+>", " ", bruto)
    return " ".join(html_mod.unescape(sem_tag).split())


def classificar(texto: str) -> str | None:
    """
    Diz se o ato é uma saída de AFFC e de que tipo. `None` quando não é.

    A ordem importa: vacância e aposentadoria costumam trazer também a palavra
    "exoneração" no mesmo ato, então a exoneração é a última hipótese testada.
    """
    normalizado = normalizar(texto)

    if not re.search(PADRAO_CARGO, normalizado):
        return None

    # IMPORTANTE: quando um tipo é descartado, o certo é `continue` — testar os
    # demais —, nunca `return None`. Os atos se sobrepõem no vocabulário: um ato
    # de aposentadoria termina com "declarar vago o referido cargo", e um
    # `return` no teste de vacância engolia a aposentadoria inteira.
    for tipo in TIPOS:
        if not any(re.search(p, normalizado) for p in PADROES[tipo]):
            continue

        if tipo == "vacancia" and not re.search(PADRAO_VACANCIA_MOTIVO, normalizado):
            continue  # "declarar vago" sem posse em outro cargo: ver se é outro tipo

        if tipo == "exoneracao":
            # Exoneração exige as duas provas: nenhum marcador de chefia no ato,
            # e a exoneração ser explicitamente DO CARGO de AFFC.
            if any(re.search(p, normalizado) for p in PADROES_NAO_E_SAIDA):
                continue
            if not re.search(PADRAO_EXONERACAO_EFETIVA, normalizado):
                continue

        return tipo

    return None


def nome_arquivo(resultado: dict, tipo: str) -> str:
    data = datetime.strptime(resultado["pubDate"], "%d/%m/%Y").strftime("%Y-%m-%d")
    fatia = re.sub(r"[^a-z0-9]+", "-", resultado["urlTitle"].lower())[:70].strip("-")
    return f"{data}_{tipo}_{fatia}.html"


def salvar_ato(resultado: dict, tipo: str, pagina_html: str, texto: str) -> str:
    DIR_ATOS.mkdir(parents=True, exist_ok=True)
    arquivo = DIR_ATOS / nome_arquivo(resultado, tipo)
    url_original = BASE_ATO + resultado["urlTitle"]

    documento = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html_mod.escape(resultado['title'])} — DOU</title>
<style>
 body {{ font-family: Georgia, serif; max-width: 46rem; margin: 2rem auto; padding: 0 1rem;
        line-height: 1.6; color: #111; background: #fff; }}
 header {{ border-bottom: 2px solid #111; padding-bottom: .75rem; margin-bottom: 1.5rem; }}
 h1 {{ font-size: 1.15rem; margin: 0 0 .5rem; }}
 dl {{ display: grid; grid-template-columns: max-content 1fr; gap: .15rem .75rem;
       font-family: system-ui, sans-serif; font-size: .82rem; color: #444; margin: 0; }}
 dt {{ font-weight: 600; }}
 .texto {{ white-space: pre-wrap; }}
 footer {{ margin-top: 2rem; border-top: 1px solid #ccc; padding-top: .75rem;
           font-family: system-ui, sans-serif; font-size: .78rem; color: #555; }}
</style>
</head>
<body>
<header>
<h1>{html_mod.escape(resultado['title'])}</h1>
<dl>
<dt>Tipo</dt><dd>{html_mod.escape(ROTULOS[tipo])}</dd>
<dt>Publicado em</dt><dd>{html_mod.escape(resultado['pubDate'])}</dd>
<dt>Seção</dt><dd>{html_mod.escape(str(resultado.get('pubName', '')))}</dd>
<dt>Edição</dt><dd>{html_mod.escape(str(resultado.get('editionNumber', '')))}</dd>
<dt>Página</dt><dd>{html_mod.escape(str(resultado.get('numberPage', '')))}</dd>
<dt>Órgão</dt><dd>{html_mod.escape(str(resultado.get('hierarchyStr', '')))}</dd>
</dl>
</header>
<div class="texto">{html_mod.escape(texto)}</div>
<footer>
Cópia do ato publicado no Diário Oficial da União, arquivada pelo Observatório
das Evasões — CGU. Original:
<a href="{html_mod.escape(url_original)}">{html_mod.escape(url_original)}</a>
</footer>
</body>
</html>
"""
    arquivo.write_text(documento, encoding="utf-8")
    return arquivo.name


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Busca no DOU as saídas mais recentes de AFFC da CGU."
    )
    parser.add_argument(
        "--meses", type=int, default=12, help="Até quantos meses atrás varrer (padrão: 12)."
    )
    parser.add_argument(
        "--diagnostico",
        action="store_true",
        help="Mostra os candidatos e a classificação, sem gravar JSON nem HTML.",
    )
    args = parser.parse_args()

    encontrados: dict[str, dict] = {}
    hoje = date.today()
    fim = hoje
    janelas = max(1, (args.meses * 30) // DIAS_POR_JANELA)

    print(f"Frase   : {FRASE_BUSCA}")
    print(f"Órgão   : {ORGAO_CGU}")
    print(f"Período : até {args.meses} meses atrás, em janelas de {DIAS_POR_JANELA} dias")
    if args.diagnostico:
        print("Modo    : DIAGNÓSTICO — nada será gravado.")
    print()

    vistos: set[str] = set()

    for numero in range(janelas):
        if len(encontrados) == len(TIPOS):
            break

        inicio = fim - timedelta(days=DIAS_POR_JANELA - 1)
        resultados = buscar_janela(inicio, fim)
        candidatos = [r for r in resultados if e_da_cgu(r)]
        print(
            f"[{numero + 1}/{janelas}] {inicio:%d/%m/%Y}–{fim:%d/%m/%Y}: "
            f"{len(resultados)} atos, {len(candidatos)} da CGU"
        )

        for resultado in candidatos:
            chave = resultado.get("urlTitle", "")
            if not chave or chave in vistos:
                continue
            vistos.add(chave)

            faltando = [t for t in TIPOS if t not in encontrados]
            if not faltando:
                break

            pagina = baixar(BASE_ATO + chave, timeout=60)
            if not pagina:
                continue
            texto = extrair_texto(pagina)
            tipo = classificar(texto)
            if tipo is None or tipo in encontrados:
                continue

            registro = {
                "tipo": tipo,
                "rotulo": ROTULOS[tipo],
                "titulo": resultado["title"],
                "dataPublicacao": datetime.strptime(
                    resultado["pubDate"], "%d/%m/%Y"
                ).strftime("%Y-%m-%d"),
                "secao": resultado.get("pubName"),
                "edicao": resultado.get("editionNumber"),
                "pagina": resultado.get("numberPage"),
                "orgao": resultado.get("hierarchyStr"),
                "urlDou": BASE_ATO + chave,
                "arquivo": None,
                "trecho": texto[:400],
            }

            if not args.diagnostico:
                registro["arquivo"] = salvar_ato(resultado, tipo, pagina, texto)

            encontrados[tipo] = registro
            print(f"    -> {ROTULOS[tipo]}: {resultado['pubDate']} | {resultado['title'][:60]}")

        fim = inicio - timedelta(days=1)

    print()
    if not encontrados:
        print("Nenhuma saída de AFFC encontrada no período. Nada foi gravado.")
        return 1

    faltando = [t for t in TIPOS if t not in encontrados]
    if faltando:
        print(f"Sem ato recente para: {', '.join(ROTULOS[t] for t in faltando)}")

    mais_recente = max(encontrados.values(), key=lambda r: r["dataPublicacao"])
    print(f"Mais recente: {mais_recente['rotulo']} em {mais_recente['dataPublicacao']}")

    if args.diagnostico:
        print()
        print("=== classificação (confira antes de publicar) ===")
        for tipo in TIPOS:
            registro = encontrados.get(tipo)
            if not registro:
                print(f"  {ROTULOS[tipo]}: (nenhum)")
                continue
            print(f"  {ROTULOS[tipo]} — {registro['dataPublicacao']}")
            print(f"    {registro['trecho'][:260]}")
        return 0

    ARQUIVO_JSON.parent.mkdir(parents=True, exist_ok=True)
    saida = {
        "geradoEm": datetime.now().astimezone().isoformat(timespec="seconds"),
        "fonte": "Diário Oficial da União — in.gov.br",
        "cargo": "Auditor Federal de Finanças e Controle",
        "orgao": "Controladoria-Geral da União",
        "dataMaisRecente": mais_recente["dataPublicacao"],
        "tipoMaisRecente": mais_recente["tipo"],
        "eventos": [encontrados[t] for t in TIPOS if t in encontrados],
    }
    ARQUIVO_JSON.write_text(
        json.dumps(saida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"JSON gravado: {ARQUIVO_JSON.relative_to(RAIZ)}")
    print(f"Atos salvos : {DIR_ATOS.relative_to(RAIZ)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
