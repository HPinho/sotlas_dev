# Sotlas — Current Implementation Progress

**Atualizado em:** 2026-09-25  
**Último baseline verde certificado:** `2fee4aa5342df1822389c7f1dd51979fe42abeeb`  
**CI de referência:** Sotlas CI & Toolchain Build Farm #560 — `success`

> Este arquivo é o snapshot canônico de progresso de engenharia. Os percentuais medem o escopo necessário para o Sotlas 1.0, não a implementação de toda generalização teórica prevista para versões futuras.

## Estado atual

```text
Fase 0 — Reality Reset              ~80%
Fase 1 — Typed Semantic Core       100% ✅
Fase 2 — Ownership Domains         100% ✅  (escopo Sotlas 1.0)
Fase 3 — Authority Domains         100% ✅  (escopo Sotlas 1.0)
Fase 4 — State Spaces               ~20% 🟡
Fase 5 — Effects                    ~10%
Fase 6 — Flow                        ~0%
Fase 7 — Execution Domains          ~10%
Fase 8 — Heterogeneous Compute       ~0%
Fase 9 — Trust Domains               ~5%
Fase 10 — Guarantees                 ~0%
Fase 11 — Causality                  ~0%
Fase 12 — Counterfactuals            ~0%
Fase 13 — Transactions               ~0%
Fase 14 — Intent                     ~0%
Fase 15 — SIR completo              ~30%
Fase 16 — Native Machine Backend      ~5%
Fase 17 — Tooling avançado          ~15%
```

## Regra de versão

O roadmap usa a fronteira de release definida para o 1.0:

- **BLOCKER 1.0:** correção, safety, invariantes semânticas, integração necessária ao caminho suportado e pelo menos um e2e executável representativo;
- **DEFER 1.0.x:** generalizações de CFG, payloads, combinações raras, diagnósticos, ergonomia, cobertura e otimizações quando a forma ainda não suportada pode falhar fechado;
- **DEFER 1.1+:** capacidades novas ou generalizações que alteram o contrato público.

Um caso rejeitado de forma clara e fail-closed não mantém uma fase aberta apenas porque poderá ser suportado futuramente. Um caso aceito com semântica incorreta continua sendo regressão/blocker.

## Fase 1 — Typed Semantic Core

**Status do roadmap 1.0: 100% ✅ — COMPLETE**

O núcleo tipado, contratos de chamadas/retornos, ownership `sole`, safety básica, branches/loops estruturados e reality gates permanecem certificados. Extensões como ABI geral de enum payload continuam como maturação separada quando não forem necessárias ao subset 1.0.

## Fase 2 — Ownership Domains

**Status do roadmap 1.0: 100% ✅ — COMPLETE**

O subset `SUPPORTED` de `sole/exclusive`, `shared`, `region`, `island`, `quarantine`, `handover`, `direct` e `whisper` possui semântica certificada e caminhos backend representativos. `device` e `external` permanecem `PREVIEW`.

Refinamentos como CFG ARC arbitrário, arena `region` completamente geral, weak invalidation ampla, todos os pares de `handover`, runtime/sync geral de `device` e ABI/lifetime geral de `external` ficam em 1.0.x/1.1 enquanto permanecerem fail-closed.

Detalhes: `docs/sotlas_1_0_release_scope.md`.

## Fase 3 — Authority Domains

**Status do roadmap 1.0: 100% ✅ — COMPLETE**

Named `@system(capability)`, fronteiras source-stable, integração Phase 1, strict SIR, safety contra widening/tamper e o subset ABI contratado (`io.port`, `cpu.interrupts`, `cpu.msr`) fecham o 1.0. Catálogos privilegiados adicionais ficam para 1.0.x/1.1.

Detalhes: `docs/sotlas_1_0_phase3_authority_scope.md`.

## Fase 4 — State Spaces

**Status do roadmap 1.0: ~20% 🟡 — EM CONSTRUÇÃO**

A Fase 4 começou sobre uma base backend-neutral e fail-closed. O objetivo do 1.0 é tornar `space`, typestate e transitions parte do pipeline real sem exigir antes do release todas as generalizações possíveis de state machines.

### Já implementado

- [x] `StateSpacePlan` canônico com conjunto finito de estados;
- [x] payload contract ordenado por estado;
- [x] grafo explícito de transições, sem inventar reverse/transitive/self edges;
- [x] rejeição de estados, payloads e transições malformados;
- [x] `StateQualifiedType` backend-neutral para fatos `Type<State>`;
- [x] boundary check exato de typestate;
- [x] transição de typestate somente por edge declarado no `space`;
- [x] isolamento de identidade entre State Spaces distintos;
- [x] análise backend-neutral de cobertura de estados;
- [x] gate de exaustividade que rejeita arms duplicados, desconhecidos ou estados ausentes.

### BLOCKERS restantes para fechar a Fase 4 no Sotlas 1.0

- [ ] sintaxe pública/AST de declaração `space`;
- [ ] sintaxe e Typed AST para tipos `Type<State>` no caminho de produção;
- [ ] integração do grafo e do typestate ao `check`/pipeline público;
- [ ] representação source-stable de transições no SIR;
- [ ] lowering/backend mínimo do subset declarado `SUPPORTED`;
- [ ] e2e positivo e negativo a partir de código Sotlas real;
- [ ] release gate da Fase 4 garantindo `check => backend suportado`;
- [ ] integração de coverage ao consumidor público que fizer parte do 1.0 (sem obrigar a UI DSL completa).

### DEFER 1.0.x / 1.1

- wildcard/guards sofisticados de coverage;
- pattern matching avançado de payloads;
- merges de typestate altamente path-dependent;
- state machines dinâmicas/generalizadas;
- integração ampla com UI/persistência/networking;
- otimizações de representação de estado;
- diagnósticos e ergonomia adicionais.

Escopo formal: `docs/sotlas_1_0_phase4_state_space_scope.md`.

## Baseline e disciplina de CI

```text
baseline verde confirmado
        ↓
1 blocker real ou 1 pacote coerente
        ↓
testes reais
        ↓
CI verde
        ↓
novo baseline
```

Não contornar testes, não relaxar invariantes para obter CI verde e não empilhar feature sobre regressão.

## Próximo foco principal

O caminho crítico permanece na **Fase 4 — State Spaces**. Depois do núcleo de grafo, typestate e coverage, o próximo marco de maior valor é levar `space` e `Type<State>` ao frontend/Typed AST de produção, preservando as mesmas provas semânticas já certificadas nos módulos backend-neutral.
