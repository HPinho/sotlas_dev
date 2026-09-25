# Sotlas — Current Implementation Progress

**Atualizado em:** 2026-09-25  
**Baseline verde de referência:** `3b5114fb99f25f2ac92f2346b2c7d5a31db277e4`  
**CI de referência:** Sotlas CI & Toolchain Build Farm #557 — `success`

> Este arquivo é o snapshot canônico de progresso de engenharia. Percentuais medem o escopo necessário para o roadmap Sotlas 1.0; generalizações pós-release permanecem registradas separadamente nos documentos de release-scope e nos documentos técnicos.

## Estado atual

```text
Fase 0 — Reality Reset              ~80%
Fase 1 — Typed Semantic Core       100% ✅
Fase 2 — Ownership Domains         100% ✅  (escopo Sotlas 1.0)
Fase 3 — Authority Domains         100% ✅  (escopo Sotlas 1.0)
Fase 4 — State Spaces                ~0%
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

## Fase 2 — Ownership Domains

**Status do roadmap 1.0: 100% ✅ — COMPLETE**

A Fase 2 não significa que toda combinação teórica de ownership foi implementada. O critério de saída do Sotlas 1.0 é definido em `docs/sotlas_1_0_release_scope.md`: o subset declarado `SUPPORTED` precisa estar semanticamente correto, possuir caminho backend executável representativo e rejeitar formas fora do contrato de maneira fail-closed.

Esse gate está fechado no baseline de referência.

### Contrato 1.0 por macroentrega

| Macroentrega | Status 1.0 | Observação |
|---|---|---|
| `sole` / `exclusive` | **SUPPORTED ✅** | ownership linear, moves, invalidation, joins e cleanup no subset aceito |
| `shared` / ARC | **SUPPORTED ✅** | modelo ARC backend-neutral + alias chain/runtime nativo; CFG/payloads arbitrários foram movidos para 1.0.x |
| `region` | **SUPPORTED ✅** | lifetime/CFG/interprocedural, arena epochs/flow, loop recurrence e activation flow + gate C11 mínimo |
| `island` | **SUPPORTED ✅** | quarantine e handover possuem caminhos C11 representativos, incluindo same-domain cleanup |
| `quarantine` | **SUPPORTED ✅** | subset de isolamento congelado; invalidation/runtime amplo fica para 1.0.x |
| `handover` | **SUPPORTED ✅** | pares certificados fazem parte do 1.0; combinações ainda não suportadas permanecem fail-closed |
| `direct` | **SUPPORTED ✅** | borrow call-scoped/zero-bookkeeping certificado pelo gate 1.0 |
| `whisper` | **SUPPORTED ✅** | const/non-owning call-scoped e forwarding certificado; weak refs gerais ficam para 1.0.x |
| `device` | **PREVIEW** | não bloqueia 1.0; runtime/sincronização geral fica para evolução posterior |
| `external` | **PREVIEW** | caminhos `repr(C)`/FFI existem, mas ABI/lifetime geral não é contrato estável do 1.0 |

### Evidência de fechamento

- `tests/test_sotlas_phase2_v1_region_release_gate.py` certifica `region` semanticamente e executa o subset nativo mínimo com cleanup determinístico.
- `tests/test_sotlas_phase2_v1_borrow_release_gate.py` certifica `direct` e `whisper` em C11 nativo.
- `test_shared_alias_chain_runs_with_native_arc_runtime` mantém o subset `shared` sobre ARC real.
- `test_island_quarantine_handover_runs_through_c11` e `test_island_to_island_handover_runs_through_c11` mantêm o subset de isolamento/handover executável.
- O gate de release da Fase 2 permanece definido em `docs/sotlas_1_0_release_scope.md`.

## Backlog pós-Fase 2

O seguinte trabalho **não reabre automaticamente a Fase 2**. Ele pertence à maturação 1.0.x/1.1 enquanto os casos fora do subset estável continuam fail-closed:

- CFG arbitrário de `shared`/ARC;
- payloads/layouts adicionais;
- combinações profundas de defer/aliases;
- arena `region` completamente geral;
- merges path-dependent avançados;
- activation + ciclos/recursão geral;
- weak invalidation geral de `whisper`;
- todas as formas ABI de `direct`;
- todos os pares possíveis de `handover`;
- runtime amplo de `quarantine`;
- runtime/sync geral de `device`;
- ABI/lifetime geral de `external`.

Se um desses itens revelar corrupção, double-free, use-after-free ou lowering incorreto em um caso que já faz parte do subset `SUPPORTED`, ele volta a ser tratado como regressão/blocker.

## Fase 3 — Authority Domains

**Status do roadmap 1.0: 100% ✅ — COMPLETE**

A Fase 3 está encerrada no escopo de release definido em `docs/sotlas_1_0_phase3_authority_scope.md`. O objetivo do 1.0 é possuir um modelo real de least-authority, não catalogar toda instrução privilegiada de toda arquitetura antes do primeiro release.

### Caminho certificado

```text
@system(capability)
        ↓
production frontend safety
        ↓
Phase1CheckedModule / AuthorityDomainPlan
        ↓
strict checked SIR
        ↓
source boundaries + AuthorityABIInst
        ↓
AuthoritySIRCertificate
        ↓
AuthoritySIRSafety
```

### Contrato 1.0 por macroentrega

| Macroentrega | Status 1.0 | Observação |
|---|---|---|
| named `@system(capability)` | **SUPPORTED ✅** | least-authority explícito; uma capability não implica outra |
| bare `@system` | **SUPPORTED/LEGACY ✅** | mantém compatibilidade irrestrita sem ser confundido com named authority |
| source `@system` boundary | **SUPPORTED ✅** | abstração encapsulada; caller não herda nem precisa da authority interna do callee |
| production frontend gate | **SUPPORTED ✅** | `check`/`compile_source` compartilham o planner canônico de Authority |
| Phase-1 integration | **SUPPORTED ✅** | `Phase1CheckedModule` carrega Authority e o Typed AST reconhece ABI named contratado |
| strict Authority SIR | **SUPPORTED ✅** | fatos source-stable preservados e certificados backend-neutral |
| SIR tamper/widening safety | **SUPPORTED ✅** | remoção, inserção ou ampliação indevida de authority é rejeitada |
| `io.port` | **SUPPORTED ✅** | `in/out` de 8/16/32 bits contratados |
| `cpu.interrupts` | **SUPPORTED ✅** | save/restore/status + `cli`/`sti` contratados |
| `cpu.msr` | **SUPPORTED ✅** | `rdmsr`/`wrmsr` contratados |
| CRx / TLB / GS / halt / catálogos adicionais | **DEFER 1.0.x** | permanecem legado/fail-closed onde named authority não possui contrato |

### Evidência de fechamento

- `authority.py` mantém os contratos e edges canônicos de Authority Domains.
- `authority_abi.py` registra apenas fronteiras ABI cujo significado de authority já está explícito.
- `authority_frontend_safety.py` protege o caminho de produção.
- `authority_typed_ast.py` integra os ABI contracts nomeados ao Phase 1 sem duplicar assinaturas de builtins.
- `authority_sir.py` preserva source boundaries e ABI facts no SIR.
- `AuthorityABIInst` é um fato backend-neutral e source-stable, sem inventar lowering físico.
- `authority_safety.py` revalida o certificado contra o SIR e detecta divergências pós-certificação.
- CI #557 passou C11, Python 3.10/3.11/3.12 em Ubuntu, Windows e macOS e o snapshot de toolchain.

## Backlog pós-Fase 3

O seguinte trabalho pertence à maturação 1.0.x/1.1 e **não reabre automaticamente a Fase 3**:

- capabilities específicas para CR0/CR2/CR3/CR4;
- TLB / `invlpg`;
- GS / `swapgs` / per-CPU;
- CPU halt e demais intrinsics privilegiados ainda legados;
- catálogo de Authority para MMIO, DMA e outros subsistemas;
- contracts Authority gerais de FFI;
- assinaturas ABI não escalares no bridge de Typed AST;
- expansão target-specific para outras arquiteturas;
- refinamentos de diagnóstico e ergonomia.

Se um desses itens permitir privilege escalation, authority implícita ou lowering incorreto dentro do subset `SUPPORTED`, ele volta a ser blocker.

## Regra de baseline

```text
baseline verde confirmado
        ↓
um blocker real ou pacote coerente
        ↓
CI verde
        ↓
novo baseline
        ↓
próxima entrega do roadmap
```

Se o slice falhar, nenhuma feature adicional deve ser empilhada. A correção ou restauração parte do último baseline verde.

## Próximo foco principal

Com **Ownership Domains** e **Authority Domains** encerrados para o Sotlas 1.0, o caminho principal avança para **Fase 4 — State Spaces** (`space`, typestate e transitions). Refinamentos das Fases 2 e 3 continuam em pacotes 1.0.x/1.1 sem monopolizar o roadmap principal.
