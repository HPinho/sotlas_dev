# Sotlas 1.0 — Phase 6 Flow Scope

**Atualizado em:** 2026-09-26
**Status:** 🟡 IN PROGRESS  
**Último baseline verde certificado:** `24ef5ff` — CI #588 `success`

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

Este executor é uma API runtime para grafos certificados. Ele ainda não é
sintaxe Sotlas e não afirma tipagem, lowering SIR, integração com Effects ou
Ownership, nem agendamento distribuído.

## Candidato de frontend de fonte

A rota canônica reconhece declarações `flow Name { stage output = function
after dependency, ...; }`. O checker certifica o DAG, resolve cada função de
stage, exige resultados não-void, confere aridade e garante que cada parâmetro
receba o mesmo tipo do resultado do stage produtor. Chamadas não resolvidas em
um stage são rejeitadas pelo subset inicial. O plano tipado é preservado em
`Phase1CheckedModule.flows`. O compilador C11 ainda rejeita explicitamente
essas declarações, pois não há lowering de fonte para scheduler.

Este candidato valida declaração e tipos; ele ainda não baixa chamadas para
SIR nem executa a fonte pelo scheduler.

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
- [ ] CI #588 confirma a sintaxe e tipagem (candidato atual; ainda na fila);
- [ ] lowering para SIR e integração com Effects/Ownership;
- [ ] cancelamento cooperativo de ações, backpressure e políticas de retry;
- [ ] e2e da fonte Sotlas ao scheduler e ao backend suportado.

## Fora deste subset

O runtime não executa tarefas assíncronas, não interrompe threads em execução,
não define retries/timeouts, não agenda em mais de um processo e não valida
effects ou ownership das closures. Essas operações permanecem fora de
`SUPPORTED` até terem contratos de linguagem e integração com o compilador.
