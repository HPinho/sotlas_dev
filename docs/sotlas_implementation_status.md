# Sotlas — Implementation Status

**Atualizado em:** 2026-09-22  
**Fonte arquitetural:** `SOTLAS — ESPECIFICAÇÃO MESTRA`  
**Regra:** nenhum item é chamado de `SUPPORTED` apenas por existir no parser, AST ou em um passe isolado.

Auditoria detalhada da Fase 0: [phase0_reality_audit.md](phase0_reality_audit.md).

## Legenda

- [x] concluído/certificado no escopo declarado
- [ ] pendente
- 🟡 infraestrutura parcial / em desenvolvimento

## Fase 1 — Typed Semantic Core

**Status:** ✅ CERTIFIED (`ISOLATED_PHASE1`)

- [x] Typed AST de declarações
- [x] Typed AST de corpos estruturados
- [x] pipeline público Phase 1
- [x] typing e contextualização de inteiros
- [x] range checking de constantes inteiras
- [x] contratos de assignment/return/calls/method calls
- [x] struct literal validation
- [x] function pointer signatures
- [x] raw pointer vs safe reference boundaries
- [x] lexical `unsafe`
- [x] recursive by-value type rejection
- [x] ownership `sole`
- [x] branch ownership merge
- [x] loop ownership guard
- [x] move em argumentos, retornos e campos `sole`
- [x] reality/maturity gates

### Enum payload — extensão em desenvolvimento sobre a Fase 1

- [x] payload type no AST/Typed AST
- [x] constructor typecheck
- [x] ownership move para payload `sole`
- [x] tag normalization
- [x] tagged-union logical layout
- [x] tag/payload storage plan backend-neutral
- [x] emissão C11 de tagged union e construtores para payloads escalares, com validação de tags `u64`
- [x] fixture `.sotlas` de payload escalar compilada até binário C11 e executada, verificando tags e valor do payload
- [ ] ABI física definitiva
- [ ] C11 type representation para todos os payloads
- [ ] C11 constructor lowering para todos os payloads
- [ ] cleanup/destruição de payload `sole`
- [ ] end-to-end de todos os payloads até binário/backend suportado (somente o subconjunto escalar foi exercitado)

## Fase 2 — Ownership Domains

**Status:** 🟡 EM CONSTRUÇÃO

### Concluído como fundação

- [x] `sole` como ownership exclusivo linear
- [x] move invalida origem
- [x] use-after-move rejeitado
- [x] estado condicional `MAYBE_MOVED`
- [x] transferências em calls/returns/struct fields/enum payloads
- [x] integração parcial com cleanup/deinit existente
- [x] `sole` mapeado para metadados de domínio `exclusive` em declarações, bindings e contratos de função do Typed AST isolado
- [x] nomes de domínios ainda sem semântica rejeitados antes do backend C11
- [x] cleanup `sole` isolado por ramo C11 em retornos antecipados; transferência condicional que continua é rejeitada
- [x] grafo canônico de Ownership Domains integrado ao snapshot semântico, com nós function-scoped e arestas de transferência

### Falta para concluir a Fase 2

- [x] `exclusive` formalizado como fato explícito no Typed AST de tipos sole, parâmetros e retornos; `sole` permanece a sintaxe que origina o contrato
- [ ] `shared` end-to-end: sintaxe e semântica frontend existem, ARC/SIR parcial existe, mas runtime/backend ainda não
- [x] modelo semântico backend-neutral de `co-owned`/ARC com strong-reference accounting explícito, retain/release e destruição elegível no último owner
- [ ] integração completa do ARC com bindings, aliases, cleanup, lowering e runtime/backend
- [ ] `region`
- [ ] `device`
- [ ] `external`
- [ ] `island`
- [ ] `whisper`
- [ ] `direct`
- [ ] `handover` — statement canônico + transferência EXCLUSIVE implementados; destino/domínio, reacquisition e backend ainda pendentes
- [ ] `quarantine`
- [x] ownership/domain graph canônico para owners rastreados e transferências `exclusive` (`call`, `return`, campos e payloads), backend-neutral
- [x] merge canônico de domínio em branches para owners rastreados: domínio deve permanecer idêntico; joins de estado são registrados no grafo
- [x] contrato backend-neutral da primeira transição explícita `exclusive → shared` via operação `share`, exigindo source LIVE e sem aplicar runtime implicitamente
- [x] aplicação semântica real de `exclusive → shared` no OwnershipEnv: owner original muda para `shared`, permanece LIVE e pode criar alias strong explícito
- [x] alias compartilhado incrementa strong_refs exatamente uma vez e colisões/stale transition são rejeitadas
- [x] nó semântico `TypedShareExpression` liga uma operação share de binding inteiro ao OwnershipEnv/ARC sem depender do parser
- [x] share de member/index/temporário permanece fail-closed até o contrato de aliasing parcial ser definido
- [x] sintaxe pública `let alias = share owner;` possui AST dedicado `ShareExpr`, typecheck e integração com OwnershipEnv
- [x] C11 reconhece a construção apenas para rejeitá-la fail-closed até ARC/cleanup lowering
- [x] plano backend-neutral de cleanup no scope normal da função: releases em ordem reversa e destroy apenas no último strong owner
- [x] early-return shared cleanup path-sensitive, usando histórico de ownership visível na entrada do ramo
- [x] branch-local shared aliases recebem cleanup somente no caminho que os criou/encerrou
- [x] cleanup de caminho e cleanup de fallthrough permanecem planos separados, evitando double-release no merge
- [x] shared owners podem ser capturados por `defer` sem transferência, permanecendo LIVE até a saída
- [x] plano de saída executa shared defers em LIFO antes dos releases ARC; destroy continua após o release final
- [x] regra antiga de `sole/exclusive` em defer permanece rígida: captura sem transferência continua rejeitada
- [x] ponte backend-neutral OwnershipTrace → plano SIR com `ShareInst`, `RetainInst`, `ReleaseInst` e `DestroyInst`, sem fingir placement CFG
- [x] pontos de cleanup ARC possuem identidade source-stable (`return@L:C`, `continue@L:C`, `break@L:C`, `*_backedge@L:C`)
- [x] plano SIR preserva segmentos distintos para saídas de mesmo tipo em pontos CFG diferentes
- [x] placement real de segmentos ARC em `ReturnInst(point_id=...)`, sempre imediatamente antes do retorno correspondente
- [x] placement de return falha fechado para point_id ausente ou duplicado
- [x] SIRGenerator preserva `ReturnInst.point_id` para return terminal linear diretamente representável pela AST
- [x] CFG estruturado inicial para funções `void`: `if flag { return; } return;` e `if/else` com retornos diretos, preservando point_id por branch
- [x] condições ainda não representáveis no SIR não recebem CFG/point_id fictício
- [ ] expansão do CFG estruturado para expressões condicionais e corpos arbitrários
- [x] placement de break/continue/backedge no CFG de produção para o subset estruturado atualmente representável
- [ ] runtime/backend para tornar `share` executável
- [ ] transições para `region/device/external` e merges correspondentes
- [x] invariância canônica de tipo/domínio/estado no backedge de loops para owners visíveis
- [x] contas shared inteiramente locais à iteração recebem release reverso antes do backedge
- [x] cleanup path-specific de shared locals em `break`/`continue`, inclusive em branches aninhados
- [x] defers shared ativos no escopo do loop executam em LIFO antes dos releases ARC no salto
- [x] caminhos break/continue não recebem também cleanup de backedge, evitando double-release
- [ ] integração completa de cleanup/early return/defer
- [ ] lowering backend-neutral dos domains
- [ ] implementação/rejeição explícita por backend
- [ ] testes positivos + negativos + end-to-end por domínio

## Progresso das fases

> Percentuais aproximados de engenharia. Eles não substituem os gates formais de `CERTIFIED`/`SUPPORTED`.
>
> **Regra de cálculo:** a porcentagem é estimada por macroentregas da fase, não pela contagem bruta de checkboxes. Subpassos de uma mesma feature (por exemplo, vários passos de ARC/`shared`) não podem compensar domínios inteiros ainda não implementados.

```text
Fase 0 — Reality Reset              ~80%
Fase 1 — Typed Semantic Core       100% ✅
Fase 2 — Ownership Domains          ~54% 🟡
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

**Desenvolvimento geral aproximado da linguagem: ~17%.**  
Este índice geral é apenas uma leitura agregada conservadora das fases acima; não equivale a `SUPPORTED` e não substitui os gates formais.

### Fase 2 — leitura por macroentregas

| Macroentrega | Estado aproximado | Observação |
|---|---:|---|
| `sole` / `exclusive` | ~100% semântico | domínio explícito congelado em structs, parâmetros, retornos, bindings e graph; backend geral da Fase 2 continua separado |
| `shared` / co-owned / ARC semântico | ~75% | frontend, accounting, cleanup e SIR avançados; runtime/backend e e2e ainda faltam |
| CFG + cleanup + defer para ownership | ~65% | vários paths reais cobertos; CFG arbitrário e todos os payloads de defer ainda não |
| `region` | ~0% | ainda não implementado |
| `device` | ~0% | ainda não implementado |
| `external` | ~0% | ainda não implementado |
| `island` | ~65% | parâmetros, retornos, locais e campos preservam ISLAND; transferências domain-preserving são explícitas e mismatches falham fechados |
| `whisper` | ~0% | ainda não implementado |
| `direct` | ~0% | ainda não implementado |
| `handover` | ~60% | transições EXCLUSIVE→EXCLUSIVE e ISLAND→EXCLUSIVE possuem source/target/destination domain explícitos no graph; outros domínios/backend/e2e faltam |
| `quarantine` | ~40% | EXCLUSIVE→ISLAND é fato de transição explícito e validado no Ownership Domain Graph; weak invalidation/runtime/e2e faltam |
| runtime/backend + e2e por domínio | ~5% | gates/fail-closed existem, mas execução real de Ownership Domains ainda não |

A combinação ponderada dessas macroentregas coloca a Fase 2 em **~54%**.

### Fase 2 detalhada

```text
Fase 2 — Ownership Domains                  ~54%

✅ sole / exclusive
✅ move semantics
✅ use-after-move
✅ MAYBE_MOVED
✅ call/return/field/enum transfers
✅ exclusive metadata
✅ branch cleanup isolation
✅ reserved domains fail-closed
✅ Ownership Domain Graph
✅ branch domain merge
✅ divergence rejection
✅ shared domain internal model
✅ exclusive → shared transition contract
✅ shared ARC/reference-accounting model
✅ retain/release semantics
✅ last-owner destruction eligibility
✅ apply shared transition to real env
✅ real shared strong alias model
✅ stale transition / alias collision guards
✅ TypedShareExpression canonical semantics
✅ partial-share sources remain fail-closed
✅ public share syntax + dedicated AST
✅ parser → Typed AST → OwnershipEnv path
✅ C11 share gate remains fail-closed
✅ function-scope shared cleanup plan
✅ reverse release order / final destroy
✅ unaccounted shared owners fail-closed
✅ early-return shared cleanup
✅ branch-aware shared cleanup
✅ path/fallthrough cleanup isolation
✅ shared defer capture while owner LIVE
✅ defer LIFO before ARC release
✅ exclusive defer rule remains strict
✅ loop domain/state/type backedge invariant
✅ loop-local shared cleanup before backedge
✅ break/continue path-specific cleanup      ← NOVO
✅ loop-control defer before ARC release     ← NOVO
✅ no double cleanup on control paths        ← NOVO

✅ backend-neutral ARC/SIR operation plan    ← NOVO
✅ Share/Retain/Release/Destroy SIR ops       ← NOVO
✅ fail-closed when ownership type is unknown ← NOVO

✅ OwnershipTrace → SIR plan → return placement integration ← NOVO
✅ generated if-return CFG accepts ARC cleanup placement      ← NOVO

✅ break/continue ARC placement on identified BranchInst   ← NOVO
✅ missing/duplicate loop-control points fail-closed
✅ return/control/backedge ARC placement is transactional   ← NOVO
✅ apply_shared_ownership_trace preflights all CFG points before mutation ← NOVO
✅ loop-control defer lowering remains fail-closed          ← NOVO

✅ SIRGenerator emits source-identified break/continue BranchInst ← NOVO
✅ minimal while CFG: entry → cond → body/exit               ← NOVO
✅ generated loop CFG accepts ARC control placement          ← NOVO

✅ normal while backedge gets source-stable BranchInst identity ← NOVO
✅ ARC cleanup placement before normal loop backedge             ← NOVO
✅ continue/backedge remain disjoint during placement
✅ conditional continue preserves fallthrough backedge cleanup   ← NOVO
✅ terminated if-branches no longer pollute fallthrough env
✅ break/continue exit env snapshots preserve loop invariants    ← CORRIGIDO
✅ nested control cleanup history no longer duplicates accounts  ← CORRIGIDO

✅ shared defer registrations preserve source-stable defer@L:C identity
✅ control-exit point and defer-registration point remain distinct
✅ SIR rejects anonymous/invalid defer obligations fail-closed
✅ expression-name defer lowers to DeferUseInst before ARC cleanup       ← NOVO
✅ SIR can lower validated direct deferred-call payloads once to CallInst before ARC
✅ break/continue placement preserves defer → release → destroy order    ← NOVO
✅ shared → sole-consuming call/defer-call requires explicit handover            ← CORRIGIDO
✅ handover EXCLUSIVE source → MOVED binding destination                     ← NOVO
✅ handover destination reacquisition requires same type + prior MOVED state ← NOVO
✅ Ownership Domain Graph preserves explicit handover destination            ← NOVO
✅ canonical quarantine EXCLUSIVE → ISLAND                                  ← NOVO
✅ quarantined owner remains LIVE but cannot move/escape implicitly          ← NOVO
✅ quarantine transfer is preserved in Ownership Domain Graph                ← NOVO
✅ C11 quarantine remains fail-closed                                        ← NOVO
✅ explicit ISLAND → EXCLUSIVE handover reacquisition                         ← NOVO
✅ island handover requires same-type EXCLUSIVE destination already MOVED     ← NOVO
✅ targetless handover from ISLAND remains fail-closed                        ← NOVO
✅ cross-domain handover preserves source domain + destination in graph        ← NOVO
✅ domain graph freezes EXCLUSIVE → ISLAND quarantine direction                ← NOVO
✅ domain graph freezes ISLAND → EXCLUSIVE reacquisition direction             ← NOVO
✅ destination domain is explicit for binding-to-binding handover              ← NOVO
✅ incomplete cross-domain graph facts fail-closed                             ← NOVO
✅ public island T ownership modifier parsed and frozen in Typed AST             ← NOVO
✅ explicit island bindings seed ISLAND/LIVE ownership                           ← NOVO
✅ island qualifier restricted to direct by-value sole types                     ← NOVO
✅ explicit island participates in handover reacquisition                         ← NOVO
✅ C11 island-qualified types remain fail-closed                                  ← NOVO
✅ island return signature preserves ISLAND → ISLAND transfer                      ← NOVO
✅ island → exclusive return escape is rejected fail-closed                        ← NOVO
✅ return transfer direction is explicit in Ownership Domain Graph                 ← NOVO
✅ island local bindings preserve ISLAND → ISLAND ownership                         ← NOVO
✅ island struct fields preserve ISLAND → ISLAND ownership                          ← NOVO
✅ EXCLUSIVE → ISLAND local/field moves remain forbidden without quarantine          ← NOVO
✅ invalid island field/global type annotations fail in Typed AST                    ← NOVO
✅ unsupported call shapes and assign/block/method/try defer payloads remain fail-closed

⬜ general call/assign/block/method/try defer payload lowering
⬜ ARC runtime/backend
⬜ region
⬜ device
⬜ external
⬜ island
⬜ whisper
⬜ direct
⬜ handover
⬜ quarantine
⬜ backend/e2e
```

## Objetivo transversal — Backend Nativo / "Assembly moderno tipado"

**Status:** ⬜ PLANEJADO — dependente das fundações semânticas e do SIR.

A direção arquitetural é tornar C11 um backend de bootstrap/referência, não uma dependência semântica permanente.

Pipeline alvo:

```text
Sotlas
→ Typed AST / Sema
→ SIR
→ Target Lowering
→ Machine/Object Code
  └→ --emit=asm (inspeção)
```

### Pré-requisitos que as fases atuais precisam entregar

- [x] Typed Semantic Core isolado e certificado;
- [x] C11 preservado como backend de referência/fail-closed;
- [ ] Ownership Domains completos no Typed AST/SIR;
- [ ] Authority/Effects suficientes para `@system` e hardware;
- [ ] Execution Domain CPU/SIMD formalizado;
- [ ] SIR completo como fronteira backend-independent;
- [ ] ABI/layout/cleanup não dependentes do backend C11.

### Fase 16 — Native Machine Backend

- [ ] Target Lowering / Target IR;
- [ ] calling convention e ABI lowering;
- [ ] stack-frame layout;
- [ ] instruction selection;
- [ ] virtual registers;
- [ ] register allocation + spill/reload;
- [ ] prologue/epilogue;
- [ ] native lowering de intrinsics de sistema;
- [ ] relocations + symbols;
- [ ] object-file writer;
- [ ] linker integration;
- [ ] `--emit=asm`;
- [ ] emissão direta de object/machine code;
- [ ] testes ABI/differential/end-to-end;
- [ ] fail-closed por target/feature não implementada.

**Critério de sucesso inicial:** um programa Sotlas não trivial deve conseguir atravessar `Typed AST → SIR → target lowering → object code` e ser linkado/executado sem C intermediário, mantendo as mesmas garantias semânticas declaradas.

## Regra para próximos commits

Quando uma entrega fechar um item deste arquivo:

1. implementar a semântica real;
2. adicionar/fortalecer testes;
3. manter fail-closed onde o pipeline ainda não estiver completo;
4. somente depois marcar `[x]` neste arquivo;
5. não transformar CI verde em substituto para correção arquitetural.

## Próxima frente ativa

O trabalho atual está fechando **enum payload / tagged-union lowering**:

- [x] semantic payload metadata
- [x] constructor typecheck
- [x] `sole` payload ownership transfer
- [x] canonical tags
- [x] logical tagged-union layout
- [x] backend-neutral storage plan
- [ ] physical representation contract
- [x] backend C11 type representation para payload escalar
- [x] constructor lowering para payload escalar
- [ ] backend C11 e constructor lowering para payloads não escalares
- [ ] cleanup ownership for active payload
- [x] end-to-end de payload escalar com fixture `.sotlas` e binário C11
- [ ] end-to-end certification para todos os payloads
