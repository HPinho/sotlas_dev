# Sotlas — Historical Implementation Progress Snapshot (2026-09-25)

**Atualizado em:** 2026-09-25  
**Último baseline verde certificado:** `70a58e767b0812e2e2b3bc87cebaa9757a682a4b`  
**CI de referência:** Sotlas CI & Toolchain Build Farm #563 — `success`

> Snapshot histórico de 2026-09-25. Os percentuais abaixo não representam o status atual. Consulte [sotlas_implementation_status.md](sotlas_implementation_status.md) para o índice vigente e os percentuais certificados do Sotlas 1.0.

## Estado registrado no snapshot

```text
Fase 0 — Reality Reset              ~80%
Fase 1 — Typed Semantic Core       100% ✅
Fase 2 — Ownership Domains         100% ✅  (escopo Sotlas 1.0)
Fase 3 — Authority Domains         100% ✅  (escopo Sotlas 1.0)
Fase 4 — State Spaces               ~45% 🟡
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

O núcleo tipado, contratos de chamadas/retornos, ownership `sole`, safety básica, branches/loops estruturados e reality gates permanecem certificados. Extensões que excedem o subset necessário ao 1.0 continuam como maturação separada.

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

**Status do roadmap 1.0: ~45% 🟡 — EM CONSTRUÇÃO**

A Fase 4 já possui núcleo semântico backend-neutral, sintaxe pública e uma extensão Typed AST canônica integrável ao `Phase1CheckedModule`, mantendo o release gate público fechado até existir backend certificado.

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
- [x] gate de exaustividade para consumers;
- [x] parser oficial de produção reconhece declaração pública `space`;
- [x] AST fonte de `space`, estados, payload contracts e edges é preservada no `bootstrap.Module`;
- [x] sintaxe pública `Space<State>` é reconhecida no subset 1.0 quando existe `space Space`;
- [x] generics existentes continuam com a semântica anterior quando não existe State Space homônimo;
- [x] `StateSpaceFrontendPlan` reconcilia a AST fonte com `StateSpacePlan` e `StateQualifiedType`;
- [x] typestate direto por valor é revalidado contra o espaço correto; formas indiretas ainda não contratadas falham fechado;
- [x] `StateSpaceTypedSnapshot` congela State Spaces, payloads, edges e typestates em fatos Typed AST determinísticos;
- [x] sites de typestate possuem identidade determinística para parâmetros, retornos, campos, globals, enum payloads e locals tipados;
- [x] frontend e Typed AST são cruzados por multiset de fatos; divergência falha fechado;
- [x] o pipeline Phase 1 pode validar State Spaces em cópia privada do AST, sem mutar a fonte nem abrir o release gate;
- [x] `Phase1CheckedModule` passa a carregar o snapshot tipado de State Spaces no caminho opt-in;
- [x] `check` e emissão C/header continuam com gate PREVIEW explícito: State Spaces não são aceitos como compiláveis antes do SIR/backend certificado.

### Por que o gate PREVIEW continua intencional

Neste ponto o frontend e o pipeline semântico opt-in conseguem **entender e congelar** `space`/`Space<State>`, mas ainda não existe lowering 1.0 certificado para preservar transições até o backend. Portanto:

```text
parse                    ✅
source AST               ✅
semantic plan            ✅
Phase1 typed snapshot    ✅
production check SUPPORTED ❌ (fail-closed)
state transition SIR     ❌
backend                  ❌
```

Isso impede o compilador de retornar sucesso para um programa que o backend oficial ainda não consegue materializar corretamente.

### BLOCKERS restantes para fechar a Fase 4 no Sotlas 1.0

- [ ] definir a operação pública de transição em código Sotlas real;
- [ ] validar chamadas/retornos que efetivamente mudam typestate;
- [ ] preservar identidade source-stable das transições no SIR;
- [ ] revalidar source facts ↔ SIR fail-closed;
- [ ] lowering/backend mínimo do subset `SUPPORTED`;
- [ ] e2e positivo e negativo a partir de código Sotlas real;
- [ ] release gate garantindo `check => backend suportado`;
- [ ] integrar coverage ao consumidor público escolhido para o 1.0, sem exigir a UI DSL completa.

### DEFER 1.0.x / 1.1

- wildcard/guards sofisticados de coverage;
- pattern matching avançado de payloads;
- aliases/mapeamentos arbitrários entre tipo nominal e State Space;
- typestate indireto/reference forms além do subset inicial;
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

O caminho crítico permanece na **Fase 4 — State Spaces**. Com frontend e Typed AST conectados, o próximo blocker é definir a primeira operação de transição source-stable em código Sotlas real e levá-la ao SIR sem inventar transições implícitas.
