# Sotlas — Implementation Status

**Atualizado em:** 2026-09-23
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
- [x] by-value `sole` method receivers participate in ownership transfers; shared receivers require explicit handover
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
- [x] grafo canônico de Ownership Domains integrado ao snapshot semântico, com nós function-scoped e arestas de transferência; pontos source-stable duplicados ou compartilhados entre movimento, `share`, `handover` e `quarantine` são rejeitados fail-closed; fatos de destino de `handover`, tipo/domínio da transição e resultados de merge são revalidados ao construir o grafo
- [x] `quarantine` produz transição tipada no grafo canônico com origem `exclusive`, destino `island`, fonte `LIVE` e ponto source-stable; isso fecha a validação semântica/IR da transição, sem habilitar runtime/backend
- [x] `handover` `island → island` preserva o domínio e o destino no graph; C11 repõe cleanup/deinit no binding destino e execução nativa confirma o valor transferido e uma destruição por owner
- [x] C11 baixa `quarantine` validado como transição estática e `handover source to destination` validado como transferência entre bindings; handover sem destino e runtime/weak-alias continuam bloqueados
- [x] C11 baixa `island T` por valor em parâmetros/retornos de funções com tipos `sole`; também aceita campo `island T` em container `sole` quando o payload é POD recursivo sem ponteiros, ownership aninhado ou cleanup implícito; globals, enum, classes e formas indiretas continuam fail-closed
- [x] LLVM rejeita ARC, domain transfer, `WhisperBorrowInst` e `DeferUseInst` sem runtime ABI; `DirectAccessInst` validado como borrow `exclusive/shared/direct` call-scoped baixa para anotação LLVM sem bookkeeping; pipeline fonte→LLVM integra o graph apenas para chamadas lineares `direct` com owners `sole` triviais
- [x] SIR baixa `defer Name` como `DeferUseInst` antes do ARC em fallthrough, break/continue e early returns source-identified; retorno cedo preserva apenas registros ativos no ramo
- [x] lowering SIR de chamadas diretas diferidas em early returns quando o payload tem argumentos nomeados tipados; deduplicação por `defer@` e ordenação antes do ARC estão cobertas
- [x] SIR baixa `defer receiver.method(named_args)` como `CallInst` source-stable quando receiver e argumentos são bindings diretos, inclusive nos early returns estruturados suportados
- [x] chamadas a parâmetros `whisper` registram aresta de borrow source-stable no Ownership Domain Graph e preservam o fato como `WhisperBorrowInst` no plano SIR; borrows de owners `island` exigem `&binding` direto, estado LIVE e prova no-escape, sem mover a origem nem permitir storage/retorno
- [x] `direct` aceita borrow imutável call-scoped de owner `island` LIVE; o edge chega ao graph/SIR e passou execução nativa C11 e compilação LLVM até objeto no subset POD linear, com prova no-escape preservada
- [x] receivers de métodos `direct` aceitam owner `island` LIVE como borrow call-scoped; o graph/SIR preserva `Token_inspect` e C11 executa a leitura nativa
- [x] escape checks de `whisper` acompanham aliases locais e rejeitam retorno de ponteiro/member, casts para ponteiro bruto ou inteiro e forwarding sem summary no-escape verificado; o checker de produção prova summaries por ponto fixo para calls diretas; leituras escalares copiadas e forwarding para funções provadas permanecem permitidos
- [x] summaries no-escape de `whisper` resolvem ciclos recursivos fechados por maior ponto fixo; uma dupla recursiva compilou e executou no C11, e um ciclo com membro escapante continua rejeitado
- [x] backend C11 baixa parâmetros e receivers de método `whisper` internos com lifetime/no-escape verificados como `const T *`; leitura escalar e forwarding entre duas funções foram compilados com warnings-as-errors e executados nativamente, enquanto storage, retorno e FFI continuam rejeitados
- [x] `quarantine` rejeita aliases locais usados após a transição, aliases em campos e aliases criados após o isolamento; aliases enviados a chamadas opacas ou armazenados fora do escopo bloqueiam o isolamento; aliases mortos antes da transição continuam aceitos; usos em ramos mutuamente exclusivos são distinguidos, o join continua conservador e loops com alias do owner falham fechado até análise path-sensitive completa
- [x] bloco `defer { call(named_args); }` com uma chamada direta/método e bindings diretos preserva `defer@L:C` e baixa para `CallInst` no SIR em break/continue e em cada early return
- [ ] argumentos por referência/complexos, blocos com múltiplas instruções e payloads assign/try ainda precisam de lowering tipado dedicado
- [x] defers shared em fallthrough de bloco condicional/unsafe e backedge de loop sem placement lexical são rejeitados fail-closed; defer interno não contamina a saída normal da função
- [x] SIR coloca cleanup de early-return e function-exit no mesmo CFG quando o caminho explícito e o fallthrough coexistem

### Falta para concluir a Fase 2

- [x] `exclusive` formalizado como fato explícito no Typed AST de tipos sole, parâmetros e retornos; `sole` permanece a sintaxe que origina o contrato
- [ ] `shared` end-to-end: frontend/Typed AST, accounting, graph→SIR e lowering C11 experimental de aliases locais imutáveis existem; payloads escalares, POD aninhado e árvores de campos `sole` atravessando wrappers e arrays fixos multidimensionais por valor foram compilados/executados nativamente com Clang, incluindo aliases em cadeia, cleanup em `if`/early-return, loops com aliases externos, cleanup de alocação local em cada backedge normal de `for`/`while`/`loop` e em `break`/`continue`/`return` aninhados, blocos com fallthrough e destruição recursiva em ordem reversa; `deinit` do owner e wrapper não `sole` sem referência a `self` rodam antes dos campos owned; defer local no backedge, fallthrough de owner externo, payloads com ponteiros, CFG arbitrário e certificação backend ampla ainda pendentes
- [x] modelo semântico backend-neutral de `co-owned`/ARC com strong-reference accounting explícito, retain/release e destruição elegível no último owner
- [ ] integração completa do ARC com bindings, aliases, cleanup, lowering e runtime/backend
- [ ] `region` | qualificador tipado em parâmetro/local `sole` por valor; moves, merges e handover same-domain são validados no graph; C11 repõe o drop glue no destino de handover e execução nativa confirma destruição única; arena/lifetime e runtime amplo seguem pendentes
- [ ] `device` | Owners sole e moves/merges same-domain chegam ao graph; handover explicito exclusive->device preserva origem/destino no graph; reacquisition device->exclusive exige completion ainda ausente; transfer CPU/dispositivo, sync e runtime seguem pendentes e C11 permanece fail-closed
- [ ] `external` | O backend C11 aceita owners sole repr(C) por valor em parametro exportado quando consumidos exatamente uma vez por uma declaracao @extern(C) sem corpo; a prova cobre ramos exclusivos if/else e cada saida, com execucao nativa dos dois ramos; layouts sem repr(C), storage/campos/retornos, owners nao consumidos e fronteiras opacas falham fechado; ABI geral de handles, lifetime e runtime seguem pendentes
- [ ] `island`
- [ ] `whisper` | parâmetros de funções internas com no-escape provado baixam no C11 como `const T *` e passam execução nativa para leitura escalar; storage, retorno, FFI e invalidação weak seguem pendentes
- [ ] `direct`
- [ ] `handover` | EXCLUSIVE -> EXCLUSIVE, ISLAND -> EXCLUSIVE e ISLAND -> ISLAND com destino estao no grafo/C11; execucao nativa confirma cleanup unico apos ISLAND -> ISLAND; demais dominios, handover sem destino e e2e amplo faltam
- [ ] `quarantine` | EXCLUSIVE -> ISLAND esta no grafo e C11; aliases rastreaveis sao invalidados estaticamente ou o gate falha fechado; weak/runtime invalidation e e2e amplo faltam
- [x] ownership/domain graph canônico para owners rastreados e transferências `exclusive` (`call`, `return`, campos e payloads), backend-neutral; pontos source-stable duplicados ou compartilhados entre movimento, `share`, `handover` e `quarantine` são rejeitados; domínios/tipos de destino e o resultado de cada merge são revalidados fail-closed
- [x] merge canônico de domínio em branches para owners rastreados: domínio deve permanecer idêntico; joins de estado são registrados no grafo
- [x] contrato backend-neutral da primeira transição explícita `exclusive → shared` via operação `share`, exigindo source LIVE e sem aplicar runtime implicitamente
- [x] aplicação semântica real de `exclusive → shared` no OwnershipEnv: owner original muda para `shared`, permanece LIVE e pode criar alias strong explícito
- [x] alias compartilhado incrementa strong_refs exatamente uma vez e colisões/stale transition são rejeitadas
- [x] nó semântico `TypedShareExpression` liga uma operação share de binding inteiro ao OwnershipEnv/ARC sem depender do parser
- [x] share de member/index/temporário permanece fail-closed até o contrato de aliasing parcial ser definido
- [x] sintaxe pública `let alias = share owner;` possui AST dedicado `ShareExpr`, typecheck e integração com OwnershipEnv
- [x] share de owner já `shared` preserva a identidade do source e retém uma vez, com source LIVE e colisões de alias validados
- [x] graph canônico registra aliases strong adicionais e source-stable `share@L:C`; SIR reconcilia cada alias com graph e trace
- [x] C11 gera caixas ARC experimentais para aliases explícitos múltiplos e imutáveis de `sole` local com `core::arc`; shares de owner declarado dentro do bloco com fallthrough e shares em ramo terminal têm cleanup nativo no escopo que os criou; o release final executa drop glue recursivo para campos e arrays fixos `sole` por valor em ordem reversa, chama hooks `deinit` detached do owner/wrapper antes dos campos owned e destrói cada campo; hooks de wrapper que referenciam `self`, mutação/escape, fallthrough de owner externo, alocações dentro de loops e CFG arbitrário continuam fail-closed
- [x] C11 executa `defer` de chamada direta com argumentos `direct`, `whisper` no-escape e escalares, e método `&self` imutável com argumento escalar independente do alias, antes do release/destroy ARC; testes nativos cobrem `continue`, `break` e early return, argumentos calculados pela iteração, compilação com warnings-as-errors e `deinit` confirmando payload vivo; escapes `whisper` e argumentos que recapturam o alias shared continuam rejeitados
- [ ] métodos mutáveis/externos, argumentos derivados do alias shared, assignments e blocos complexos ainda sem suporte geral no backend C11
- [x] C11 preserva aliases shared externos a `if`/`while`/`loop`/`for`/`unsafe` e faz cleanup em early returns, em `if/else` cujos dois ramos retornam e na saída normal; `break`/`continue` não liberam owners do escopo externo, e `share` criado dentro de controle aninhado continua fail-closed
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
- [x] CFG estruturado inicial para funções `void`: `if flag { return; } return;` e `if/else` com retornos diretos, preservando point_id por branch; subset aceita prefixo de `share` e defer direto sobre alias
- [x] sequência de `if` com condições booleanas de parâmetros e retornos antecipados diretos, seguida de retorno final, gera blocos e identidades `return@L:C` distintas; placement ARC executa release/destroy em cada saída
- [x] condições `!param` em `if` e `while` invertem arestas do CFG sobre o valor SSA existente, sem placeholder, preservando break/continue/backedge e cleanup
- [x] condições booleanas compostas `&&`/`||` com curto-circuito entre parâmetros e `!` geram blocos condicionais explícitos; cleanup ARC continua associado às saídas source-stable
- [x] condições `==`, `!=`, `<`, `<=`, `>` e `>=` entre parâmetros inteiros geram `CompareInst` e branch SIR; LLVM baixa comparação signed/unsigned para `icmp` e compila fonte até objeto; literais e expressões compostas fora do subset seguem fail-closed
- [x] condições literais `true`/`false` em `if` e `while` usam arestas SIR incondicionais para o destino constante, sem fabricar valor SSA; validado para retorno antecipado e saída de loop
- [x] condições ainda não representáveis no SIR não recebem CFG/point_id fictício
- [ ] expansão do CFG estruturado além desse subset protótipo, cobrindo expressões condicionais, corpos arbitrários e integração com o lowering de produção
- [x] placement de break/continue/backedge no CFG de produção para o subset estruturado atualmente representável
- [ ] runtime/backend completo para tornar `share` executável em todos os payloads/caminhos; o subset C11 experimental cobre aliases locais, payload POD, criação lexical e drop glue recursivo para campos `sole` por valor em execução nativa
- [ ] transições para `region/device/external` e merges correspondentes
- [x] parser e Typed AST preservam owners sole region/device/external por valor; moves e merges same-domain chegam ao graph; handovers exclusive->device e same-domain chegam ao graph; cruzamentos implicitos sao rejeitados; device continua sem runtime C11, region tem subset C11 e external tem fronteira C11 repr(C) restrita
- [x] invariância canônica de tipo/domínio/estado no backedge de loops para owners visíveis
- [x] contas shared inteiramente locais à iteração recebem release reverso antes do backedge
- [x] cleanup path-specific de shared locals em `break`/`continue`, inclusive em branches aninhados
- [x] defers shared ativos no escopo do loop executam em LIFO antes dos releases ARC no salto
- [x] caminhos break/continue não recebem também cleanup de backedge, evitando double-release
- [ ] integração completa de cleanup/early return/defer
- [x] lowering backend-neutral inicial de `handover`/`quarantine` como `OwnershipDomainTransferInst`, com domínio/origem/destino e identity source-stable preservados
- [x] C11 e LLVM têm gates fail-closed exercitados para combinações ainda não suportadas de `region/device/external` e runtime ARC/domains
- [ ] lowering executável e matriz positiva/negativa completa de cada operação por domínio/backend
- [ ] testes positivos + negativos + end-to-end por domínio

## Progresso das fases

> Percentuais aproximados de engenharia. Eles não substituem os gates formais de `CERTIFIED`/`SUPPORTED`.
>
> **Regra de cálculo:** a porcentagem é estimada por macroentregas da fase, não pela contagem bruta de checkboxes. Subpassos de uma mesma feature (por exemplo, vários passos de ARC/`shared`) não podem compensar domínios inteiros ainda não implementados.

```text
Fase 0 — Reality Reset              ~80%
Fase 1 — Typed Semantic Core       100% ✅
Fase 2 — Ownership Domains          ~84% 🟡
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
| `shared` / co-owned / ARC semântico | ~91% | frontend, accounting, cleanup e SIR avançados; lowering C11 experimental cobre aliases locais imutáveis, payload escalar/POD, hooks detached de owner/wrapper e drop glue recursivo em ordem reversa para campos e arrays fixos `sole` multidimensionais; owner compartilhado por parâmetro agora também limpa no fallthrough da saída da função, com `defer` antes do release e execução nativa confirmando observação e destruição; formas C11 estáticas ainda não cobrem payloads com ponteiros, CFG geral ou e2e amplo |
| CFG + cleanup + defer para ownership | ~69% | retornos e loops com condições booleanas diretas, negadas, compostas `&&`/`||` ou comparação de parâmetros inteiros têm CFG explícito; corpos arbitrários, operandos literais e todos os payloads de defer ainda não |
| `region` | ~57% | parser/Typed AST, moves/merges, retorno e handover same-domain chegam ao graph/SIR; C11 executa transferência com drop único e rearma o drop glue no destino de handover; cleanup recursivo também cobre campos, arrays fixos e wrappers POD comuns que contêm owners `region` `sole`, inclusive wrappers locais, em ordem reversa; borrows call-scoped para parâmetros `direct`/`whisper` chegam ao graph/SIR/LLVM/C11; testes nativos cobrem `defer` antes do drop em early return/fallthrough e destruição de locals em `continue`/`break`; `deinit` do wrapper que acessa `self` com filhos region-owned é rejeitado para evitar double-drop; arena/lifetime graph e validação ampla de escapes ainda faltam |
| `device` | ~22% | parser/Typed AST preservam owners, moves e merges same-domain; handover explicito exclusive->device fica registrado no graph; leitura de campos, escapes e borrows host sao rejeitados; completion/reacquisition, transferencia real CPU/dispositivo, sync e runtime seguem pendentes |
| `external` | ~34% | parser/Typed AST e graph preservam moves e handovers same-domain; owner sole repr(C) atravessa por valor uma declaracao @extern(C) sem corpo quando consumidor exportado prova consumo exatamente uma vez em todos os caminhos, inclusive ramos exclusivos if/else; execucao nativa cobre ambos os ramos; storage/retorno, transferencia opaca, ABI geral de handles, lifetime e runtime continuam pendentes |
| `island` | ~99% | fronteiras funcionais, subset C11 por valor em parâmetros/retornos e campos `sole` com payload POD recursivo estão cobertos; borrows `whisper`/`direct` call-scoped e handover `ISLAND→ISLAND` chegam ao graph/SIR; C11 executa os casos nativos com no-escape e cleanup único, e LLVM aceita borrow direto no subset POD linear; aliases armazenados, globals, enum/classes fora do subset e runtime de aliases ainda faltam |
| `whisper` | ~75% | qualificador canônico em parâmetros; chamadas non-owning produzem aresta source-stable no Ownership Domain Graph e `WhisperBorrowInst` para owners `exclusive/shared/island/region/direct` LIVE; forwarding `direct → whisper` exige no-escape provado e executa em C11 e LLVM; summaries provam ciclos recursivos fechados e rejeitam ciclos com membro escapante; leitura escalar e receivers internos executam como ponteiro const; weak invalidation, lifetime CFG completo, lowering amplo de defer e FFI continuam pendentes |
| `direct` | ~62% | parâmetro imutável call-scoped preservado no Typed AST, graph e SIR; owners `region` e `island` originam acesso verificado; borrows e receivers de método sobre owners `island` executam em C11, e o borrow por argumento também passa LLVM até objeto no subset POD linear; forwarding `direct → direct` e para `whisper` no-escape preserva a origem e executa em C11/LLVM; `defer inspect(&shared_alias)` preserva argumento pointer-typed e marker source-stable no SIR, com chamada antes dos releases em cada early return; defer C11 cobre também `continue`/`break`, argumentos `whisper` no-escape e escalares; lifetime CFG geral, aliases complexos, mutabilidade, ABI ARC LLVM e e2e amplo ainda faltam |
| `handover` | ~73% | transições EXCLUSIVE→EXCLUSIVE, ISLAND→EXCLUSIVE e ISLAND→ISLAND preservam domínio e destino no graph; C11 baixa bindings validados e rearma cleanup do destino, com execução nativa confirmando destruição única; outros domínios e e2e amplo faltam |
| `quarantine` | ~66% | EXCLUSIVE→ISLAND é validado no grafo e tem lowering estático C11; o gate de produção rastreia aliases locais/campos, distingue ramos mutuamente exclusivos e conserva a rejeição após joins ambíguos; teste C11 compila e executa a leitura no ramo oposto ao quarantine e verifica a destruição nos dois caminhos; weak invalidation/runtime, CFG path-sensitive geral e e2e amplo faltam |
| runtime/backend + e2e por domínio | ~5% | gates/fail-closed existem, mas execução real de Ownership Domains ainda não |

A combinacao ponderada dessas macroentregas coloca a Fase 2 em **~84%**.

`region`, `device` e `external` possuem identidade no enum canonico OwnershipDomain, com qualificador, moves, merges same-domain e transferencias por chamada/handover no grafo.
`region` tem lowering C11 restrito com drop recursivo de campos sole, validacao de cleanup e execucao nativa com destruicao unica; arena/lifetime graph e validacao ampla de escapes seguem pendentes.
`device` continua fail-closed ate existir transferencia CPU/dispositivo, completion e runtime.
`external` tem caminho C11 restrito a handles sole repr(C) passados por valor a declaracoes @extern(C) sem corpo, com consumo validado e execucao nativa; ABI geral e lifetime seguem pendentes.

### Fase 2 detalhada

O contrato canônico de `direct T` está restrito a parâmetros: acesso imutável durante a chamada, passado por `&binding` de owner `exclusive/shared/region/island` vivo. Não consome ownership; aliases locais de frame são permitidos, e forwarding `direct → direct` preserva o source domain no grafo e SIR. Defer de função interna com argumento `&shared_alias` é executado antes dos releases em break/continue; retorno, campo/global, outras formas de defer e FFI opaca ainda exigem contratos. Cada chamada gera aresta `direct@L:C` no grafo e `DirectAccessInst` em SIR. C11 compila e executa o subset como ponteiro const; LLVM fonte→objeto aceita apenas funções `void` lineares com structs `sole` triviais, gera chamada e consome a prova canônica no graph. Payloads com destrutor/ownership aninhado, ARC, CFG amplo e escape permanecem fail-closed. Isso inicia o backend; não promove `direct` a completo.

```text
Fase 2 — Ownership Domains                  ~84%

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
✅ C11 `share` experimental com aliases locais múltiplos imutáveis e preflight do Ownership Graph/Trace canônico
⬜ compilação/execução nativa, validação de runtime heap e promoção de `shared` para suporte validado
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
✅ backend-neutral ownership-domain SIR plan  ← NOVO
✅ quarantine EXCLUSIVE→ISLAND lowers to explicit SIR ownership transfer ← NOVO
✅ handover ISLAND→EXCLUSIVE lowers with explicit destination in SIR      ← NOVO
✅ incomplete domain-transfer facts fail-closed before backend             ← NOVO
✅ OwnershipModuleAnalysis lowers to one SIR ownership plan per function    ← NOVO
✅ module SIR plan composes domain-transfer + shared/ARC semantics           ← NOVO
✅ duplicate function traces fail-closed before SIR consumption             ← NOVO
✅ public Phase-1 pipeline now emits OwnershipModuleSIRPlan automatically     ← NOVO
✅ Phase1CheckedModule composes semantic snapshot + ownership SIR             ← NOVO
✅ plain functions produce explicit empty ownership SIR plans                 ← NOVO
✅ SIRGenerator emits source-stable quarantine/handover ownership points       ← NOVO
✅ ownership-domain plan replaces validated source points transactionally       ← NOVO
✅ operation/source/destination/point mismatches fail before CFG mutation        ← NOVO
✅ unsupported mixed linear bodies do not receive invented ownership placement  ← NOVO
✅ module-level domain placement matches plans to SIR functions                   ← NOVO
✅ all function placements preflight before first module mutation                  ← NOVO
✅ missing/duplicate SIR functions and duplicate plans fail-closed                 ← NOVO
✅ later function mismatch cannot partially mutate earlier functions               ← NOVO
✅ unified module ownership placement preflights domain + supported ARC CFG points  ← NOVO
✅ ARC failure in later function cannot commit earlier domain transfer               ← NOVO
✅ domain + return/control/backedge cleanup commit from one validated module plan    ← NOVO
✅ share/retain events now freeze one shared source-stable share@L:C point           ← NOVO
✅ SIRGenerator emits SharedOwnershipPointInst for linear let alias = share owner     ← NOVO
✅ module ownership placement replaces shared marker with ShareInst + RetainInst      ← NOVO
✅ shared semantic marker mismatch fails before any module CFG mutation                ← NOVO
✅ shared semantic placement resolves exact share@L:C points independent of CFG order   ← NOVO
✅ duplicate/missing shared semantic source points fail before module CFG mutation       ← NOVO
✅ checked frontend module can generate + ownership-place one SIRModule in one API       ← NOVO
✅ canonical OwnershipDomainGraph now drives quarantine/handover SIR lowering              ← NOVO
✅ OwnershipDomainGraph now materializes canonical EXCLUSIVE→SHARED transitions             ← NOVO
✅ graph shared_accounts preserve function/account/owners/strong_refs/share@L:C              ← NOVO
✅ canonical graph now drives ShareInst/RetainInst + shared semantic source points            ← NOVO
✅ trace remains authoritative only for path-sensitive cleanup/defer ARC obligations           ← NOVO
✅ graph/trace shared identity or strong-ref accounting divergence fails before placement      ← NOVO
✅ shared account identity is function-scoped even when local binding names repeat           ← NOVO
✅ retain without canonical share account or with mismatched source point fails-closed       ← NOVO
✅ public checked pipeline composes graph-based domains with trace-based shared/ARC         ← NOVO
✅ missing canonical graph node/type/domain facts fail-closed before SIR placement          ← NOVO
✅ quarantine/handover source points are frozen into OwnershipDomainGraph transfers          ← NOVO
✅ graph-based domain SIR preserves canonical quarantine@L:C / handover@L:C identities       ← NOVO
✅ domain placement matches canonical source point instead of incidental instruction order    ← NOVO
✅ missing/duplicate canonical domain source points fail before CFG mutation                  ← NOVO
✅ SIR composition boundary consumes parsed_module + ownership_sir without frontend cycle ← NOVO
✅ malformed checked-module contracts fail-closed before SIR generation                  ← NOVO
✅ canonical whisper parameter qualifier freezes immutable non-owning borrow metadata ← NOVO
✅ whisper parameters do not consume sole ownership or enter OwnershipEnv as owners    ← NOVO
✅ whisper fields/globals/returns remain fail-closed until lifetime graph is formalized ← NOVO
✅ local escape analysis rejects whisper-derived pointer/integer returns and stored aliases ← NOVO
✅ C11 lowers verified no-escape internal whisper parameters as const pointers         ← NOVO
✅ fail-closed when ownership type is unknown ← NOVO

✅ normal function_exit ARC cleanup placed before one implicit fallthrough return ← NOVO
✅ function_exit cleanup refuses ambiguous multiple implicit returns                ← NOVO
✅ function_exit never stacks over source-identified early-return cleanup          ← NOVO
✅ module ownership transaction preflights function_exit before any CFG mutation   ← NOVO
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
✅ SIR places validated direct deferred calls once before ARC on fallthrough and loop exits
✅ break/continue placement preserves defer → release → destroy order    ← NOVO
✅ shared → sole-consuming call/defer-call requires explicit handover            ← CORRIGIDO
✅ handover EXCLUSIVE source → MOVED binding destination                     ← NOVO
✅ handover destination reacquisition requires same type + prior MOVED state ← NOVO
✅ Ownership Domain Graph preserves explicit handover destination            ← NOVO
✅ canonical quarantine EXCLUSIVE → ISLAND                                  ← NOVO
✅ quarantined owner remains LIVE but cannot move/escape implicitly          ← NOVO
✅ quarantine transfer is preserved in Ownership Domain Graph                ← NOVO
✅ C11 lowers validated quarantine as compile-time ownership transition      ← NOVO
✅ explicit ISLAND → EXCLUSIVE handover reacquisition                         ← NOVO
✅ island handover requires same-type EXCLUSIVE destination already MOVED     ← NOVO
✅ targetless handover from ISLAND remains fail-closed                        ← NOVO
✅ C11 lowers validated handover to a binding destination                    ← NOVO
✅ cross-domain handover preserves source domain + destination in graph        ← NOVO
✅ domain graph freezes EXCLUSIVE → ISLAND quarantine direction                ← NOVO
✅ domain graph freezes ISLAND → EXCLUSIVE reacquisition direction             ← NOVO
✅ destination domain is explicit for binding-to-binding handover              ← NOVO
✅ incomplete cross-domain graph facts fail-closed                             ← NOVO
✅ public island T ownership modifier parsed and frozen in Typed AST             ← NOVO
✅ explicit island bindings seed ISLAND/LIVE ownership                           ← NOVO
✅ island qualifier restricted to direct by-value sole types                     ← NOVO
✅ explicit island participates in handover reacquisition                         ← NOVO
✅ C11 lowers direct by-value island function parameters and returns              ← NOVO
✅ island return signature preserves ISLAND → ISLAND transfer                      ← NOVO
✅ island → exclusive return escape is rejected fail-closed                        ← NOVO
✅ return transfer direction is explicit in Ownership Domain Graph                 ← NOVO
✅ island local bindings preserve ISLAND → ISLAND ownership                         ← NOVO
✅ island struct fields preserve ISLAND → ISLAND ownership                          ← NOVO
✅ EXCLUSIVE → ISLAND local/field moves remain forbidden without quarantine          ← NOVO
✅ invalid island field/global type annotations fail in Typed AST                    ← NOVO
✅ island function calls preserve ISLAND → ISLAND ownership                           ← NOVO
✅ island method arguments preserve ISLAND → ISLAND ownership                         ← NOVO
✅ EXCLUSIVE → ISLAND call arguments remain fail-closed                                ← NOVO
✅ call/method transfer direction is explicit in Ownership Domain Graph                ← NOVO
✅ island enum payloads preserve ISLAND → ISLAND ownership                              ← NOVO
✅ EXCLUSIVE → ISLAND enum payload transfer remains forbidden                           ← NOVO
✅ ISLAND → EXCLUSIVE enum payload escape remains forbidden                             ← NOVO
✅ invalid island enum payload types fail in Typed AST                                  ← NOVO
✅ C11 island enum payloads remain fail-closed                                           ← NOVO
✅ &island owner reference aliases remain fail-closed                                     ← NOVO
✅ &island.member aliases cannot expose the isolated subgraph                              ← NOVO
✅ island reference arguments remain fail-closed without whisper/borrow contract           ← NOVO
✅ island → shared through share remains fail-closed                                       ← NOVO
✅ ordinary island member reads remain valid                                               ← NOVO
✅ sole globals freeze EXCLUSIVE ownership metadata                                     ← NOVO
✅ island global storage remains fail-closed                                              ← NOVO
✅ island class fields remain fail-closed pending ARC/island containment                  ← NOVO
✅ invalid island globals still fail type validation before storage policy                ← NOVO
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
