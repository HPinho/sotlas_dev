# Sotlas 1.0 — Phase 4 State Spaces Release Scope

**Atualizado em:** 2026-09-25  
**Status:** 🟡 IN PROGRESS  
**Último baseline verde antes deste pacote:** `c34e568787a8afc8ce22150933555067c84468a8` — CI #561 `success`

## Objetivo do 1.0

A Fase 4 deve colocar State Spaces no caminho real da linguagem sem exigir, antes do primeiro release, toda generalização possível de máquinas de estado, pattern matching, UI ou persistência.

O contrato mínimo do 1.0 é:

```text
space declarado
      ↓
estados e payload contracts conhecidos
      ↓
grafo de transições certificado
      ↓
Type<State> conhecido pelo checker
      ↓
transições inválidas rejeitadas
      ↓
fatos preservados no pipeline suportado
      ↓
backend/e2e mínimo executável
```

A mesma regra das fases anteriores continua válida:

> unsupported pode falhar fechado; accepted-but-wrong não é aceitável.

## Subset semântico já implementado

- [x] State Space como conjunto finito e nomeado de estados;
- [x] payload contract ordenado por estado;
- [x] grafo dirigido explícito de transições;
- [x] nenhum reverse edge, self edge ou transitive edge é inventado;
- [x] estados/transições duplicados ou desconhecidos são rejeitados;
- [x] `StateQualifiedType` representa semanticamente `Type<State>`;
- [x] boundary checks exigem tipo nominal, State Space e estado exatos;
- [x] transições de typestate consultam exclusivamente o grafo certificado;
- [x] State Spaces com estados homônimos não compartilham identidade;
- [x] cobertura de estados possui análise backend-neutral;
- [x] arms duplicados/desconhecidos são rejeitados;
- [x] missing states são preservados em ordem de declaração;
- [x] gate de exhaustividade pode rejeitar consumidor incompleto.

## Bridge do frontend de produção

- [x] a rota canônica `sotlas_compile.bootstrap` reconhece declaração `space`;
- [x] a AST fonte preserva `pub`, nome, estados, payload contracts e edges;
- [x] `Space<State>` possui sintaxe pública no subset inicial;
- [x] resolução 1.0 é deliberadamente simples: `Space<State>` só é typestate quando existe `space Space` no mesmo módulo;
- [x] generics comuns mantêm o comportamento anterior quando não existe State Space homônimo;
- [x] `StateSpaceFrontendPlan` reconcilia AST fonte com `StateSpacePlan` e `StateQualifiedType`;
- [x] estado inexistente, espaço duplicado, edge inválido e forma indireta fora do subset falham fechado;
- [x] `check`, C11 e header mantêm um gate `PREVIEW` explícito até existir SIR/backend certificado.

### Por que `check` ainda rejeita esses módulos

O parser e o planner semântico agora compreendem State Spaces, mas o contrato de produção da Sotlas exige:

> se `sotlas check` retorna sucesso, o pipeline oficialmente suportado deve conseguir compilar corretamente o programa.

Como State Spaces ainda não possuem lowering SIR/backend 1.0, retornar sucesso agora seria uma promoção falsa. O gate PREVIEW é, portanto, parte da segurança do release e não uma regressão.

## BLOCKERS 1.0

- [x] parser e AST público para declaração `space`;
- [ ] representação Typed AST canônica de `space` dentro de `Phase1CheckedModule`;
- [x] sintaxe pública para tipos `Type<State>` no subset `Space<State>`;
- [x] resolução de `Type<State>` contra o State Space homônimo correto;
- [ ] integração do typestate ao Typed AST/checker de produção de forma que o módulo possa ser aceito quando houver backend;
- [ ] construção de transições a partir de código Sotlas real;
- [ ] contratos de chamadas/retornos que mudam typestate;
- [ ] identidade source-stable das transições no SIR;
- [ ] revalidação fail-closed entre semântica fonte e SIR;
- [ ] lowering/backend mínimo para o subset declarado estável;
- [ ] teste positivo e2e: fonte → check → backend → execução;
- [ ] teste negativo e2e para transição inexistente;
- [ ] gate que garanta que `sotlas check` não aceite um caso que o backend 1.0 não consegue compilar corretamente;
- [ ] integrar coverage ao consumer público mínimo escolhido para o 1.0.

## DEFER 1.0.x

Podem ser adicionados depois do 1.0 sem reabrir a fase, desde que os casos ainda não suportados continuem fail-closed:

- wildcard de coverage;
- guards sofisticados;
- patterns avançados de payload;
- mapeamento arbitrário entre nome do tipo e State Space;
- typestate sobre referências/ponteiros/ownership domains além do subset inicial;
- diagnósticos com sugestões de caminhos alternativos;
- merges de typestate mais gerais em CFG;
- payload lowering adicional;
- representação backend otimizada de tags/estado;
- mais formas de consumers exaustivos.

## DEFER 1.1+

- state machines dinâmicas;
- transições dependentes de prova temporal avançada;
- integração ampla de State Spaces com UI declarativa;
- persistência automática de estado;
- sincronização distribuída/networked state;
- generalizações que alterem o contrato público da Fase 4.

## Critério de fechamento da Fase 4

A Fase 4 poderá ser marcada `100% ✅` para o Sotlas 1.0 quando:

1. `space` e `Type<State>` estiverem representados no frontend e Typed AST canônicos;
2. o checker rejeitar transições inválidas antes do backend;
3. o pipeline preservar identidade source-stable das transições no SIR;
4. houver pelo menos um backend/e2e real para o subset estável;
5. os casos fora do subset forem rejeitados de forma explícita/fail-closed;
6. o CI possuir um release gate específico da Fase 4.

Não é necessário implementar antes disso todas as combinações de CFG, UI, payload pattern ou state-machine generalization.
