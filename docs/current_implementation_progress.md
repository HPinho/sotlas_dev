# Sotlas — Current Implementation Progress

**Atualizado em:** 2026-09-24  
**Baseline verde de referência:** `bd77265c95f7959165307a7f001388202f5477e5`  
**CI de referência:** Sotlas CI & Toolchain Build Farm #506 — `success`

> Este arquivo é o snapshot canônico de progresso de engenharia enquanto os documentos históricos maiores são consolidados. Percentuais são estimativas por macroentregas e não substituem os gates formais `CERTIFIED`/`SUPPORTED`.

## Estado atual

```text
Fase 0 — Reality Reset              ~80%
Fase 1 — Typed Semantic Core       100% ✅
Fase 2 — Ownership Domains          ~89% 🟡
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

**Progresso conservador atual: ~89% 🟡**

A estimativa anterior de ~84% ficou defasada depois da expansão do modelo `region`, do avanço backend-neutral de `device`, do fortalecimento do graph/SIR e das provas CFG/interprocedurais adicionadas sobre baseline verde.

A Fase 2 ainda não é `SUPPORTED` nem `CERTIFIED` como um todo. Permanecem blocos importantes de runtime/backend e end-to-end por domínio.

### Leitura atual por macroentrega

| Macroentrega | Estado aproximado | Observação |
|---|---:|---|
| `sole` / `exclusive` | ~100% semântico | ownership linear, moves, merges e contratos explícitos estabilizados; backend geral continua separado |
| `shared` / ARC semântico | ~91% | accounting, cleanup, graph→SIR e subset C11 avançados; runtime/backend geral e CFG arbitrário ainda faltam |
| CFG + cleanup + defer ownership | ~74% | retornos, branches e loops estruturados avançaram; corpos arbitrários/efeitos e cobertura geral ainda faltam |
| `region` | ~78% | lifetime topology, escape gates, CFG path-sensitive, calls/returns interprocedurais e fronteiras de call graph agora certificados; arena/runtime/backend amplo ainda faltam |
| `device` | em reauditoria | completion/reacquisition/sync backend-neutral já avançaram além do percentual histórico; não atualizar numericamente sem reauditoria completa |
| `external` | ~39% | subset C11 `repr(C)` e consumo validado existem; ABI/lifetime/runtime gerais ainda faltam |
| `island` | ~99% | semanticamente quase fechado no subset atual; runtime/aliases e formas fora do subset ainda faltam |
| `whisper` | ~75% | no-escape, forwarding e subset C11 avançados; weak invalidation/lifetime amplo/FFI ainda faltam |
| `direct` | ~62% | borrow call-scoped, graph/SIR e subset C11/LLVM existem; lifetime CFG geral e ABI ARC LLVM ainda faltam |
| `handover` | ~73% | múltiplas transições e cleanup nativo existem; domínios/caminhos restantes e e2e amplo ainda faltam |
| `quarantine` | ~69% | graph, alias checks e subset C11 existem; weak/runtime e CFG amplo ainda faltam |
| runtime/backend + e2e por domínio | ~5% | principal freio restante da Fase 2 |

## Regra de baseline

A partir da recuperação das regressões recentes, o desenvolvimento da Fase 2 segue esta regra obrigatória:

```text
baseline verde confirmado
        ↓
um único slice pequeno
        ↓
CI verde
        ↓
novo baseline
        ↓
próximo slice
```

Se o slice falhar, nenhuma feature adicional deve ser empilhada. A correção ou restauração parte do último baseline verde.

## Percentuais superseded

Os percentuais antigos de `~84%` para a Fase 2 e `~58%` para `region`, ainda presentes em snapshots históricos de documentação, ficam superseded por este arquivo até a consolidação textual desses documentos maiores.
