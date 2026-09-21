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

### Falta para concluir a Fase 2

- [ ] Ownership Domain `exclusive` explícito
- [ ] `shared`
- [ ] `co-owned` / ARC formal no Typed AST/lowering
- [ ] `region`
- [ ] `device`
- [ ] `external`
- [ ] `island`
- [ ] `whisper`
- [ ] `direct`
- [ ] `handover`
- [ ] `quarantine`
- [ ] ownership/domain graph canônico
- [ ] merges de domínio em branches/loops
- [ ] integração completa de cleanup/early return/defer
- [ ] lowering backend-neutral dos domains
- [ ] implementação/rejeição explícita por backend
- [ ] testes positivos + negativos + end-to-end por domínio

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
