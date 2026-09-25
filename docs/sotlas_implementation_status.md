# Sotlas — Implementation Status

**Atualizado em:** 2026-09-25  
**Último baseline verde certificado:** `2fee4aa5342df1822389c7f1dd51979fe42abeeb`  
**CI de referência:** Sotlas CI & Toolchain Build Farm #560 — `success`  
**Fonte arquitetural:** `SOTLAS — ESPECIFICAÇÃO MESTRA`

> Este documento passa a ser o índice operacional atual. O snapshot detalhado anterior, com o histórico extenso das microentregas da Fase 2, foi preservado em `docs/archive/sotlas_implementation_status_2026-09-23.md`.

## Regra de status

Nenhum item recebe `SUPPORTED` apenas porque existe no parser, AST ou em um passe isolado. O 1.0 exige coerência semântica, fail-closed para formas não suportadas e um caminho backend/e2e representativo para o subset declarado estável.

Legenda:

- ✅ `COMPLETE`: gate do Sotlas 1.0 fechado;
- 🟡 `IN PROGRESS`: blockers 1.0 ainda abertos;
- `PREVIEW`: existe implementação útil, mas não faz parte do contrato estável 1.0;
- `DEFER`: evolução planejada para 1.0.x/1.1.

## Progresso por fase

| Fase | Área | Progresso 1.0 | Estado |
|---:|---|---:|---|
| 0 | Reality Reset | ~80% | 🟡 |
| 1 | Typed Semantic Core | 100% | ✅ COMPLETE |
| 2 | Ownership Domains | 100% | ✅ COMPLETE |
| 3 | Authority Domains | 100% | ✅ COMPLETE |
| 4 | State Spaces | ~20% | 🟡 IN PROGRESS |
| 5 | Effects | ~10% | 🟡 |
| 6 | Flow | ~0% | 🟡 |
| 7 | Execution Domains | ~10% | 🟡 |
| 8 | Heterogeneous Compute | ~0% | 🟡 |
| 9 | Trust Domains | ~5% | 🟡 |
| 10 | Guarantees | ~0% | 🟡 |
| 11 | Causality | ~0% | 🟡 |
| 12 | Counterfactuals | ~0% | 🟡 |
| 13 | Transactions | ~0% | 🟡 |
| 14 | Intent | ~0% | 🟡 |
| 15 | SIR completo | ~30% | 🟡 |
| 16 | Native Machine Backend | ~5% | 🟡 |
| 17 | Tooling avançado | ~15% | 🟡 |

Os percentuais acima medem o escopo necessário para o Sotlas 1.0. Eles não significam que toda generalização teórica prevista para 1.0.x/1.1 já foi implementada.

## Fase 1 — Typed Semantic Core

**Status 1.0: 100% ✅**

- [x] Typed AST de declarações e corpos estruturados;
- [x] typing/contextualização/range checking;
- [x] contratos de assignment/return/calls/method calls;
- [x] function pointers e raw pointer vs safe reference boundaries;
- [x] lexical `unsafe`;
- [x] recursive by-value rejection;
- [x] ownership `sole`, moves, branch merge e loop guard;
- [x] reality/maturity gates.

Extensões de enum payload que excedem o subset necessário ao 1.0 permanecem como maturação separada.

## Fase 2 — Ownership Domains

**Status 1.0: 100% ✅ — COMPLETE**

O subset estável de `sole/exclusive`, `shared`, `region`, `island`, `quarantine`, `handover`, `direct` e `whisper` está fechado para o 1.0. `device` e `external` permanecem `PREVIEW`.

- [x] ownership/domain graph canônico e source-stable;
- [x] moves, invalidation, joins e transfers suportados;
- [x] ARC backend-neutral + cleanup no subset `shared`;
- [x] lifetime/arena/interprocedural mínimo de `region`;
- [x] isolamento e transferências certificadas de `island`/`quarantine`/`handover`;
- [x] borrows call-scoped/no-escape de `direct`/`whisper`;
- [x] caminhos C11/e2e representativos;
- [x] unsupported shapes permanecem fail-closed.

Refinamentos amplos de CFG/runtime/ABI continuam em 1.0.x/1.1 sem reabrir automaticamente a fase.

Escopo: `docs/sotlas_1_0_release_scope.md`.

## Fase 3 — Authority Domains

**Status 1.0: 100% ✅ — COMPLETE**

- [x] named `@system(capability)` com least-authority;
- [x] bare `@system` preservado como legado explícito;
- [x] production frontend safety;
- [x] integração com Phase 1;
- [x] strict Authority SIR source-stable;
- [x] safety contra tamper/widening;
- [x] subset ABI contratado para `io.port`, `cpu.interrupts` e `cpu.msr`;
- [x] unsupported privileged shapes permanecem fail-closed.

Escopo: `docs/sotlas_1_0_phase3_authority_scope.md`.

## Fase 4 — State Spaces

**Status 1.0: ~20% 🟡 — IN PROGRESS**

### Núcleo semântico já entregue

- [x] `StateSpacePlan` canônico;
- [x] estados com payload contracts ordenados;
- [x] grafo explícito de transições;
- [x] validação fail-closed de estados/transições;
- [x] `StateQualifiedType` para `Type<State>`;
- [x] boundary check exato de typestate;
- [x] transições de typestate validadas pelo grafo;
- [x] identidade de State Space preservada;
- [x] coverage backend-neutral;
- [x] exhaustiveness gate com missing-state diagnostics.

### Blockers 1.0 ainda abertos

- [ ] parser/AST público de `space`;
- [ ] `Type<State>` no frontend/Typed AST de produção;
- [ ] integração com `check` e pipeline público;
- [ ] fatos source-stable de transição no SIR;
- [ ] lowering/backend mínimo;
- [ ] e2e positivo/negativo a partir de fonte Sotlas;
- [ ] gate formal de release da Fase 4.

### Pós-1.0

- coverage com wildcard/guards complexos;
- patterns avançados de payload;
- merges de estado altamente path-dependent;
- state machines dinâmicas/generalizadas;
- integração ampla com UI, persistência e networking;
- otimizações e ergonomia adicionais.

Escopo: `docs/sotlas_1_0_phase4_state_space_scope.md`.

## Regra de baseline

```text
baseline verde
    ↓
1 blocker real ou 1 pacote coerente
    ↓
testes reais
    ↓
CI verde
    ↓
novo baseline
```

Se um slice falhar, corrigir a regressão antes de empilhar outra feature. Nunca contornar testes para produzir CI verde.
