# Sotlas — Implementation Status

**Atualizado em:** 2026-09-21  
**Fonte arquitetural:** `SOTLAS — ESPECIFICAÇÃO MESTRA`  
**Regra:** nenhum item é chamado de `SUPPORTED` apenas por existir no parser, AST ou em um passe isolado.

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
- [ ] ABI física definitiva
- [ ] C11 type representation para todos os payloads
- [ ] C11 constructor lowering para todos os payloads
- [ ] cleanup/destruição de payload `sole`
- [ ] end-to-end até binário/backend suportado

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

- [ ] Ownership Domain `exclusive` explícito
- [ ] `shared` (domínio já existe internamente como destino semântico; sintaxe/runtime/ARC ainda não suportados)
- [x] modelo semântico backend-neutral de `co-owned`/ARC com strong-reference accounting explícito, retain/release e destruição elegível no último owner
- [ ] integração do ARC com bindings reais, aliases, cleanup e lowering
- [ ] `region`
- [ ] `device`
- [ ] `external`
- [ ] `island`
- [ ] `whisper`
- [ ] `direct`
- [ ] `handover`
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
- [ ] ARC lowering/runtime para tornar `share` executável no backend
- [ ] transições para `region/device/external` e merges correspondentes
- [ ] regras de domínio para loops além do gate conservador atual
- [ ] integração completa de cleanup/early return/defer
- [ ] lowering backend-neutral dos domains
- [ ] implementação/rejeição explícita por backend
- [ ] testes positivos + negativos + end-to-end por domínio

## Progresso das fases

> Percentuais aproximados de engenharia. Eles não substituem os gates formais de `CERTIFIED`/`SUPPORTED`.

```text
Fase 0 — Reality Reset              ~80%
Fase 1 — Typed Semantic Core       100% ✅
Fase 2 — Ownership Domains          ~73% 🟡
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

### Fase 2 detalhada

```text
Fase 2 — Ownership Domains                  ~73%

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
✅ apply shared transition to real env       ← NOVO
✅ real shared strong alias model            ← NOVO
✅ stale transition / alias collision guards
✅ TypedShareExpression canonical semantics
✅ partial-share sources remain fail-closed
✅ public share syntax + dedicated AST        ← NOVO
✅ parser → Typed AST → OwnershipEnv path     ← NOVO
✅ C11 share gate remains fail-closed
✅ function-scope shared cleanup plan         ← NOVO
✅ reverse release order / final destroy      ← NOVO

✅ early-return shared cleanup              ← NOVO
✅ branch-aware shared cleanup              ← NOVO
✅ path/fallthrough cleanup isolation       ← NOVO

⬜ defer integration for shared owners
⬜ ARC lowering/runtime
⬜ region
⬜ device
⬜ external
⬜ island
⬜ whisper
⬜ direct
⬜ handover
⬜ quarantine
⬜ loop-domain semantics
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
- [ ] backend C11 type representation
- [ ] constructor lowering
- [ ] cleanup ownership for active payload
- [ ] end-to-end certification
