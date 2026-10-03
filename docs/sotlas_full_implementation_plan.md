# Sotlas — Full Implementation Plan

**Status do documento:** PLANO VIVO  
**Atualizado em:** 2026-09-29 (America/Fortaleza)  
**Baseline verde atual:** `ddf0353d804bbd1fc3387931c702104b364be637`  
**Último avanço funcional certificado:** `3c66cd305b8af3ab65521445ca0544f060ef74e0`  
**CI de referência:** Sotlas CI & Toolchain Build Farm #938 — `success`  
**Fonte arquitetural principal:** `docs/sotlas_master_roadmap.md`  
**Índice operacional do 1.0:** `docs/sotlas_implementation_status.md`

> Este arquivo acompanha a implementação ampla da linguagem Sotlas além dos
> contratos delimitados do Sotlas 1.0. Um status `COMPLETE` no índice 1.0 não
> significa que toda a visão do Master Roadmap esteja implementada. O objetivo
> deste plano é manter visíveis, em um único lugar, o que já está realmente
> executável, o que está em hardening, o que permanece PREVIEW e o que ainda
> precisa ser construído para a linguagem alcançar a visão arquitetural completa.

---

## 1. Regra central do desenvolvimento

Nenhuma feature deve ser tratada como pronta somente porque possui parser, AST,
modelo semântico isolado, relatório ou protótipo.

A trilha normal de promoção é:

```text
SPECIFICATION
      ↓
PARSER
      ↓
TYPED AST
      ↓
SEMANTIC CHECK
      ↓
CANONICAL SIR
      ↓
TARGET IR / BACKEND CONTRACT
      ↓
BACKEND
      ↓
POSITIVE TEST
      ↓
NEGATIVE TEST
      ↓
END-TO-END TEST
      ↓
CI VERDE
      ↓
SUPPORTED NO ESCOPO DECLARADO
```

Regras de engenharia obrigatórias:

1. nunca contornar, remover ou enfraquecer testes apenas para obter CI verde;
2. uma regressão bloqueia o avanço de novas features até a baseline ser
   recuperada;
3. uma unidade lógica de desenvolvimento deve resultar em um commit atômico;
4. formas ainda não suportadas devem falhar fechado antes de lowering incorreto;
5. `compiler/` é a implementação instalada canônica; `tools/` permanece apenas
   enquanto necessário para compatibilidade histórica e deve convergir para a
   árvore canônica;
6. Baken, kernel, UI, engine, IA ou qualquer projeto consumidor nunca devem
   receber bypasses específicos dentro da linguagem;
7. quando um consumidor exigir uma primitiva inexistente, a primitiva deve ser
   implementada primeiro de forma geral em parser/semântica/SIR/backend/testes;
8. nenhuma capacidade PREVIEW deve ser descrita como suporte geral da linguagem;
9. LLVM e C11 podem continuar como backends de produção enquanto o backend
   Sotlas-owned amadurece; a substituição deve ser progressiva e comprovada;
10. o Master Roadmap representa a visão ampla; os documentos de release 1.0
    representam subsets deliberadamente limitados.

---

## 2. Objetivo de produto

Sotlas deve evoluir como linguagem geral e soberana, capaz de atender, sem ser
especializada em apenas um deles:

- aplicações nativas;
- firmware e UEFI;
- bootloaders;
- kernels e sistemas operacionais;
- drivers e runtimes;
- bibliotecas e CLIs;
- desktop, UI, compositor e animações;
- game engines e jogos;
- bancos de dados;
- networking;
- áudio e vídeo;
- computação científica e HPC;
- GPU/NPU/heterogeneous compute;
- runtimes de IA, treinamento e inferência;
- compiladores e ferramentas;
- eventualmente o próprio compilador, backend e toolchain Sotlas.

O caminho de longo prazo é:

```text
SOURCE SOTLAS
    ↓
CANONICAL FRONTEND
    ↓
TYPED SEMANTICS
    ↓
OWNERSHIP / AUTHORITY / STATE / EFFECTS / FLOW / TRUST / GUARANTEES
    ↓
CANONICAL SIR
    ↓
TARGET IR
    ↓
┌──────────────────┬──────────────────┬──────────────────┐
│ Sotlas machine   │ LLVM production  │ C11 portability  │
│ backend          │ backend          │ backend          │
└──────────────────┴──────────────────┴──────────────────┘
    ↓
OBJECTS / EXECUTABLES / FIRMWARE / KERNELS / RUNTIMES
```

---

## 3. Estado atual certificado

### 3.1 Contratos Sotlas 1.0

O índice `docs/sotlas_implementation_status.md` registra as Fases 0–17 como
`COMPLETE` para seus contratos deliberadamente delimitados do 1.0. Isso inclui
subsets certificados de:

- Typed Semantic Core;
- Ownership Domains;
- Authority Domains;
- State Spaces;
- Effects;
- Flow;
- Execution Domains;
- Heterogeneous Compute de referência;
- Trust Domains;
- Guarantees;
- Causality;
- Counterfactuals;
- Transactions;
- Intent;
- SIR canônico;
- backend LLVM nativo;
- tooling determinístico.

Essa conclusão não fecha as generalizações do Master Roadmap.

### 3.2 Target profiles e barecore

Já existe contrato canônico de perfil fonte:

```sotlas
target native;
target barecore;
target web;
```

com `barecore;` como spelling transitório aceito.

Estado atual:

- [x] parser canônico preserva perfil e localização fonte;
- [x] ausência de declaração mantém compatibilidade `native`;
- [x] `barecore` influencia o driver público;
- [x] target físico e execution profile são reconciliados em contrato canônico;
- [x] combinações `barecore` + target hosted contraditório falham fechado;
- [x] C11 barecore é auditado contra dependências hosted conhecidas;
- [x] `sotlas run` rejeita barecore;
- [x] artefato barecore não cai silenciosamente em link hosted;
- [ ] linker freestanding completo ainda não está certificado;
- [ ] entrypoint/ABI de boot genérico ainda não está fechado;
- [ ] ELF/PE/EFI freestanding próprio ainda precisa de caminho E2E completo;
- [ ] `target web` continua fail-closed no caminho nativo atual.

### 3.3 Backend de máquina próprio — primeiro slice certificado

Baseline `3c66cd30` introduz o primeiro slice executável Sotlas-owned em x86-64
SysV sobre Target IR canônico.

Já certificado:

- [x] Target IR como entrada do machine backend;
- [x] liveness/interference já existentes alimentam allocation real;
- [x] virtual registers são mapeados para `r10`/`r11`;
- [x] spills reais usam slots de stack;
- [x] `alloc_stack` possui slots locais separados dos spills;
- [x] `store`/`load` materializam memória local real;
- [x] frame é alinhado a 16 bytes;
- [x] argumentos inteiros SysV em registradores no subset atual;
- [x] `u8`, `u16`, `u32`, `u64`, `usize`;
- [x] `const_int`, `add`, `sub`, `mul`, `return`;
- [x] signed arithmetic permanece fail-closed até overflow Sotlas ser definido;
- [x] funções fora do subset falham fechado;
- [x] E2E Linux executa assembly produzido pelo backend Sotlas-owned;
- [x] `compiler/` e `tools/` permanecem byte-idênticos para esse backend.

Ainda não suportado nesse backend próprio:

- [ ] compare instruction selection;
- [ ] branches;
- [ ] conditional branches;
- [ ] labels/CFG arbitrário;
- [ ] phi lowering/coalescing;
- [ ] loops gerais;
- [ ] calls;
- [ ] stack-passed arguments;
- [ ] callee-saved register management amplo;
- [ ] Windows x64 ABI;
- [ ] macOS symbol/ABI completion;
- [ ] AArch64;
- [ ] floats/SIMD;
- [ ] aggregate ABI;
- [ ] structs/enums/slices/strings;
- [ ] unwind/debug metadata;
- [ ] direct object emission sem assembler externo;
- [ ] linker Sotlas-owned geral.

---

## K. Kernel / Barecore Implementation Track

Este track acompanha especificamente o caminho necessário para Sotlas produzir
e executar kernels reais, sem transformar a linguagem em uma linguagem
específica do Baken. O Baken pode funcionar como consumidor e prova E2E, mas
qualquer primitiva descoberta durante esse trabalho deve ser implementada como
capacidade geral da linguagem/toolchain.

### K.1 Regra de maturidade do kernel

A existência de `bootstrap/sotlas/kernel/main.sotlas`, `kernel_main`, estruturas
de boot ou chamadas de serial/framebuffer **não** significa que o kernel já seja
bootável pela toolchain Sotlas de ponta a ponta.

Enquanto a cadeia abaixo não estiver certificada, o kernel permanece um
**bootstrap/source contract + preview de integração**:

```text
kernel .sotlas
    ↓
canonical frontend
    ↓
typed semantics
    ↓
canonical SIR
    ↓
freestanding object
    ↓
freestanding linker
    ↓
bootable image
    ↓
QEMU / firmware
    ↓
Sotlas entrypoint executes
    ↓
observable serial/framebuffer proof
```

O primeiro marco que pode ser chamado de **kernel bootável certificado** exige
essa cadeia completa, um gate E2E e ausência de dependências hosted implícitas.

### K.2 Estado fonte atual

O kernel canônico atual em `bootstrap/sotlas/kernel/main.sotlas` já possui:

- [x] `barecore;` antes da declaração do módulo;
- [x] módulo `kernel::minimal`;
- [x] `BootFrame` com `@repr(C)` e `@packed`;
- [x] `kernel_main(frame: *mut BootFrame) -> u64` exportado e `@system`;
- [x] contrato fonte para framebuffer;
- [x] chamadas fonte para serial;
- [x] desenho fonte mínimo em framebuffer;
- [x] gate impedindo dependências hosted óbvias no bootstrap;
- [ ] boot real desse arquivo ainda não é certificado.

`tests/test_sotlas_kernel_freestanding_profile.py` fixa o perfil barecore, o
contrato ABI fonte de `BootFrame`/`kernel_main` e a ausência de chamadas hosted
óbvias. Esse teste é evidência do contrato fonte, não de boot E2E.

### K.3 Milestones K0–K14

| Milestone | Objetivo | Estado atual | Critério de saída |
|---|---|---|---|
| **K0** | Target profile freestanding | ✅ CERTIFICADO | `barecore` reconhecido pelo frontend, reconciliado com target freestanding e impedido de cair silenciosamente em execução/link hosted |
| **K1** | Kernel source/ABI bootstrap | ✅ CONTRATO FONTE | kernel canônico declara `barecore`, `BootFrame` e `kernel_main`; testes protegem ABI fonte e hosted-dependency guard |
| **K2** | Objeto freestanding real | 🟡 PARCIAL | fonte barecore produz `.o` freestanding verificável; nenhuma fallback path pode gerar executável hosted; caminho Sotlas-owned de objeto continua milestone posterior |
| **K3** | Linker ELF freestanding | 🟡 PREVIEW | target/link plan usa semântica freestanding canônica, entry explícito, OSABI/layout corretos e relocações certificadas; nenhuma heurística hosted pode decidir o layout |
| **K4** | Boot ABI / startup / entry | ⬜ PENDENTE | definir `_start`/entry genérico, estado inicial da stack/CPU, handoff do bootloader e chamada explícita para a entrada Sotlas sem alias silencioso de `kernel_main` |
| **K5** | Sections e image layout | ⬜ PENDENTE | `.text/.rodata/.data/.bss`, alinhamentos, endereços e símbolos especiais possuem contrato freestanding verificável e configuração explícita |
| **K6** | Imagem bootável | ⬜ PENDENTE | objeto(s) + linker geram uma imagem consumível pelo boot path escolhido sem libc/CRT/startup hosted |
| **K7** | QEMU boot E2E | ⬜ PENDENTE | CI inicia a imagem, chega ao entry Sotlas e verifica marcador determinístico por serial ou mecanismo equivalente |
| **K8** | Early diagnostics | 🟡 SOURCE PREVIEW | serial/framebuffer do bootstrap tornam-se E2E reais; falhas iniciais têm caminho freestanding de panic/trap e diagnóstico mínimo |
| **K9** | CPU early setup | ⬜ PENDENTE | GDT/IDT/exception/IRQ setup no x86-64 usa calling/interrupt contracts Sotlas certificados, sem glue específico de produto dentro do compilador |
| **K10** | Memory management | ⬜ PENDENTE | memory map/handoff, physical pages, paging/address spaces e allocator freestanding possuem APIs e ownership/lifetime definidos |
| **K11** | Timer e scheduler | ⬜ PENDENTE | timer/clock + interrupt integration + scheduler mínimo executam com efeitos/authority apropriados; primitivas são reutilizáveis por qualquer kernel Sotlas |
| **K12** | Drivers / MMIO / PCI / DMA | ⬜ PENDENTE | volatile/MMIO, port I/O, PCI, IRQ e DMA usam primitives gerais de Authority/Ownership/Effects; pelo menos um driver E2E é certificado |
| **K13** | UEFI / PE-COFF path | ⬜ PENDENTE | caminho UEFI é separado do ELF bare-metal quando necessário, com ABI, entry e image format próprios e testes em firmware virtual |
| **K14** | Kernel majoritariamente Sotlas / soberania | ⬜ LONGO PRAZO | kernel, runtime necessário e toolchain crítica deixam de depender de bridges ad hoc; self-host/backend próprio avançam sem remover Stage 0 antes da paridade |

**K3 local hardening candidate (CI pending):** the internal ELF linker now requires
the requested entry to resolve to bytes in an executable section, rejects duplicate
strong symbols and invalid relocation targets, applies relocations to the correctly
aligned section slice, and uses the same virtual-address layout for relocation and
`PT_LOAD` emission. Synthetic ELF tests cover the exact entry, missing and
non-executable entries, section alignment, relocation bounds and overflow. This
does not certify compiler-generated kernel objects, a bootable image, or a QEMU
boot; K3 remains in preview until those integration gates run.

### K.4 Dependências do track de kernel

O track de kernel não é uma trilha isolada. Ele depende diretamente de outras
partes do plano:

- **K2–K3:** Fase 16 / M16.6, execution targets e linker freestanding;
- **K4–K5:** calling conventions, entry functions, linker sections e symbol model;
- **K7:** CI/reality gates e execução QEMU determinística;
- **K8:** `core::serial`, framebuffer, freestanding panic/trap;
- **K9:** interrupt ABI, CPU intrinsics, port I/O e Authority Domains;
- **K10:** pointers/address spaces, integer semantics, atomics, allocator e Ownership;
- **K11:** effects, interrupt/realtime safety, clock e concurrency;
- **K12:** MMIO/volatile, `device`, DMA, Authority/Effects/Ownership;
- **K13:** PE/COFF/UEFI backend/linker/ABI específicos;
- **K14:** self-host, Sotlas-owned backend, runtime e stdlib freestanding.

### K.5 Ordem operacional recomendada

O caminho crítico imediato do kernel é:

```text
K0/K1 certificados
      ↓
K2 freestanding object contract
      ↓
K3 linker target contract
      ↓
K4 entry/startup ABI
      ↓
K5 sections/layout
      ↓
K6 bootable image
      ↓
K7 QEMU E2E
```

Depois do primeiro boot certificado, avançar K8–K12 de maneira incremental,
sempre promovendo para a linguagem qualquer primitiva geral descoberta.

O backend próprio M16.2–M16.6 pode evoluir em paralelo. O primeiro boot não
precisa esperar a remoção de LLVM se o caminho LLVM usado estiver corretamente
freestanding e certificado; a substituição por backend/object writer Sotlas-owned
é um objetivo de soberania posterior, não justificativa para fingir que o boot
já existe hoje.

### K.6 O que nunca deve ser feito para “fechar” o kernel

- não colocar UI, wallpaper, Baken, framebuffer específico ou lógica de produto
  dentro do compilador;
- não tratar `kernel_main` como `_start` por alias implícito;
- não usar linker hosted por trás de um target barecore;
- não esconder libc/CRT/startup objects no artefato final;
- não usar um endereço de carga universal sem contrato/configuração explícitos;
- não marcar serial/framebuffer como E2E enquanto apenas o código fonte existir;
- não contornar SIR/backend com C específico do Baken;
- não enfraquecer testes de barecore para obter uma imagem que apenas “pareça”
  bootável.

---

## 4. Matriz ampla por fase do Master Roadmap

A tabela abaixo descreve o trabalho além dos subsets 1.0 já certificados.

| Fase | Área | Contrato 1.0 | Implementação ampla restante |
|---:|---|---|---|
| 0 | Reality Reset | COMPLETE | consolidar definitivamente árvores duplicadas, reduzir adapters históricos, manter claims públicos aderentes ao código real |
| 1 | Typed Semantic Core | COMPLETE | generalizar tipos, expressões, mutabilidade, aggregates, generics, traits/interfaces e diagnósticos sem depender de caminhos legados |
| 2 | Ownership Domains | COMPLETE | ARC/shared em CFG arbitrário, payloads gerais, region totalmente geral, weak invalidation, handover amplo, device/external completos |
| 3 | Authority Domains | COMPLETE | catálogo amplo de capabilities, capabilities como valores, propagação interprocedural geral, hardware/OS authority policies completas |
| 4 | State Spaces | COMPLETE no subset | pattern/payload coverage ampla, references/aliases, path-dependent merges, integração geral com UI/network/persistência |
| 5 | Effects | COMPLETE no subset | inferência interprocedural geral, budgets, interrupt/realtime safety ampla, efeitos extensíveis e integração com otimização/scheduler |
| 6 | Flow | COMPLETE no subset | CFG arbitrário, payloads ownership-bearing, scheduler nativo completo, GPU/NPU execution providers e failure semantics amplas |
| 7 | Execution Domains | COMPLETE no subset | targets físicos amplos, affinity/runtime, barecore completo, cross-target ABI, heterogeneous execution policies |
| 8 | Heterogeneous Compute | COMPLETE no reference subset | hardware/DMA reais, completion física, sync, timeout/failure, GPU/NPU providers, device matrix |
| 9 | Trust Domains | COMPLETE no subset | isolamento real/sandbox, wrappers/policies gerais, FFI ABI/lifetime amplos, trust propagation completa |
| 10 | Guarantees | COMPLETE no subset | proof language mais ampla, runtime fallback quando apropriado, bounds/contract proofs mais gerais, proof artifacts estáveis |
| 11 | Causality | COMPLETE no subset | mutação, aliases complexos, CFG geral, causal graph amplo entre domains/effects/state e debugger causal |
| 12 | Counterfactuals | COMPLETE no subset | equivalência mais poderosa, state/rollback geral, cenários fora de Flow, custo/efeitos/targets heterogêneos |
| 13 | Transactions | COMPLETE no subset | snapshots, inverse verification, crash recovery, concurrent journals, external atomicity models |
| 14 | Intent | COMPLETE no API subset | sintaxe fonte declarativa, goals tipados, integração com guarantees/ownership/scheduler e planejamento mais geral |
| 15 | Canonical SIR | COMPLETE no subset | arbitrary source-body lowering, aggregates/ABI completos, representação estável, máquina/ownership cleanup geral |
| 16 | Native Machine Backend | COMPLETE LLVM 1.0 + machine slice inicial | backend Sotlas-owned completo, ABIs, regalloc avançado, CFG, objects, linker, multi-arch |
| 17 | Tooling avançado | COMPLETE nos relatórios 1.0 | debugger causal, views interativas, safety explorer, ABI/stack/regalloc visualization, source→instruction mapping |

---

## 5. Backlog técnico amplo por área

### 5.1 Typed Semantic Core

Objetivo: remover lacunas em que a linguagem compreende apenas formas
estruturadas específicas.

- [ ] completar cobertura de expressões escalares e constant expressions;
- [ ] completar divisão, resto, shifts, bitwise e conversões com semântica Sotlas;
- [ ] definir e implementar promotion/conversion rules canônicas;
- [ ] mutabilidade geral com análise consistente no frontend/SIR;
- [ ] aggregate literals e aggregate mutation de forma canônica;
- [ ] arrays/slices com bounds model integrado aos Guarantees;
- [ ] strings e representação runtime estável;
- [ ] enums/variants com payload lowering geral;
- [ ] generics generalizados além dos subsets atuais;
- [ ] traits/interfaces/protocols conforme especificação escolhida;
- [ ] closures/lambdas quando o contrato público for definido;
- [ ] diagnóstico source-stable uniforme em todos os caminhos.

### 5.2 Integer semantics

O Master Roadmap exige que overflow não dependa silenciosamente de UB de C.

Implementar modos explícitos:

- [ ] `checked`;
- [ ] `wrapping`;
- [ ] `saturating`;
- [ ] `unchecked` com contrato definido;
- [ ] comportamento padrão da linguagem;
- [ ] semântica para add/sub/mul/div/neg/shifts;
- [ ] lowering idêntico em C11, LLVM e machine backend;
- [ ] differential tests entre backends;
- [ ] signed arithmetic liberada no machine backend somente depois desse contrato.

### 5.3 Ownership Domains

#### `sole` / `exclusive`

- [ ] cleanup backend-neutral completo;
- [ ] moves/returns/fields/payloads em CFG arbitrário;
- [ ] aggregates e containers ownership-bearing;
- [ ] unwinding/failure cleanup quando aplicável;
- [ ] interprocedural analysis mais geral.

#### `shared`

- [ ] ARC geral em CFG arbitrário;
- [ ] aliases e assignments complexos;
- [ ] payloads/layouts arbitrários;
- [ ] defer + shared + controle arbitrário;
- [ ] otimização de retain/release preservando semântica;
- [ ] integração ampla com machine backend.

#### `region`

- [ ] topologias CFG gerais;
- [ ] merges altamente path-dependent;
- [ ] ciclos/recursão gerais;
- [ ] arena runtime mais amplo;
- [ ] containers e aggregates region-owned;
- [ ] E2E multi-backend mais amplo.

#### `whisper` / `direct`

- [ ] weak invalidation geral;
- [ ] borrow em ABI/backend amplos;
- [ ] storage/escape rules completas;
- [ ] FFI e async interaction explicitamente definidas.

#### `device`

- [ ] runtime CPU↔device real;
- [ ] ownership transfer para hardware;
- [ ] async completion;
- [ ] fences/sync;
- [ ] timeout/failure;
- [ ] GPU/NPU/DMA providers.

#### `external`

- [ ] ABI/layout geral;
- [ ] lifetime FFI geral;
- [ ] callbacks;
- [ ] ownership crossing FFI;
- [ ] foreign allocator/deallocator contracts.

### 5.4 Authority Domains

- [ ] capabilities como valores tipados em fluxo normal;
- [ ] acquisition/revocation/lifetime de capability;
- [ ] authority graph interprocedural geral;
- [ ] delegação explícita;
- [ ] menor autoridade provável pelo compiler;
- [ ] catálogo de filesystem/network/process/thread/clock/random;
- [ ] catálogo de PCI/MMIO/DMA/IRQ/GPU;
- [ ] políticas específicas para interrupt/realtime/barecore;
- [ ] source-stable diagnostics completos.

### 5.5 State Spaces / Typestate

- [ ] payload pattern matching geral;
- [ ] coverage com guards/wildcards quando formalizado;
- [ ] aliases/references de typestate;
- [ ] merges path-dependent gerais;
- [ ] state transitions em CFG arbitrário;
- [ ] integração ownership + state;
- [ ] state + transaction rollback;
- [ ] consumers de UI/persistência/networking;
- [ ] otimização de representação sem perder proof facts.

### 5.6 Effects

- [ ] effect inference interprocedural geral;
- [ ] propagation through higher-order/generic code;
- [ ] effect polymorphism se adotado;
- [ ] budgets de allocation/latency quando verificáveis;
- [ ] interrupt safety ampla;
- [ ] realtime safety ampla;
- [ ] call graph restrictions;
- [ ] integração com authority/trust/state/flow;
- [ ] effect-aware optimization e scheduling.

### 5.7 Flow

- [ ] CFG de stages arbitrário;
- [ ] valores ownership-bearing;
- [ ] state-bearing payloads;
- [ ] transactional flow execution geral;
- [ ] scheduler nativo sem Python como production runtime;
- [ ] deterministic parallel execution contract;
- [ ] cancellation/failure source-level;
- [ ] GPU/NPU stages;
- [ ] scheduling por capabilities/effects/targets;
- [ ] backpressure/streaming quando especificado.

### 5.8 Execution Domains e targets

- [ ] resolução completa profile + architecture + ABI;
- [ ] x86-64 hosted amplo;
- [ ] x86-64 barecore amplo;
- [ ] AArch64 hosted;
- [ ] AArch64 barecore;
- [ ] Windows x64 ABI;
- [ ] macOS ABI;
- [ ] Web/WASM quando o contrato for implementado;
- [ ] CPU feature model consumido pelo backend próprio;
- [ ] feature detection/dispatch;
- [ ] target-specific diagnostics consistentes.

### 5.9 Heterogeneous Compute

- [ ] hardware provider interface estável;
- [ ] DMA buffers reais;
- [ ] GPU memory spaces;
- [ ] host/device synchronization;
- [ ] events/fences;
- [ ] timeout/failure/recovery;
- [ ] provider CPU;
- [ ] provider GPU;
- [ ] provider NPU;
- [ ] multi-device scheduling;
- [ ] ownership + authority + effects integrados ao provider.

### 5.10 Trust Domains / FFI

- [ ] isolation real para `isolated`;
- [ ] sandbox target-aware;
- [ ] unsafe boundary enforcement geral;
- [ ] wrappers verificados;
- [ ] callback boundaries;
- [ ] FFI aggregate ABI;
- [ ] foreign exceptions/errors policy;
- [ ] external ownership/lifetime;
- [ ] symbol visibility/linkage model completo.

### 5.11 Guarantees / Contracts / Proofs

- [ ] proof engine deliberadamente limitado mas geral o suficiente para bounds;
- [ ] `requires` e `ensures` em CFG mais amplo;
- [ ] contract propagation interprocedural;
- [ ] dynamic check fallback onde o contrato permitir;
- [ ] freestanding trap/panic para contracts barecore;
- [ ] proof artifacts estáveis;
- [ ] machine-code/source mapping para guarantees críticas;
- [ ] integração com state/authority/effects/ownership.

### 5.12 Causality

- [ ] mutação;
- [ ] aliases não triviais;
- [ ] branches/loops gerais;
- [ ] ownership transfer causality;
- [ ] state transition causality;
- [ ] effect/authority causality;
- [ ] causal graph interprocedural amplo;
- [ ] debugger causal interativo.

### 5.13 Counterfactuals

- [ ] equivalência além do subset unsigned puro;
- [ ] state-aware alternatives;
- [ ] ownership-aware alternatives;
- [ ] rollback-aware alternatives;
- [ ] target/device alternatives;
- [ ] effects/cost comparison;
- [ ] scenarios outside Flow;
- [ ] proof evidence explícita para cada alternativa.

### 5.14 Transactions

- [ ] snapshots;
- [ ] inverse operations verificadas;
- [ ] journaling;
- [ ] crash recovery;
- [ ] concurrent transaction semantics;
- [ ] external effect atomicity model explícito;
- [ ] nested transactions se adotadas;
- [ ] ownership/state interaction geral.

### 5.15 Intent

- [ ] sintaxe Sotlas fonte;
- [ ] typed goals;
- [ ] constraints de effects/authority/state;
- [ ] preferred/fallback source declarations;
- [ ] planner integrado ao scheduler;
- [ ] ownership-aware execution;
- [ ] proof/guarantee-aware planning;
- [ ] explainability de seleção/rejeição.

### 5.16 Canonical SIR

- [ ] lowering de corpos fonte gerais;
- [ ] CFG arbitrário;
- [ ] aggregates;
- [ ] calls/methods/generics completos;
- [ ] ownership cleanup canônico;
- [ ] effect/authority/state/trust facts preservados integralmente;
- [ ] debug/source locations amplas;
- [ ] serialization/versioning estáveis se adotados;
- [ ] verifier independente forte;
- [ ] pass manager/optimization contracts.

### 5.17 Backend de máquina Sotlas-owned

#### Milestone M16.1 — scalar linear x86-64

- [x] Target IR input;
- [x] liveness/interference;
- [x] register assignment consumido pelo emitter;
- [x] spills;
- [x] stack locals;
- [x] constants;
- [x] unsigned add/sub/mul;
- [x] return;
- [x] native E2E Linux.

#### Milestone M16.2 — comparisons + control flow

- [ ] integer comparisons;
- [ ] bool materialization;
- [ ] labels;
- [ ] unconditional branch;
- [ ] conditional branch;
- [ ] phi resolution on edges;
- [ ] critical-edge handling quando necessário;
- [ ] E2E `if/else`;
- [ ] E2E bounded loop.

#### Milestone M16.3 — calls e ABI

- [ ] direct calls;
- [ ] return values;
- [ ] first six SysV integer arguments;
- [ ] stack arguments;
- [ ] stack alignment across calls;
- [ ] caller/callee-saved policy;
- [ ] recursion contract;
- [ ] symbol visibility/linkage;
- [ ] multi-function E2E.

#### Milestone M16.4 — aggregates

**Current local increment — M16.4h2e2c2 (CI certification pending).** The central
x86-64 SysV aggregate transport plan now consumes certified nominal tagged-union
classifications. It assigns one or two INTEGER eightbytes to argument and return
registers, records MEMORY-class parameters as stack-passed units, reserves `rdi`
for hidden `sret`, and shifts following integer arguments accordingly. Register
exhaustion spills an entire enum value instead of partially consuming registers.
The gate covers source-derived `MaybeToken`, 16-byte and MEMORY-class enums,
mixed scalar arguments, planner parity, and fail-closed SSE and uncertified-layout
cases. This stage plans ABI locations only; it does not emit enum construction,
payload extraction, or machine instructions. The Windows run also skips the
Linux-only native execution gates.

- [ ] pointers;
- [ ] address calculation;
- [ ] struct fields;
- [ ] fixed arrays;
- [ ] enum representation;
- [ ] slices;
- [ ] ABI classification;
- [ ] ownership-bearing aggregates.

#### Milestone M16.5 — arithmetic completeness

- [ ] division/remainder;
- [ ] bitwise;
- [ ] shifts;
- [ ] conversions;
- [ ] signed integer modes;
- [ ] float32/float64;
- [ ] SIMD foundation.

#### Milestone M16.6 — object emission

- [ ] machine instruction encoding;
- [ ] sections;
- [ ] symbols;
- [ ] relocations;
- [ ] ELF relocatable objects;
- [ ] debug/unwind metadata contract;
- [ ] object E2E without external assembler.

#### Milestone M16.7 — additional ABIs/architectures

- [ ] Windows x64;
- [ ] macOS x86-64 completion;
- [ ] AArch64 instruction selector;
- [ ] AArch64 ABI;
- [ ] architecture-neutral machine IR/register classes.

### 5.18 Linker e freestanding

- [ ] target-neutral link plan;
- [ ] explicit entrypoint contract;
- [ ] ELF executable/image layout;
- [ ] sections and alignment;
- [ ] relocations;
- [ ] freestanding symbols;
- [ ] linker script equivalent/config format;
- [ ] kernel load address policy;
- [ ] UEFI/PE-COFF path quando necessário;
- [ ] no implicit libc/startup objects;
- [ ] barecore E2E in QEMU;
- [ ] diagnostics para símbolos/relocations/layout inválidos.

### 5.19 Systems primitives

Para permitir kernels, drivers e runtimes sem atalhos de produto:

- [ ] volatile load/store canônicos;
- [ ] atomics completos e memory order;
- [ ] MMIO abstractions;
- [ ] port I/O generalizado por authority;
- [ ] CPU intrinsics target-aware;
- [ ] calling conventions;
- [ ] interrupt ABI;
- [ ] naked/entry functions se o contrato for adotado;
- [ ] linker sections/attributes;
- [ ] physical/address-space pointer contracts;
- [ ] page-table friendly integer/pointer operations;
- [ ] freestanding panic/trap;
- [ ] no-stdlib core subset.

### 5.20 Runtime e standard library

- [ ] allocator interface estável;
- [ ] freestanding allocator hooks;
- [ ] Vec/dynamic arrays;
- [ ] strings;
- [ ] slices completas;
- [ ] hash map/set;
- [ ] result/error abstractions conforme linguagem;
- [ ] filesystem;
- [ ] sockets/network;
- [ ] threads;
- [ ] synchronization;
- [ ] async runtime se adotado;
- [ ] time/clock/random;
- [ ] process APIs;
- [ ] math/numerics;
- [ ] SIMD abstractions;
- [ ] testing library;
- [ ] package-level stable APIs.

### 5.21 Self-host compiler

Arquitetura desejada:

```text
Python Stage 0
    ↓ compila
Sotlas Stage 1
    ↓ compila a si mesmo
Sotlas Stage 2
    ↓
fixed point / reproducibility
```

Trabalho:

- [ ] lexer Sotlas parity;
- [ ] parser Sotlas parity;
- [ ] AST parity;
- [ ] semantic/type checker parity;
- [ ] Ownership/Authority/State/Effects parity;
- [ ] canonical SIR builder em Sotlas;
- [ ] C emitter parity como bootstrap inicial;
- [ ] CLI/compiler driver em Sotlas;
- [ ] Stage0→Stage1 E2E;
- [ ] Stage1→Stage2;
- [ ] compare Stage1/Stage2 outputs;
- [ ] remover dependência Python somente depois de paridade comprovada;
- [ ] posteriormente conectar o compilador self-host ao backend Sotlas-owned.

### 5.22 Tooling

- [ ] LSP com todos os novos facts sem parser duplicado;
- [ ] formatter estável;
- [ ] package manager hardening;
- [ ] build graph incremental;
- [ ] dependency lock/reproducibility;
- [ ] causal debugger;
- [ ] State/Authority/Ownership graph viewer;
- [ ] safety explorer;
- [ ] register allocation viewer;
- [ ] ABI/stack frame viewer;
- [ ] source→SIR→Target IR→machine mapping;
- [ ] profiler hooks;
- [ ] test runner first-class;
- [ ] documentation generator.

### 5.23 Ecosystem e distribuição

- [ ] release reproducível;
- [ ] signed artifacts quando a política for definida;
- [ ] stable package registry workflow;
- [ ] version/dependency resolution hardened;
- [ ] standard library versioning;
- [ ] compatibility policy;
- [ ] platform support matrix;
- [ ] examples que reflitam apenas suporte real;
- [ ] GitHub Linguist/extension lifecycle;
- [ ] public documentation generated from certified contracts.

---

## 6. Ordem recomendada de implementação

O desenvolvimento não precisa fechar uma fase inteira antes de tocar a próxima.
A ordem abaixo prioriza dependências que desbloqueiam várias áreas ao mesmo tempo.

### Prioridade P0 — preservar baseline e realidade

Sempre ativa:

- CI verde antes de nova feature;
- no test bypass;
- reality gates;
- compiler/tools parity enquanto a duplicação existir;
- claims públicos coerentes;
- unsupported fail-closed.

### Prioridade P1 — tornar o backend próprio realmente geral

Próximos blocos preferenciais:

1. comparisons + bool lowering;
2. unconditional/conditional branch;
3. phi resolution;
4. bounded loops;
5. direct calls;
6. ABI de chamadas SysV completa para escalares;
7. register classes/callee-saved;
8. pointer/address operations;
9. aggregates básicos;
10. signed integer modes depois do contrato de overflow.

Critério de saída P1:

```text
Sotlas source
  → checked semantics
  → canonical SIR
  → Target IR
  → Sotlas register allocation
  → Sotlas instruction selection
  → assembly
  → native executable
```

para programas multi-block e multi-function representativos.

### Prioridade P2 — object emission + linker + barecore

Depois que o backend possuir CFG/calls suficientes:

1. encoder x86-64;
2. ELF object writer;
3. relocations/symbols;
4. internal linker freestanding;
5. entrypoint contract;
6. kernel ELF E2E;
7. QEMU boot gate;
8. UEFI/PE path separada quando necessária.

Esses itens correspondem diretamente aos milestones **K2–K7** e **K13** do
Kernel / Barecore Track. O boot inicial pode usar o backend LLVM certificado
enquanto o object writer Sotlas-owned amadurece, desde que todo o caminho seja
realmente freestanding e fail-closed.

Critério de saída P2:

```text
.sotlas
  ↓
Sotlas-owned machine backend
  ↓
.o sem assembler externo
  ↓
Sotlas linker
  ↓
freestanding image
  ↓
QEMU executes Sotlas entrypoint
```

### Prioridade P3 — semântica geral da linguagem

Em paralelo e sem depender totalmente do backend:

- integer overflow modes;
- remaining arithmetic;
- mutable CFG;
- aggregates;
- state/ownership/effects generalization;
- guarantees/contracts;
- trust/FFI;
- richer Flow execution.

Cada extensão deve chegar pelo menos a C11/LLVM enquanto o backend próprio ainda
não tiver o shape necessário, mas não deve ser marcada como suportada pelo
machine backend antes do lowering correspondente.

### Prioridade P4 — runtimes e standard library

Quando types/ownership/error model estiverem estáveis o suficiente:

- allocator;
- collections;
- strings/slices;
- filesystem/network/threading;
- numerics;
- async/concurrency;
- heterogeneous runtime.

### Prioridade P5 — self-host

Avançar continuamente, mas sem remover Python Stage 0 prematuramente.

Meta intermediária:

```text
Stage0 Python compila Stage1 Sotlas
Stage1 compila Stage2
Stage1 ≈ Stage2
```

Só depois discutir Stage0 retirement.

### Prioridade P6 — tooling e ecosystem

Ampliar depois que os contracts consumidos estiverem estáveis, evitando
ferramentas que dependam de AST/SIR instáveis sem versionamento.

---

## 7. Próximos commits atômicos sugeridos

Esta lista é operacional e pode ser atualizada a cada baseline verde.

### M16.2a — compare instruction selection

- Target IR `compare` → `cmp` + `setcc`/materialização bool;
- unsigned predicates primeiro;
- signed predicates apenas quando não dependerem de overflow indefinido;
- positive/negative tests;
- native E2E.

### M16.2b — branches

- labels determinísticos;
- `branch`;
- `cond_branch`;
- validator de terminators;
- E2E `if/else`.

### M16.2c — phi

- edge copies;
- parallel-copy handling;
- integração com register allocation;
- E2E merge de `if`.

### M16.2d — bounded loop

- backedges;
- phi loop-carried;
- compare + branch;
- accumulator/counter;
- E2E loop equivalente ao subset LLVM certificado.

### M16.3a — direct call ABI

- callee symbol;
- arguments in SysV integer registers;
- return in RAX;
- stack alignment;
- live-value preservation;
- two-function E2E.

### LANG-INT-1 — integer overflow contract

- congelar comportamento padrão;
- syntax/AST dos modos;
- semantic checks;
- SIR facts;
- C11 + LLVM differential tests;
- depois machine backend.

### BARECORE-LINK-1 — freestanding link plan

- explicit entry;
- no hosted startup;
- section/layout model;
- canonical target/OSABI/load-address policy;
- fail-closed until enough relocation support exists;
- primeira entrega do caminho K3–K5.

---

## 8. Gates de promoção

### Feature level

Uma feature ampla só passa de PREVIEW para SUPPORTED quando:

- [ ] sintaxe/semântica pública estão documentadas;
- [ ] parser canônico aceita somente shapes válidos;
- [ ] Typed AST preserva facts necessários;
- [ ] verifier rejeita inconsistências;
- [ ] canonical SIR preserva semantics/source identity;
- [ ] backend suportado implementa a operação;
- [ ] positive test;
- [ ] negative test;
- [ ] E2E real;
- [ ] CI matrix verde;
- [ ] docs de suporte/limites atualizados.

### Backend próprio

Um novo opcode não conta como implementado porque o emitter contém um `if`.
Precisa de:

- [ ] Target IR verified input;
- [ ] interaction with liveness/regalloc;
- [ ] ABI/frame correctness;
- [ ] encoding/emission correctness;
- [ ] negative unsupported-shape coverage;
- [ ] native execution test.

### Barecore

Uma capacidade barecore só é real quando não depender silenciosamente de:

- libc;
- hosted startup objects;
- malloc/free não declarados;
- abort/stdio/process runtime;
- linker hosted implícito.

Um **kernel bootável** exige adicionalmente:

- [ ] entry/startup ABI explícito;
- [ ] layout/sections freestanding definidos;
- [ ] imagem realmente carregável;
- [ ] QEMU/firmware chega ao código Sotlas;
- [ ] prova observável determinística, preferencialmente serial;
- [ ] gate de CI repetível.

---

## 9. Como este arquivo deve ser mantido

Após cada bloco importante:

1. atualizar `Baseline verde atual` somente depois do CI `success`;
2. mover itens realmente concluídos para `[x]`;
3. não marcar generalização como feita porque existe um subset;
4. adicionar novos gaps descobertos por E2E/regressões;
5. manter o índice 1.0 separado da visão ampla;
6. registrar decisões arquiteturais que alterem prioridades;
7. preferir referências a arquivos/testes reais em vez de percentuais subjetivos;
8. atualizar o Kernel / Barecore Track quando um milestone K0–K14 mudar de
   estado, sem promover source preview a boot E2E.

Percentuais amplos da linguagem só devem ser usados quando existir uma métrica
objetiva. Até lá, checklists, gates e E2E são indicadores mais confiáveis.

---

## 10. Definição de sucesso de longo prazo

A visão ampla do Sotlas não estará concluída apenas quando todas as palavras do
roadmap tiverem parser. O objetivo é chegar a uma cadeia em que programas reais
possam atravessar as abstrações centrais sem adapters experimentais ou backends
que inventem semântica.

Um estado de maturidade muito mais próximo da visão completa requer:

```text
Language semantics broadly implemented
        +
Canonical SIR general enough for real programs
        +
Ownership/Authority/State/Effects/Trust preserved end-to-end
        +
Sotlas-owned machine backend for at least x86-64 and AArch64
        +
Object writer + linker + barecore path
        +
Hosted runtime + standard library
        +
Heterogeneous compute providers
        +
Self-hosted compiler fixed point
        +
Tooling/ecosystem suitable for external developers
```

Até lá, cada avanço deve ser descrito pelo subset exato que consegue provar e
executar.

---

## 11. Baseline de partida deste plano

```text
3c66cd305b8af3ab65521445ca0544f060ef74e0
backend: add executable x86-64 machine slice
CI #936: success
```

Essa baseline certifica o primeiro machine-backend slice Sotlas-owned com
register allocation consumida por code generation, spills reais, stack locals,
`alloc_stack`, `store`, `load`, unsigned `const/add/sub/mul/return` e E2E Linux.

O primeiro commit documental do plano, já certificado no CI, é:

```text
ddf0353d804bbd1fc3387931c702104b364be637
docs: add full Sotlas implementation plan
CI #938: success
```

O próximo avanço técnico recomendado é **M16.2a — compare instruction selection**,
salvo se uma regressão aparecer antes. Como sempre, regressão tem prioridade
sobre feature nova.
