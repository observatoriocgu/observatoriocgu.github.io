# Observatório CGU (fork do Observatório SEF-MG)
Site estático (GitHub Pages) que monitora a evasão de aprovados em concurso.
Versão original: Auditores Fiscais SEF-MG. Esta versão: concurso CGU 2021 (FGV),
cargos AFFC (áreas: Auditoria e Fiscalização, TI, Contabilidade Pública e
Finanças, Correição e Combate à Corrupção) e TFFC (nível médio).

## Regras de adaptação
- Matrícula: MASP (MG) vira SIAPE (federal)
- Diário oficial: DOE-MG vira DOU
- Fonte da lista de aprovados: Resultado Final FGV de 13/06/2022
  (https://conhecimento.fgv.br/concursos/concursocgu21)
- Fonte mensal de servidores: Portal da Transparência do Governo Federal
- Homologação do concurso: 14/06/2022 (início da observação)
- Colunas específicas de MG (UNIDADE, VAGA FA, CDCOMI, DESCCOMI) devem ser
  removidas ou substituídas por equivalentes federais (unidade CGU/lotação UF)

## Regras de trabalho
- NUNCA alterar mais de uma fase por vez (ver PLANO.md)
- Sempre rodar npm run build em evasao/ antes de encerrar uma tarefa
- Não tocar em evasao/dist/ manualmente (é gerado pelo build)
- Não inventar dados: onde não houver dado real da CGU, usar placeholder
  claramente marcado como EXEMPLO