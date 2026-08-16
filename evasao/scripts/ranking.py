#!/usr/bin/env python3
"""
Camada de acesso ao rankingdosconcursos.com.br — o DESTINO de quem já saiu.

Este módulo NÃO é executável: é a biblioteca que `enriquecer_destinos_ranking.py`
usa. A ordem importa e é sempre a mesma (é o que o usuário pediu, e é o que
mantém o observatório honesto):

    JÁ SABENDO QUE A PESSOA SAIU (SIAPE/DOU)  ->  procurar no ranking PARA ONDE

Nunca o contrário. Passar em outro concurso não é sair da CGU: há Auditor com
seis aprovações que continua na CGU. O ranking só é consultado para quem já tem
saída registrada, e só serve para responder "para onde", nunca "saiu?".

COMO O SITE SE COMPORTA (levantado em 15/08/2026, não há documentação)
---------------------------------------------------------------------
  - busca por nome: GET /index.php?tab=nome&nome_candidato=FULANO&pesquisar=Pesquisar
  - sem autenticação, sem token. O widget do Cloudflare Turnstile existe no HTML
    mas está COMENTADO — se um dia for reativado, esta biblioteca para de
    funcionar de uma vez, e não silenciosamente: a tabela some do HTML.
  - a resposta é a home inteira (2,9 MB) com a tabela de resultados embutida.
    Com `Accept-Encoding: gzip` são 218 KB. Daí `aceitar_gzip=True` no download:
    sem isso, uma varredura de 160 nomes baixaria 480 MB.
  - a busca é por PREFIXO, e é acento-insensível: "MARIANA DE SOUZA LIMA"
    devolve também "Mariana de Souza Lima Velasco", que é OUTRA PESSOA. É por
    isso que `linhas_da_pessoa` exige igualdade EXATA do nome normalizado —
    é a mesma armadilha de homônimo por prefixo que o `dou.cita_nome` trata.
  - a tabela traz uma linha por (candidato x concurso x cargo), com nota e
    colocação, e uma coluna "Fez tb:" que repete os outros concursos da própria
    pessoa. Ela PARECE redundante e não é: às vezes traz a marca que a linha
    própria perdeu, e às vezes cita concurso que a tabela nem lista como linha.
    Ver `aprovacoes_da_pessoa`.

A LEGENDA DE CORES, E ONDE ELA ENXERGA
--------------------------------------
O site marca cada aprovação com um quadradinho: verde `#22c55e` = "Dentro das
Vagas", azul `#3b82f6` = "Nomeado". O azul afirma um FATO — a pessoa foi nomeada
naquele concurso —, e é por isso que ele DESEMPATA desde a D26, enquanto todos
os outros critérios continuam proibidos.

O que ele não afirma é o contrário. **A ausência de marca não quer dizer que a
pessoa não foi nomeada**: o site não mantém a lista de nomeados de todo concurso.
Medido nas 155 fichas baixadas em 16/08/2026, o TCU tem **zero marca azul em 38
linhas** e a própria CGU **zero em 84** — e 20 pessoas do gabarito têm nomeação
no TCU comprovada pelo DOU, nenhuma com marca. Daí a guarda `ORGAOS_CEGOS_A_TAG`,
que é o que separa um desempate de 94,5% de um de 75,7%.

O QUE O RANKING SABE E O QUE ELE NÃO SABE
-----------------------------------------
Ele sabe em que concursos a pessoa passou, e às vezes em qual ela foi nomeada.
Ele NUNCA sabe qual ela foi EXERCER. Fora a marca azul, nenhum critério de
escolha sobreviveu à medição:

    melhor colocação        24 de 62   38,7%
    colocação até 100º       4 de 15   26,7%
    ano igual ao da saída    0 de  1        —

Conclusão, e é ela que define esta biblioteca: **publica-se quando sobra um
candidato só, ou quando a marca azul aponta um e nenhum órgão cego a ela está no
caminho**. O resto vai para a pauta humana, com a lista de candidatos e o link
da consulta. Ver `destino_da_pessoa`.
"""

from __future__ import annotations

import html as html_mod
import re
import time
import urllib.parse
from pathlib import Path

import dou
from dou import normalizar

RAIZ = Path(__file__).resolve().parent.parent
DIR_CACHE = RAIZ / "data" / "cache_ranking"

BASE = "https://www.rankingdosconcursos.com.br/index.php"

# Resposta de busca por nome NÃO é imutável: o site ganha concursos novos toda
# semana. Cache curto — serve para não repetir a mesma consulta dentro de uma
# execução ou de um dia de desenvolvimento, não para congelar o resultado.
# Quem decide a cadência de verdade é `DIAS_PARA_RECONSULTAR`, no enriquecedor.
VALIDADE_HORAS = 12.0

# O site tem limitador de ritmo próprio, e ele NÃO responde 429: devolve uma
# página "Muitas Consultas" com status 200 (ver `pagina_respondeu_a_busca`).
# Uma requisição por segundo — o ritmo do in.gov.br — o dispara. Três segundos
# passaram a varredura inteira de 43 nomes sem um único bloqueio.
PAUSA_SEGUNDOS = 3.0

# Quando o bloqueio aparece assim mesmo, esperar e insistir. A espera dobra a
# cada tentativa (20s, 40s), porque insistir no mesmo ritmo é o que provocou o
# bloqueio.
TENTATIVAS = 3
ESPERA_APOS_BLOQUEIO_SEGUNDOS = 20.0

# Cores da legenda do site.
COR_DENTRO_DAS_VAGAS = "#22c55e"
COR_NOMEADO = "#3b82f6"

# O concurso de ENTRADA. É a âncora que prova que a ficha é de um Auditor da CGU
# — e, obviamente, nunca é destino de quem saiu da CGU.
ORGAO_CGU = "Controladoria-Geral da União"


# ------------------------------------------------------------------ a consulta

def url_da_consulta(nome: str) -> str:
    """A URL que a pessoa pode abrir no navegador para conferir o que lemos."""
    return BASE + "?" + urllib.parse.urlencode(
        {"tab": "nome", "nome_candidato": nome, "pesquisar": "Pesquisar"}
    )


def _texto(celula: str) -> str:
    return " ".join(html_mod.unescape(re.sub(r"<[^>]+>", " ", celula)).split())


# Cada item da coluna "Fez tb:" é "[quadradinho?] 43º <rótulo do concurso> <link>",
# separado dos outros por <br>. O número é a colocação, e sai daqui.
_ITEM_FEZ_TAMBEM = re.compile(r"^(\d+)\s*[ºo°]?\s*(.+)$")


def _fez_tambem(celula: str) -> list[dict]:
    """
    Os outros concursos DA MESMA PESSOA, como a última coluna os lista.

    Não é enfeite, e por muito tempo pareceu ser: **esta coluna carrega marcas
    que a célula da própria linha não tem**. O site rende o quadradinho nos dois
    lugares e às vezes só num deles — medido nas fichas baixadas, três pessoas
    têm a marca azul SÓ aqui, e uma delas é o caso que motivou esta leitura
    (ROSICLEIDE RAMOS ALVES, "Nomeado" no TCM SP, invisível na linha do TCM SP).

    Ela também cita, de vez em quando, concurso que a tabela NÃO lista como
    linha — visto com `RFB` e `Camara dos Deputados`. Ler daqui é o que impede
    chamar de "candidato único" quem tem um segundo concurso escondido.
    """
    itens = []
    for pedaco in re.split(r"<br\s*/?>", celula):
        texto = _texto(pedaco)
        achado = _ITEM_FEZ_TAMBEM.match(texto)
        if not achado:
            continue
        marcas = re.findall(r"background-color:\s*(#[0-9a-fA-F]{6})", pedaco)
        itens.append({
            "concurso": achado.group(2),
            "colocacao": achado.group(1),
            "nomeado": COR_NOMEADO in marcas,
            "dentro_das_vagas": COR_DENTRO_DAS_VAGAS in marcas,
        })
    return itens


def analisar(pagina: str) -> list[dict]:
    """
    As linhas da tabela de resultados. Lista vazia quando não há tabela.

    Lista vazia é resposta legítima (ninguém com aquele nome no site) e também é
    o que aparece se o site mudar de forma. Quem chama não consegue distinguir os
    dois casos — e não precisa: nos dois, o observatório não afirma nada. O que
    protege contra a mudança silenciosa de layout é `testar_ranking.py`.

    Cada linha traz também `tambem`, a leitura da coluna "Fez tb:" — ver
    `_fez_tambem` para o porquê de ela não poder ser ignorada.
    """
    corpo = re.search(r"<tbody>(.*?)</tbody>", pagina, re.S)
    if not corpo:
        return []

    linhas = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", corpo.group(1), re.S):
        celulas = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(celulas) < 7:
            continue
        marcas = re.findall(r"background-color:\s*(#[0-9a-fA-F]{6})", celulas[0])
        linhas.append({
            "nome": _texto(celulas[1]),
            "concurso": _texto(celulas[2]),
            "cargo": _texto(celulas[3]),
            "nota": _texto(celulas[4]),
            "colocacao": _texto(celulas[5]),
            "nomeado": COR_NOMEADO in marcas,
            "dentro_das_vagas": COR_DENTRO_DAS_VAGAS in marcas,
            "tambem": _fez_tambem(celulas[6]),
        })
    return linhas


def pagina_respondeu_a_busca(pagina: str, nome: str) -> bool:
    """
    True se a página é mesmo o resultado da busca por `nome`.

    ISTO NÃO É PARANOIA — é o defeito mais caro que este crawler teve. O site
    responde à consulta rápida demais com uma página de 1,3 KB intitulada
    "Muitas Consultas", **e com status HTTP 200**. Ela não tem tabela, então
    `analisar` devolvia lista vazia, e a lista vazia era lida como "esta pessoa
    não está no ranking". Na primeira varredura de 43 nomes, isso gravou
    SEM_FICHA para gente que tem ficha — e, pior, com data de consulta de hoje,
    o que adiaria a correção por 30 dias.

    A prova de que a busca rodou é o próprio formulário devolver o que foi
    pedido: o `value` do campo `nome_candidato` ecoa o nome consultado. Sem
    esse eco, o que veio não é resposta de busca, seja lá o que for.
    """
    achado = re.search(r'name="nome_candidato"\s+value="([^"]*)"', pagina)
    return bool(achado) and normalizar(achado.group(1)) == normalizar(nome)


def buscar_por_nome(nome: str, usar_cache: bool = True) -> list[dict] | None:
    """
    Todas as linhas que a busca devolve para `nome` — INCLUSIVE de homônimos.

    Devolve `None` quando não foi possível obter uma resposta confiável, e é
    obrigatório distinguir isso de `[]`: lista vazia é "não há ninguém com esse
    nome no site", `None` é "não sabemos". Quem chama não pode gravar a segunda
    como se fosse a primeira.
    """
    url = url_da_consulta(nome)
    espera = ESPERA_APOS_BLOQUEIO_SEGUNDOS

    for tentativa in range(TENTATIVAS):
        pagina = dou.baixar(
            url,
            usar_cache=usar_cache,
            validade_horas=VALIDADE_HORAS,
            dir_cache=DIR_CACHE,
            aceitar_gzip=True,
            pausa_segundos=PAUSA_SEGUNDOS,
        )
        if pagina and pagina_respondeu_a_busca(pagina, nome):
            return analisar(pagina)

        # A página ruim pode ter sido gravada no cache por uma execução
        # anterior a esta guarda — ou por esta mesma, já que `dou.baixar`
        # cacheia toda resposta não-vazia. Apagá-la é o que permite a próxima
        # tentativa ir à rede em vez de reler o mesmo erro.
        caminho = dou._caminho_cache(url, DIR_CACHE)
        caminho.unlink(missing_ok=True)

        if tentativa < TENTATIVAS - 1:
            time.sleep(espera)
            espera *= 2

    return None


def linhas_da_pessoa(nome: str, linhas: list[dict]) -> list[dict]:
    """
    Só as linhas cujo nome é EXATAMENTE o da pessoa, normalizado.

    A guarda não é teórica. A busca do site casa por prefixo: consultar
    "MARIANA DE SOUZA LIMA" traz junto "Mariana de Souza Lima Velasco". Sem este
    filtro, as aprovações de uma pessoa viram destino de outra. Medido nos 161
    nomes da primeira varredura: 2 fichas vinham contaminadas assim.
    """
    alvo = normalizar(nome)
    return [linha for linha in linhas if normalizar(linha["nome"]) == alvo]


def aprovacoes_da_pessoa(nome: str, linhas: list[dict]) -> list[dict]:
    """
    As aprovações da pessoa, uma por concurso, unindo as DUAS leituras da página.

    O site conta a mesma coisa em dois lugares — a linha da tabela e a coluna
    "Fez tb:" das outras linhas da pessoa — e conta diferente:

      - a MARCA às vezes só aparece num dos dois. ROSICLEIDE RAMOS ALVES tem
        "Nomeado" no TCM SP visível apenas no "Fez tb:"; a linha do TCM SP vem
        sem marca nenhuma. Por isso a marca é a UNIÃO das duas, nunca a da
        linha sozinha.
      - o CONCURSO às vezes só aparece num dos dois. O "Fez tb:" de ANDRE
        VINICIUS NUNES SILVA cita `91º Camara dos Deputados` e a tabela não
        traz essa linha. Ler daqui é o que impede chamar de "candidato único"
        quem tem um segundo concurso que a tabela escondeu.

    Uma aprovação por rótulo INTEIRO, edição incluída — `TCE PE 17` e `TCE PE 25`
    seguem separados. São o mesmo órgão, e viram um candidato só lá na frente,
    mas cada um tem a SUA edição, e é por ela que a janela de anos decide. Fundir
    aqui pelo `rotulo_base` faria as duas edições herdarem o ano de uma delas.
    """
    minhas = linhas_da_pessoa(nome, linhas)
    por_rotulo: dict[str, dict] = {}

    def juntar(concurso: str, colocacao: str, nomeado: bool, dentro: bool) -> None:
        # A mesma aprovação é escrita `SEFAZ AM 22` na linha e `SEFAZ/AM/22` no
        # "Fez tb:". Normalizar a barra é o que faz as duas caírem na mesma chave.
        chave = normalizar(concurso.replace("/", " "))
        if not chave:
            return
        atual = por_rotulo.setdefault(chave, {
            "concurso": concurso, "colocacao": colocacao,
            "nomeado": False, "dentro_das_vagas": False,
        })
        atual["nomeado"] = atual["nomeado"] or nomeado
        atual["dentro_das_vagas"] = atual["dentro_das_vagas"] or dentro

    # As linhas da tabela primeiro: é delas que sai a grafia do rótulo que vai
    # para o relatório, e a do "Fez tb:" usa barra ("SEFAZ/AM/22").
    for linha in minhas:
        juntar(linha["concurso"], linha["colocacao"],
               linha["nomeado"], linha["dentro_das_vagas"])
    for linha in minhas:
        for item in linha.get("tambem", ()):
            juntar(item["concurso"], item["colocacao"],
                   item["nomeado"], item["dentro_das_vagas"])

    return list(por_rotulo.values())


# -------------------------------------------------- o catálogo de órgãos (D24)
#
# O problema que este catálogo existe para impedir: o mesmo órgão entrando duas
# vezes na tabela de destinos com grafias diferentes ("TCU" e "Tribunal de
# Contas da União" como se fossem dois lugares). Por isso o rótulo do site NUNCA
# vai para a tela: ele é traduzido para um nome canônico, e nome canônico que
# também vem do DOU é escrito EXATAMENTE como o DOU escreve — senão o mesmo
# defeito volta pela outra ponta.
#
# Rótulo sem regra não vira destino: `canonico` devolve "" e o enriquecedor
# registra o rótulo na pauta, para alguém acrescentar aqui. Preferir não afirmar
# a inventar um nome novo é o que mantém a tabela de destinos fechada.

# Os que o DOU já produz hoje, escritos como ele escreve. Mudar qualquer um
# destes parte a tabela de destinos em dois grupos.
_DO_DOU = {
    "TCU": "Tribunal de Contas da União",
    "TCU TI": "Tribunal de Contas da União",
    "SENADO": "Senado Federal",
    "CAMARA DOS DEPUTADOS": "Câmara dos Deputados",
    "CAMARA DOS DEPUTADOS CONSULTOR": "Câmara dos Deputados",
    # A Receita Federal publica seus atos sob o Ministério da Fazenda, e é assim
    # que os dois destinos vindos do DOU estão gravados. "RFB" tem de cair no
    # mesmo balde, ou a Receita aparece duas vezes.
    "RFB": "Ministério da Fazenda",
    "AGU": "Advocacia-Geral da União",
    # A família TRF fica aqui, e não entre as outras, porque o DOU já produziu
    # "Tribunal Regional Federal da 3ª Região" — o molde tem de gerar
    # exatamente essa forma, ou a mesma corte vira dois destinos.
}

ORGAO_POR_ROTULO = {
    **_DO_DOU,
    "CGU": ORGAO_CGU,
    "BANCO CENTRAL": "Banco Central do Brasil",
    "MPO": "Ministério do Planejamento e Orçamento",
    "MPU": "Ministério Público da União",
    "MINISTERIO DE MINAS E ENERGIA MME": "Ministério de Minas e Energia",
    "STJ": "Superior Tribunal de Justiça",
    "CNMP": "Conselho Nacional do Ministério Público",
    "EMBRAPA": "Empresa Brasileira de Pesquisa Agropecuária (Embrapa)",
    "IPEA": "Instituto de Pesquisa Econômica Aplicada (Ipea)",
    "EPE ENERGETICA": "Empresa de Pesquisa Energética (EPE)",
    "CPRM SERVICO GEOLOGICO DO BRASIL": "Serviço Geológico do Brasil (CPRM)",
    "CFP CONS. FED. PSI.": "Conselho Federal de Psicologia",
    "CRM DF": "Conselho Regional de Medicina do Distrito Federal",
    "DETRAN AP": "Departamento Estadual de Trânsito do Amapá (Detran-AP)",
    "SERPRO": "Serviço Federal de Processamento de Dados (Serpro)",
    "CONAB": "Companhia Nacional de Abastecimento (Conab)",
    "PETROBRAS": "Petróleo Brasileiro S.A. (Petrobras)",
    "TELEBRAS": "Telecomunicações Brasileiras S.A. (Telebras)",
    "EBSERH NACIONAL": "Empresa Brasileira de Serviços Hospitalares (Ebserh)",
    "HEMOBRAS": "Empresa Brasileira de Hemoderivados e Biotecnologia (Hemobrás)",
    "PRODERJ": "Centro de Tecnologia da Informação e Comunicação do Estado do Rio de Janeiro (Proderj)",
    "DPF": "Polícia Federal",
    "PRF": "Polícia Rodoviária Federal",
    "PC DF": "Polícia Civil do Distrito Federal",
    "TC DF": "Tribunal de Contas do Distrito Federal",
    "TJDFT": "Tribunal de Justiça do Distrito Federal e dos Territórios",
    "CG DF": "Controladoria-Geral do Distrito Federal",
    "SEPLAD DF": "Governo do Distrito Federal",
    "PPGG DF": "Governo do Distrito Federal",
    "APO RJ": "Governo do Estado do Rio de Janeiro",
    "CGE RJ": "Governo do Estado do Rio de Janeiro",
    "CGE SC": "Governo do Estado de Santa Catarina",
    "AGE MG": "Governo do Estado de Minas Gerais",
    "PGE PE": "Governo do Estado de Pernambuco",
    "CAGE RS": "Governo do Estado do Rio Grande do Sul",
    "ALESP": "Assembleia Legislativa do Estado de São Paulo",
    "ALEPE": "Assembleia Legislativa do Estado de Pernambuco",
    "TCM SP": "Tribunal de Contas do Município de São Paulo",
    # Fisco/procuradoria municipal: o rótulo do site é "ISS <cidade>" ou a sigla
    # da secretaria. Os dois viram o MESMO nome de prefeitura — "SMF RJ" e
    # "ISS Rio de Janeiro" são a mesma porta.
    "SMF RJ": "Prefeitura do Rio de Janeiro",
    "ISS RIO DE JANEIRO": "Prefeitura do Rio de Janeiro",
    "PGM SP": "Prefeitura de São Paulo",
    "ISS SP": "Prefeitura de São Paulo",
    "ISS ARACAJU": "Prefeitura de Aracaju",
    "ISS BELO HORIZONTE": "Prefeitura de Belo Horizonte",
    "ISS CAMPINAS": "Prefeitura de Campinas",
    "ISS CUIABA": "Prefeitura de Cuiabá",
    "ISS FORTALEZA": "Prefeitura de Fortaleza",
    "ISS GUARULHOS": "Prefeitura de Guarulhos",
    "ISS ITAJAI": "Prefeitura de Itajaí",
    "ISS MANAUS": "Prefeitura de Manaus",
    "ISS MOSSORO": "Prefeitura de Mossoró",
    "ISS OSASCO": "Prefeitura de Osasco",
    "ISS PAULINIA": "Prefeitura de Paulínia",
    "ISS SUZANO": "Prefeitura de Suzano",
    "ISS PORTO ALEGRE": "Prefeitura de Porto Alegre",
    "ISS S.J. RIO PRETO": "Prefeitura de São José do Rio Preto",
    "ISS SANTOS": "Prefeitura de Santos",
    "ISS UBERLANDIA": "Prefeitura de Uberlândia",
    "PGM NITEROI": "Prefeitura de Niterói",
    "CGM JOAO PESSOA": "Prefeitura de João Pessoa",
    "CAMARA SAO ROQUE SP": "Câmara Municipal de São Roque",
    "CAMARA MUNICIPAL MACEIO": "Câmara Municipal de Maceió",
}

# Concursos UNIFICADOS: aprovação real, órgão indefinido. O CNU distribui
# aprovados por dezenas de órgãos e o "TSE Unificado" por TSE e TREs de todo o
# país — o rótulo não diz para onde a pessoa foi.
#
# Eles não são só "ignorados": a presença de um deles torna o caso AMBÍGUO (ver
# `destino_da_pessoa`). Descartar em silêncio seria pior que não saber — o caso
# com "TCU + CNU" pareceria ter candidato único e o TCU iria ao ar sozinho.
ROTULOS_SEM_ORGAO = {"CNU", "TSE UNIFICADO"}

_UF = {
    "AC": "do Acre", "AL": "de Alagoas", "AM": "do Amazonas", "AP": "do Amapá",
    "BA": "da Bahia", "CE": "do Ceará", "DF": "do Distrito Federal",
    "ES": "do Espírito Santo", "GO": "de Goiás", "MA": "do Maranhão",
    "MG": "de Minas Gerais", "MS": "de Mato Grosso do Sul", "MT": "de Mato Grosso",
    "PA": "do Pará", "PB": "da Paraíba", "PE": "de Pernambuco", "PI": "do Piauí",
    "PR": "do Paraná", "RJ": "do Rio de Janeiro", "RN": "do Rio Grande do Norte",
    "RO": "de Rondônia", "RR": "de Roraima", "RS": "do Rio Grande do Sul",
    "SC": "de Santa Catarina", "SE": "de Sergipe", "SP": "de São Paulo",
    "TO": "do Tocantins",
}

# Famílias previsíveis: uma UF nova aparece a cada concurso estadual, e não faz
# sentido esperar alguém acrescentar "TCE RO" à mão para o observatório voltar a
# funcionar. Só valem para siglas conhecidas — "TCE XX" com UF inventada não casa.
_FAMILIAS = (
    (re.compile(r"^TCE ([A-Z]{2})$"), "Tribunal de Contas do Estado {uf}"),
    (re.compile(r"^SEFAZ ([A-Z]{2})$"), "Secretaria de Fazenda {uf}"),
    (re.compile(r"^TJ ([A-Z]{2})$"), "Tribunal de Justiça {uf}"),
    (re.compile(r"^TRE ([A-Z]{2})$"), "Tribunal Regional Eleitoral {uf}"),
)
_TRT = re.compile(r"^TRT (\d{1,2}) [A-Z]{2}$")
# `TRF 5 24` chega aqui como `TRF 5`: o 24 é a edição e sai em `rotulo_base`,
# o 5 é a Região e fica. O molde reproduz a forma que o DOU já usa.
_TRF = re.compile(r"^TRF (\d{1,2})$")

# Sufixos de EDIÇÃO e de NÍVEL, que não fazem parte do nome do órgão:
# "Camara dos Deputados 25 NS" e "Camara dos Deputados" são a mesma casa.
_ANO_NO_FIM = re.compile(r"\s+(?:(?:19|20)\d{2}|\d{2})$")
_NIVEL_NO_FIM = re.compile(r"\s+(?:NS|NM|TEC|APOIO)$")


def rotulo_base(rotulo: str) -> str:
    """
    O rótulo do site sem ano nem nível: `TCE PE 17` e `TCE PE 25` -> `TCE PE`.

    Cuidado embutido: o ano só é cortado no FIM. `TRT 13 PB` guarda o 13, que é
    a Região, não uma edição — cortá-lo transformaria a 13ª e a 6ª Regiões no
    mesmo tribunal.

    A barra vira espaço porque o MESMO concurso é escrito das duas formas no
    mesmo HTML: a linha da tabela diz `SEFAZ AM 22` e a coluna "Fez tb:" diz
    `SEFAZ/AM/22`. Sem isso as duas leituras da mesma aprovação viram dois
    concursos, e um deles cai fora do catálogo.
    """
    base = normalizar(rotulo.replace("/", " "))
    for _ in range(3):  # "SEFAZ RS TEC 18" precisa de duas passadas
        antes = base
        base = _NIVEL_NO_FIM.sub("", _ANO_NO_FIM.sub("", base)).strip()
        if base == antes:
            break
    return base


def ano_do_rotulo(rotulo: str) -> int | None:
    """
    A edição do concurso, quando o rótulo a declara. `None` quando não declara.

    `None` é o caso MAIS COMUM entre os destinos reais (TCU, Senado e Câmara
    aparecem sem ano), então tratar ausência de ano como motivo de descarte
    derrubaria quase todo o sinal — foi medido: exigir ano conhecido leva o
    acerto a 0 de 4.
    """
    texto = normalizar(rotulo.replace("/", " "))
    achado = re.search(r"\b(?:19|20)\d{2}\b", texto)
    if achado:
        return int(achado.group(0))
    achado = re.search(r"\b(\d{2})\b(?:\s+(?:NS|NM|TEC|APOIO))?$", texto)
    if achado and 10 <= int(achado.group(1)) <= 30:
        return 2000 + int(achado.group(1))
    return None


def canonico(rotulo: str) -> str | None:
    """
    O nome canônico do órgão de um rótulo do site.

    Três respostas, e elas são diferentes:
      - o nome do órgão  — dá para publicar
      - `None`           — concurso unificado: aprovação real, órgão indefinido
      - `""`             — rótulo sem regra: o catálogo não conhece este concurso
    """
    base = rotulo_base(rotulo)
    if not base:
        return ""
    if base in ROTULOS_SEM_ORGAO:
        return None
    if base in ORGAO_POR_ROTULO:
        return ORGAO_POR_ROTULO[base]

    for padrao, molde in _FAMILIAS:
        achado = padrao.match(base)
        if achado and achado.group(1) in _UF:
            return molde.format(uf=_UF[achado.group(1)])

    achado = _TRT.match(base)
    if achado:
        return f"Tribunal Regional do Trabalho da {int(achado.group(1))}ª Região"

    achado = _TRF.match(base)
    if achado:
        return f"Tribunal Regional Federal da {int(achado.group(1))}ª Região"

    return ""


# --------------------------------------------------------------- a decisão
#
# JANELA DE ANOS, e ela só olha PARA A FRENTE. Um concurso cuja edição é
# POSTERIOR à saída não pode ter motivado a saída — isso é lógica, não
# estatística, e continua valendo (caso real: uma Câmara municipal de 2026
# aparecendo como destino de quem saiu em 11/2025).
#
# O LADO DE TRÁS FOI REMOVIDO em 16/08/2026 (D26). Ele descartava concurso mais
# velho que `saída - 3`, na suposição de que aprovação antiga já teria sido
# exercida. A suposição é falsa: a nomeação sai anos depois da homologação, e a
# janela estava apagando a resposta CERTA em casos concretos —
#
#     ANDRE LUIZ LIMA DA ROCHA   saída 05/2025, única aprovação SEFAZ RS **18**
#     ROSICLEIDE RAMOS ALVES     saída 05/2024, "Nomeado" no TCM SP **20**
#
# nos dois, o concurso caía fora por ser velho, e a pessoa ia para a pauta como
# "sem candidato". Medido no gabarito de 113 destinos que o DOU conhece, o corte
# custa pouco e some junto com a regra nova: sem a janela de trás são 45
# publicados e 43 certos, contra 45 e 44 com ela; com a tag azul no jogo os dois
# empatam em 55 publicados e 52 certos.
ANOS_DE_FOLGA_ANTES: int | None = None

# ONDE A TAG AZUL É CEGA — e é isto que a torna utilizável (D26).
#
# O site não anota nomeação de todo concurso. Medido nas 155 fichas baixadas:
# TCU tem **0 marca azul em 38 linhas** e a própria CGU **0 em 84**, enquanto
# SEFAZ e ISS aparecem marcados com frequência. Ou seja, a AUSÊNCIA de marca no
# TCU não diz nada — o site simplesmente não mantém aquela lista.
#
# A consequência é exata, e foi medida: usando a tag como desempate solta, os
# erros contra o gabarito são TODOS de gente que foi para o TCU ou para o
# Senado e tinha marca azul num concurso estadual antigo. Nenhum erro com
# destino estadual ou municipal. Logo, quando um destes órgãos está entre os
# candidatos SEM marca, a tag não está discriminando nada e não pode decidir.
#
#     tag solta                 69 publicados, 53 certos  (76,8%)
#     tag com esta guarda       53 publicados, 50 certos  (94,3%)
#     sem tag nenhuma (antes)   48 publicados, 46 certos  (95,8%), e metade da
#                                                          cobertura
#
# O preço é conhecido e aceito: quem tem TCU, Senado ou Câmara na ficha continua
# indo para a pauta humana mesmo com marca azul em outro lugar. Os dois casos
# são exemplares — e nos dois a colocação no órgão cego é boa demais para a
# máquina decidir contra ela:
#
#     ALAOR ANTONIO RODRIGUES VILELA JUNIOR   10º Câmara Consultor, azul na SEFAZ AM (92º)
#     DANIEL LIMA OLIVEIRA                     4º Câmara,           azul na SEFAZ RN (135º)
ORGAOS_CEGOS_A_TAG = frozenset({
    "Tribunal de Contas da União",
    "Senado Federal",
    "Câmara dos Deputados",
})

# As decisões que viram destino em tela. Existe como constante para que
# acrescentar uma terceira não dependa de alguém achar os quatro lugares do
# enriquecedor que comparavam com a string "UNICO" — foi o que aconteceu quando
# `UNICO_NOMEADO` entrou (D26).
DECISOES_QUE_PUBLICAM = frozenset({"UNICO", "UNICO_NOMEADO"})

# O pseudo-concurso de quem já estava na CGU antes do primeiro concurso
# monitorado (D9). Espelha `painel.ID_CONCURSO_VETERANO`.
ID_CONCURSO_VETERANO = "VETERANO"


def exige_ancora(concurso: str) -> bool:
    """
    A âncora (ver `destino_da_pessoa`) só é exigível de quem PODERIA tê-la.

    O ranking lista concursos, e o único concurso da CGU que ele conhece é o de
    2022. Quem entrou antes dele — `VETERANO` — nunca prestou concurso que o
    site cubra, então a ficha de um veterano JAMAIS terá a linha da CGU. Exigir
    a âncora dele não filtra ficha incompleta: exclui a categoria inteira, para
    sempre, por uma condição que ele não tem como satisfazer.

    Isso não é teoria — foi o defeito que a primeira versão desta regra teve. Um
    veterano com vacância em 08/2026 e uma única aprovação no site (TCU, 8º)
    ficava fora do painel, e o motivo era só este.

    Medido no gabarito, e é o que sustenta a distinção:

        CGU-2021 COM âncora     45 publicados, 43 certos   95,6%
        CGU-2021 SEM âncora      2 publicados,  0 certos    0,0%   <- filtra bem
        VETERANO  (sem âncora)   2 publicados,  2 certos  100,0%   <- e os 5 do
                                                                     gabarito são
                                                                     todos assim
    A ausência da âncora é informativa para quem é do concurso — ali ela indica
    ficha incompleta, e os 2 erros que ela corta são exatamente disso. Para o
    veterano ela não informa nada, porque é o estado esperado.
    """
    return (concurso or "").strip().upper() != ID_CONCURSO_VETERANO


def destino_da_pessoa(
    nome: str,
    mes_saida: str,
    linhas: list[dict],
    concurso: str = "",
) -> dict:
    """
    O destino que o ranking sustenta para uma saída — ou a razão de não haver um.

    `linhas` é o resultado cru da busca, com homônimos e tudo: o recorte por nome
    acontece aqui dentro, para que nenhum chamador possa esquecê-lo.

    Devolve sempre um dicionário com `decisao`:
      SEM_FICHA       ninguém com esse nome exato no site
      SEM_CANDIDATO   a pessoa está lá, mas sem nenhum outro concurso
      UNICO           sobrou um órgão só  -> este é o destino, e vai à tela
      UNICO_NOMEADO   sobrou mais de um, mas a marca azul "Nomeado" aponta um só
                      e nenhum dos outros é órgão cego a ela -> vai à tela (D26)
      AMBIGUO         sobrou mais de um, ou há concurso unificado no meio
      SEM_CATALOGO    todo candidato tem rótulo que o catálogo não conhece
      SEM_ANCORA_CGU  há candidato, mas a ficha não tem o concurso da CGU —
                      e esta pessoa é de um concurso que o site cobre, então a
                      falta significa alguma coisa (ver `exige_ancora`)

    `UNICO` e `UNICO_NOMEADO` publicam, e são guardados separados de propósito:
    o primeiro é o caso em que não havia escolha a fazer, o segundo é o caso em
    que a marca do site desempatou. Quem for curar sabe olhar o segundo primeiro.

    A régua vem da medição contra os 113 destinos que o DOU já conhece:

      só candidato único (a regra até a D25)  48 publicados, 46 certos  (95,8%)
      + a marca azul com guarda (D26)         53 publicados, 50 certos  (94,3%)

    A segunda linha é a atual. Ela troca 1,5 ponto de precisão pelo DOBRO da
    cobertura sobre quem segue sem destino: 9 saídas resolvidas viram 18, de 37.
    Só a marca COM a guarda de `ORGAOS_CEGOS_A_TAG` faz essa troca — a marca
    solta desaba para 76,8%.

    E a queda de 95,8% para 94,3% NÃO é da marca. Aberto por decisão, no mesmo
    gabarito: `UNICO` publica 48 e acerta 45; `UNICO_NOMEADO` publica 5 e acerta
    5. Os três erros são todos do caminho antigo — o que mudou nele foi a saída
    da janela de anos para trás, que custou um acerto e devolveu dois casos que
    ela apagava. Cinco acertos em cinco é amostra pequena demais para virar
    número de propaganda; o que ela sustenta é que a marca com guarda não é a
    parte frágil desta regra.

    E SÓ DECIDE QUANDO A MARCA É UMA SÓ. Escolher entre vários marcados foi
    medido e reprovou: publicaria 5 a mais e erraria 3 deles, derrubando o
    conjunto para 91,4%. Os dois erros são do mesmo tipo, e é um tipo que não
    tem conserto por heurística — NAZLI SETTON FILIPPINI e JAIDIR ALVES COSTA
    DOS SANTOS foram os dois para a Receita, e nos dois a RFB ESTAVA marcada de
    azul, ao lado de outra marca que o desempate por colocação preferiu (ISS
    Guarulhos 1º sobre RFB 6º; Senado 64º sobre RFB 87º). Com duas marcas, o
    site está dizendo que a pessoa foi nomeada nos dois lugares, e qual ela foi
    exercer é justamente o que ele não sabe.

    A ÂNCORA é a linha do concurso da própria CGU na ficha. Sem ela, o que se tem
    é um nome batendo com um nome num site que nem sabe que essa pessoa foi da
    CGU; com ela, o site registra um Auditor da CGU com aquele nome exato — é a
    prova de que a ficha é desta pessoa, e sinal de que a lista de concursos dela
    ali está mais completa. Os dois erros que ela remove são exatamente disto:
    fichas que não conheciam o concurso para o qual a pessoa de fato foi.

    Mas ela SÓ É EXIGIDA DE QUEM PODERIA TÊ-LA (`exige_ancora`, e é lá que está
    a medição): veterano entrou antes do concurso que o site cobre e nunca vai
    ter aquela linha. A regra final publica 47 e acerta 45 — mais que os 45 e 43
    da âncora indiscriminada, e muito mais que os 49 e 45 sem âncora nenhuma.

    O DESEMPATE ENTRE CANDIDATOS MÚLTIPLOS existe desde a D26, e é UM SÓ: a marca
    azul "Nomeado" do site, com a guarda de `ORGAOS_CEGOS_A_TAG`. Os desempates
    por colocação, por ano e por "melhor classificado" continuam reprovados
    (27-39%) e continuam fora. A marca é diferente deles porque não é heurística:
    ela afirma que a pessoa FOI NOMEADA naquele concurso. O que ela não sabe é o
    que a guarda cobre — que o silêncio dela sobre o TCU não significa nada.
    """
    resposta = {
        "decisao": "SEM_FICHA",
        "orgao": "",
        "candidatos": [],
        # Os candidatos que carregam a tag azul "Nomeado". Desde a D26 eles
        # DECIDEM, quando a guarda deixa; e vão para a pauta sempre, para que
        # quem for curar veja de imediato o que o site marcou.
        "marcados_nomeado": [],
        "rotulos_sem_catalogo": [],
        "url": url_da_consulta(nome),
    }

    aprovacoes = aprovacoes_da_pessoa(nome, linhas)
    if not aprovacoes:
        return resposta

    # `concurso` vazio cai no caminho ESTRITO de propósito: quem chama sem
    # dizer de quem se trata recebe a regra mais conservadora, não a mais frouxa.
    ancora_necessaria = exige_ancora(concurso)
    tem_ancora = any(canonico(a["concurso"]) == ORGAO_CGU for a in aprovacoes)
    ancora_ok = tem_ancora or not ancora_necessaria

    ano_saida = int(mes_saida[:4]) if len(mes_saida) >= 4 and mes_saida[:4].isdigit() else None

    candidatos: dict[str, list[dict]] = {}
    tem_unificado = False
    sem_catalogo: list[str] = []

    for aprovacao in aprovacoes:
        orgao = canonico(aprovacao["concurso"])
        if orgao == ORGAO_CGU:
            continue  # o concurso de entrada não é destino de saída

        ano = ano_do_rotulo(aprovacao["concurso"])
        if ano is not None and ano_saida is not None:
            if ano > ano_saida:
                continue  # edição posterior à saída não pode tê-la motivado
            if ANOS_DE_FOLGA_ANTES is not None and ano < ano_saida - ANOS_DE_FOLGA_ANTES:
                continue

        if orgao is None:
            tem_unificado = True
        elif orgao == "":
            sem_catalogo.append(aprovacao["concurso"])
        else:
            candidatos.setdefault(orgao, []).append(aprovacao)

    marcados = sorted(
        orgao for orgao, aa in candidatos.items() if any(a["nomeado"] for a in aa)
    )
    resposta["candidatos"] = sorted(candidatos)
    resposta["marcados_nomeado"] = marcados
    resposta["rotulos_sem_catalogo"] = sorted(set(sem_catalogo))

    if not candidatos and not tem_unificado:
        resposta["decisao"] = "SEM_CATALOGO" if sem_catalogo else "SEM_CANDIDATO"
        return resposta

    # Um rótulo fora do catálogo pode ser o destino verdadeiro; um concurso
    # unificado pode esconder o órgão de chegada. Nos dois casos há candidato
    # que não sabemos nomear, então não há candidato único — só parece haver.
    if (len(candidatos) == 1 and not tem_unificado and not sem_catalogo
            and ancora_ok):
        resposta["decisao"] = "UNICO"
        resposta["orgao"] = resposta["candidatos"][0]
        return resposta

    # A MARCA AZUL DESEMPATA (D26) — nas condições em que ela enxerga.
    #
    # Ela é cega em `ORGAOS_CEGOS_A_TAG`: se um deles está entre os candidatos e
    # NÃO está marcado, a falta de marca é do site, não da pessoa, e a marca em
    # outro lugar não a exclui. Também não se desempata quando há concurso
    # unificado ou rótulo fora do catálogo no meio: ali existe candidato que
    # sequer sabemos nomear, e "sobrou um marcado" seria ilusão.
    #
    # E é UMA marca só. Duas marcas não são um empate a desempatar: são o site
    # dizendo que a pessoa foi nomeada nos dois lugares. Escolher entre elas foi
    # medido e reprovou (ver o docstring) — vai para a pauta, com as duas à
    # vista em `marcados_nomeado`.
    if (len(marcados) == 1 and ancora_ok and not tem_unificado and not sem_catalogo
            and not (set(candidatos) - set(marcados)) & ORGAOS_CEGOS_A_TAG):
        resposta["decisao"] = "UNICO_NOMEADO"
        resposta["orgao"] = marcados[0]
        return resposta

    # Sem a ÂNCORA — e só para quem poderia tê-la —, o que sobrou não é candidato
    # único: é candidato único numa ficha que talvez nem seja a desta pessoa, e
    # que comprovadamente costuma estar incompleta. Marcar assim (e não como
    # "sem candidato") é o que manda o caso para a pauta com a lista intacta.
    if ancora_necessaria and not tem_ancora and candidatos:
        resposta["decisao"] = "SEM_ANCORA_CGU"
        return resposta

    resposta["decisao"] = "AMBIGUO"
    return resposta
