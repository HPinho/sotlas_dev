# Sotlas — Development Blueprint

**Status:** CANONICAL DEVELOPMENT GUIDE  
**Baseline verde na criação:** `72e1f157edc12bf8f7c8da9bbe61dbe1cd5cc5f6`  
**CI de referência na criação:** Sotlas CI & Toolchain Build Farm #939 — `success`  
**Fonte arquitetural:** `docs/sotlas_master_roadmap.md`  
**Status operacional do subset 1.0:** `docs/sotlas_implementation_status.md`  
**Backlog técnico amplo:** `docs/sotlas_full_implementation_plan.md`

---

## 0. Papel deste documento

Este arquivo é o guia de execução do desenvolvimento do Sotlas.

Os documentos do projeto têm papéis diferentes e complementares:

| Documento | Papel |
|---|---|
| `docs/sotlas_master_roadmap.md` | visão arquitetural e semântica mestra |
| `docs/sotlas_implementation_status.md` | estado do contrato delimitado do Sotlas 1.0 |
| `docs/sotlas_full_implementation_plan.md` | backlog técnico detalhado e gaps conhecidos |
| `docs/sotlas_development_blueprint.md` | ordem de desenvolvimento, trilhas, dependências, gates e critérios de promoção |

O blueprint não substitui a especificação mestra. Ele transforma a visão em uma estratégia executável.

A regra principal é:

> Sotlas deve evoluir como uma linguagem geral. Kernel, aplicações, desktop, animações, engines AAA, IA, HPC, GPU/NPU, bancos de dados, networking, áudio, vídeo e o próprio compilador são consumidores e provas da mesma fundação, não versões diferentes da linguagem.

Nenhum consumidor pode receber um atalho específico dentro do compilador apenas para fazê-lo funcionar.

Quando um consumidor revelar uma capacidade ausente, a capacidade deve ser implementada como primitiva geral da linguagem/toolchain, atravessando os layers necessários e recebendo testes próprios.

---

# 1. Missão do Sotlas

Sotlas deve ser capaz, em estágios progressivos de maturidade, de servir como linguagem para:

- aplicações desktop e CLI;
- serviços e servidores;
- firmware e UEFI;
- bootloaders;
- kernels e sistemas operacionais;
- drivers;
- bibliotecas e runtimes;
- interfaces gráficas;
- compositores e window managers;
- animações de sistema operacional com frame pacing consistente;
- game engines e jogos de grande porte;
- renderização 2D/3D;
- física, áudio, networking e asset pipelines;
- bancos de dados e storage engines;
- computação científica;
- HPC;
- machine learning;
- treinamento e inferência de IA;
- computação GPU/NPU;
- compiladores, linkers e ferramentas;
- eventualmente o próprio compilador e toolchain Sotlas.

A linguagem não precisa atingir todos esses objetivos ao mesmo tempo. Precisa, porém, ser arquitetada de modo que o avanço de uma área fortaleça as demais em vez de criar subsistemas incompatíveis.

---

# 2. Princípios imutáveis de engenharia

## 2.1 Verdade antes de marketing

Uma feature não está pronta porque possui parser, palavra-chave, nó AST, relatório ou protótipo.

A promoção normal é:

```text
SPEC
 ↓
PARSER
 ↓
TYPED AST
 ↓
SEMANTIC CHECK
 ↓
CANONICAL SIR
 ↓
TARGET IR / RUNTIME CONTRACT
 ↓
BACKEND OR EXECUTION PROVIDER
 ↓
POSITIVE TESTS
 ↓
NEGATIVE TESTS
 ↓
END-TO-END TEST
 ↓
CI GREEN
 ↓
SUPPORTED WITH EXPLICIT SCOPE
```

## 2.2 Fail closed

Se o compilador não consegue preservar a semântica correta, deve rejeitar a forma de maneira determinística.

Nunca:

- gerar código silenciosamente incorreto;
- transformar barecore em hosted;
- ignorar ownership;
- ignorar efeitos;
- esconder uma falha de ABI;
- usar fallback que muda a semântica;
- enfraquecer um teste para obter CI verde.

## 2.3 Um bloco lógico, um commit

Cada microentrega deve ser atômica.

Se um commit introduz regressão, recuperar a baseline antes de desenvolver a próxima feature.

## 2.4 Consumidores não definem a linguagem

Baken, uma engine, um framework de IA ou um app podem revelar necessidades, mas não podem introduzir bypasses específicos.

Exemplos:

- se o kernel precisa de volatile, implementar volatile geral;
- se a UI precisa de SIMD, implementar SIMD geral;
- se a engine precisa de atomics, implementar atomics gerais;
- se IA precisa de device memory, implementar memory spaces/device ownership gerais;
- se desktop precisa de animação, construir primitives reutilizáveis de tempo/frame scheduling/rendering.

## 2.5 Soberania progressiva

LLVM e C11 continuam válidos enquanto o backend Sotlas-owned amadurece.

Soberania não significa remover dependências cedo demais. Significa substituir componentes apenas quando a alternativa Sotlas possui paridade, testes e evidência E2E.

---

# 3. Linguagem como fundação horizontal

As trilhas verticais dependem de uma fundação compartilhada.

```text
                       SOTLAS CORE
                           │
     ┌─────────────────────┼─────────────────────┐
     │                     │                     │
 SEMANTICS              MEMORY               EXECUTION
     │                     │                     │
 Types                 Ownership             Targets
 State                 Lifetimes             Backend
 Effects               Regions               Runtime
 Authority             Shared/ARC            Scheduler
 Trust                 Device memory         Heterogeneous
 Guarantees            External memory       Linker
     │                     │                     │
     └─────────────────────┼─────────────────────┘
                           │
                          SIR
                           │
                       TARGET IR
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
     C11                 LLVM            SOTLAS-OWNED
                                             MACHINE
                                             BACKEND
```

Nenhuma vertical deve criar sua própria semântica paralela para tipos, memória, erros, concorrência ou devices.

---

# 4. Estados de maturidade usados neste blueprint

| Estado | Significado |
|---|---|
| `CERTIFIED` | existe contrato delimitado, E2E relevante e CI verde |
| `PARTIAL` | existe implementação real, mas faltam shapes ou integração importante |
| `PREVIEW` | implementação útil/experimental sem contrato de suporte completo |
| `PLANNED` | arquitetura ou necessidade conhecida, sem implementação suficiente |
| `BLOCKED` | depende explicitamente de outro milestone ainda ausente |

Não usar percentuais globais sem uma métrica objetiva.

---

# 5. Estado certificado de partida

Na baseline de criação deste blueprint, o projeto já possui, entre outros subsets delimitados:

- Fases 0–17 do contrato Sotlas 1.0 registradas como COMPLETE em seu escopo próprio;
- frontend canônico com reality gates;
- target profiles `native`, `barecore` e `web` reconhecidos pelo contrato fonte;
- reconciliação entre source profile e execution target;
- caminho barecore fail-closed contra fallback hosted conhecido;
- SIR canônico delimitado;
- backend LLVM 1.0 delimitado;
- C11 como caminho de portabilidade;
- primeiro slice executável do backend x86-64 Sotlas-owned;
- liveness/interference consumindo register allocation real;
- `r10`/`r11`, spills e stack locals reais no slice atual;
- `alloc_stack`, `store`, `load`, constantes e add/sub/mul unsigned no machine slice;
- E2E Linux do primeiro machine slice;
- kernel source contract em `bootstrap/sotlas/kernel/main.sotlas`;
- Kernel/Barecore Track K0–K14 no plano amplo;
- runtime DEVICE de referência, ainda sem provider hardware/DMA geral;
- módulos de self-host existentes, ainda sem fixed point completo.

Esse estado não significa que o Master Roadmap inteiro esteja implementado.

---

# 6. Fundação F — linguagem e semântica geral

Esta é a trilha mais importante porque todas as verticais dependem dela.

## F0 — Reality and canonical frontend

**Estado:** CERTIFIED no subset 1.0; hardening contínuo.

Objetivos permanentes:

- uma única verdade semântica de produção;
- parser/frontend públicos coerentes;
- diagnósticos source-stable;
- inventários explícitos de previews e diferenças históricas;
- remoção progressiva de duplicação `compiler/` vs `tools/` sem quebrar compatibilidade.

## F1 — Typed Semantic Core geral

**Estado:** PARTIAL além do subset 1.0.

Ainda precisa amadurecer para programas grandes:

- tipos escalares completos;
- promotion/conversion rules canônicas;
- arrays e slices gerais;
- strings;
- aggregates;
- enums/variants;
- generics gerais;
- traits/interfaces/protocols conforme contrato final;
- closures/lambdas se adotadas;
- mutabilidade geral;
- constant expressions;
- diagnostics consistentes em todos os backends.

## F2 — Integer semantics

**Estado:** PLANNED/PARTIAL.

Definir explicitamente:

- comportamento padrão de overflow;
- `checked`;
- `wrapping`;
- `saturating`;
- `unchecked` com contrato explícito;
- divisão/remainder;
- shifts;
- bitwise;
- casts e narrowing/widening.

Critério de saída:

- C11, LLVM e machine backend produzem semântica equivalente;
- differential tests cobrem edge cases;
- signed arithmetic deixa de depender de UB de linguagem hospedeira.

## F3 — Ownership geral

**Estado:** COMPLETE no subset 1.0; generalização PARTIAL.

Expandir:

- `sole`/exclusive em CFG arbitrário;
- shared/ARC em CFG arbitrário;
- regions gerais;
- weak/whisper;
- direct/borrow;
- handover;
- device ownership;
- external/FFI ownership;
- aggregates ownership-bearing;
- cleanup backend-neutral;
- failure/unwind cleanup onde aplicável.

## F4 — Authority, Effects, Trust and Guarantees

**Estado:** subsets 1.0 certificados; generalização PARTIAL.

Expandir para:

- capabilities como valores;
- filesystem/network/process/thread/clock/random authorities;
- PCI/MMIO/DMA/IRQ/GPU authorities;
- effect inference interprocedural;
- realtime/interrupt restrictions;
- trust propagation;
- FFI boundaries gerais;
- contracts/proofs com runtime fallback quando apropriado;
- freestanding trap/panic para contracts barecore.

## F5 — State, Flow, Causality, Transactions, Intent

**Estado:** subsets 1.0 certificados; generalização PARTIAL.

Objetivo de longo prazo:

- CFG arbitrário;
- aliases/mutação;
- ownership-bearing payloads;
- state-aware execution;
- causal graph interprocedural;
- rollback/crash recovery;
- scheduler nativo;
- source syntax para intent;
- integração com devices e heterogeneous compute.

---

# 7. Fundação IR — SIR, Target IR e otimização

## IR0 — Canonical SIR

**Estado:** CERTIFIED no subset 1.0; PARTIAL para linguagem geral.

Necessidades:

- arbitrary source-body lowering;
- CFG geral;
- calls;
- aggregates;
- pointer/address ops;
- ownership cleanup;
- state/effect/authority/trust facts preservados;
- source locations completas;
- verifier independente;
- versioning/serialization se adotado.

## IR1 — Target IR

Objetivos:

- representação machine-oriented sem perder semântica necessária;
- register classes;
- calling conventions;
- stack objects;
- branches/phi;
- relocatable symbols;
- source map;
- debug facts;
- target features.

## IR2 — Pass manager

**Estado:** PLANNED.

Princípios:

- otimização nunca remove facts sem prova;
- cada pass declara pré-condições e invariantes;
- verifier entre passes críticos;
- deterministic output;
- optimization levels reproduzíveis.

Passes futuros possíveis:

- constant folding;
- dead code elimination;
- CFG simplification;
- copy propagation;
- phi simplification;
- ARC retain/release optimization;
- bounds-check elimination comprovada;
- vectorization quando legal.

---

# 8. Fundação BE — backends, ABI, objetos e linker

## BE0 — C11 backend

Papel:

- portabilidade;
- bootstrap;
- differential oracle em subsets definidos;
- integração com toolchains existentes.

Não pode definir semântica do Sotlas por acidente.

## BE1 — LLVM backend

Papel atual:

- backend nativo de produção do subset certificado;
- ponte para arquiteturas e otimizações enquanto o backend próprio amadurece.

## BE2 — Sotlas-owned x86-64 backend

**Estado atual:** primeiro slice CERTIFIED.

Sequência imediata:

1. compare instruction selection;
2. bool materialization;
3. labels;
4. unconditional branch;
5. conditional branch;
6. phi/edge copies;
7. bounded loops;
8. calls;
9. SysV scalar call ABI completa;
10. caller/callee-saved policy;
11. pointers/addressing;
12. aggregates;
13. remaining arithmetic;
14. floats;
15. SIMD;
16. instruction encoder;
17. object writer.

## BE3 — Multi-ABI

Depois do x86-64 SysV maduro:

- Windows x64;
- macOS x86-64 completion;
- AArch64 instruction selection;
- AArch64 ABI;
- architecture-neutral register classes.

## BE4 — Object writer

Necessidades:

- sections;
- symbols;
- relocations;
- ELF relocatable;
- PE/COFF quando necessário;
- debug/unwind metadata contract;
- no external assembler para caminho soberano.

## BE5 — Linker

Necessidades:

- canonical link plan;
- entrypoint explícito;
- target-aware layout;
- ELF executable/image;
- symbol resolution;
- relocations certificadas;
- no implicit CRT/libc em barecore;
- PE/COFF/UEFI path;
- diagnostics determinísticos.

---

# 9. Fundação RT — runtime, standard library e concorrência

## RT0 — Core freestanding

Deve funcionar sem OS quando necessário:

- memory primitives;
- panic/trap;
- integer helpers;
- basic formatting que não dependa de libc quando usado em barecore;
- slices básicas;
- target intrinsics controlados.

## RT1 — Allocator contract

- allocator interface;
- global allocator hosted;
- allocator hooks barecore;
- arenas/regions;
- alignment;
- allocation failure semantics;
- integration with ownership.

## RT2 — Collections and text

- Vec/dynamic arrays;
- strings;
- slices;
- maps/sets;
- queues/deques;
- small/fixed containers para systems/realtime.

## RT3 — Errors and results

Definir modelo consistente de:

- recoverable errors;
- panic/trap;
- FFI errors;
- device failures;
- async failures;
- transaction failures.

## RT4 — Concurrency

- threads;
- atomics;
- memory order;
- mutex/rwlock/semaphore/condition primitives;
- channels/queues se adotados;
- work-stealing/task runtime se adotado;
- data-race contract.

## RT5 — Async and event loops

- async model se adotado;
- futures/tasks;
- cancellation;
- timers;
- IO readiness;
- integration with UI, servers and devices.

## RT6 — OS services

Hosted stdlib:

- files;
- directories;
- sockets;
- processes;
- environment;
- clock/time;
- random;
- dynamic libraries;
- platform abstraction.

---

# 10. Fundação NUM — numerics, SIMD e scientific/HPC

Esta trilha é necessária tanto para IA quanto para games, áudio, vídeo e ciência.

## NUM0 — Scalar math

- integer completeness;
- float32/float64;
- math functions;
- deterministic/fast modes onde fizer sentido.

## NUM1 — SIMD

- vector types;
- target feature detection;
- explicit SIMD intrinsics;
- portable SIMD abstraction;
- alignment;
- vector loads/stores;
- horizontal/reduction ops;
- masked operations.

## NUM2 — Arrays and tensors foundation

- multidimensional shapes;
- strides;
- views;
- contiguous/non-contiguous layout;
- dtype model;
- bounds/proof integration.

## NUM3 — Linear algebra

- vectors/matrices;
- BLAS-like primitives;
- matmul;
- reductions;
- convolution building blocks;
- CPU vectorized kernels.

## NUM4 — Parallel numerics

- thread pool integration;
- deterministic reductions options;
- NUMA awareness futuramente;
- heterogeneous dispatch.

---

# 11. Fundação H — GPU, NPU e Heterogeneous Compute

## H0 — Execution provider contract

**Estado:** reference subset existe; hardware geral ainda PLANNED/PARTIAL.

Provider deve expor:

- device discovery;
- capabilities;
- memory spaces;
- queues/streams;
- execution submission;
- events/fences;
- failure/timeout;
- synchronization.

## H1 — Device memory

- allocation;
- host-visible/device-local distinctions;
- copies;
- mapped memory;
- alignment;
- lifetime;
- ownership handover;
- safe reacquisition.

## H2 — GPU compute

- kernels;
- dispatch dimensions;
- buffers;
- barriers;
- shader/compute compilation path;
- portable provider interface.

## H3 — NPU/accelerator compute

- graph/command submission;
- tensor buffers;
- precision/capability negotiation;
- async completion;
- fallback policy.

## H4 — Multi-device scheduler

- CPU/GPU/NPU cost model;
- explicit preferred/fallback policy;
- deterministic failure behavior;
- device authority/effects;
- Flow integration.

---

# 12. Trilha APP — aplicações, desktop e serviços

Objetivo: provar que Sotlas também é confortável fora de systems programming.

## APP0 — CLI application baseline

**Estado:** PARTIAL/experimental através dos caminhos atuais.

Critério de maturidade:

- package build estável;
- arguments;
- files;
- errors;
- strings;
- collections;
- tests;
- release artifact cross-platform.

## APP1 — General application runtime

- stable main/entry model;
- environment;
- logging;
- config;
- filesystem;
- networking;
- threads/async;
- package dependencies.

## APP2 — Server/service workloads

- sockets;
- HTTP foundation via library/ecosystem;
- async IO;
- timers;
- synchronization;
- graceful shutdown;
- observability hooks.

## APP3 — Cross-platform desktop apps

Depende de UI track.

Critério:

- window creation;
- event loop;
- rendering surface;
- input;
- files/network;
- packaging.

## APP4 — Production application gate

Um app representativo deve:

- compilar sem bypass;
- usar stdlib real;
- possuir testes;
- rodar em pelo menos dois targets hosted antes de reivindicar suporte cross-platform.

---

# 13. Trilha UI — desktop, compositor e animações

Esta trilha cobre a necessidade de interfaces fluidas, inclusive um sistema operacional com animações de alta qualidade.

Não implementar animações específicas no bootloader ou compilador.

## UI0 — Time and frame clock

- monotonic clock;
- frame timestamps;
- delta time;
- target refresh rate;
- stable scheduling.

## UI1 — Graphics primitives

- surfaces;
- colors;
- rectangles;
- images;
- clipping;
- transforms;
- alpha composition.

## UI2 — Rasterization/rendering abstraction

- CPU rasterizer inicial;
- GPU renderer posterior;
- render targets;
- command representation;
- resource lifetime.

## UI3 — Window/event model

- window lifecycle;
- input events;
- resize;
- focus;
- pointer/keyboard;
- event queue.

## UI4 — Compositor

- surfaces/layers;
- z-order;
- damage tracking;
- clipping;
- composition;
- present;
- buffer lifecycle.

## UI5 — Frame scheduler

Fundamental para fluidez:

- frame deadlines;
- vsync/present synchronization;
- frame pacing;
- missed-frame accounting;
- animation update before composition;
- input-to-photon latency metrics.

## UI6 — Animation engine

- timeline;
- interpolation;
- easing curves;
- spring/damped motion;
- keyframes;
- composition of animations;
- interruption/reversal;
- deterministic clock source;
- no abrupt state jumps unless requested.

## UI7 — Retained/immediate UI primitives

Definir arquitetura deliberadamente:

- layout;
- constraints;
- text;
- controls;
- state;
- focus;
- accessibility hooks.

## UI8 — GPU accelerated compositor

Depende de H track:

- GPU surfaces;
- upload/resource management;
- command submission;
- synchronization;
- zero/low-copy paths quando possíveis.

## UI9 — OS desktop proof

Prova vertical:

```text
input
 ↓
window manager
 ↓
UI state
 ↓
animation timeline
 ↓
renderer
 ↓
compositor
 ↓
present/vsync
```

Critério de saída:

- animações contínuas;
- frame pacing medido;
- sem lógica gráfica escondida no bootloader/compiler;
- compositor/window manager independentes do kernel core.

---

# 14. Trilha GAME — game engine e capacidade AAA

Objetivo não é declarar “AAA ready” cedo. É construir as fundações exigidas por engines grandes e validar workloads progressivamente.

## G0 — Game loop and timing

- fixed/variable timestep;
- high-resolution clock;
- frame pacing;
- task scheduling;
- profiling markers.

## G1 — Data-oriented memory

- arenas;
- pools;
- SoA/AoS-friendly layouts;
- alignment;
- predictable allocation;
- ownership models adequados a ECS/assets.

## G2 — ECS foundation

- entities;
- components;
- archetypes/storage;
- queries;
- parallel systems;
- deterministic lifecycle.

## G3 — Math library

- vectors;
- matrices;
- quaternions;
- transforms;
- SIMD;
- geometry primitives.

## G4 — Renderer abstraction / RHI

- buffers;
- textures;
- samplers;
- pipelines;
- shaders;
- render passes;
- command buffers;
- synchronization;
- backend/provider abstraction.

## G5 — Modern renderer

Progressão possível:

- forward renderer;
- deferred/clustered as library choices;
- PBR;
- shadows;
- post-processing;
- compute workloads;
- streaming resources.

## G6 — Asset system

- virtual paths;
- import pipeline;
- serialization;
- compression;
- hot reload;
- streaming;
- dependency graph.

## G7 — Scene/world system

- hierarchy;
- transforms;
- spatial indexing;
- streaming levels/world partitions.

## G8 — Animation system

Diferente da UI animation, mas compartilha math/time/task primitives:

- skeletal animation;
- blend trees;
- state machines;
- interpolation;
- animation compression;
- GPU skinning futuramente.

## G9 — Physics integration

- collision;
- rigid bodies;
- constraints;
- deterministic/update contracts;
- multithreading;
- external library FFI enquanto engine própria não existir.

## G10 — Audio engine

- mixer;
- streaming;
- spatial audio;
- low-latency callback constraints;
- DSP/SIMD.

## G11 — Networking

- UDP/TCP foundations;
- replication;
- snapshot/delta;
- prediction/reconciliation como library patterns;
- latency metrics.

## G12 — Scripting/gameplay layer

Pode ser Sotlas ou uma camada embutida, mas requer:

- hot reload policy;
- stable ABI;
- reflection/metadata se adotados;
- sandbox/trust boundaries quando necessário.

## G13 — Editor/tooling

- asset browser;
- scene editor;
- inspector;
- profiler;
- live reload;
- shader/build diagnostics.

## G14 — AAA workload gate

Não usar o termo AAA support até existir uma prova representativa com:

- renderer moderno;
- asset streaming;
- multithreading;
- frame profiling;
- animation;
- audio;
- networking foundation;
- memory budgets;
- large-world/content stress;
- stable tooling.

A linguagem pode ser adequada a engines antes desse gate, mas o claim deve permanecer preciso.

---

# 15. Trilha AI — IA, ML, treinamento e inferência

## AI0 — Tensor foundation

Depende de NUM2:

- dtype;
- shape;
- stride;
- views;
- broadcasting;
- indexing;
- device placement.

## AI1 — Tensor operations

- elementwise ops;
- reductions;
- matmul;
- convolution primitives;
- normalization building blocks;
- activation functions.

## AI2 — CPU kernel library

- scalar fallback;
- SIMD kernels;
- threading;
- cache-aware tiling;
- benchmarking.

## AI3 — GPU/NPU kernels

Depende de H:

- device buffers;
- kernel dispatch;
- synchronization;
- precision capabilities;
- asynchronous execution.

## AI4 — Graph execution

- operation graph;
- shape/type inference;
- dependency scheduling;
- memory planning;
- fusion opportunities;
- heterogeneous partitioning.

## AI5 — Autograd

- tape/graph representation;
- backward rules;
- gradient accumulation;
- lifecycle/memory control;
- custom ops.

## AI6 — Optimizers

- SGD;
- Adam-family via libraries;
- state handling;
- mixed precision integration.

## AI7 — Data pipeline

- datasets;
- batching;
- preprocessing;
- async loading;
- streaming;
- reproducible random state.

## AI8 — Training runtime

- forward/backward;
- optimizer step;
- checkpoint;
- metrics;
- mixed precision;
- device placement;
- distributed support futuramente.

## AI9 — Inference runtime

- graph loading;
- constant weights;
- memory planning;
- batching;
- quantization support;
- CPU/GPU/NPU execution;
- latency/throughput profiling.

## AI10 — Model interchange

Potential ecosystem work:

- external model format loaders;
- FFI with existing ML ecosystems;
- stable tensor ABI where useful.

## AI11 — Production AI gate

Claims de IA devem distinguir:

- tensor library works;
- inference works;
- GPU inference works;
- training works;
- distributed training works.

Não condensar tudo em “AI supported”.

---

# 16. Trilha HPC — ciência e computação de alto desempenho

## HPC0 — Numerical reliability

- float semantics;
- reductions;
- reproducibility modes;
- error behavior;
- benchmark harness.

## HPC1 — Parallel CPU

- thread pools;
- parallel loops/library primitives;
- NUMA-aware design futuramente;
- vectorization.

## HPC2 — Heterogeneous kernels

- GPU compute;
- device memory;
- async overlap;
- profiling.

## HPC3 — Distributed compute

Longo prazo:

- networking collectives via libraries;
- MPI interoperability inicialmente;
- distributed scheduler patterns.

## HPC4 — Scientific ecosystem

- linear algebra;
- FFT libraries/interop;
- statistics;
- optimization;
- sparse data structures;
- plotting/data ecosystem via packages.

---

# 17. Trilha K — kernel, barecore e OS

O detalhe operacional K0–K14 vive em `docs/sotlas_full_implementation_plan.md`.

Resumo:

| Milestone | Estado na criação do blueprint | Objetivo |
|---|---|---|
| K0 | CERTIFIED | target/profile freestanding |
| K1 | CERTIFIED source contract | kernel source/ABI bootstrap |
| K2 | PARTIAL | objeto freestanding real |
| K3 | PREVIEW | linker ELF freestanding |
| K4 | PLANNED | startup/entry ABI |
| K5 | PLANNED | sections/image layout |
| K6 | PLANNED | bootable image |
| K7 | PLANNED | QEMU E2E |
| K8 | PREVIEW at source level | early serial/framebuffer/panic |
| K9 | PLANNED | GDT/IDT/IRQ/CPU setup |
| K10 | PLANNED | physical memory/paging/allocator |
| K11 | PLANNED | timer/scheduler |
| K12 | PLANNED | drivers/MMIO/PCI/DMA |
| K13 | PLANNED | UEFI/PE-COFF |
| K14 | LONG TERM | sovereign Sotlas-heavy kernel/toolchain |

Regra:

> Um arquivo `kernel_main` não é sinônimo de kernel bootável certificado.

Boot real exige source → object → link → image → QEMU/firmware → observable Sotlas entry.

---

# 18. Trilha DATA — banco de dados, storage e networking

## D0 — Binary/data representation

- stable integer/float representation;
- byte buffers;
- endianness;
- serialization primitives;
- checksums.

## D1 — File and block IO

- files;
- mmap quando suportado;
- buffered IO;
- fsync/durability contracts;
- async IO futuramente.

## D2 — Networking base

- sockets;
- DNS via library/runtime;
- TCP/UDP;
- TLS via vetted library/FFI inicialmente;
- event loop.

## D3 — Concurrent server runtime

- task scheduling;
- backpressure;
- connection lifecycle;
- cancellation;
- metrics.

## D4 — Storage engine proof

- pages;
- cache;
- WAL/journal;
- transactions;
- indexes;
- crash recovery tests.

## D5 — Database proof

Somente depois de storage/runtime maduros:

- query/parser as library;
- execution engine;
- indexing;
- concurrency control;
- persistence;
- benchmark/consistency tests.

---

# 19. Trilha MEDIA — áudio, vídeo e realtime media

## M0 — Realtime-safe foundation

- callback constraints;
- no-allocation regions quando necessário;
- atomics/queues;
- timing;
- effects/realtime annotations futuramente.

## M1 — Audio

- sample buffers;
- mixer;
- resampling;
- DSP;
- SIMD;
- device backend via platform/FFI.

## M2 — Video/image

- pixel formats;
- frame buffers;
- conversion;
- SIMD kernels;
- codec FFI inicialmente;
- GPU upload/render integration.

## M3 — Streaming

- network buffers;
- clocks;
- synchronization;
- decode/encode pipeline;
- backpressure.

---

# 20. Trilha WEB — WASM e aplicações web

O source profile `web` existe como contrato, mas caminhos nativos ainda devem permanecer fail-closed quando não implementados.

## W0 — WASM target contract

- architecture/ABI model;
- supported types;
- memory model;
- imports/exports;
- diagnostics.

## W1 — WASM backend

- scalar ops;
- CFG;
- calls;
- memory;
- objects/modules;
- E2E runtime tests.

## W2 — Browser interop

- JS/host boundary;
- DOM bindings via generated/FFI layers;
- async events;
- web graphics bindings.

## W3 — WASI/server WASM

- files/sockets conforme runtime;
- package/deployment path.

---

# 21. Trilha SH — self-host e soberania do toolchain

## SH0 — Native compiler modules

**Estado:** PREVIEW/PARTIAL.

Continuar paridade de:

- lexer;
- parser;
- AST;
- semantic checker;
- SIR builder;
- emitter inicial.

## SH1 — Stage 0 → Stage 1

Python Stage 0 compila um compilador Sotlas funcional.

## SH2 — Stage 1 → Stage 2

O compilador Sotlas compila a si próprio.

## SH3 — Fixed point

Comparar Stage 1 e Stage 2 com política de equivalência/reproducibility definida.

## SH4 — Backend ownership

Conectar o self-host ao Target IR e ao backend Sotlas-owned.

## SH5 — Toolchain sovereignty

Longo prazo:

- compiler;
- assembler/object writer;
- linker;
- package tooling;
- build tooling;
- debugger/profiler components conforme viável.

Regra:

> Não remover Stage 0 Python antes de a paridade estar comprovada.

---

# 22. Trilha TOOL — developer experience e ecossistema

## T0 — CLI stability

- deterministic commands;
- diagnostics;
- exit codes;
- machine-readable reports.

## T1 — Formatter and linter

- stable formatting;
- semantic lint rules;
- safe autofixes quando comprováveis.

## T2 — LSP

- completion;
- hover;
- diagnostics;
- go-to-definition;
- references;
- rename;
- semantic tokens;
- semantic facts from canonical frontend only.

## T3 — Package manager

- manifest;
- semver policy;
- lockfile;
- reproducibility;
- registry;
- offline/cache behavior;
- integrity.

## T4 — Build system

- incremental graph;
- target profiles;
- feature flags;
- artifacts;
- cross compilation;
- build scripts/policies cuidadosamente controlados.

## T5 — Testing

- unit tests;
- integration tests;
- compile-fail tests;
- property tests;
- benchmarks;
- target/device tests.

## T6 — Debugger/profiler

- source maps;
- stack/unwind;
- breakpoints;
- registers;
- causal/state/ownership visualizations;
- frame profiler para UI/game;
- kernel debug hooks.

## T7 — IDE/Studio

- diagnostics;
- graph viewers;
- SIR/Target IR viewer;
- register allocation viewer;
- ABI/stack viewer;
- performance timelines.

## T8 — Ecosystem

- standard library docs;
- package registry;
- templates;
- examples only from certified support;
- compatibility policy;
- release notes;
- migration guides.

---

# 23. Dependências entre as grandes trilhas

Legenda: `→` significa “desbloqueia diretamente”.

```text
F / IR / BE
  ├→ APP
  ├→ UI
  ├→ GAME
  ├→ AI
  ├→ HPC
  ├→ KERNEL
  ├→ DATA
  ├→ MEDIA
  └→ SELF-HOST

RT / CONCURRENCY
  ├→ APP
  ├→ UI
  ├→ GAME
  ├→ AI training
  ├→ DATA
  └→ MEDIA

NUM / SIMD
  ├→ UI rendering
  ├→ GAME
  ├→ AI
  ├→ HPC
  └→ MEDIA

HETEROGENEOUS
  ├→ UI GPU compositor
  ├→ GAME renderer
  ├→ AI GPU/NPU
  └→ HPC accelerators

OBJECT/LINKER/SYSTEMS
  ├→ KERNEL
  ├→ DRIVERS
  ├→ SELF-HOST sovereignty
  └→ cross-platform native packaging
```

Consequência: o kernel não precisa terminar antes de IA ou games começarem, e IA não precisa terminar antes de UI. Todos consomem partes diferentes da fundação.

---

# 24. Matriz de capacidades compartilhadas

| Capacidade | Apps | UI | AAA/Game | AI/HPC | Kernel | Data/Net | Media |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| strings/collections | ✓ | ✓ | ✓ | ✓ | parcial/freestanding | ✓ | ✓ |
| allocator | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| ownership | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| threads/atomics | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| async/event loop | ✓ | ✓ | útil | data pipeline | opcional | ✓ | ✓ |
| SIMD | útil | ✓ | ✓ | ✓ | útil | útil | ✓ |
| GPU/device | opcional | ✓ | ✓ | ✓ | drivers | opcional | ✓ |
| filesystem | ✓ | assets | assets | datasets | via FS driver | ✓ | media files |
| networking | ✓ | opcional | multiplayer | distributed | network stack | ✓ | streaming |
| precise timing | ✓ | ✓ | ✓ | profiling | ✓ | ✓ | ✓ |
| profiler | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| FFI | ✓ | platform | middleware | libraries | firmware/hw | TLS/libs | codecs |

Essa matriz deve orientar prioridades: uma primitiva usada por muitas colunas normalmente tem prioridade arquitetural maior que uma feature extremamente específica.

---

# 25. Ondas de implementação

As ondas não são releases rígidos; são ordem de dependências.

## Wave 0 — preservar verdade e baseline

Sempre ativa:

- regressions first;
- reality gates;
- no test bypass;
- claims precisos;
- unsupported fail-closed;
- commits atômicos.

## Wave 1 — machine backend e semântica essencial

Prioridade imediata atual:

1. M16.2a comparisons;
2. M16.2b branches;
3. M16.2c phi;
4. M16.2d bounded loops;
5. M16.3 direct calls/ABI;
6. pointer/address ops;
7. integer semantics definidas;
8. aggregate lowering básico.

Em paralelo:

- runtime/stdlib contracts;
- self-host parity;
- heterogeneous provider contracts;
- generalização de ownership/effects/state.

## Wave 2 — objects, linker e runtime útil

- x86-64 encoder;
- ELF object writer;
- freestanding link plan;
- hosted link/package hardening;
- allocator;
- strings/slices/collections;
- files/sockets/threads;
- atomics.

Essa wave libera muito de APP, KERNEL e DATA.

## Wave 3 — SIMD, graphics e heterogeneous

- SIMD;
- math foundation;
- graphics surfaces;
- frame clock;
- GPU/device memory;
- events/fences;
- compute kernels.

Essa wave libera UI fluida, GAME, AI e MEDIA.

## Wave 4 — primeiras provas verticais sérias

Executar em paralelo conforme dependências:

- APP: aplicação real com filesystem/network/testes;
- UI: compositor + animation timeline + frame pacing;
- GAME: ECS + renderer + asset system mínimo;
- AI: tensor + CPU kernels + inference pequena;
- KERNEL: boot QEMU E2E;
- DATA: storage/network service;
- MEDIA: mixer ou frame pipeline.

## Wave 5 — escala e produção

- multi-platform;
- robust error handling;
- profiling;
- performance budgets;
- stability;
- package ecosystem;
- stress/fuzz/property testing;
- security/trust hardening.

## Wave 6 — soberania avançada

- self-host fixed point;
- backend próprio amplo;
- object writer/linker próprios;
- reduced dependence on bootstrap toolchains;
- reproducible releases.

---

# 26. Próximos blocos técnicos recomendados a partir da baseline atual

A menos que uma regressão apareça, a sequência preferencial é:

## P0 — Backend CFG

1. `compare` → x86-64 `cmp` + condition code materialization;
2. labels;
3. unconditional branch;
4. conditional branch;
5. E2E if/else;
6. phi resolution;
7. loop-carried phi;
8. bounded loop E2E.

## P1 — Call ABI

1. direct calls;
2. return in RAX;
3. SysV integer registers;
4. stack args;
5. 16-byte call alignment;
6. caller/callee-saved rules;
7. multi-function E2E.

## P2 — Systems/object path

1. pointer/address operations;
2. volatile/atomics contracts;
3. instruction encoder;
4. ELF relocatable writer;
5. linker freestanding plan;
6. K2/K3 hardening;
7. startup/entry ABI;
8. QEMU gate.

## P3 — Runtime/application path

Em paralelo quando seguro:

1. allocator API;
2. error/result model;
3. strings/slices;
4. Vec/container baseline;
5. files;
6. sockets;
7. threads/atomics;
8. first representative application gate.

## P4 — Numerics/graphics/device path

1. float completeness;
2. SIMD foundation;
3. frame clock;
4. graphics buffers/surfaces;
5. device memory/fence APIs;
6. GPU provider;
7. UI animation/compositor proof;
8. tensor/game renderer proofs.

---

# 27. Gates por tipo de capacidade

## 27.1 Language feature gate

Antes de SUPPORTED:

- spec;
- parser;
- typed semantics;
- invalid-shape diagnostics;
- SIR representation;
- backend/runtime implementation;
- positive tests;
- negative tests;
- E2E;
- CI matrix green;
- docs atualizados.

## 27.2 Backend opcode gate

- verified Target IR input;
- register allocation interaction;
- frame/ABI correctness;
- encoding/emission correctness;
- unsupported forms fail closed;
- executable native test.

## 27.3 Runtime API gate

- ownership/lifetime defined;
- error behavior defined;
- concurrency behavior defined;
- target support listed;
- leak/lifetime tests;
- E2E consumer.

## 27.4 Kernel gate

- no implicit hosted runtime;
- explicit entry/startup;
- explicit sections/layout;
- loadable image;
- QEMU/firmware executes Sotlas code;
- deterministic observable proof.

## 27.5 UI/animation gate

- deterministic frame clock;
- no bootloader/compiler rendering hacks;
- input/event lifecycle;
- frame scheduling;
- measured frame pacing;
- renderer/compositor separation;
- interruption/reversal behavior tested.

## 27.6 Game/AAA gate

- memory and task systems;
- renderer;
- assets;
- animation;
- audio;
- profiling;
- frame budget/stress proof;
- no claim “AAA ready” based only on a demo triangle.

## 27.7 AI gate

Claims must be granular:

- tensor operations;
- CPU inference;
- GPU inference;
- autograd;
- training;
- mixed precision;
- distributed training.

Cada claim precisa do próprio E2E.

---

# 28. Test strategy

## Layer 1 — unit

- parser;
- type rules;
- analyses;
- IR builders;
- utilities.

## Layer 2 — compile-fail

- invalid syntax;
- ownership violations;
- authority violations;
- unsupported backend shapes;
- ABI contradictions;
- target contradictions.

## Layer 3 — cross-backend differential

Quando aplicável:

- C11 vs LLVM;
- LLVM vs machine backend;
- reference scheduler vs native runtime;
- CPU vs device provider.

## Layer 4 — native execution

- executable functions;
- multi-function programs;
- runtime APIs;
- application workloads.

## Layer 5 — system E2E

- QEMU kernel;
- UI frame loop;
- game frame;
- GPU kernel;
- AI inference;
- network service.

## Layer 6 — stress/performance

Não usar performance como substituto de correctness.

Depois da correção:

- frame time;
- throughput;
- latency;
- allocations;
- memory footprint;
- compile time;
- binary size.

---

# 29. Regressão: protocolo obrigatório

Quando CI falhar:

1. congelar feature work;
2. identificar o primeiro gate real que falhou;
3. reproduzir o shape;
4. distinguir bug de código, teste, documentação ou infraestrutura;
5. corrigir a causa;
6. não reduzir cobertura;
7. preferir substituir o commit candidato quando ele ainda não virou baseline;
8. somente promover a baseline após CI green.

---

# 30. Arquitetura de repositório desejada

Direção de longo prazo:

```text
compiler/              canonical Stage-0 implementation
bootstrap/sotlas/      Sotlas-written bootstrap/self-host sources
stdlib/                language standard library
runtime/               target/runtime providers
spec/                   normative/auxiliary specifications
docs/                   architecture/status/blueprint
examples/               only explicitly classified examples
tests/                  unit, negative, differential, E2E
editors/                IDE/LSP integrations
```

`tools/` deve convergir progressivamente para compatibilidade fina ou desaparecer quando seguro, sem manter uma segunda implementação semântica independente.

---

# 31. Platform strategy

Não declarar cross-platform baseado apenas em parser support.

Matriz-alvo de longo prazo:

| Target | Hosted | Barecore/Firmware | Machine backend próprio |
|---|---|---|---|
| x86-64 Linux | objetivo principal inicial | barecore/QEMU | primeiro backend próprio |
| x86-64 Windows | planejado | n/a/firmware separado | planejado |
| x86-64 macOS | planejado | n/a | planejado |
| AArch64 Linux | planejado | planejado | planejado após x86-64 |
| AArch64 macOS | planejado | n/a | planejado |
| UEFI x86-64/AArch64 | firmware | sim | PE/COFF path |
| WebAssembly | web/WASI | n/a | backend separado |

Cada célula só muda para suporte público depois de E2E específico.

---

# 32. Performance philosophy

Sotlas pretende servir workloads de baixo nível e alto desempenho, mas performance deve ser mensurada, não assumida.

Princípios:

- zero-cost apenas quando demonstrável;
- ownership/effects podem habilitar otimizações, não apenas restrições;
- no hidden allocation em realtime/barecore quando contrato proíbe;
- predictable layout quando ABI exige;
- SIMD/device execution explícitos;
- benchmark suites versionadas;
- performance regressions tratadas depois de correctness regressions.

Workloads de benchmark futuros:

- scalar arithmetic;
- memory copy/fill;
- hash/map;
- JSON/data parsing via ecosystem;
- network echo/service;
- UI frame composition;
- ECS iteration;
- matrix multiplication;
- tensor kernels;
- device transfer/dispatch;
- kernel boot time.

---

# 33. Segurança e robustez

A ambição de systems + apps + IA exige que segurança seja transversal.

Áreas:

- memory safety dentro do contrato Sotlas;
- explicit unsafe boundaries;
- explicit authority;
- trust domains;
- FFI validation;
- integer overflow semantics;
- concurrency/data race model;
- package integrity;
- sandbox/isolation quando implementado;
- reproducible builds;
- dependency provenance;
- fuzzing de parser/IR/linker/runtime.

---

# 34. Como decidir a próxima feature

Priorizar uma feature quando ela satisfaz vários destes critérios:

1. desbloqueia múltiplas trilhas verticais;
2. remove uma dependência externa crítica;
3. fecha um gap E2E já exposto;
4. resolve uma regressão ou ambiguidade semântica;
5. melhora fail-closed correctness;
6. reduz duplicação de semântica;
7. possui um teste E2E claro;
8. evita que consumidores criem hacks locais.

Exemplo: `compare + branches + phi` tem prioridade alta porque desbloqueia programas gerais, loops, kernel logic, UI logic, game logic e numerics no backend próprio.

---

# 35. Como manter as trilhas sincronizadas

Após cada baseline verde relevante:

- atualizar o status do milestone correspondente;
- registrar novos gaps descobertos;
- atualizar dependências se mudaram;
- não promover a vertical inteira por causa de um único demo;
- manter o Master Roadmap como autoridade arquitetural;
- manter o Implementation Status como autoridade do subset 1.0;
- manter o Full Implementation Plan como backlog técnico;
- manter este Blueprint como guia de execução.

---

# 36. Definições de sucesso por vertical

## Aplicações

Um conjunto de apps reais pode ser construído, testado, empacotado e distribuído sem depender de hacks do compilador.

## UI/OS animations

Window/event/render/compositor/animation/frame-scheduling formam uma pilha separada do bootloader e conseguem manter frame pacing mensurável.

## Game/AAA

A linguagem sustenta memory/task/render/assets/audio/network/tooling workloads representativos e a engine mantém budgets de frame e memória medidos.

## AI

Tensor/numerics/device runtime executa inferência e, posteriormente, training com claims separados e medidos.

## Kernel

Uma imagem gerada pelo toolchain chega a código Sotlas em QEMU/firmware e progride para memory/interrupts/drivers sem glue especial no compilador.

## Self-host

Stage 1 compila Stage 2 com fixed-point/reproducibility policy comprovada.

---

# 37. Visão de longo prazo integrada

O objetivo final não é apenas um compilador que aceita muitas palavras-chave.

É um ecossistema em que a mesma semântica Sotlas sustenta workloads muito diferentes:

```text
                         SOTLAS
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
       SYSTEMS           APPLICATIONS       COMPUTE
          │                 │                 │
  kernel / firmware    desktop / CLI      AI / HPC
  drivers / runtime    server / data      GPU / NPU
          │                 │                 │
          ├────────────── GRAPHICS ──────────┤
          │                 │                 │
       compositor      UI / animation     game engine
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
                   SAME LANGUAGE CORE
                            │
             semantics / ownership / effects
               SIR / Target IR / backends
                 runtime / stdlib / tools
```

A linguagem estará madura quando essas verticais compartilharem a mesma fundação sem exigir semânticas duplicadas, bypasses de produto ou backends que inventem comportamento.

---

# 38. Ordem operacional atual

Na baseline de criação deste documento, a próxima frente técnica recomendada continua sendo o backend próprio:

```text
M16.2a compare
   ↓
M16.2b branch
   ↓
M16.2c phi
   ↓
M16.2d loop
   ↓
M16.3 calls / ABI
   ↓
pointers / aggregates
   ↓
object writer
   ↓
linker
```

Em paralelo, sem esperar toda essa sequência terminar, podem avançar quando houver blocos atômicos bem definidos:

- integer semantics;
- runtime/stdlib contracts;
- ownership/effects generalization;
- self-host parity;
- heterogeneous provider contracts;
- numerics/SIMD design e tests;
- application-facing APIs.

A cada etapa, a pergunta deve ser:

> Isto melhora apenas um demo ou aumenta uma capacidade geral do Sotlas?

Se a resposta for “apenas um demo”, redesenhar a entrega antes de promovê-la.

---

# 39. Regra final

Sotlas não será considerada completa porque consegue compilar um kernel, abrir uma janela, renderizar um triângulo, executar uma rede neural ou compilar a si mesma isoladamente.

A visão é mais ampla:

> uma linguagem geral, coerente, verificável, eficiente e progressivamente soberana, capaz de atravessar sistemas de baixo nível, aplicações, gráficos, engines, IA e computação de alto desempenho usando a mesma arquitetura semântica.

Este blueprint deve ser atualizado conforme essa visão deixa de ser planejamento e passa a ser evidência E2E certificada.
