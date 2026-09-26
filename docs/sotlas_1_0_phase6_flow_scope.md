# Sotlas 1.0 — Phase 6 Flow Scope

**Atualizado em:** 2026-09-25  
**Status:** 🟡 IN PROGRESS  
**Último baseline verde certificado:** `645590f` — CI #576 `success`

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
- [ ] sintaxe `flow` e tipagem de valores dependentes no frontend;
- [ ] lowering para SIR e integração com Effects/Ownership;
- [ ] cancelamento cooperativo de ações, backpressure e políticas de retry;
- [ ] e2e da fonte Sotlas ao scheduler e ao backend suportado.

## Fora deste subset

O runtime não executa tarefas assíncronas, não interrompe threads em execução,
não define retries/timeouts, não agenda em mais de um processo e não valida
effects ou ownership das closures. Essas operações permanecem fora de
`SUPPORTED` até terem contratos de linguagem e integração com o compilador.
