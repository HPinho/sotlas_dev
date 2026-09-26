# Sotlas 1.0 — Phase 6 Flow Scope

**Atualizado em:** 2026-09-26
**Status:** 🟡 IN PROGRESS  
**Último baseline verde certificado:** `0d09d86` — CI #633 `success`

## Subset de runtime disponível

`certify_flow_graph` valida nomes, referências, duplicatas e ciclos e deriva
estágios paralelos estáveis na ordem declarada. `execute_flow` executa cada
estágio concorrentemente, entrega a cada ação somente os resultados de suas
dependências diretas em um mapa imutável e publica os resultados na ordem dos
nós declarados.

Uma falha cancela tarefas ainda enfileiradas, aguarda as tarefas síncronas já
iniciadas e impede o início dos estágios seguintes. Se várias ações do mesmo
estágio falham, o diagnóstico seleciona a primeira na ordem declarada. Um
`threading.Event` permite cancelamento externo antes ou durante estágios; ações
síncronas em execução não podem ser interrompidas à força e precisam retornar
para que o scheduler conclua o cancelamento.

Este executor é uma API runtime para grafos certificados. A sintaxe Sotlas e
seu checker são descritos abaixo; agendamento distribuído continua fora deste
subset.

## Candidato de frontend de fonte

A rota canônica reconhece declarações `flow Name { stage output = function
after dependency, ...; }`. O checker certifica o DAG, resolve cada função de
stage, exige resultados não-void, confere aridade e garante que cada parâmetro
receba o mesmo tipo do resultado do stage produtor. Chamadas não resolvidas em
um stage são rejeitadas pelo subset inicial. O plano tipado é preservado em
`Phase1CheckedModule.flows`. O compilador C11 ainda rejeita explicitamente
essas declarações, pois não há lowering de fonte para scheduler.

Este candidato valida declaração e tipos. O plano SIR declarativo está descrito
abaixo; ainda não há chamadas em CFG executável nem execução da fonte pelo
scheduler.

O plano tipado de fonte é preservado em `Phase1CheckedModule.flows`. O lowering
canônico reconcilia tipos, assinaturas e summaries de efeitos e anexa
`FlowSIRPlan` ao `SIRModule`; o dump expõe estágios paralelos e chamadas com
referências tipadas a resultados produtores. O C11 continua rejeitando Flow:
chamadas de stage ainda não foram baixadas em CFG executável nem ligadas ao
scheduler.

`execute_typed_flow` executa diretamente esse plano tipado no runtime local.
Antes de iniciar ações, confere a ordem canônica do grafo, o conjunto de stages,
as dependências de cada stage e a quantidade de tipos de entrada. Cada ação
recebe os resultados de suas dependências como argumentos posicionais na ordem
declarada pela fonte. O runtime ainda não executa código compilado pelo backend
C11 nem integra ownership de closures.

`execute_bound_sir_flow` valida os `FlowSIRPlan` do módulo antes de iniciar o
scheduler e recebe bindings explícitos por símbolo de função SIR. Argumentos
de cada stage são resolvidos somente a partir dos outputs indicados pela
provenance validada. Esse runner executa os bindings fornecidos pelo host; ele
não interpreta instruções SIR nem afirma executar código compilado.

## Verificações

- execução concorrente de nós independentes e leitura de dependências diretas;
- mapas de entrada e resultado imutáveis e outputs em ordem estável;
- falha cancela o trabalho pendente, junta peers ativos e não executa sucessores;
- falhas simultâneas usam ordem de fonte estável;
- cancelamento antes e durante o estágio, inclusive no estágio final;
- ações ausentes/extras e planos adulterados são rejeitados.

## Blockers de 1.0

- [x] grafo canônico e stages paralelos determinísticos;
- [x] runtime local por estágios com limite opcional de workers;
- [x] propagação de resultados de dependências diretas;
- [x] falha e cancelamento impedem estágios posteriores e não deixam tarefas ativas sem join;
- [x] sintaxe `flow` com stages nomeados e dependências explícitas;
- [x] frontend tipa valores vindos das dependências e rejeita grafo cíclico;
- [x] CI #588 confirma a sintaxe e tipagem;
- [x] plano declarativo Flow reconciliado com SIR e summaries Effects;
- [x] executor local consome o plano tipado de fonte, valida sua estrutura e invoca stages com valores dependentes;
- [x] runner SIR revalida plano, assinaturas, efeitos e provenance antes de invocar bindings de função pelo scheduler;
- [x] executor de grafo oferece token cooperativo opt-in; ações podem observar cancelamento externo ou falha de peer e parar antes do join;
- [ ] lowering para CFG executável, integração de Ownership e execução pelo scheduler;
- [ ] validação do token cooperativo nos bindings de Flow tipados/SIR, backpressure e políticas de retry;
- [ ] e2e da fonte Sotlas ao scheduler e ao backend suportado.

## Fora deste subset

O runtime não executa tarefas assíncronas, não interrompe threads em execução,
não define retries/timeouts, não agenda em mais de um processo e não valida
effects ou ownership das closures. Essas operações permanecem fora de
`SUPPORTED` até terem contratos de linguagem e integração com o compilador.
