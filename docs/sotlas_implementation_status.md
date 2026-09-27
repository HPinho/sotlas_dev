# Sotlas — Implementation Status

**Atualizado em:** 2026-09-26
**Último baseline verde certificado antes do candidato 1.0:** `ea527ea`
**CI de referência:** Sotlas CI & Toolchain Build Farm #653 — workflow `success` nessa baseline. O commit de release precisa ter execução própria verde.
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
| 0 | Reality Reset | 100% do contrato 1.0 | ✅ COMPLETE |
| 1 | Typed Semantic Core | 100% | ✅ COMPLETE |
| 2 | Ownership Domains | 100% | ✅ COMPLETE |
| 3 | Authority Domains | 100% | ✅ COMPLETE |
| 4 | State Spaces | 100% | ✅ COMPLETE |
| 5 | Effects | 100% do contrato 1.0 | ✅ COMPLETE |
| 6 | Flow | 100% do contrato 1.0 | ✅ COMPLETE |
| 7 | Execution Domains | 100% do contrato 1.0 | ✅ COMPLETE |
| 8 | Heterogeneous Compute | 100% do contrato 1.0 | ✅ COMPLETE |
| 9 | Trust Domains | 100% do contrato 1.0 | ✅ COMPLETE |
| 10 | Guarantees | 100% do contrato 1.0 | ✅ COMPLETE |
| 11 | Causality | 100% do contrato 1.0 | ✅ COMPLETE |
| 12 | Counterfactuals | 100% do contrato 1.0 | ✅ COMPLETE |
| 13 | Transactions | 100% do contrato 1.0 | ✅ COMPLETE |
| 14 | Intent | 100% do contrato 1.0 | ✅ COMPLETE |
| 15 | SIR canônico | 100% do subset canônico 1.0 | ✅ COMPLETE |
| 16 | Native Machine Backend | 100% do backend LLVM 1.0 | ✅ COMPLETE |
| 17 | Tooling avançado | 100% dos relatórios CLI 1.0 | ✅ COMPLETE |

Os percentuais medem o escopo necessário para o Sotlas 1.0. Generalizações pós-release não mantêm uma fase aberta quando o subset atual pode rejeitá-las de forma correta e fail-closed.

Escopos concluídos: `docs/phase0_reality_audit.md`, contratos 1.0 das fases 5–10 e `docs/sotlas_1_0_phases_13_17_scope.md`.

## Preview hardening update — 2026-09-26

- The reviewed evidence map for phases 0–17 is generated from `phase_gate_matrix.json`; its test verifies phase coverage, gate-file existence, and generated-document freshness.
- CI now runs explicit gates for phases 0–3 and 11–12, in addition to the existing phase-specific gates and the complete test suite.
- `check`, `compile --emit-c`, and `run` have a shared negative acceptance test that compares the exact diagnostic, source location, caret, and safe parser hint.
- The SIR Flow interpreter now accepts checked boolean parameters and parameter forwarding; the new Flow case runs a comparison result through a second stage.
- C11 and direct LLVM are compared by compiling the same unsigned arithmetic function and running both artifacts with the same native C caller and inputs.
- Standard-library ownership, mutability, allocator lifetime, cleanup, and failure contracts are documented in `stdlib/core/README.md`.
- Flow now emits a C-callable C11 entrypoint for serial pure signed/unsigned integer and bool plans; native callers receive the final stage result. The gate rejects parallel plans, unsupported types, contracts, global access, method calls, and system/foreign stage functions. Parallel native scheduling, source-level Flow invocation, error/cancellation propagation, ownership payloads, and GPU/NPU providers remain open. Production compiler self-hosting also remains open: Sotlas-lite does not replace the Python compiler.
- `tests/test_sotlas_flow_native.py` compiles and executes the generated entrypoint with the same C toolchain used by the native preview gates.

## Fase 0 — Reality Reset

**Status 1.0: 100% do contrato de realidade — COMPLETE**

- [x] frontend de produção, maturidade certificada e limites do SIR protótipo são identificados sem claims globais de suporte;
- [x] exemplos e snippets públicos são classificados; a fonte marcada `RUNNABLE` passa pelo CLI canônico e emissão C11 em CI;
- [x] versão, maturidade, quickstarts, inventário e paridade `compiler/`/`tools/` são cobertos por reality gates;
- [x] diferenças e módulos exclusivos das árvores duplicadas são inventariados; `compiler/` é a fonte instalada canônica;
- [x] a retenção temporária da árvore histórica `tools/` e a consolidação pós-1.0 estão documentadas como decisão de compatibilidade.

Escopo e decisão de migração: `docs/phase0_reality_audit.md`.

### Avanço de Heterogeneous Compute — pipeline de referência DEVICE

- [x] API compõe um `Phase1CheckedModule` verificado com lifecycle canônico, SIR, ABI lógico/físico e artefato C11 do runtime de referência;
- [x] identidades de handover/completion/sync/reacquisition são preservadas de ponta a ponta;
- [x] bindings SIR explícitos devem corresponder exatamente aos owners certificados; bindings ausentes ou extras falham fechado;
- [x] execução nativa Clang valida a transferência e reacquisition para dois owners;
- [ ] provider de hardware/DMA, completion física, sincronização do target, falha/timeout e matriz por dispositivo continuam pendentes; a implementação atual é somente o runtime de referência single-threaded.

### Avanço de SIR — aritmética escalar sem sinal

- [x] retorno linear de `u8`, `u16`, `u32`, `u64` e `usize` com `+`, `-` ou `*` entre parâmetros do mesmo tipo chega ao SIR como `BinaryOpInst` e ao LLVM como operação modular;
- [x] comparação direta de parâmetros inteiros de mesmo tipo chega ao SIR como `CompareInst`; o subset LLVM emite comparações signed/unsigned e uma comparação signed passou por execução nativa via caller C;
- [x] as rotas de AST bootstrap e parser legado são cobertas;
- [x] o SIR só emite essa instrução aritmética unsigned quando operandos e resultado atendem ao subset; o backend LLVM rejeita tipos assinados e operações desconhecidas;
- [ ] constantes em expressões, demais formas aritméticas, signed overflow definido pela linguagem, CFG geral e lowering completo para máquina seguem pendentes.

### Avanço inicial de Trust Domains

- [x] `@trust(trusted|unsafe|isolated)` classifica explicitamente declarações `@extern(C)`;
- [x] fronteiras FFI exigem summary com efeito `ffi` e podem exigir classificação explícita;
- [x] o SIR preserva símbolo, convenção, classificação, efeitos e estado de verificação de isolamento;
- [x] `@trust(unsafe)` exige bloco `unsafe` explícito no ponto de chamada FFI, assim como declarações `unsafe fn`;
- [ ] política de chamadas/wrappers, enforcement de `unsafe` e isolamento real por target continuam pendentes;
- [x] `isolated` permanece marcado como não verificado até existir sandbox implementado.
- [x] cada boundary no SIR declara o contexto obrigatório (`system`, mais `unsafe` para trust unsafe ou função foreign unsafe), permitindo auditorias de backend sem inferir política do rótulo;

API inicial: `analyze_foreign_trust_boundaries(module, require_explicit_trust=True)` em `sotlas_compile.trust_domains`.

### Execução interpretada do subset SIR Flow

- [x] stages puros de inteiros sem sinal executam a partir dos corpos SIR validados, sem bindings fornecidos pelo host;
- [x] comparacoes unsigned EQ/NEQ/LT/LTE/GT/GTE retornam bool no interpretador;
- [x] o subset aceita constantes, `add`/`sub`/`mul`, retorno direto e a materialização inerte de parâmetros em slots;
- [x] planos, provenance, summaries de efeitos, assinaturas, tipos e forma linear do corpo são verificados antes do scheduler;
- [x] operações, efeitos, tipos, CFG e instruções fora do subset falham fechados;
- [ ] CFG arbitrário, integração de ownership/cleanup e execução nativa pelo backend continuam pendentes.

API candidata: `execute_interpreted_sir_flow(module, flow, ...)` em `sotlas_compile`.

### Avanço inicial de Causality

- [x] consulta source-stable de caminho causal entre stages em Flow tipado/SIR;
- [x] cada passo informa funções, parâmetro/valor transferido, tipo e summaries de efeitos dos dois stages;
- [x] consulta não infere caminho por mera ordem: stages desconectados e nomes ausentes falham com erro;
- [x] consulta source-stable de caminhos de chamadas diretas entre funções fora de Flow, incluindo locais, aridade, parâmetros destino e summaries de efeitos;
- [x] cada argumento da cadeia causal preserva expressão estrutural, parâmetro destino e bindings de origem;
- [x] bindings seguem aliases locais imutáveis em sequência linear antes de `return`/chamada; mutação e controle de fluxo continuam sem resolução especulativa;
- [x] propagação causal de valores/expressões entre chamadas, provenance de diagnósticos e visualização IDE.
- [x] causal provenance propagates origins and expressions across a deterministic call chain; Mermaid output includes source locations.
- [x] unresolved mutation, ambiguous aliases, and control flow remain fail-closed.

**Status 1.0: 100% do contrato delimitado; limites futuros em docs/sotlas_1_0_phases_11_12_scope.md.**
API inicial: `explain_sir_flow_causality(module, flow, source_stage, target_stage)` em `sotlas_compile.causality`.

### Avanço inicial de Counterfactuals

- [x] análise source-stable do impacto de uma stage indisponível em Flow tipado/SIR;
- [x] stages afetadas incluem o ponto indisponível e todos os consumidores transitivos; stages independentes são preservadas;
- [x] consulta valida grafo, dependências e cronograma SIR canônicos e não executa funções;
- [x] alternativas estruturais com tipo e efeitos comparados; uma allowlist explícita marca efeitos proibidos;
- [x] equivalência limitada para expressões SIR puras unsigned idênticas, com igualdade dos produtores usados provada recursivamente;
- [x] normalização comutativa de `add` e `mul` unsigned puros reconhece operandos invertidos, mantendo iguais as provas recursivas dos produtores;
- [x] normalização modular unsigned faz constant folding e reduz identidades seguras (`x + 0`, `x - 0`, `x * 1`, `x * 0`) antes da prova recursiva de produtores;
- [x] equivalência além do subset estrutural, estado/rollback e análise de cenários fora de Flow.

**Status 1.0: 100% do contrato delimitado; limites futuros em docs/sotlas_1_0_phases_11_12_scope.md.**

- [x] opções SIR de stage em outro plano com mesmo nome e tipo de saída, sem dependência do stage indisponível;
- [x] diferenças de efeitos explícitas e avaliação opcional contra uma allowlist declarada pelo chamador;
- [x] candidatos que violam a allowlist são marcados sem descartar evidência;
- [x] equivalência só é marcada quando os corpos são expressões puras unsigned normalizadas por comutatividade, constant folding e identidades seguras, e cada producer usado tem equivalência recursiva;
- [x] prova para transformações algébricas não idênticas, estado/rollback e cenários fora de Flow.

- [x] modular polynomial equivalence for pure unsigned expressions, pure SIR function equivalence, and rollback plans for sequential Flow, within documented limits.
APIs: `analyze_sir_flow_stage_unavailability(module, flow, stage)` e
`analyze_sir_flow_recovery_options(module, flow, unavailable_stage,
target_stage, allowed_effects=...)` em `sotlas_compile.counterfactuals`.

### Fase 13 — Transactions

**Status 1.0: 100% do contrato de auditoria e execução sequencial — COMPLETE**

- [x] auditoria estática dos efeitos de um Flow SIR contra política explícita de reversibilidade;
- [x] efeito sem política, irreversível ou compensável sem handler bloqueia a satisfação da política de rollback;
- [x] handler declarado precisa existir no SIR;
- [x] assinatura do handler é validada contra o tipo de saída da stage antes de qualquer execução ou rollback;
- [x] auditoria satisfeita expõe camadas de stages que precisam de compensação em ordem reversa de dependência;
- [x] executor SIR sequencial valida política e bindings antes de iniciar qualquer stage;
- [x] falha após stages concluídas executa handlers compensatórios em ordem inversa;
- [x] falhas de compensação são retidas junto ao erro original e à lista de stages concluídas;
- [x] cronogramas paralelos são rejeitados antes da execução enquanto não houver journal concorrente seguro;
- [x] atomicidade externa, efeitos da própria stage que falha, snapshots e inversas sem prova permanecem fora do rollback garantido e falham fechado quando exigidos.

APIs: `analyze_sir_flow_transaction_effects(module, flow, policies, handlers)` e `execute_transactional_sir_flow(module, flow, bindings, policies, handlers)` em `sotlas_compile`.

### Integridade canônica do Flow em SIR — parte das fases 13 e 15

- [x] validador reconcilia argumentos, parâmetros, tipos de retorno, arestas, ordem paralela e summaries de efeitos do SIR;
- [x] lowering e consultas de Causality, Counterfactuals e Transactions exigem o plano reconciliado;
- [x] testes negativos adulteram argumentos e confirmam rejeição em todos os consumidores;
- [x] chamadas gerais no CFG SIR, integração de ownership/cleanup e verificação ampla de passes são explicitamente pós-1.0; as operações do subset são reconciliadas antes de uso.

API: `validate_sir_flow_plans(module)` em `sotlas_compile.flow_sir`.

### Fase 14 — Intent

**Status 1.0: 100% da API de planejamento e execução verificada — COMPLETE**

- [x] planejamento determinístico escolhe a primeira estratégia Flow elegível em ordem `prefer` e `fallback`;
- [x] inspeção registra efeitos observados e razões de rejeição por candidato;
- [x] constraints iniciais verificam ausência de efeitos proibidos e disponibilidade das stages escolhidas;
- [x] execução chama apenas a Flow selecionada depois de revalidar o plano Intent e reconciliar stages, tipos, dependências e efeitos entre Typed Flow e SIR;
- [x] execução alternativa consome bindings por símbolo de função e agenda o plano SIR reconciliado, revalidando preferência, fallback, efeitos proibidos e stages indisponíveis;
- [x] sintaxe declarativa `intent`, goals, guarantees tipadas e integração de Ownership estão explicitamente pós-1.0; planos API desconhecidos/adulterados falham fechado.

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

**Status 1.0: 100% do contrato delimitado — COMPLETE**

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
- [x] emissor C11 aceita contrato explícito de capacidades, revalida os efeitos do SIR e bloqueia a emissão antes de gerar código quando o target não permite os efeitos inferidos;
- [x] `@realtime` valida efeitos inferidos transitivamente e rejeita alocação, bloqueio, async, I/O, sincronização, FFI e chamadas desconhecidas;
- [x] dump SIR inclui efeitos inferidos/declarados e chamadas desconhecidas por função;
- [x] declarações `extern "C"` carregam efeito `ffi` distinto e contratos omissos falham;
- [x] contrato C11 automático rejeita `async` sem runtime de suspensão e `unknown_call` sem ABI/efeito verificados;
- [x] `extern "C"` com efeito `ffi` é a fronteira estrangeira explícita; summaries C11/LLVM são revalidados antes do lowering;
- [x] chamadas de locks conhecidas são classificadas como `sync`; nomes de runtime não catalogados permanecem `unknown_call` e falham fechados na fronteira C11;
- [x] `@realtime` aplica restrições transitivas a alocação, bloqueio, async, I/O, sync, FFI e chamadas desconhecidas;
- [x] testes end-to-end de fonte Sotlas e gate dedicado desta fatia;
- [x] testes positivos/negativos e gates dedicados validam o contrato de efeitos do subset Sotlas 1.0.

Escopo e limites pós-1.0: `docs/sotlas_1_0_phase5_effects_scope.md`.

## Fase 6 — Flow

**Status 1.0: 100% do contrato delimitado — COMPLETE**

- [x] grafo backend-neutral valida dependências e rejeita ciclos;
- [x] estágios paralelos são derivados deterministicamente da topologia e da ordem declarada;
- [x] executor local roda nós independentes por estágio e limita workers;
- [x] ações recebem somente outputs de dependências diretas por mapa imutável;
- [x] falha/cancelamento param estágios posteriores, cancelam tarefas pendentes e aguardam peers já iniciados;
- [x] sintaxe fonte `flow` com stages e dependências declaradas;
- [x] frontend confere funções de stage, ciclos, aridade e tipos dos valores dependentes;
- [x] testes fonte→SIR→CFG→scheduler confirmam a sintaxe, tipagem e execução do subset;
- [x] plano tipado Flow é reconciliado com assinaturas e summaries Effects e anexado ao SIR canônico;
- [x] runtime local executa o plano tipado por nome de stage, reconcilia dependências e passa resultados na ordem declarada;
- [x] runner SIR revalida o plano canônico, reconcilia funções/efeitos e encaminha outputs por provenance para bindings explícitos do scheduler local;
- [x] runners Flow tipado e SIR podem injetar token cooperativo nos bindings e validam cancelamento externo antes de iniciar stages dependentes;
- [x] consulta source-stable explica caminho causal entre stages usando argumentos tipados e summaries Effects do SIR;
- [x] executor de grafo oferece token cooperativo opt-in, permite que actions parem após cancelamento ou falha de peer e faz join dos workers;
- [x] `flow-report` serializa em JSON determinístico o cronograma, assinaturas, efeitos e provenance de cada plano validado no SIR;
- [x] planos estritamente seriais de tipos escalares baixam a `CallInst` em CFG SIR certificado e validado contra plano, assinaturas, dependências e provenance;
- [x] scheduler executa o CFG certificado interpretando os corpos SIR puros e revalida efeitos antes da execução;
- [x] entrypoint C11 nativo para Flow estritamente serial, puro e escalar (`i8/i16/i32/i64/isize/u8/u16/u32/u64/usize/bool`), chamado e verificado por um caller C;
- [x] Flow C11 falha fechado para planos paralelos, efeitos, acesso global direto/transitivo, chamadas de método, contratos, funções foreign/system e tipos fora do subset;
- [x] teste end-to-end parte de fonte Sotlas, constrói SIR/CFG e confirma resultados no scheduler;
- [x] formas fora do contrato (CFG paralelo executável, efeitos em stages, tipos com ownership/lifetime) falham fechadas antes de executar.

Escopo e limites pós-1.0: `docs/sotlas_1_0_phase6_flow_scope.md`.

## Fase 7 — Execution Domains

**Status 1.0: 100% do contrato de configuração e validação de targets — COMPLETE**

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
- [x] matriz de presets x86-64/AArch64 coberta para triples, ABI identificada, largura, endianness e layouts LLVM dos formatos suportados;
- [x] features SIMD de CPU têm registro limitado, normalização, validação e encaminhamento; intrinsics Sotlas e dispatch multi-versionado são explicitamente pós-1.0;
- [x] targets e features não suportados falham fechado; lowering heterogêneo pertence às fases de backend/domain;
- [x] gate dedicado da configuração de execution targets na CI;
- [x] testes positivos/negativos do contrato de target e argumentos Clang específicos de arquitetura; execução nativa em todos os targets é pós-1.0.

Escopo: `docs/sotlas_1_0_phase7_execution_scope.md`.

## Fase 8 — Heterogeneous Compute

**Status 1.0: 100% do contrato do runtime DEVICE de referência — COMPLETE**

- [x] fonte verificada compõe lifecycle, SIR, ABI lógico/físico e artefato C11;
- [x] submit, completion, synchronization e reacquisition preservam identidades e ordem;
- [x] bindings de owners devem coincidir exatamente com os certificados;
- [x] lifecycle single-owner e batch multi-owner têm testes end-to-end;
- [x] ABI gerado liga ao provider C de referência e executa nativamente, incluindo consumo da fence;
- [x] CI executa runtime, pipeline de fonte a C11 e link/run nativo;
- [x] hardware, DMA, driver, falhas/timeouts e GPU/NPU físicos são explicitamente pós-1.0.

Escopo: `docs/sotlas_1_0_phase8_heterogeneous_compute_scope.md`.

## Fase 9 — Trust Domains

**Status 1.0: 100% do contrato de fronteiras FFI — COMPLETE**

- [x] classificação `trusted`, `unsafe` e `isolated` validada em `extern(C)`;
- [x] efeito `ffi`, ABI C e contexto obrigatório são preservados no SIR;
- [x] chamadas FFI exigem `@system`; trust/declaração unsafe exige bloco `unsafe` explícito;
- [x] provenance de ponteiro estrangeiro mantém as regras de acesso cru;
- [x] testes positivos e negativos cobrem classificação e contexto de chamada;
- [x] CI executa gates de efeitos/trust e unsafe FFI;
- [x] `isolated` é sempre não verificado; sandbox e isolamento físico são pós-1.0.

Escopo: `docs/sotlas_1_0_phase9_trust_domains_scope.md`.

## Fase 10 — Guarantees

**Status 1.0: 100% do contrato escalar de requires/ensures — COMPLETE**

- [x] `requires` tipado em funções com corpo;
- [x] chamadas com argumentos constantes são provadas ou rejeitadas;
- [x] chamadas falsas falham estaticamente; demais chamadas são guardadas em runtime;
- [x] funções públicas mantêm a precondição no ABI C11 com guarda de entrada;
- [x] relatório de prova da chamada é preservado no SIR canônico;
- [x] fatos booleanos de branches `if`/`else` provam precondições dinâmicas simples e são preservados no SIR;
- [x] comparações inteiras simples em branches provam implicações por limites, como `value > 0` ⇒ `value != 0`;
- [x] refinamentos são invalidados depois de atribuições locais e chamadas potencialmente mutáveis;
- [x] `ensures result` tipado para retornos numéricos e booleanos escalares, com guarda em cada retorno C11 e evidência preservada no SIR; retorno booleano falso que viola a pós-condição falha em execução nativa;
- [x] `ensures` pode comparar o resultado com parâmetros escalares numéricos/booleanos;
- [x] contratos ainda falham fechado para funções `void`, retornos não escalares e parâmetros não escalares;
- [x] prova de fluxo por fatos exatos de branch e implicações inteiras suportadas, com invalidação conservadora;
- [x] `contract-report` separa prova estática e guardas dinâmicas em JSON determinístico;
- [x] CI cobre frontend, guardas em execução nativa e relatório;
- [x] prova geral de teoremas, estado/heap, declaração `guarantee` e safety reports estão delimitados como pós-1.0.

Escopo: `docs/sotlas_1_0_phase10_guarantees_scope.md`.

## Fase 15 — SIR canônico suportado

**Status 1.0: 100% do subset canônico validado — COMPLETE**

- [x] fonte verificada baixa para SIR com placement de Ownership, summaries de efeitos, trust boundaries, contratos e planos Flow suportados;
- [x] plano Flow é reconciliado com assinaturas, argumentos, dependências, schedule e efeitos antes de consumidores canônicos;
- [x] adulterações de tipos/arestas/schedule falham fechado nos consumidores;
- [x] `sir-report` expõe inventário determinístico de funções, blocos, operações e Flows validados;
- [x] CFG arbitrário, todos os corpos da linguagem e serialização reimportável estão fora do contrato 1.0.

## Fase 16 — Native Machine Backend

**Status 1.0: 100% do caminho nativo direto via LLVM para o subset certificado — COMPLETE**

- [x] subset SIR suportado baixa diretamente para LLVM IR sem C intermediário;
- [x] LLVM emite assembly, objetos relocáveis e executáveis no host;
- [x] testes cobrem retorno, aritmética/comparação escalar, branches/phi, objeto e execução por caller C;
- [x] formas SIR e domínios não baixados são rejeitados antes de gerar artefato;
- [x] selector/alocador próprios, ABI completa, unwind/debug completo e targets executáveis adicionais são pós-1.0.

## Fase 17 — Tooling avançado

**Status 1.0: 100% dos relatórios determinísticos de compilação — COMPLETE**

- [x] CLI emite `contract-report` como JSON determinístico derivado do SIR canônico;
- [x] CLI emite `flow-report` determinístico somente depois de reconciliar cada plano com o SIR canônico;
- [x] o relatório separa provas estáticas de precondições e pós-condições que ainda exigem guarda em runtime;
- [x] `--emit-asm` encaminha diretamente o subset validado ao backend LLVM e falha fechado para construções ainda não representadas;
- [x] `target-report` emite JSON estável com triple, ABI, largura de ponteiro, endianness, CPU, features normalizadas e data layout;
- [x] `sir-report` apresenta inventário JSON do subset SIR canônico após revalidar planos Flow;
- [x] fonte inválida é rejeitada sem relatório JSON parcial;
- [x] visualizações interativas, alocação de registradores, ABI/stack e source-to-instruction mapping são pós-1.0.

### SIR e backend nativo — slice de constantes inteiras

- [x] retorno de literal inteiro tipado `i/u8`, `i/u16`, `i/u32`, `i/u64`, `isize` e `usize` baixa para `ConstantIntInst` no SIR;
- [x] bootstrap e AST legado cobertos para literais decimais; bootstrap também aceita literal hexadecimal tipado;
- [x] LLVM verifica tipo e intervalo antes de emitir o valor;
- [x] `--emit-asm` e `--emit=asm` aceitam retorno direto e aritmética inteira unsigned de parâmetros no subset LLVM; a cobertura nativa depende de Clang/LLVM disponível;
- [x] execução nativa chama um objeto Sotlas com aritmética unsigned por parâmetros e confere o resultado por um caller C compilado;
- [x] aritmética unsigned linear no SIR aceita operandos literais tipados e preserva a operação modular; retorno direto do parâmetro unsigned também chega ao SIR sem instruções extras;
- [x] função Sotlas com comparação signed direta de parâmetros compila para objeto LLVM e executa via caller C para os casos `-10 < 2` e `2 < -10`;
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
