# Sotlas — Current Implementation Progress

**Atualizado em:** 2026-09-24  
**Baseline verde de referência:** `5075c6454c0e1f5830b3f0537d267f6fe289d122`  
**CI de referência:** Sotlas CI & Toolchain Build Farm #536 — `success`

> Este arquivo é o snapshot canônico de progresso de engenharia. Percentuais medem o escopo necessário para o roadmap Sotlas 1.0; generalizações pós-release permanecem registradas separadamente em `sotlas_1_0_release_scope.md` e nos documentos técnicos.

## Estado atual

```text
Fase 0 — Reality Reset              ~80%
Fase 1 — Typed Semantic Core       100% ✅
Fase 2 — Ownership Domains         100% ✅  (escopo Sotlas 1.0)
Fase 3 — Authority Domains          ~10%
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
- CI #536 passou C11, Python 3.10/3.11/3.12 em Ubuntu, Windows e macOS e o snapshot de toolchain.

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

Com Ownership Domains encerrado para o Sotlas 1.0, o caminho principal pode avançar para **Fase 3 — Authority Domains**. Refinamentos da Fase 2 continuam em pacotes 1.0.x/1.1 sem monopolizar o roadmap principal.