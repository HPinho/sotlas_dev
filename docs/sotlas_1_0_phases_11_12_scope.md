# Sotlas 1.0 - Fases 11 e 12

Este documento fecha os contratos 1.0 suportados para Causality e
Counterfactuals. As formas listadas como futuras permanecem fora do contrato e
falham fechadas quando nao possuem evidencia suficiente.

## Fase 11 - Causality

**Status 1.0: 100% do contrato delimitado.**

- `explain_source_call_causality` encontra uma cadeia de chamadas verificada,
  com escolha deterministica de caminho e localizacao por linha e coluna.
- Cada argumento preserva expressao local, binding, parametro de destino e
  origem causal propagada desde os parametros da funcao inicial.
- A expressao causal substitui parametros ao longo da cadeia, por exemplo
  `decode(input + 2)` seguido de `parse(raw * 3)` produz origem `(input + 2) * 3`.
- `render_source_call_causality_mermaid` expoe um grafo deterministico para
  visualizacao e integracao com ferramentas de editor.
- `explain_flow_causality` e `explain_sir_flow_causality` continuam limitados
  aos grafos canonicos e preservam funcao, parametro, tipo e efeitos por passo.

Aliases locais imutaveis em sequencia linear sao resolvidos. Mutacao e fluxo de
controle arbitrario nao recebem provenance especulativa; o binding local fica
explicito. Integracao de interface LSP, refatoracoes e rastreamento de heap
ficam para versoes futuras.

## Fase 12 - Counterfactuals

**Status 1.0: 100% do contrato delimitado.**

- A indisponibilidade de uma stage propaga para todos os consumidores
  transitivos; stages independentes permanecem identificadas.
- Opcoes de recuperacao usam planos Flow canonicos, rejeitam dependencia da
  stage falha e mostram efeitos adicionados, removidos e proibidos.
- A equivalencia pura unsigned usa polinomios sobre aritmetica modular,
  incluindo comutatividade, associatividade, distributividade, folding e
  identidades seguras. A normalizacao para quando excede 256 monomios.
- `analyze_pure_sir_function_equivalence` aplica a mesma prova a funcoes SIR
  fora de Flow, desde que assinaturas e dominios sejam compativeis.
- `analyze_sir_flow_failure_rollback` analisa o prefixo concluido de um Flow
  sequencial, sua ordem de compensacao e efeitos da stage que falhou.
- Um resultado so afirma `rollback_proven_complete` quando a politica do
  prefixo tem handlers validos e a stage falha nao tem efeitos pendentes.

Analise geral de heap/estado, equivalencia de signed overflow, CFG arbitrario,
Flow paralelo e compensacao parcial da propria stage que falhou ficam fora do
contrato 1.0. O analisador de rollback recusa cronogramas paralelos e mantem
`rollback_proven_complete` falso quando nao consegue provar a recuperacao.
