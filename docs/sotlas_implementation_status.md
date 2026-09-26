# Sotlas — Implementation Status

**Atualizado em:** 2026-09-26
**Último baseline verde certificado:** `8b645c0`
**CI de referência:** Sotlas CI & Toolchain Build Farm #627 — workflow `success`
**Fonte arquitetural:** `SOTLAS — ESPECIFICAÇÃO MESTRA`

> Este é o índice operacional atual. O snapshot detalhado anterior, com o histórico extenso das microentregas da Fase 2, permanece preservado em `docs/archive/sotlas_implementation_status_2026-09-23.md`.

## Regra de status

Nenhum item recebe `SUPPORTED` apenas porque existe no parser, AST ou em um passe isolado. O 1.0 exige coerência semântica, fail-closed para formas não suportadas e um caminho backend/e2e representativo para o subset declarado estável.

Legenda:

- ✅ `COMPLETE`: gate do Sotlas 1.0 fechado;
- 🟡 `IN PROGRESS`: blockers 1.0 ainda abertos;
- `PREVIEW`: existe implementação útil, mas ela ainda não integra o contrato estável 1.0;
- `DEFER`: evolução planejada para 1.0.x/1.1.

## Progresso por fase

| Fase | Área | Progresso 1.0 | Estado |
|---:|---|---:|---|
| 0 | Reality Reset | ~85% | 🟡 |
| 1 | Typed Semantic Core | 100% | ✅ COMPLETE |
| 2 | Ownership Domains | 100% | ✅ COMPLETE |
| 3 | Authority Domains | 100% | ✅ COMPLETE |
| 4 | State Spaces | 100% | ✅ COMPLETE |
| 5 | Effects | ~57% candidato | 🟡 |
| 6 | Flow | ~47% candidato | 🟡 |
| 7 | Execution Domains | ~45% | 🟡 |
| 8 | Heterogeneous Compute | ~0% | 🟡 |
| 9 | Trust Domains | ~16% candidato | 🟡 |
| 10 | Guarantees | ~25% candidato | 🟡 |
| 11 | Causality | ~12% candidato | 🟡 |
| 12 | Counterfactuals | ~12% candidato | 🟡 |
| 13 | Transactions | ~25% candidato | 🟡 |
| 14 | Intent | ~20% candidato | 🟡 |
| 15 | SIR completo | ~42% candidato | 🟡 |
| 16 | Native Machine Backend | ~8% | 🟡 |
| 17 | Tooling avançado | ~18% | 🟡 |

Os percentuais medem o escopo necessário para o Sotlas 1.0. Generalizações pós-release não mantêm uma fase aberta quando o subset atual pode rejeitá-las de forma correta e fail-closed.

### Avanço de SIR — aritmética escalar sem sinal

- [x] retorno linear de `u8`, `u16`, `u32`, `u64` e `usize` com `+`, `-` ou `*` entre parâmetros do mesmo tipo chega ao SIR como `BinaryOpInst` e ao LLVM como operação modular;
- [x] as rotas de AST bootstrap e parser legado são cobertas;
- [x] o SIR só emite essa instrução quando operandos e resultado atendem ao subset; o backend LLVM rejeita tipos assinados e operações desconhecidas;
- [ ] constantes, demais expressões, signed overflow definido pela linguagem, CFG geral, lowering para máquina e execução nativa seguem pendentes.

### Avanço inicial de Trust Domains

- [x] `@trust(trusted|unsafe|isolated)` classifica explicitamente declarações `@extern(C)`;
- [x] fronteiras FFI exigem summary com efeito `ffi` e podem exigir classificação explícita;
- [x] o SIR preserva símbolo, convenção, classificação, efeitos e estado de verificação de isolamento;
- [x] `@trust(unsafe)` exige bloco `unsafe` explícito no ponto de chamada FFI, assim como declarações `unsafe fn`;
- [ ] política de chamadas/wrappers, enforcement de `unsafe` e isolamento real por target continuam pendentes;
- [x] `isolated` permanece marcado como não verificado até existir sandbox implementado.

API inicial: `analyze_foreign_trust_boundaries(module, require_explicit_trust=True)` em `sotlas_compile.trust_domains`.

### Avanço inicial de Causality

- [x] consulta source-stable de caminho causal entre stages em Flow tipado/SIR;
- [x] cada passo informa funções, parâmetro/valor transferido, tipo e summaries de efeitos dos dois stages;
- [x] consulta não infere caminho por mera ordem: stages desconectados e nomes ausentes falham com erro;
- [x] consulta source-stable de caminhos de chamadas diretas entre funções fora de Flow, incluindo locais, aridade, parâmetros destino e summaries de efeitos;
- [x] cada argumento da cadeia causal preserva expressão estrutural, parâmetro destino e bindings de origem;
- [ ] propagação causal de valores/expressões entre chamadas, provenance de diagnósticos e visualização IDE.

API inicial: `explain_sir_flow_causality(module, flow, source_stage, target_stage)` em `sotlas_compile.causality`.

### Avanço inicial de Counterfactuals

- [x] análise source-stable do impacto de uma stage indisponível em Flow tipado/SIR;
- [x] stages afetadas incluem o ponto indisponível e todos os consumidores transitivos; stages independentes são preservadas;
- [x] consulta valida grafo, dependências e cronograma SIR canônicos e não executa funções;
- [x] alternativas estruturais com tipo e efeitos comparados; uma allowlist explícita marca efeitos proibidos;
- [ ] equivalência semântica, estado/rollback e análise de cenários fora de Flow.

**Status 1.0: ~12% candidato 🟡 — IN PROGRESS**

- [x] opções SIR de stage em outro plano com mesmo nome e tipo de saída, sem dependência do stage indisponível;
- [x] diferenças de efeitos explícitas e avaliação opcional contra uma allowlist declarada pelo chamador;
- [x] candidatos que violam a allowlist são marcados sem descartar evidência; equivalência semântica permanece não verificada;
- [ ] alternativas com equivalência semântica provada, estado/rollback e cenários fora de Flow.

APIs: `analyze_sir_flow_stage_unavailability(module, flow, stage)` e
`analyze_sir_flow_recovery_options(module, flow, unavailable_stage,
target_stage, allowed_effects=...)` em `sotlas_compile.counterfactuals`.

### Avanço inicial de Transactions

**Status 1.0: ~25% candidato 🟡 — IN PROGRESS**

- [x] auditoria estática dos efeitos de um Flow SIR contra política explícita de reversibilidade;
- [x] efeito sem política, irreversível ou compensável sem handler bloqueia a satisfação da política de rollback;
- [x] handler declarado precisa existir no SIR;
- [x] auditoria satisfeita expõe camadas de stages que precisam de compensação em ordem reversa de dependência;
- [x] executor SIR sequencial valida política e bindings antes de iniciar qualquer stage;
- [x] falha após stages concluídas executa handlers compensatórios em ordem inversa;
- [x] falhas de compensação são retidas junto ao erro original e à lista de stages concluídas;
- [x] cronogramas paralelos são rejeitados antes da execução enquanto não houver journal concorrente seguro;
- [ ] atomicidade de efeitos externos, compensação da própria stage que falhou, snapshots `before/after` e inversas verificadas.

APIs: `analyze_sir_flow_transaction_effects(module, flow, policies, handlers)` e `execute_transactional_sir_flow(module, flow, bindings, policies, handlers)` em `sotlas_compile`.

### Integridade canônica do Flow em SIR

- [x] validador reconcilia argumentos, parâmetros, tipos de retorno, arestas, ordem paralela e summaries de efeitos do SIR;
- [x] lowering e consultas de Causality, Counterfactuals e Transactions exigem o plano reconciliado;
- [x] testes negativos adulteram argumentos e confirmam rejeição em todos os consumidores;
- [ ] execução de chamadas no CFG SIR, integração de ownership/cleanup e validação de passes contra perda de obrigações.

API: `validate_sir_flow_plans(module)` em `sotlas_compile.flow_sir`.

### Avanço inicial de Intent

**Status 1.0: ~20% candidato 🟡 — IN PROGRESS**

- [x] planejamento determinístico escolhe a primeira estratégia Flow elegível em ordem `prefer` e `fallback`;
- [x] inspeção registra efeitos observados e razões de rejeição por candidato;
- [x] constraints iniciais verificam ausência de efeitos proibidos e disponibilidade das stages escolhidas;
- [x] execução chama apenas a Flow selecionada depois de revalidar o plano Intent e reconciliar stages, tipos, dependências e efeitos entre Typed Flow e SIR;
- [x] execução alternativa consome bindings por símbolo de função e agenda o plano SIR reconciliado, revalidando preferência, fallback, efeitos proibidos e stages indisponíveis;
- [ ] sintaxe `intent`, objetivos funcionais, guarantees tipadas e lowering do plano no scheduler SIR com Ownership.

API adicional: `execute_bound_sir_intent(module, plan, function_bindings)`.

API inicial: `plan_sir_intent(module, name, prefer=..., fallback=...)` em `sotlas_compile.intent`.

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

**Status 1.0: 100% ✅ — COMPLETE**

### Núcleo semântico

- [x] `StateSpacePlan` canônico;
- [x] estados com payload contracts ordenados;
- [x] grafo explícito de transições;
- [x] estado inicial precisa ser declarado explicitamente; estado não é inferido pela ordem das declarações;
- [x] validação fail-closed de estados/transições;
- [x] `StateQualifiedType` para `Type<State>`;
- [x] boundary check e transições validadas pelo grafo;
- [x] identidade de State Space preservada;
- [x] coverage backend-neutral e exhaustiveness gate.

### Frontend e Typed AST

- [x] `space` é reconhecido na rota canônica `sotlas_compile.bootstrap`;
- [x] AST fonte preserva nome, visibilidade, estados, payloads e transições;
- [x] `Space<State>` é reconhecido como typestate no subset 1.0 quando existe `space Space`;
- [x] generics não associados a um State Space continuam compatíveis;
- [x] `StateSpaceFrontendPlan` reconcilia fonte → grafo canônico → typestate;
- [x] construção de valor nominal só recebe typestate por initializer direto quando coincide com o estado inicial declarado; outros estados não podem ser inventados na inicialização;
- [x] `StateSpaceTypedSnapshot` preserva State Spaces, payloads, edges e sites tipados;
- [x] sites de typestate possuem identidade determinística em declarações e locals explícitos;
- [x] divergência frontend ↔ Typed AST falha fechado;
- [x] `Phase1CheckedModule` carrega o snapshot tipado no pipeline opt-in;
- [x] análise Phase 1 usa uma cópia privada para reaproveitar o checker canônico sem mutar o AST original;
- [x] transição `transition(move(binding), Target)` é certificada no pipeline opt-in e preserva fato source-stable no SIR com revalidação do edge e do estado de retorno;
- [x] `check`/C11/header aceitam o subset com `sole struct`, estados sem payload e transição única em retorno `unsafe`; armazenamento, payloads e formas gerais continuam fail-closed;

### Blockers 1.0 ainda abertos

- [x] operação pública `transition(move(binding), Target)` no subset de retorno direto;
- [x] parâmetros, chamadas e retornos preservam `Type<State>` no subset direto;
- [x] inicialização explícita de valores frescos no estado inicial declarado;
- [x] fatos source-stable de transição no SIR para o subset opt-in de retorno direto;
- [x] revalidação semântica source ↔ SIR para esse subset;
- [x] lowering C11 do subset nominal, com transição validada antes da emissão;
- [x] e2e positivo nativo e rejeição semântica de edges/transições inválidos;
- [x] gate dedicado da Fase 4 na CI executa frontend, SIR e e2e C11;
- [x] API pública backend-neutral para analisar coverage e exigir exhaustividade em `StateSpacePlan` certificado;
- [x] `discern` exige cobertura exaustiva de estados no frontend de produção e seleciona o arm tipado no C11;
- [x] CI #586 confirma o e2e nativo desse subset.

### Pós-1.0

- wildcard/guards complexos de coverage;
- patterns avançados de payload;
- mapping arbitrário tipo ↔ State Space;
- typestate indireto amplo;
- merges de estado altamente path-dependent;
- state machines dinâmicas/generalizadas;
- integração ampla com UI, persistência e networking;
- otimizações e ergonomia adicionais.

Escopo: `docs/sotlas_1_0_phase4_state_space_scope.md`.

## Fase 5 — Effects

**Status 1.0: ~57% candidato 🟡 — IN PROGRESS**

- [x] SIR infere efeitos diretos e transitivos com ponto fixo sobre chamadas recursivas;
- [x] chamadas não resolvidas são classificadas como `unknown_call` e seus nomes permanecem no summary;
- [x] contratos de efeitos explícitos no SIR rejeitam efeitos desconhecidos ou omitidos;
- [x] handlers de interrupção rejeitam alocação/bloqueio transitivos, `await` e chamadas desconhecidas;
- [x] diagnósticos preservam a cadeia de chamadas até a operação proibida;
- [x] contratos `@effects(...)` reconhecidos e validados pelo checker da rota canônica;
- [x] inferência direta/transitiva sobre chamadas locais recursivas, builtins classificados, FFI sem contrato e `asm`;
- [x] summaries determinísticos source-stable anexados ao módulo verificado;
- [x] contratos malformados ou que omitem efeitos falham antes do lowering C11;
- [x] summaries diretos/transitivos, não resolvidos e declarados preservados por função na Typed AST;
- [x] summaries de fonte acompanham funções no SIR e contratos declarados são revalidados pela inferência SIR;
- [x] contrato backend-neutral aceita ou rejeita funções conforme os efeitos SIR revalidados;
- [x] emissor LLVM aceita contrato explícito de capacidades e valida inferência SIR antes de emitir IR;
- [x] C11 aplica contrato de lowering e rejeita `async` antes de emitir código sem runtime de suspensão;
- [x] `@realtime` valida efeitos inferidos transitivamente e rejeita alocação, bloqueio, async, I/O, sincronização, FFI e chamadas desconhecidas;
- [x] dump SIR inclui efeitos inferidos/declarados e chamadas desconhecidas por função;
- [x] declarações `extern "C"` carregam efeito `ffi` distinto e contratos omissos falham;
- [ ] contratos C11/LLVM cobrem todos os efeitos, capabilities e runtimes por target;
- [ ] restrições completas para `@realtime`, async, locks, FFI e efeitos externos;
- [x] testes end-to-end de fonte Sotlas e gate dedicado desta fatia;
- [ ] end-to-end amplo por domínio e matriz de runtime/backend.

Escopo: `docs/sotlas_1_0_phase5_effects_scope.md`.

## Fase 6 — Flow

**Status 1.0: ~47% candidato 🟡 — IN PROGRESS**

- [x] grafo backend-neutral valida dependências e rejeita ciclos;
- [x] estágios paralelos são derivados deterministicamente da topologia e da ordem declarada;
- [x] executor local roda nós independentes por estágio e limita workers;
- [x] ações recebem somente outputs de dependências diretas por mapa imutável;
- [x] falha/cancelamento param estágios posteriores, cancelam tarefas pendentes e aguardam peers já iniciados;
- [x] sintaxe fonte `flow` com stages e dependências declaradas;
- [x] frontend confere funções de stage, ciclos, aridade e tipos dos valores dependentes;
- [x] CI #588 confirma a nova sintaxe e tipagem;
- [x] plano tipado Flow é reconciliado com assinaturas e summaries Effects e anexado ao SIR canônico;
- [x] runtime local executa o plano tipado por nome de stage, reconcilia dependências e passa resultados na ordem declarada;
- [x] runner SIR revalida o plano canônico, reconcilia funções/efeitos e encaminha outputs por provenance para bindings explícitos do scheduler local;
- [x] consulta source-stable explica caminho causal entre stages usando argumentos tipados e summaries Effects do SIR;
- [ ] lowering das chamadas de stage em CFG executável, integração de Ownership e execução pelo scheduler;
- [ ] cancelamento cooperativo, runtime assíncrono/distribuído e backpressure;
- [ ] e2e de fonte Sotlas para runtime/backend.

Escopo: `docs/sotlas_1_0_phase6_flow_scope.md`.

## Fase 7 — Execution Domains

**Status 1.0: ~45% 🟡 — IN PROGRESS**

- [x] modelo tipado de target x86-64, ABI básica, largura de ponteiro e endianness;
- [x] triples Linux, Windows, Darwin e freestanding reconhecidos com aliases legados;
- [x] validação fail-closed e normalização de dependências de CPU features;
- [x] LLVM IR e Clang recebem target/features configurados;
- [x] `@target_feature(...)` é preservado no SIR e o LLVM rejeita targets sem as features requeridas; backend C11 falha fechado para essa anotação;
- [x] CLI expõe seleção de target e features x86-64;
- [x] presets LLVM/ABI AArch64 Linux, Windows, Darwin e freestanding;
- [x] data layouts LLVM por formato de objeto ELF, COFF e Mach-O nos presets x86-64 e AArch64;
- [x] layout x86-64 Darwin usa mangling Mach-O e a ABI i128/f80 correspondente, em vez do layout ELF;
- [x] features AArch64 `crc`, `aes`, `sha2`, `lse`, `sve`, `sve2` são validadas por arquitetura e normalizadas;
- [x] flags freestanding e seleção de features AArch64 não recebem flags x86;
- [x] testes de target, ABI declarado, dependências de features e atributos LLVM AArch64;
- [ ] matrizes completas de ABI/layout e suporte x86-64/AArch64;
- [ ] intrinsics SIMD Sotlas e dispatch multi-versionado;
- [ ] domains de execução e lowering heterogêneo tipado;
- [x] gate dedicado da configuração de execution targets na CI;
- [ ] testes nativos positivos/negativos e matriz de release por target.

Escopo: `docs/sotlas_1_0_phase7_execution_scope.md`.

## Fase 10 — Guarantees

**Status 1.0: ~25% candidato 🟡 — IN PROGRESS**

- [x] `requires` tipado em funções com corpo;
- [x] chamadas com argumentos constantes são provadas ou rejeitadas;
- [x] chamadas falsas falham estaticamente; demais chamadas são guardadas em runtime;
- [x] funções públicas mantêm a precondição no ABI C11 com guarda de entrada;
- [x] relatório de prova da chamada é preservado no SIR canônico;
- [x] fatos booleanos de branches `if`/`else` provam precondições dinâmicas simples e são preservados no SIR;
- [x] comparações inteiras simples em branches provam implicações por limites, como `value > 0` ⇒ `value != 0`;
- [x] refinamentos são invalidados depois de atribuições locais e chamadas potencialmente mutáveis;
- [x] `ensures result` tipado para retorno numérico escalar, com guarda em cada retorno C11 e evidência preservada no SIR;
- [x] a primeira versão falha fechado para funções `void`, retornos não escalares e pós-condições que referenciam parâmetros;
- [ ] prova simbólica por refinamento de condições e argumentos dinâmicos;
- [ ] pós-condições sobre estado/heap, declaração `guarantee`, safety reports e gate e2e por propriedade.

Escopo: `docs/sotlas_1_0_phase10_guarantees_scope.md`.

## Fase 17 — Tooling avançado

**Status 1.0: ~20% 🟡 — IN PROGRESS**

- [x] CLI emite `contract-report` como JSON determinístico derivado do SIR canônico;
- [x] o relatório separa provas estáticas de precondições e pós-condições que ainda exigem guarda em runtime;
- [x] `--emit-asm` encaminha diretamente o subset validado ao backend LLVM e falha fechado para construções ainda não representadas;
- [ ] inspeção de Target IR/lowering, register allocation, ABI/stack e source-to-instruction mapping.

### SIR e backend nativo — slice de constantes inteiras

- [x] retorno de literal inteiro tipado `i/u8`, `i/u16`, `i/u32`, `i/u64`, `isize` e `usize` baixa para `ConstantIntInst` no SIR;
- [x] bootstrap e AST legado cobertos para literais decimais; bootstrap também aceita literal hexadecimal tipado;
- [x] LLVM verifica tipo e intervalo antes de emitir o valor;
- [x] `--emit-asm` aceita retorno direto e aritmética inteira unsigned de parâmetros no subset LLVM; a cobertura nativa depende de Clang/LLVM disponível;
- [ ] lowering nativo validado com `llc`/Clang, execução por target, CFG completo e semântica definida de overflow.

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
