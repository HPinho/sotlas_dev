# SOTLAS — ESPECIFICAÇÃO MESTRA

> Documento consolidado da arquitetura-base da linguagem Sotlas e da extensão Sotlas Domains.

## Estatuto desta especificação

Este documento preserva integralmente as ideias, exemplos, regras, nuances técnicas e roadmaps das duas especificações de origem. Apenas os títulos-raiz foram unificados e a matéria foi organizada em duas partes complementares. Conceitos que se aproximam, mas acrescentam condições, exemplos ou consequências diferentes, foram mantidos; somente a duplicação editorial do título de documento foi removida.

A Parte I estabelece a arquitetura semântica fundamental. A Parte II integra Sotlas Domains e atualiza a arquitetura com Ownership, Execution e Trust Domains, inclusive computação heterogênea. Quando os dois roadmaps expressam ordens diferentes, o roadmap integrado da Parte II é a sequência canônica mais recente; o roadmap da Parte I permanece como decomposição técnica e registro completo das dependências originais.

Duas regras de credibilidade são normativas em todo o documento:

1. Sotlas não alegará originalidade inédita sem pesquisa comparativa séria e evidência contra trabalhos e linguagens anteriores.
2. Uma feature só poderá ser marcada como `SUPPORTED` depois de atravessar e comprovar o pipeline end-to-end: especificação, parser, Typed AST, verificação semântica, lowering, backend, testes positivos, testes negativos e teste end-to-end.

---

# Parte I — Arquitetura semântica fundamental

### 1. Visão

Sotlas não deve existir apenas para ser uma alternativa a C, C++, Rust, Zig ou Swift.

Seu objetivo é investigar uma forma diferente de representar software.

Em vez de um programa ser somente uma coleção de instruções e funções, Sotlas pretende permitir que o desenvolvedor represente explicitamente:

- intenção;
- fluxo;
- estado;
- causalidade;
- efeitos;
- autoridade;
- ownership de memória;
- ownership de recursos físicos;
- transações;
- garantias;
- propriedades verificáveis.

Essas dimensões devem convergir em uma representação semântica comum compreendida pelo compilador.

A arquitetura conceitual é:

```text
                         SOTLAS
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
       INTENT              FLOW             STATE
          │                 │                 │
          └──────────── CAUSAL GRAPH ─────────┘
                            │
                         EFFECTS
                            │
             ┌──────────────┼──────────────┐
             │              │              │
         OWNERSHIP       AUTHORITY      GUARANTEES
          / sole        capabilities       proof
             │              │              │
             └──────────────┼──────────────┘
                            │
                      TYPED SEMANTICS
                            │
                           SIR
                            │
                 ┌──────────┼──────────┐
                 │          │          │
               Native       C         WASM
```

A meta não é adicionar palavras-chave exóticas.

A meta é fazer o compilador compreender relações que normalmente permanecem implícitas no código.

---

## 2. PRINCÍPIO FUNDAMENTAL

Sotlas deve responder estaticamente, sempre que tecnicamente possível, a perguntas como:

```text
Quem possui este valor?

Quem possui este recurso?

Quem tem autoridade para executar esta operação?

Em qual estado este objeto está?

Para quais estados ele pode transicionar?

Quais efeitos esta função pode produzir?

Esta operação pode bloquear?

Pode alocar?

Pode executar durante uma interrupção?

Pode acessar hardware?

De onde este valor veio?

Por que este estado existe?

Que consequências uma mudança produziria?

Esta garantia pode ser provada?
```

Esse conjunto forma o modelo semântico da linguagem.

---

## 3. SAFE BY CONSTRUCTION, NÃO SAFE BY MARKETING

Nenhuma funcionalidade será declarada implementada simplesmente porque:

- possui parser;
- existe um nó AST;
- existe um RFC;
- existe um passe SIR isolado;
- existe código experimental.

Uma feature somente recebe status `SUPPORTED` quando existe:

```text
SPECIFICATION
      ↓
PARSER
      ↓
TYPED AST
      ↓
SEMANTIC CHECK
      ↓
LOWERING
      ↓
BACKEND
      ↓
POSITIVE TEST
      ↓
NEGATIVE TEST
      ↓
END-TO-END TEST
```

E deverá existir uma regra central:

> Se `sotlas check program.sot` retorna sucesso, o programa deve ser compilável pelo pipeline oficialmente suportado.

Erros internos do backend não devem substituir diagnósticos Sotlas para programas aceitos pelo frontend.

---

## 4. `unsafe` E `@system` NÃO SIGNIFICAM A MESMA COISA

Essa distinção existente na Sotlas deve tornar-se um dos fundamentos da linguagem.

`unsafe` responde:

> Esta operação está fora das garantias normais de segurança?

`@system` responde:

> Este código possui autoridade para realizar determinada operação privilegiada?

Portanto:

```text
                     SAFE             UNSAFE

normal              permitido         rejeitado

@system             permitido         requer unsafe
```

`@system` nunca substitui `unsafe`.

---

## 5. AUTHORITY SAFETY

Sotlas deve introduzir autoridade como dimensão verificável pelo compilador.

Em vez de:

```sotlas
@system
fn configure() {}
```

preferimos capacidades explícitas:

```sotlas
@system(pci.config)
fn configure_pci() {}
```

Outro exemplo:

```sotlas
@system(io.port)
fn keyboard_write() {
    unsafe {
        io::out8(0x64, 0xAE);
    }
}
```

Ter:

```text
pci.config
```

não concede automaticamente:

```text
io.port
mmio
dma
irq
filesystem
network
```

Autoridades devem seguir o princípio da menor autoridade.

---

## 6. CAPABILITIES COMO VALORES

Capabilities também poderão existir como recursos tipados:

```sotlas
let pci = system.acquire<PciConfig>();
```

Uma função poderá exigir explicitamente:

```sotlas
fn enumerate(pci: borrow PciConfig) {
}
```

Código que nunca recebeu `PciConfig` não poderá acessar configuração PCI.

A autoridade deixa de ser global e passa a fazer parte do fluxo de dados.

---

## 7. AUTHORITY GRAPH

O compilador deverá construir um grafo de autoridade.

Exemplo:

```text
boot
 ├── pci.config
 ├── mmio
 └── irq
```

Se:

```sotlas
fn application() {
    configure_pci();
}
```

não possuir a capability necessária:

```text
error[S401]

application cannot call configure_pci

missing authority:
    pci.config

authority chain:

application
    └── configure_pci
          └── requires pci.config
```

---

## 8. `sole` — OWNERSHIP LINEAR PRÁTICO

`sole` deverá representar ownership exclusivo.

```sotlas
sole struct Device {
    handle: DeviceHandle
}
```

Ao mover:

```sotlas
close(move device);
```

o valor anterior deixa de ser utilizável.

```sotlas
close(move device);

device.reset();
```

deverá produzir:

```text
error[S421]

use of moved sole value `device`

ownership transferred at:
    close(move device)
```

O primeiro sistema não precisa reproduzir todo o borrow checker do Rust.

A implementação poderá evoluir:

```text
linear flow
   ↓
branches
   ↓
fields
   ↓
loops
   ↓
interprocedural analysis
```

---

## 9. RESOURCE OWNERSHIP

Ownership não será limitado à memória.

Também poderá representar:

- file handles;
- sockets;
- GPU buffers;
- DMA buffers;
- locks;
- devices;
- interrupts;
- MMIO mappings;
- transactions;
- OS resources.

Exemplo:

```sotlas
let region = dma.allocate(4096);

device.submit(move region);
```

Depois:

```sotlas
region[0] = 42;
```

será inválido.

```text
DMA ownership transferred to device.

CPU access forbidden until ownership returns.
```

A linguagem passa a modelar ownership de recursos físicos.

---

## 10. STATE SPACES

Sotlas introduzirá estados como construção de primeira classe.

```sotlas
space Download {
    initial state idle
    state downloading(progress: Percent)
    state paused(progress: Percent)
    state completed(File)
    state failed(Error)

    idle -> downloading
    downloading -> paused
    paused -> downloading
    downloading -> completed
    downloading -> failed
}
```

O compilador conhece o grafo:

```text
idle
 │
 ▼
downloading ─────► completed
 │
 ├───────────────► failed
 │
 ▼
paused
 │
 └──────────────► downloading
```

Transições inexistentes são erros de compilação.

---

## 11. TYPESTATE

Tipos podem carregar estado.

Conceitualmente:

```text
Device<Discovered>
Device<Configured>
Device<Running>
```

Exemplo:

```sotlas
fn configure(dev: Device<Discovered>)
    -> Device<Configured>
```

e:

```sotlas
fn start(dev: Device<Configured>)
    -> Device<Running>
```

Isso torna impossível:

```sotlas
let dev = discover();

start(dev);
```

Diagnóstico:

```text
start requires:

Device<Configured>

received:

Device<Discovered>

valid transition:

Discovered -> Configured -> Running
```

---

## 12. STATE COVERAGE

UI e lógica poderão consumir State Spaces diretamente.

```sotlas
view DownloadView(download: Download) {
    when download {
        idle        => DownloadButton()
        downloading => Progress(download.progress)
        paused      => ResumeButton()
        completed   => FileView(download.file)
        failed      => RetryView()
    }
}
```

Se for adicionado:

```sotlas
state verifying
```

o compilador detectará:

```text
DownloadView does not represent state `verifying`.

coverage:
5 / 6
```

O mesmo modelo de estado pode alimentar:

- UI;
- concorrência;
- persistência;
- networking;
- debugging;
- testes.

---

## 13. EFFECT SYSTEM

Funções devem poder declarar efeitos.

```sotlas
fn loadAvatar(id)
    uses network
    may fail NetworkError
    allocates <= 4MB
```

Outra:

```sotlas
fn resize(image)
    uses cpu
    pure
```

Possíveis efeitos:

```text
network
filesystem
allocation
blocking
locking
io
mmio
dma
irq
gpu
database
clock
random
process
thread
unsafe
```

O sistema deverá permitir extensão controlada.

---

## 14. EFFECT INFERENCE

Nem todo efeito precisa ser repetido manualmente.

Se:

```text
A -> B -> C
```

e `C` usa `network`, o compilador pode inferir a propagação desse efeito quando apropriado.

Ferramentas devem permitir:

```text
sotlas effects foo
```

Resultado:

```text
foo
 └── loadProfile
      └── HTTPClient.request
           └── network
```

---

## 15. INTERRUPT SAFETY

Contextos de interrupção poderão impor restrições:

```sotlas
@interrupt
fn timer_irq() {
    allocate();
}
```

Se `allocate()` possui:

```text
allocation
blocking
```

o compilador rejeita.

Exemplo:

```text
error:

allocation effect is forbidden
inside interrupt context.
```

---

## 16. REALTIME SAFETY

Sotlas poderá representar funções sensíveis a tempo:

```sotlas
@realtime
fn audio_callback() {
}
```

Inicialmente, a garantia não será “esta função termina exatamente em X microssegundos”.

Serão verificadas propriedades demonstráveis:

```text
no blocking syscall
no blocking lock
no heap allocation
no unbounded recursion
restricted effects
restricted call graph
```

Posteriormente poderão existir modelos temporais mais fortes.

---

## 17. `GUARANTEE`

Uma construção central da linguagem será `guarantee`.

Exemplo conceitual:

```sotlas
guarantee PacketBuffer {
    memory.safe
    bounds.safe
    authority(network.rx)
    state(received -> parsed -> consumed)
}
```

Uma garantia não é comentário.

Ela deve corresponder a propriedades verificadas pelo compilador.

---

## 18. CONTRACTS

Funções poderão expressar pré e pós-condições verificáveis:

```sotlas
fn divide(a: i32, b: i32) -> i32
    requires b != 0
{
    a / b
}
```

E:

```sotlas
fn configure(dev)
    requires dev.state == discovered
    ensures dev.state == configured
{
}
```

O compilador tentará demonstrar as condições dentro de um subconjunto deliberadamente limitado.

Sotlas não pretende inicialmente ser um theorem prover geral.

---

## 19. BOUNDS PROOFS

Exemplo:

```sotlas
fn write(buf: Slice<u8>, index: usize)
    requires index < buf.len
{
    buf[index] = 42;
}
```

Quando:

```sotlas
if i < data.len {
    write(data, i);
}
```

o compilador poderá provar a condição.

Quando não puder, deverá exigir verificação dinâmica ou rejeitar de acordo com o contrato escolhido.

Isso permite relacionar safety e otimização.

---

## 20. INTEGER SEMANTICS

Sotlas deverá possuir semântica própria para overflow.

Nunca depender silenciosamente de UB herdado de C.

A linguagem deve definir explicitamente comportamentos como:

```text
checked
wrapping
saturating
unchecked
```

Exemplos futuros:

```sotlas
checked a + b
wrapping a + b
saturating a + b
```

O backend C deve preservar exatamente essa semântica.

---

## 21. PROOF

A toolchain deverá conseguir produzir um relatório verificável:

```text
sotlas prove kernel.sot
```

Exemplo:

```text
SOTLAS SAFETY REPORT

Memory safety          PROVEN
Bounds safety          PROVEN
Integer policy         PROVEN
Resource ownership     PROVEN
Authority              PROVEN
State transitions      PROVEN
Interrupt safety       PROVEN

Unsafe regions         3

Unproven:
DMA lifetime
    drivers/nvme.sot:218
```

`PROVEN` somente poderá ser utilizado quando existir uma prova correspondente segundo o modelo definido pela linguagem.

---

## 22. AUDITABLE UNSAFE

`unsafe` não deverá simplesmente apagar informações.

Exemplo:

```sotlas
unsafe(reason: "volatile MMIO access") {
    ptr.write(value);
}
```

A toolchain registra:

```text
NVMeDriver
 ├── queue          SAFE
 ├── allocator      SAFE
 └── mmio
      └── UNSAFE
           reason: volatile MMIO access
           capability: pci.mmio
           isolated: yes
```

Poderá existir:

```sotlas
guarantee driver {
    no_unjustified_unsafe
}
```

---

## 23. `FLOW`

`flow` representa dependências computacionais.

```sotlas
flow ProfileScreen(user) {
    profile = fetch Profile(user)
    avatar  = fetch Avatar(user)
    posts   = fetch Posts(user)

    render ProfileView(profile, avatar, posts)
}
```

O compilador observa:

```text
            ┌── Profile ──┐
User ───────┼── Avatar ───┼──► Render
            └── Posts ────┘
```

Como os três nós são independentes, o runtime poderá executá-los concorrentemente.

O programador não precisa necessariamente construir manualmente tasks.

---

## 24. DEPENDÊNCIAS IMPLÍCITAS EM FLOW

Se:

```sotlas
flow Profile(user) {
    profile = fetch Profile(user)
    posts   = fetch Posts(profile.id)
}
```

o compilador produz:

```text
User
 ↓
Profile
 ↓
Posts
```

A topologia surge das dependências de dados.

---

## 25. DETERMINISTIC FLOW

`flow` não significa execução imprevisível.

O compilador deverá produzir uma representação inspecionável:

```text
sotlas flow ProfileScreen
```

Resultado:

```text
ProfileScreen

stage 0
    Profile
    Avatar
    Posts

barrier

stage 1
    ProfileView
```

Efeitos deverão participar das decisões de scheduling.

---

## 26. STRUCTURED CANCELLATION

Cancelamento deverá fazer parte de `flow`.

Se um consumidor desaparece:

```text
ProfileScreen cancelled
```

o runtime conhece os nós dependentes e poderá cancelar trabalho desnecessário.

Recursos `sole` envolvidos devem possuir regras determinísticas de cleanup.

---

## 27. `INTENT`

`intent` representa o objetivo computacional, não somente sua implementação procedural.

Exemplo:

```sotlas
intent LoadUser(id: UserId) -> User {
    obtain User(id)

    prefer cache
    fallback network

    guarantee {
        ui.nonblocking
        privacy.local_first
    }
}
```

A estratégia concreta deverá ser compilada para um plano explícito e inspecionável.

---

## 28. INTENT NÃO É IA

O significado de `intent` deve permanecer:

- determinístico;
- especificado;
- compilável;
- auditável;
- testável.

IA poderá auxiliar desenvolvimento, mas não determinar silenciosamente a semântica do programa.

---

## 29. INTENT PLANS

A ferramenta poderá mostrar:

```text
sotlas plan LoadUser
```

Resultado:

```text
LoadUser

1. LocalCache.lookup
      │
      ├── hit ───────► return
      │
      └── miss
             ↓
2. Network.fetch
             ↓
3. Validate
             ↓
4. Cache.store
             ↓
5. return
```

O desenvolvedor consegue visualizar aquilo que o compilador decidiu.

---

## 30. CAUSAL PROGRAMMING

Sotlas deverá preservar relações causais selecionadas.

Exemplo:

```text
email ↓
email.valid
 ↓
form.valid
 ↓
submitButton.enabled
```

Essas relações poderão alimentar debugging e ferramentas.

---

## 31. `WHY`

O desenvolvedor poderá perguntar:

```text
why submitButton.enabled
```

Resultado:

```text
submitButton.enabled = false

because:

form.valid = false
    because:
        email.valid = false
            because:
                email = "hiago@"

origin:
    UserInput
    LoginView.sot:48
```

O objetivo é transformar causalidade em informação estruturada.

---

## 32. `WHATIF`

O inverso também poderá existir:

```text
whatif email.valid = true
```

Resultado:

```text
Affected state:

email.valid
 ↓
form.valid
 ↓
submitButton.enabled

External effects:
none
```

`whatif` deve operar apenas sobre regiões que possam ser simuladas com segurança.

Efeitos externos nunca deverão ser executados silenciosamente durante uma simulação.

---

## 33. EXPLAINABLE SOFTWARE

Uma propriedade poderá ser consultada:

```text
explain payment.allowed
```

Resultado:

```text
payment.allowed = false

Derived from:

Account.active             true
Cart.total > 0             true
PaymentMethod.valid        false
FraudCheck.approved        true

Blocking condition:

PaymentMethod.valid
```

Isso transforma “por que?” em uma operação de tooling baseada na semântica do programa.

---

## 34. CAUSAL DEBUGGER

O debugger Sotlas poderá navegar em duas direções:

```text
PAST

Por que isto aconteceu?

            ↑
         CURRENT
            ↓

FUTURE

O que depende disto?
```

Debugging deixa de ser exclusivamente temporal e passa também a ser causal.

---

## 35. REVERSIBLE STATE CHANGES

Sotlas poderá representar mudanças estruturadas:

```sotlas
change RenameFile(file, newName) {
    file.name <- newName
}
```

Quando semanticamente possível, o compilador/runtime poderá derivar metadados para:

```text
apply
diff
audit
rollback
```

Isso não significa que qualquer efeito do mundo seja automaticamente reversível.

A reversibilidade precisa ser demonstrável.

---

## 36. TRANSACTIONS

```sotlas
transaction {
    account.name <- "Hiago"
    profile.avatar <- image
}
```

O modelo deverá registrar:

```text
before
   ↓
transition
   ↓
after
```

e, quando possível:

```text
inverse
rollback
```

---

## 37. TRANSACTIONAL EFFECTS

Efeitos deverão declarar sua relação com transações.

Exemplo conceitual:

```text
reversible
compensatable
irreversible
```

Uma operação de envio de email, por exemplo, não deve fingir que pode ser revertida.

O compilador poderá alertar:

```text
irreversible effect inside rollback-capable transaction
```

---

## 38. UI COMO CONSEQUÊNCIA DE ESTADO

Sotlas poderá futuramente possuir uma camada declarativa de UI baseada nos mesmos State Spaces e Flows.

Não criaremos um segundo sistema semântico apenas para interface.

A UI observará:

```text
STATE
 ↓
DERIVED STATE
 ↓
VIEW
```

Isso aproxima lógica e representação sem misturá-las.

---

## 39. UI THREAD SAFETY

Um contexto:

```sotlas
@ui
flow Screen() {
}
```

poderá proibir:

```text
blocking
long synchronous IO
unsafe UI mutation from another domain
```

O effect system fornece essa garantia.

---

## 40. CONCORRÊNCIA DERIVADA DE DEPENDÊNCIAS

Em vez de obrigar o desenvolvedor a descrever toda a topologia de tarefas, `flow` permite que o compilador derive concorrência segura a partir de:

```text
data dependencies
ownership
effects
state
authority
```

Quando duas operações podem executar em paralelo com segurança, isso pode ser identificado.

Quando não podem, a dependência permanece explícita.

---

## 41. STRUCTURED CONCURRENCY

Tasks criadas por `flow` devem pertencer a uma estrutura.

Nada de tarefas órfãs por padrão.

```text
Flow
 ├── Task A
 ├── Task B
 └── Task C
```

Ao terminar/cancelar o flow, suas subtarefas obedecem às regras de lifetime definidas pela linguagem.

---

## 42. GENERICS

Generics deverão ser implementados de verdade, inicialmente por monomorfização.

```sotlas
struct Pair<A, B> {
    first: A
    second: B
}
```

Uma instância:

```text
Pair<u32, i64>
```

poderá gerar internamente:

```text
Pair$u32$i64
```

O compilador deve garantir que nenhum placeholder genérico chegue indevidamente ao backend C.

---

## 43. RECURSIVE TYPES

Tipos recursivos por valor deverão ser rejeitados:

```sotlas
struct Node {
    next: Node
}
```

Uma forma indireta deverá ser usada:

```sotlas
struct Node {
    next: Option<Box<Node>>
}
```

ou futura abstração Sotlas equivalente.

---

## 44. CLASSES E ARC

ARC não será declarado funcional antes de possuir semântica real.

Se Sotlas mantiver `class`, deve definir:

```text
retain
release
ownership interaction
weak references
cycles
destruction
thread semantics
```

Caso contrário, `class` permanecerá experimental.

---

## 45. MEMORY MODEL

Sotlas deverá possuir um memory model próprio documentado.

Ele deve especificar pelo menos:

```text
value semantics
references
raw pointers
sole values
borrows
aliasing
atomic operations
volatile operations
thread visibility
FFI boundaries
```

Não devemos simplesmente herdar comportamentos acidentais de C.

---

## 46. FFI

Interoperabilidade com C será importante.

Mas a fronteira será explícita:

```sotlas
extern "C" {
    unsafe fn memcpy(...)
}
```

Wrappers seguros poderão encapsular a operação.

O relatório de safety deverá saber onde existem fronteiras FFI.

---

## 47. BAKENOS COMO RUNTIME, NÃO COMO COMPILADOR

O compilador Sotlas não deve conter elementos específicos como:

```text
baken_get_logo_pixels
application icons
wallpaper
dock
Baken UI
```

A arquitetura será:

```text
                  ┌── freestanding
                  │
Sotlas Compiler ──┼── libc
                  │
                  ├── baken
                  │
                  └── future runtimes
```

Exemplo:

```text
sotlas build kernel.sot --runtime baken
```

BakenOS torna-se consumidor e laboratório da Sotlas.

---

## 48. SIR

SIR não será removido como conceito.

Mas não poderá ser apresentado como pipeline ativo até realmente receber o programa completo.

Arquitetura desejada:

```text
Source
 ↓
Lexer
 ↓
Parser
 ↓
AST
 ↓
Name Resolution
 ↓
Typed AST
 ↓
Safety / Semantic Analysis
 ↓
Flow / State / Effect / Authority Analysis
 ↓
SIR
 ↓
Optimization
 ↓
Lowering
 ↓
Backend
```

---

## 49. SIR DEVE REPRESENTAR A NOVA SEMÂNTICA

O SIR futuramente precisará carregar informações como:

```text
ownership
effects
capabilities
state transitions
causal edges
flow dependencies
guarantees
unsafe boundaries
```

Não deverá ser apenas uma versão renomeada de uma IR tradicional.

---

## 50. CAUSAL GRAPH

Além do CFG tradicional, o compilador poderá construir um Causal Graph.

Exemplo:

```text
UserInput
   ↓
EmailValue
   ↓
EmailValidation
   ↓
FormValidity
   ↓
SubmitEnabled
```

Isso alimentará:

```text
why
whatif
explain
debugger
testing
IDE
```

---

## 51. PROGRAM KNOWLEDGE GRAPH

Em longo prazo, o compilador poderá produzir uma representação unificada:

```text
functions
types
flows
states
effects
capabilities
ownership
causality
guarantees
resources
```

Isso pode tornar ferramentas muito mais inteligentes sem depender apenas de análise textual.

---

## 52. IA SOBRE SEMÂNTICA, NÃO SOBRE ADIVINHAÇÃO

Ferramentas de IA poderão consultar esse grafo.

Pergunta:

```text
Por que Login congela?
```

Informação estrutural:

```text
LoginIntent
 └── Authenticate
      └── TokenStore
           └── KeychainWrite
                └── blocking
                     └── UI domain
```

A IA passa a explicar fatos produzidos pelo compilador.

---

## 53. IDE SOTLAS

A extensão poderá futuramente apresentar:

```text
Flow View
State View
Authority View
Effect View
Ownership View
Causal View
Safety View
```

Ao clicar em uma função:

```text
loadProfile

Effects:
    network
    allocation

Authority:
    network.client

Ownership:
    returns sole Profile

Called by:
    ProfileFlow

Causal outputs:
    profile.loaded
```

---

## 54. DIAGNÓSTICOS COMO PARTE DA LINGUAGEM

Sotlas deverá tratar diagnósticos como feature principal.

Em vez de:

```text
type mismatch
```

preferir:

```text
cannot start `device`

required state:
    Configured

current state:
    Discovered

possible transition:
    configure(device)

Discovered
    ↓
Configured
    ↓
Running
```

O compilador deve explicar o modelo mental.

---

## 55. TESTES NEGATIVOS

As garantias principais precisam de testes que comprovem rejeição.

Exemplos:

```text
use-after-move
invalid state transition
missing authority
bounds violation
illegal interrupt effect
blocking UI operation
recursive value type
unsafe operation outside unsafe
unproven contract
invalid generic instantiation
```

---

## 56. TESTES END-TO-END

Todo exemplo oficial deverá passar:

```text
source
 ↓
check
 ↓
compile
 ↓
backend validation
 ↓
execute when applicable
```

O CI não deverá dizer `100% PASS` se testa apenas subconjunto não declarado.

---

## 57. DOCUMENTAÇÃO EXECUTÁVEL

Exemplos da documentação deverão ser compilados pelo CI.

Assim:

```text
README example
docs example
tutorial example
RFC executable example
```

não poderão divergir silenciosamente da linguagem real.

---

## 58. STATUS DE FEATURES

A documentação usará estados explícitos:

```text
STABLE
SUPPORTED
EXPERIMENTAL
PROTOTYPE
DESIGNED
PLANNED
```

Nunca marcar `Strong`, `Complete` ou equivalente sem critérios mensuráveis.

---

## 59. UM ÚNICO FRONTEND

Sotlas deverá convergir para uma implementação canônica.

Eliminar gradualmente:

```text
duplicated compiler
duplicated tools/sotlas
historical parser ambiguity
multiple incompatible syntaxes
```

Uma linguagem deve possuir uma gramática oficial.

---

## 60. O PRINCÍPIO DOS KILLER EXAMPLES

Nenhuma grande feature nova será implementada simplesmente porque outra linguagem possui.

Cada inovação deverá responder:

> Qual programa importante fica significativamente mais seguro, compreensível ou expressivo por causa disto?

Os primeiros killer examples deverão incluir:

#### Driver

```text
ownership de DMA
MMIO authority
device typestate
interrupt effects
unsafe auditing
```

#### Aplicativo

```text
state space
flow
intent
causal UI
why
whatif
```

#### Serviço

```text
intent
effects
transactions
causality
authority
structured concurrency
```

---

## 61. SOTLAS NÃO TENTARÁ SER “RUST MELHOR”

Rust continuará tendo suas próprias vantagens.

Swift continuará tendo suas próprias vantagens.

C++, Zig, Ada/SPARK e outras linguagens também.

A identidade Sotlas deverá surgir da integração:

```text
INTENT
+
FLOW
+
STATE
+
CAUSALITY
+
EFFECTS
+
OWNERSHIP
+
AUTHORITY
+
GUARANTEES
```

---

## 62. HIPÓTESE CENTRAL DE PESQUISA

A hipótese da Sotlas é:

> Um programa pode ser representado não apenas como instruções, mas como uma rede verificável de intenções, dependências, estados, recursos, autoridades, efeitos e causas.

Se essa hipótese funcionar na prática, várias propriedades tornam-se consequência do mesmo modelo.

---

## 63. SOTLAS SAFETY DIMENSIONS

A linguagem terá dimensões de segurança independentes:

```text
Memory Safety
Bounds Safety
Integer Safety
Ownership Safety
Resource Safety
Authority Safety
State Safety
Effect Safety
Concurrency Safety
Interrupt Safety
Realtime Structural Safety
FFI Safety
Transaction Safety
```

Uma aplicação poderá exigir subconjuntos diferentes.

---

## 64. COMPILAÇÃO COMO PROVA PARCIAL

Compilar um programa Sotlas não significa provar matematicamente tudo sobre ele.

Significa estabelecer claramente:

```text
o que foi provado;
o que foi verificado dinamicamente;
o que foi assumido;
o que depende de unsafe;
o que depende de FFI;
o que não pôde ser demonstrado.
```

Essa distinção deverá aparecer no tooling.

---

## 65. SAFETY MANIFEST

Builds poderão produzir:

```text
program.safety.json
```

ou representação equivalente contendo:

```text
guarantees
unsafe regions
FFI boundaries
capabilities
effects
unproven assumptions
resource ownership
```

Isso poderá ser usado por CI, auditorias e ferramentas externas.

---

## 66. PRINCÍPIO DE ZERO MAGIA

Toda automação da Sotlas deve ser explicável.

Se o compilador:

- paralelizou;
- inseriu bounds check;
- removeu bounds check;
- selecionou caminho de intent;
- inferiu capability;
- inferiu efeito;
- derivou rollback;

o desenvolvedor deverá conseguir perguntar por quê.

Exemplos:

```text
sotlas explain optimization ...
sotlas explain flow ...
sotlas explain authority ...
sotlas explain proof ...
```

---

## 67. ROADMAP DE IMPLEMENTAÇÃO

Não implementaremos tudo simultaneamente.

### Fase 0 — Reality Reset

Corrigir imediatamente:

```text
README vs implementação
examples quebrados
samples quebrados
CI incompleto
frontend duplicado
tools/sotlas duplicado
Baken dentro do compiler core
check que aceita C inválido
```

---

### Fase 1 — Semantic Foundation

Implementar corretamente:

```text
Typed AST
type checking
recursive type rejection
integer semantics
bounds
sole move checking
unsafe
@system
```

---

### Fase 2 — Authority

Adicionar:

```text
capabilities
authority propagation
authority graph
typed resources
```

---

### Fase 3 — State

Adicionar:

```text
space
typestate
transitions
state coverage
```

---

### Fase 4 — Effects

Adicionar:

```text
effect declarations
effect inference
interrupt restrictions
UI restrictions
realtime structural restrictions
```

---

### Fase 5 — Flow

Adicionar:

```text
flow syntax
dependency graph
parallel scheduling
structured concurrency
cancellation
ownership integration
effect-aware scheduling
```

---

### Fase 6 — Guarantees

Adicionar:

```text
requires
ensures
guarantee
bounds proofs
limited symbolic reasoning
proof reports
```
---

### Fase 7 — Causality

Adicionar:

```text
causal graph
why
explain
dependency provenance
IDE visualization
```

Status atual: protótipo source-stable consulta caminhos de dependência entre
stages de Flow tipado/SIR e mostra função, parâmetro, tipo e efeitos por passo.
Chamadas e expressões fora de Flow, provenance de diagnósticos e visualização
IDE continuam pendentes.

---

### Fase 8 — What-if

Adicionar:

```text
safe simulation
affected-state calculation
effect isolation
counterfactual inspection
```

---

### Fase 9 — Transactions

Adicionar:

```text
change
transaction
diff
rollback
compensation
irreversible effect analysis
```

---

### Fase 10 — Intent

Somente depois de Flow, Effects, State e Guarantees estarem sólidos:

```text
intent
strategy planning
prefer/fallback
intent guarantees
plan inspection
```

`intent` depende dessas fundações e não deverá ser uma camada de magia.

---

### Fase 11 — SIR 2

Fazer lowering real:

```text
Typed AST
 ↓
Semantic Graph
 ↓
SIR
 ↓
passes
 ↓
backend
```

Todos os corpos precisam ser representados corretamente.

---

### Fase 12 — Tooling

```text
LSP
formatter
linter
causal debugger
Flow View
State View
Authority View
Effect View
Safety View
Proof View
```

---

## 68. ORDEM DE PRIORIDADE

A ordem não será:

```text
mais features
mais sintaxe
mais exemplos bonitos
```

Será:

```text
CORRECTNESS
    ↓
SEMANTICS
    ↓
SAFETY
    ↓
NOVEL MODEL
    ↓
PERFORMANCE
    ↓
TOOLING
    ↓
ECOSYSTEM
```

---

## 69. REGRA PARA AFIRMAÇÕES DE ORIGINALIDADE

Nenhum recurso será chamado de:

```text
first
unique
unprecedented
never done before
```

sem pesquisa comparativa.

Antes disso deverão ser analisados pelo menos:

```text
C
C++
Rust
Swift
Zig
Ada/SPARK
Haskell
OCaml
Pony
Vale
D
Nim
Carbon
Mojo

e linguagens acadêmicas relevantes.
```

Principalmente trabalhos sobre:

```text
linear types
affine types
typestate
refinement types
effect systems
capability security
dataflow
FRP
provenance
reversible computing
dependent types
session types
gradual verification
```

A inovação poderá estar em um mecanismo novo ou na composição inédita de mecanismos existentes.

---

## 70. CRITÉRIO PARA UMA INOVAÇÃO SOTLAS

Uma proposta só entra no núcleo se responder satisfatoriamente:

```text
1. Qual problema resolve?

2. Por que biblioteca não resolve adequadamente?

3. Por que precisa do compilador?

4. Qual propriedade pode ser garantida?

5. Qual é o custo cognitivo?

6. Como interage com ownership?

7. Como interage com effects?

8. Como interage com authority?

9. Como aparece no SIR?

10. Como é testada?

11. Como é explicada pelo tooling?

12. Existe mecanismo equivalente em outra linguagem?
```

---

## 71. A EXPERIÊNCIA QUE QUEREMOS

Queremos que um desenvolvedor abra código Sotlas e consiga enxergar:

```text
o que o programa quer;
como os dados fluem;
quais estados existem;
quem possui cada recurso;
quem tem autoridade;
quais efeitos acontecem;
por que um valor possui determinado estado;
quais garantias são demonstráveis.
```

O código deve funcionar simultaneamente como implementação e mapa do comportamento do sistema.

---

## 72. VISÃO FINAL

Sotlas não deverá ser definida simplesmente como:

> Uma linguagem memory-safe.

Nem:

> Uma alternativa moderna a C++.

Nem:

> Rust mais simples.

Nem:

> Swift para sistemas.

A hipótese que guia o projeto será:

> **Sotlas explora programação causal, orientada a intenção e verificável, na qual estado, fluxo, ownership, autoridade, efeitos e garantias fazem parte do modelo semântico do programa.**

Um programa Sotlas não deverá apenas executar.

Ele deverá ser capaz de informar:

```text
WHAT it intends to accomplish
HOW data flows
WHO owns resources
WHO has authority
WHICH states are possible
WHICH effects can occur
WHY a state exists
WHAT depends on it
WHAT could change
WHICH guarantees hold
WHERE safety was escaped
```

Esse é o objetivo de pesquisa.

---

## 73. PRINCÍPIO FINAL

Não construiremos vinte features para impressionar outras empresas.

Construiremos primeiro uma propriedade que seja tão útil que um engenheiro pergunte:

> “Por que meu compilador não consegue fazer isso?”

Quando encontrarmos essa propriedade e conseguirmos demonstrá-la em software real, ela será o núcleo da Sotlas.

Todo o restante deverá existir para fortalecê-la.

---

# Parte II — Sotlas Domains e computação heterogênea unificada

Esta parte é uma extensão integral da Parte I. `Domains` não substitui Intent, Flow, State, Effects, Authority, Guarantees ou Causality: fornece a camada que explicita onde valores existem, quem os possui, onde computações executam, quais fronteiras de confiança atravessam e quais garantias sobrevivem às transições.

> Esta revisão preserva integralmente os conceitos definidos anteriormente e acrescenta **Sotlas Domains, Adaptive Ownership, Unified Heterogeneous Computing, Execution Domains, Trust Domains, Isolated FFI e Authority Domains** como partes do mesmo modelo semântico.

---

## NOVA CAMADA — SOTLAS DOMAINS

Sotlas tratará recursos computacionais não apenas através de tipos, mas através de **domínios semânticos**.

Um domínio descreve onde algo existe, quem pode utilizá-lo, onde pode executar e quais garantias atravessam suas fronteiras.

```text
                         PROGRAM
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
      OWNERSHIP         EXECUTION           TRUST
          │                 │                 │
      exclusive            CPU              safe
       shared              SIMD            verified
       region              GPU             trusted
       device              NPU             foreign
      external         accelerator         isolated
          │                 │                unsafe
          └─────────────────┼─────────────────┘
                            │
                        AUTHORITY
                            │
                       capabilities
```

Esses domínios integram-se ao restante da linguagem:

```text
INTENT
   ↓
FLOW
   ↓
DOMAINS
   ↓
STATE
   ↓
EFFECTS
   ↓
OWNERSHIP
   ↓
AUTHORITY
   ↓
GUARANTEES
   ↓
CAUSALITY
```

---

## ADAPTIVE OWNERSHIP

Sotlas não adotará obrigatoriamente um único regime de gerenciamento de memória para todos os valores.

O regime poderá fazer parte da semântica do recurso.

```text
Ownership Domain

exclusive
shared
region
device
external
```

Um valor comum poderá permanecer exclusivamente controlado:

```sotlas
let buffer = Buffer(4096);
```

Quando compartilhamento for realmente necessário:

```sotlas
let shared graph = share(Graph());
```

A transição é observável:

```text
exclusive
    │
   share
    ▼
shared
```

O compilador poderá selecionar estratégias como static ownership, ARC, region allocation ou mecanismos específicos de recursos.

Entretanto, mudanças que introduzam custo de runtime não deverão acontecer de maneira invisível.

A regra permanece:

> **Zero Magic Cost.**

O desenvolvedor deve conseguir inspecionar quando Sotlas introduziu reference counting, sincronização, movimentação de memória ou qualquer outro custo significativo.

---

## OWNERSHIP DE HARDWARE

Ownership também poderá representar quem possui fisicamente o direito de acessar um recurso.

```sotlas
let buffer = Buffer(4096);

gpu.submit(move buffer);
```

Produz conceitualmente:

```text
CPU
 │
 │ transfer
 ▼
GPU
```

Enquanto o dispositivo possui o buffer:

```sotlas
buffer[0] = 42;
```

é inválido.

Após completion:

```text
GPU
 │
 │ completion
 ▼
CPU
```

o ownership pode retornar.

O mesmo princípio poderá ser aplicado a:

- GPU;
- NPU;
- DMA;
- dispositivos PCI;
- network devices;
- accelerators;
- storage controllers.

---

## UNIFIED HETEROGENEOUS COMPUTING

Sotlas investigará um modelo no qual CPU, GPU, SIMD, NPU e futuros aceleradores sejam tratados como **Execution Domains de uma única máquina lógica**.

O programador descreve principalmente a computação.

Não necessariamente o dispositivo.

Em vez de:

```text
CPU code
GPU shader
CUDA kernel
NPU graph
```

o objetivo será permitir:

```sotlas
compute Enhance(image) {
    parallel
    independent

    ...
}
```

O compilador determina quais implementações são semanticamente válidas.

```text
                         Enhance
                            │
           ┌────────────────┼────────────────┐
           │                │                │
          CPU              GPU              NPU
           │                │                │
        scalar/SIMD       compute       neural/graph
```

Isso será denominado provisoriamente:

### Sotlas Unified Compute Model — SUCM

O princípio será:

> **One program. Multiple execution domains. Verified transitions.**

---

## COMPUTE

`compute` representa uma região computacional elegível para transformação entre Execution Domains.

Exemplo:

```sotlas
compute Transform(data) {
    parallel
    independent
    pure

    data[i] = sqrt(data[i]) * 2
}
```

O programador declarou propriedades semânticas:

```text
parallel
independent
pure
```

e não simplesmente:

```text
GPU
```

Isso fornece ao compilador evidência para decidir onde a computação pode ocorrer.

---

## EXECUTION CONTRACTS

Quando necessário, o programador poderá restringir os domínios permitidos:

```sotlas
compute Enhance(image)
    permits {
        cpu.scalar
        cpu.simd
        gpu
        npu
    }
    guarantee {
        deterministic
    }
{
    ...
}
```

Isso não significa que toda implementação seja automaticamente possível.

O compilador somente poderá escolher um domínio para o qual exista lowering válido e cujas propriedades satisfaçam o contrato.

---

## EXECUTION PLANNER

O compilador/runtime poderá possuir um **Execution Planner**.

Ele recebe:

```text
Flow Graph
Hardware Topology
Ownership
Data Location
Effects
Authority
Guarantees
Cost Model
```

e produz:

```text
Execution Plan
```

Exemplo:

```text
Camera
  │
  ▼
Decode                     CPU
  │
  ▼
Resize                     GPU
  │
  ▼
ObjectDetection            NPU
  │
  ▼
PostProcessing             SIMD
  │
  ▼
UI                         CPU
```

O código Sotlas continua sendo um único programa.

---

## DATA LOCATION É PARTE DO PLANO

Escolher GPU ou NPU não é suficiente.

Mover memória pode custar mais que executar determinada computação na CPU.

Por isso o planner deverá considerar:

```text
compute cost
transfer cost
synchronization cost
memory pressure
latency
energy
device availability
```

Exemplo:

```text
CPU ───────────────► GPU
        8 MB copy
```

pode ser pior que simplesmente:

```text
CPU
 │
 └── SIMD execution
```

Sotlas deverá conseguir justificar a decisão.

---

## ZERO INVISIBLE TRANSFERS

Assim como custos de ownership não devem ser escondidos, grandes transferências de memória não devem ser invisíveis ao tooling.

O compilador poderá otimizar automaticamente, mas deverá permitir:

```text
sotlas explain execution ProcessImage
```

Resultado conceitual:

```text
Resize selected: GPU

reason:
    parallel workload
    4.2x estimated compute advantage
    input already GPU-resident

transfer:
    none

alternative:
    CPU SIMD
```

---

## DEVICE-RESIDENT VALUES

Valores poderão possuir residência associada ao Execution Domain:

```text
Image<cpu>
Image<gpu>
Tensor<npu>
```

Isso não precisa necessariamente aparecer sempre na sintaxe superficial.

A Typed AST/SIR deverá, entretanto, conhecer a residência.

Assim:

```text
CPU ownership
     │
     ▼
GPU ownership
     │
     ▼
NPU ownership
```

torna-se uma sequência verificável.

---

## FLOW + HETEROGENEOUS COMPUTING

`flow` torna-se especialmente poderoso nesse modelo.

```sotlas
flow Vision(camera) {

    frame    = camera.capture()

    enhanced = compute Enhance(frame)

    objects  = compute DetectObjects(enhanced)

    result   = classify(objects)

    render(result)
}
```

O desenvolvedor vê:

```text
Capture
   ↓
Enhance
   ↓
DetectObjects
   ↓
Classify
   ↓
Render
```

O compilador poderá produzir:

```text
Capture                  CPU
   │
   ▼
Enhance                  GPU
   │
   ▼
DetectObjects            NPU
   │
   ▼
Classify                 NPU
   │
   ▼
Render                   GPU/CPU
```

---

## FLOW FUSION

Quando dois nós consecutivos utilizam o mesmo Execution Domain:

```text
Enhance          GPU
   ↓
Filter           GPU
```

Sotlas poderá evitar:

```text
GPU → CPU → GPU
```

e manter o recurso residente:

```text
GPU
 │
 Enhance
 │
 Filter
 │
 ▼
```

Isso conecta otimização diretamente ao modelo de ownership.

---

## FLOW + OWNERSHIP

O Flow Graph também é um Ownership Graph.

```text
Frame<CPU>
     │
     │ transfer
     ▼
Frame<GPU>
     │
     │ consume
     ▼
Enhanced<GPU>
     │
     │ transfer
     ▼
Tensor<NPU>
```

Nenhum domínio poderá acessar um recurso enquanto não possuir autoridade/ownership apropriados.

---

## FLOW + EFFECTS

Uma operação poderá declarar:

```sotlas
compute Detect(image)
    effects {
        compute
        npu
    }
```

Outra poderá exigir:

```text
network
filesystem
gpu
```

O planner não poderá mover arbitrariamente operações entre domínios se isso alterar efeitos observáveis.

---

## FLOW + AUTHORITY

Possuir hardware não significa possuir autoridade para utilizá-lo.

Uma aplicação poderá possuir:

```text
gpu.compute
```

mas não:

```text
gpu.raw
```

Da mesma forma:

```text
npu.inference
```

pode ser permitido enquanto acesso direto aos registradores permanece proibido.

Assim:

```text
Hardware availability ≠ authority
```

---

## DETERMINISM ACROSS DOMAINS

Uma preocupação central será equivalência semântica.

CPU, GPU e NPU podem possuir:

- precisão diferente;
- floating-point behavior diferente;
- ordering diferente;
- atomic semantics diferentes.

Portanto:

```sotlas
guarantee {
    deterministic
}
```

deverá limitar as transformações permitidas.

Quando equivalência estrita não puder ser garantida, o compilador não deverá fingir que consegue.

---

## HARDWARE SPECIALIZATION SEM FORK DO CÓDIGO

Quando realmente necessária, Sotlas poderá permitir implementações especializadas:

```sotlas
compute MatrixMultiply(a, b) {
    default {
        ...
    }

    specialize gpu {
        ...
    }

    specialize npu {
        ...
    }
}
```

A API permanece única.

O planner seleciona a implementação apropriada.

---

## PROFILE-GUIDED EXECUTION

Uma evolução futura poderá permitir que builds utilizem perfis reais:

```text
sotlas profile
```

para alimentar o Execution Planner.

Entretanto, otimização baseada em perfil nunca deverá alterar propriedades semânticas ou garantias do programa.

---

## ENERGY-AWARE COMPUTATION

Execution Contracts poderão futuramente expressar objetivos:

```sotlas
compute BackgroundAnalysis(data)
    optimize {
        energy
    }
```

ou:

```sotlas
optimize {
    latency
}
```

ou:

```sotlas
optimize {
    throughput
}
```

Isso permite que o mesmo programa tenha estratégias diferentes dependendo do ambiente.

---

## DEVICE FAILURE

Flows heterogêneos precisam tratar falha de dispositivo.

```text
GPU unavailable
NPU unavailable
accelerator reset
```

Um Intent poderá declarar:

```sotlas
intent Analyze(image) {

    obtain Analysis(image)

    prefer npu
    fallback gpu
    fallback cpu
}
```

O plano permanece explícito e inspecionável.

---

## INTENT + UNIFIED COMPUTE

Essa integração produz algo maior:

```sotlas
intent AnalyzeScene(camera) -> Scene {
    frame = obtain CameraFrame(camera)

    enhanced = compute Enhance(frame)

    objects = compute DetectObjects(enhanced)

    guarantee {
        memory.safe
        latency < target
        privacy.local
    }
}
```

O desenvolvedor declarou:

```text
WHAT
```

O `flow` representa:

```text
DEPENDENCIES
```

Os Domains representam:

```text
WHERE
```

Ownership representa:

```text
WHO CONTROLS DATA
```

Effects representam:

```text
WHAT CAN HAPPEN
```

Authority representa:

```text
WHAT IS ALLOWED
```

Guarantees representam:

```text
WHAT MUST REMAIN TRUE
```

Causality representa:

```text
WHY
```

---

## TRUST DOMAINS

Código externo deverá possuir níveis explícitos de confiança.

```sotlas
extern trusted "C" {
    ...
}
```

```sotlas
extern unsafe "C" {
    ...
}
```

```sotlas
extern isolated "C" {
    ...
}
```

A linguagem não afirmará que wrappers C11 tornam código C arbitrário seguro.

Isolamento verdadeiro deverá utilizar mecanismos reais disponibilizados pelo target.

---

## FOREIGN DOMAINS

`isolated` poderá ser lowered para diferentes mecanismos:

```text
Desktop
    → process sandbox

Web
    → WASM sandbox

Kernel
    → compartment / protection domain

Embedded
    → MPU domain

Supported hardware
    → hardware isolation
```

A abstração da linguagem será `Foreign Domain`, não um mecanismo específico.

---

## FFI FAILURES COMO VALORES

Quando um Foreign Domain isolado falhar:

```text
segmentation fault
illegal instruction
memory violation
```

a fronteira Sotlas poderá transformar a falha isolável em:

```sotlas
Result<T, ForeignFailure>
```

quando a plataforma realmente puder fornecer essa contenção.

---

## TRUST É DIFERENTE DE AUTHORITY

Sotlas distinguirá:

```text
AUTHORITY
"What may this code do?"

TRUST
"What guarantees do we accept from this code?"
```

Um componente pode ser:

```text
low trust + low authority
```

ou:

```text
trusted + high authority
```

Essa distinção deverá aparecer no Safety Graph.

---

## DOMAIN TRANSITIONS

O compilador deverá representar transições explicitamente:

```text
                OWNERSHIP

exclusive ─────► shared
    │
    └──────────► device


                EXECUTION

CPU ───────────► GPU ───────────► NPU


                   TRUST

safe ──────────► foreign isolated


                 AUTHORITY

none ──────────► gpu.compute
```

Transições podem exigir:

```text
copy
move
synchronization
validation
permission
sandbox boundary
```

O compilador deverá conhecer esses custos e propriedades.

---

## DOMAIN GRAPH

Sotlas poderá produzir:

```text
sotlas domains app.sot
```

e apresentar:

```text
PhotoPipeline

Camera
 │
 │ CPU / exclusive
 ▼
Decode
 │ isolated foreign
 ▼
Image
 │ CPU / exclusive
 ▼
Enhance
 │ transfer ownership
 ▼
GPU
 │
 ▼
Detect
 │ transfer
 ▼
NPU
 │
 ▼
Result
 │
 ▼
CPU/UI
```

---

## DOMAIN SAFETY

`guarantee` poderá incluir:

```sotlas
guarantee VisionPipeline {
    memory.safe
    ownership.safe
    authority.safe
    foreign.isolated
    transfers.valid
}
```

O Safety Report deverá distinguir propriedades comprovadas de propriedades assumidas.

---

## NOVA ARQUITETURA UNIFICADA

Com todas as propostas reunidas, a arquitetura conceitual completa passa a ser:

```text
                            INTENT
                               │
                               ▼
                             FLOW
                               │
                               ▼
                         CAUSAL GRAPH
                               │
                ┌──────────────┼──────────────┐
                │              │              │
              STATE         EFFECTS       GUARANTEES
                │              │              │
                └──────────────┼──────────────┘
                               │
                            DOMAINS
                               │
       ┌───────────────────────┼───────────────────────┐
       │                       │                       │
   OWNERSHIP               EXECUTION                 TRUST
       │                       │                       │
 exclusive                 CPU/scalar                safe
 shared                    CPU/SIMD                 verified
 region                       GPU                   trusted
 device                       NPU                   foreign
 external                 accelerator              isolated
       │                       │                      unsafe
       └───────────────────────┼───────────────────────┘
                               │
                           AUTHORITY
                               │
                         CAPABILITIES
                               │
                               ▼
                      SEMANTIC ANALYSIS
                               │
                               ▼
                              SIR
                               │
                    ┌──────────┼──────────┐
                    │          │          │
                  Native       C         WASM
```

---

## O NOVO PAPEL DO SIR

SIR precisará eventualmente representar mais que operações tradicionais.

Ele deverá ser capaz de transportar:

```text
ownership edges
resource residence
execution domains
authority requirements
trust boundaries
effect sets
state transitions
flow dependencies
causal edges
guarantees
unsafe boundaries
transfer operations
```

Exemplo conceitual:

```text
%image = capture

transfer %image
    ownership CPU -> GPU
    execution GPU
    authority gpu.compute

%enhanced = compute Enhance(%image)

transfer %enhanced
    ownership GPU -> NPU

%objects = compute Detect(%enhanced)
```

Isso permitirá que passes raciocinem sobre o programa inteiro.

---

## PRINCÍPIO DE EXPLAINABLE COMPILATION

Toda decisão importante feita automaticamente deverá ser inspecionável.

O desenvolvedor poderá perguntar:

```text
Why GPU?

Why ARC?

Why this bounds check?

Why this transfer?

Why this synchronization?

Why this capability?

Why can't this run on NPU?

Why isn't this flow parallel?
```

A resposta deverá vir da representação semântica do compilador.

---

## SOTLAS COMO PROGRAMA EXPLICÁVEL

A visão consolidada passa a ser:

```text
WHAT?       → Intent

HOW CONNECTED?
            → Flow

WHERE?      → Execution Domain

WHO OWNS?
            → Ownership Domain

WHAT STATE?
            → State Space

WHAT HAPPENS?
            → Effects

WHO MAY?
            → Authority

WHO TRUSTS?
            → Trust Domain

WHAT MUST HOLD?
            → Guarantee

WHY?
            → Causality

WHAT IF?
            → Counterfactual analysis
```

---

## KILLER EXAMPLE — HETEROGENEOUS VISION

Um dos programas demonstradores oficiais deverá ser aproximadamente:

```sotlas
intent UnderstandScene(camera) -> Scene {

    flow {
        frame = camera.capture()

        enhanced = compute Enhance(frame)

        objects = compute DetectObjects(enhanced)

        scene = derive Scene(objects)
    }

    guarantee {
        memory.safe
        ownership.safe
        privacy.local
    }
}
```

O mesmo código poderá resultar conceitualmente em:

```text
CAMERA
   │
   ▼
CPU
Capture
   │
   │ ownership transfer
   ▼
GPU
Enhance
   │
   │ ownership transfer
   ▼
NPU
Object Detection
   │
   ▼
CPU
Scene
```

E:

```text
sotlas explain UnderstandScene
```

deverá conseguir explicar todo esse plano.

---

## KILLER EXAMPLE — BAKENOS DRIVER

Outro demonstrador deverá combinar:

```text
sole ownership
device ownership
MMIO authority
interrupt effects
typestate
DMA transfer
unsafe audit
```

para demonstrar que a mesma arquitetura serve tanto a aplicações quanto a sistemas operacionais.

---

## REGRA FUNDAMENTAL

Sotlas não prometerá:

> “O compilador sempre sabe melhor que o programador.”

A promessa será:

> **O compilador possui informação suficiente para tomar determinadas decisões quando consegue prová-las e consegue explicar cada decisão tomada.**

Quando não houver prova suficiente, Sotlas deverá:

```text
ask for an explicit constraint
use a safe fallback
or reject the transformation
```

Nunca inventar segurança.

---

## IDENTIDADE CONSOLIDADA DA SOTLAS

Sotlas deixa de ser concebida como:

> “C moderno com safety.”

Também não será definida como:

> “Rust mais simples.”

> “Swift para sistemas.”

> “C com ARC.”

A visão passa a ser:

> **Sotlas é uma linguagem de programação causal, orientada a intenção e verificável, capaz de representar um programa através de fluxos, estados, ownership, autoridade, confiança, efeitos e garantias, enquanto trata recursos heterogêneos de CPU, SIMD, GPU, NPU e aceleradores como domínios de execução de uma única máquina lógica.**

O objetivo final não é esconder hardware.

É permitir que o desenvolvedor trabalhe em um nível semântico mais alto **sem perder controle, previsibilidade, auditabilidade ou capacidade de descer até o hardware quando necessário.**

---

## PRINCÍPIO DE IMPLEMENTAÇÃO

Nada desta seção será marcado como implementado apenas porque a sintaxe foi adicionada.

Para cada mecanismo:

```text
RFC
 ↓
Grammar
 ↓
Typed AST
 ↓
Semantic Rules
 ↓
Negative Tests
 ↓
Positive Tests
 ↓
SIR
 ↓
Lowering
 ↓
Backend
 ↓
End-to-End
 ↓
Documentation
```

Só então:

```text
SUPPORTED
```

---

## REGRA OPERACIONAL DE COMMITS E CI

Durante o desenvolvimento assistido da Sotlas, o fluxo de trabalho será:

```text
Assistant
  ↓
implementa uma unidade coerente
  ↓
cria o commit
  ↓
registra exatamente o que mudou
  ↓
continua o desenvolvimento

Usuário
  ↓
monitora GitHub Actions / workflows / CI
  ↓
comunica falhas ou regressões quando aparecerem
```

Regras obrigatórias:

- o assistente **não deve permanecer monitorando workflows após cada commit**;
- o assistente deve priorizar implementação, auditoria do código e criação de commits pequenos e rastreáveis;
- após cada commit, o assistente deve informar o hash, a mensagem e as mudanças relevantes para registro;
- o acompanhamento contínuo do GitHub Actions/CI fica sob responsabilidade do usuário;
- quando o usuário comunicar falha ou regressão, o assistente deve interromper o avanço daquela linha, investigar a causa e produzir uma correção isolada;
- um commit ainda não observado no CI não deve ser descrito como baseline verde confirmado;
- certificações formais continuam exigindo os gates definidos no projeto, mas a confirmação do resultado do workflow será fornecida pelo usuário.

Essa regra é operacional e **não reduz os critérios técnicos de qualidade ou certificação da linguagem**. Ela apenas separa a responsabilidade de desenvolvimento da responsabilidade de monitoramento do CI.

---

## REGISTRO CANÔNICO DE VOCABULÁRIO RESERVADO DA SOTLAS

Esta seção preserva construções que fazem parte da identidade planejada da linguagem, mas **não antecipa o status `SUPPORTED`** de nenhuma delas. Uma palavra estar registrada aqui significa que o projeto pretende mantê-la e dar-lhe uma função própria; não significa que parser, Typed AST, semântica, lowering, backend ou ABI atuais já cumpram o contrato.

Regra normativa de maturidade:

```text
RESERVED
   ↓
RFC / SEMANTIC CONTRACT
   ↓
GRAMMAR
   ↓
TYPED AST
   ↓
SEMANTIC RULES
   ↓
NEGATIVE + POSITIVE TESTS
   ↓
SIR / LOWERING
   ↓
BACKEND
   ↓
END-TO-END
   ↓
SUPPORTED
```

Protótipos, tokens, syntax highlighting, exemplos de documentação ou lowering parcial **não promovem** uma construção a `SUPPORTED`. Se documentos antigos atribuírem funções conflitantes a uma palavra, este registro define a intenção arquitetural a ser formalizada; a divergência deverá ser resolvida por RFC antes da implementação definitiva.

### A. Gestão de Memória SRG — Scoped Reference Graph

| Construção | Função semântica reservada |
|---|---|
| `sole` | Ownership exclusivo e linear. Um único proprietário válido; transferências invalidam a origem e a destruição é determinística. |
| `co-owned` | Ownership compartilhado explícito com ARC/contagem de referências ou mecanismo equivalente definido pelo domínio. O custo de compartilhamento não pode ser oculto. |
| `island` | Subgrafo/região de ownership isolado. Aliases externos não podem apontar livremente para dentro; cruzamentos de fronteira exigem operação explícita. |
| `whisper` | Referência não proprietária/weak-borrow. Não prolonga a vida do alvo; deve obedecer ao lifetime do owner e, em grafos compartilhados, pode tornar-se inválida/nula de forma verificável. |
| `direct` | Acesso/referência SRG de zero bookkeeping para contextos de baixo nível. Não implica por si só endereço físico; lifetime e segurança devem ser explícitos e combinam-se com a topologia do ponteiro. |
| `handover` | Transferência explícita de ownership/obrigação de recurso para outro binding, escopo ou domínio, sem destruição intermediária. |
| `quarantine` | Move um recurso para um domínio `island`/isolado, cortando ou invalidando acessos externos incompatíveis antes de reutilização, inspeção ou despacho. |

### B. Ponteiros de Topologia de Hardware

Topologia é ortogonal a ownership: ela descreve **onde e como um endereço existe**, enquanto SRG descreve **quem possui ou pode referenciar o recurso**.

| Construção | Função semântica reservada |
|---|---|
| `*rawphys T` | Endereço físico direto de hardware/MMIO. Acesso exige regras de volatilidade/ordenação apropriadas ao alvo e não se converte implicitamente em virtual. |
| `*virtmap T` | Endereço virtual mapeado por MMU/tabela de páginas. Conversão para/de físico exige tradução explícita. |
| `*portwire T` | Espaço de I/O de portas separado do espaço de memória, com lowering para instruções/ABI de I/O suportadas pelo alvo. |
| `*dmazone T` | Região apta a DMA, com contrato explícito de alinhamento, coerência/cache e ownership entre CPU/dispositivo. |
| `*voidzero` | Ponteiro opaco sem tipo de payload, equivalente conceitualmente ao papel de `void*`, porém com conversões explícitas e restrições de topologia/safety. |

### C. Hardware, Seções Críticas e Interrupções

| Construção | Função semântica reservada |
|---|---|
| `clinch` | Abre uma seção crítica de hardware e cria uma obrigação de restauração/saída verificável pelo compilador. |
| `revert` | Caminho associado a `clinch` para rollback/restauração do estado crítico; a semântica final deve garantir restauração nas saídas abrangidas pelo construto. |
| `rebound` | Retomada/saída explícita após restauração de contexto de baixo nível; não deve ser sinônimo genérico de `return`. |
| `quench` | Barreira forte de ordenação/persistência de memória, com lowering específico do alvo quando houver suporte. Não deve esconder custo de flush/fence. |
| `gate` | Pré-condição/guarda estruturada de hardware em runtime, com comportamento de falha definido e auditável; não é um `if` comum sem contrato. |
| `trapfn` | Função de tratamento de interrupção com ABI de ISR e restrições automáticas de efeitos/stack/retorno. |
| `mesh` | Agregado com layout físico explícito para registradores, barramentos, SoA/ECS e estruturas que exigem alinhamento/offsets verificáveis. |
| `barecore` | Perfil freestanding para kernel, firmware e drivers: sem runtime hospedado implícito e com primitivas de hardware habilitadas sob contratos explícitos. |
| `probe` | Ponto explícito de observabilidade/verificação/instrumentação com efeitos conhecidos; não pode alterar ownership silenciosamente. |
| `pulse` | Emissão determinística de evento/sinal para sistemas reativos/flow, com política de entrega e efeitos formalizados antes de uso normativo. |

### D. Contratos e Orientação a Objetos sem Headers

| Construção | Função semântica reservada |
|---|---|
| `spec` | Contrato de API/protocolo verificável em compilação, sem necessidade de headers Sotlas. |
| `adopts` | Declara e verifica que um tipo satisfaz uma ou mais `spec`, incluindo assinaturas e requisitos associados. |
| `mould` | Contexto de shaping/especialização em compile time para adaptar layout/comportamento sob regras determinísticas. |
| `moldable` | Marca explicitamente uma operação como passível de especialização/override; despacho dinâmico nunca deve surgir implicitamente. |
| `reshape` | Implementação/override explícito de uma operação `moldable`, com validação rigorosa de assinatura e contrato. |
| `capsule` | Visibilidade restrita ao módulo/pacote/cápsula de implementação. |
| `lineage` | Visibilidade restrita à hierarquia de herança/linhagem do tipo. |
| `irqfree` | Contrato de efeitos para código utilizável em interrupções: proíbe operações como alocação, bloqueio e async quando não demonstravelmente seguras. |
| `discern` | Pattern matching exaustivo sobre enums/ADTs, com cobertura verificada estaticamente. |
| `forge` | Mecanismo reservado para construção/especialização genérica em compile time e monomorfização; a sintaxe final será congelada somente na fase de generics. |
| `enclave` | Domínio explícito de isolamento/confiança. Entradas, saídas, capabilities e transferência de recursos pela fronteira devem ser verificáveis. |

### E. Qualificadores de Estado e Memória

| Construção | Função semântica reservada |
|---|---|
| `shielded` | Estado/memória protegidos contra interferência concorrente ou de hardware. O backend deve materializar apenas as barreiras/atomicidade necessárias ao contrato e ao alvo. |
| `nvkeep` | Estado com residência/durabilidade em memória não volátil; escrita só é considerada durável após a política de persistência exigida pelo alvo. |
| `seal` | Valor/região mutável somente durante a janela de inicialização autorizada e imutável após o selamento. |

### F. Acessores Nativos de Bits e Intervalos

| Construção | Função semântica reservada |
|---|---|
| `.slit[lo..hi]` | Extrai um intervalo contíguo de bits com regras de largura e bounds verificáveis. |
| `.notch[n]` | Extrai/testa um único bit, com índice validado estaticamente quando possível. |
| `.strand` | Conversão de ordem de bytes/endianness, preferindo instrução nativa do alvo quando disponível. |
| `.bound[min..max]` | Cria/refina um tipo com intervalo de valores permitido; violações devem ser provadas impossíveis, verificadas em runtime ou rejeitadas conforme o contrato. |

### G. Vocabulário semântico avançado já preservado

Continuam reservadas as construções da arquitetura causal e orientada a intenção já descritas neste documento: `intent`, `flow`, `space`, `state`, `view`, `when`, `guarantee`, `requires`, `ensures`, `proof`, `why`, `explain`, `whatif`, `change`, `transaction`, `compute`, `@target`, `permits`, `effects`, `capabilities`, `@system`, `@interrupt`, `@realtime`, `unsafe`, `shared`, `region`, `device`, `external`, `trusted` e `isolated`.

A presença dessa lista **não exige implementar tudo agora**. Ela existe para impedir que a evolução do compilador apague conceitos deliberadamente escolhidos antes que chegue a fase correta.

### H. Regra de ativação por dependência

A implementação deve seguir dependências técnicas, e não a vontade de “ativar uma keyword” isoladamente:

1. **Agora / núcleo nativo:** terminar AST, controle de fluxo, `defer`, SIR/lowering e backend sem regressões.
2. **Ownership estabilizado:** formalizar SRG (`sole`, `co-owned`, `island`, `whisper`, `direct`, `handover`, `quarantine`).
3. **Tipos de hardware + backend bare-metal estabilizados:** formalizar topologia, `mesh`, acessores de bits e qualificadores de memória.
4. **Effects + Authority/Trust estabilizados:** formalizar `trapfn`, `irqfree`, `clinch/revert`, `rebound`, `quench`, `gate`, `enclave`.
5. **Generics/dispatch estabilizados:** congelar `spec`, `adopts`, `forge`, `mould`, `moldable`, `reshape`, `capsule`, `lineage`, `discern`.
6. **Flow/observabilidade estabilizados:** formalizar `probe` e `pulse`.
7. **Somente depois das fundações acima:** expandir Intent, Causality, Counterfactuals, Transactions e SUCM.

Nenhuma dessas etapas pode contornar o gate geral de `SUPPORTED`.

## NOVA ORDEM DE IMPLEMENTAÇÃO

> **Legenda de acompanhamento (2026-09-21)**  
> `[x]` = concluído/certificado no escopo declarado.  
> `[ ]` = ainda não concluído.  
> `🟡 PARCIAL` = infraestrutura real existe, mas o gate completo de `SUPPORTED` ainda não foi atravessado.

### 0. Reality Reset

Consertar a base atual.

Status atual:

- [x] pipeline canônico de frontend preservado;
- [x] reality gates para impedir regressão da maturidade do Typed AST;
- [x] regra formal de que testes são contratos, não obstáculos;
- [x] `check` e backend C11 possuem gate para não aceitar silenciosamente lowering ainda não implementado;
- [x] fixtures `.sotlas` exercitam os dois lados do gate: enum escalar gera e executa binário C11; `share` com defer chega ao SIR, enquanto o backend C11 o rejeita explicitamente;
- [ ] eliminação completa de todo legado/duplicação histórica do projeto;
- [ ] auditoria final de todos os exemplos, documentação pública e claims antigos.

### 1. Typed Semantic Core — ✅ CERTIFIED (`ISOLATED_PHASE1`)

Tipos, bounds, integer semantics, `sole`, `unsafe`, recursive types.

Checklist certificado do núcleo semântico isolado:

- [x] Typed AST canônico de declarações (`TypedModule`, structs, enums, classes, globals e funções);
- [x] Typed AST de corpos estruturados de função;
- [x] pipeline público `analyze_source_phase1` / `Phase1ModuleSnapshot`;
- [x] contextualização de literais inteiros;
- [x] validação de faixa de constantes inteiras;
- [x] rejeição de mismatch numérico explícito;
- [x] semântica de operadores escalares, igualdade, shifts e unários;
- [x] contratos de assignment e return;
- [x] contratos de direct call e method call;
- [x] preservação de assinaturas de function pointers;
- [x] validação de shape e tipos de struct literals;
- [x] regras de raw pointers e safe references;
- [x] contextualização de `null` restrita a raw pointers;
- [x] acesso/aritimética de raw pointer exigindo contexto apropriado;
- [x] proteção contra escrita por referência imutável;
- [x] requisitos de mutable borrow;
- [x] rejeição de tipos recursivos infinitos por valor;
- [x] ownership `sole` com estados LIVE/MOVED/MAYBE_MOVED/borrowed;
- [x] move em chamadas por valor;
- [x] move em retorno;
- [x] move em campos `sole` de struct literals;
- [x] análise de moves em branches;
- [x] rejeição conservadora de moves repetíveis em loops sem reinitialization;
- [x] lexical `unsafe` integrado ao Typed AST;
- [x] fronteira `@system`/`unsafe` preservada no frontend canônico;
- [x] testes positivos e negativos do núcleo semântico;
- [x] gate de maturidade impedindo retorno ao antigo estado `DECLARATIONS_ONLY`.

Extensões construídas sobre a fundação, mas que **não promovem a linguagem inteira a `SUPPORTED`**:

- [x] enum payload type preservado no AST/Typed AST;
- [x] typecheck de construtores `Enum::Variant(payload)`;
- [x] move de payload `sole` para construtores de enum;
- [x] normalização canônica dos discriminantes de enum;
- [x] layout lógico `tag_only` vs `tagged_union`;
- [x] plano backend-neutral separado de `tag_storage` e `payload_storage`;
- [ ] ABI física final de tagged union;
- [ ] lowering C11 completo de enum com payload;
- [ ] cleanup/destruição de payload `sole` armazenado em enum;
- [ ] teste end-to-end de enum com payload até backend/binário.
- [x] teste end-to-end do subconjunto escalar de enum com payload a partir de fixture `.sotlas`, emitindo C11 e executando binário; payloads não escalares e cleanup `sole` seguem pendentes.

**Nota de certificação:** esta fase está certificada como núcleo semântico isolado. Isso não equivale a afirmar que todo o compilador, SIR, backend, stdlib e todas as features documentadas estão `SUPPORTED`.

### 2. Ownership Domains — 🟡 EM CONSTRUÇÃO

**Progresso aproximado atual: ~84%.**

**Desenvolvimento geral aproximado da linguagem: ~17%.** Esse índice é uma leitura agregada conservadora das fases do roadmap e não representa promoção global para `SUPPORTED`.

> Este percentual é calculado por macroentregas, não por número de subchecks. O trabalho avançado em `shared`/ARC não substitui os domínios ainda ausentes (`region`, `device`, `external`, `island`, `whisper`, `direct`, `handover`, `quarantine`) nem runtime/backend e testes end-to-end por domínio.

`exclusive`, `shared`, `region`, `device`, `external`.

Fundação já implementada:

- [x] ownership exclusivo básico por meio de `sole`;
- [x] move invalida a origem;
- [x] use-after-move é rejeitado;
- [x] joins de branch produzem estado conservador `MAYBE_MOVED`;
- [x] transferência de ownership em argumentos `sole`;
- [x] transferência de ownership em retornos `sole`;
- [x] transferência para campos `sole` de structs;
- [x] transferência para payload `sole` de enums;
- [x] cleanup/deinit possui integração parcial com transferências `sole` no backend existente.
- [x] grafo backend-neutral de Ownership Domains registra owner, tipo, domínio, estado final e sink das transferências; transições cross-domain de quarantine/handover preservam source domain, target domain e domínio do destino sem inferência pelo backend; pontos duplicados ou compartilhados entre movimento, `share`, `handover` e `quarantine`, destinos incompletos/incompatíveis e resultados inconsistentes de merge falham fechado.

Ainda necessário para concluir a Fase 2 canônica:

- [x] `exclusive` formalizado como Ownership Domain explícito no Typed AST: declarações `sole`, parâmetros, retornos, bindings e summaries preservam o domínio canônico;
- [ ] `shared` end-to-end como domínio de ownership com custo e estratégia observáveis; sintaxe/frontend, accounting/SIR e lowering C11 experimental existem, incluindo drop glue recursivo testado para árvores de campos `sole` por valor através de wrappers e arrays fixos multidimensionais, com deinit do owner antes dos campos; owner compartilhado recebido por parâmetro agora libera aliases no fallthrough da saída da própria função, depois dos `defer`, validado por execução nativa; escopos internos com owner externo continuam fail-closed, e backend/runtime ainda cobrem apenas subconjuntos com os contratos amplos de CFG/ABI pendentes;
- [x] contrato semântico backend-neutral de `co-owned`/ARC com contador forte explícito, retain/release determinísticos e destruição elegível quando strong_refs chega a zero;
- [ ] integração completa desse accounting com aliases reais, cleanup, Typed AST, lowering canônico e runtime/backend; o release C11 experimental já libera recursivamente campos `sole` por valor em payloads compartilhados testados;
- [ ] `region` como domínio de lifetime/ownership verificável; parser/Typed AST e graph preservam owners `sole` por valor, moves, merges invariantes, retornos, handovers same-domain e borrows call-scoped por `direct`/`whisper`; C11 executa análise canônica, rearma drop glue no destino de handover e testes nativos confirmam drop único, inclusive em handovers nos dois ramos exclusivos com early return, além de cleanup recursivo de campos, arrays fixos e wrappers POD comuns contendo owners `region` `sole`, inclusive wrappers locais, em ordem reversa; `defer` vem antes do drop em early return e fallthrough e locals são destruídos em `continue`/`break` (deinit detached do owner antes dos filhos); deinit de wrapper que acessa `self` com filhos region-owned falha fechado. Arena/lifetime graph e validação ampla de escapes ainda faltam;
- [ ] `device` como transferencia de ownership CPU ? dispositivo com completion/reacquisition; parser/Typed AST e graph preservam owners, moves, merges same-domain e handover explicito exclusive->device; o pipeline SIR posiciona esses handovers em ramos apos chamadas consumidoras tipadas; leitura de campos, escapes de endereco e borrows host sao rejeitados; transferencia real, completion, sincronizacao, reacquisition e runtime continuam pendentes;
- [ ] `external` como ownership/lifetime em FFI e recursos externos; parser/Typed AST e graph preservam owners sole, transferencias same-domain e consumo FFI; C11 suporta owners sole `repr(C)` e wrappers `sole repr(C)` com campos `external` diretos, arrays fixos multidimensionais de handles e escalares POD por valor via declaracao @extern(C) sem corpo, exigindo consumo exatamente uma vez em todos os caminhos; testes nativos cobrem wrapper, ramos aninhados e falha para saida sem consumo/layout com ponteiro; globals, classes/enums, arrays dinamicos, retornos, transferencias opacas, ABI geral de handles, lifetime e runtime seguem pendentes;
- [ ] `island` como subgrafo/região de ownership isolado — além de `quarantine`, `island T` é preservado nas fronteiras funcionais, locais e campos suportados; C11 cobre por valor parâmetros/retornos e campos `sole` com payload POD recursivo. Borrows `whisper` e `direct` call-scoped de `island` com no-escape provado chegam ao graph/SIR/LLVM e executam em C11; LLVM cobre o subset POD linear. Handover `ISLAND→ISLAND` repõe cleanup no destino. Aliases armazenados, globals, enum/classes fora do subset e runtime de aliases continuam pendentes;
- [ ] `whisper` como referência non-owning/weak com validação de lifetime; parâmetros internos com no-escape provado baixam no C11 como `const T *` e passam execução nativa para leitura escalar; borrows de owners `exclusive/shared/island/region/direct` chegam ao graph/SIR/LLVM; forwarding `direct → whisper` exige summary no-escape e passou execução C11/LLVM; storage, retorno, FFI e invalidação weak seguem fail-closed;
- [ ] `direct` como acesso SRG de baixo nível com obrigações explícitas; o contrato canônico aceita `direct T` apenas em parâmetros como acesso imutável limitado à chamada, exige `&binding` para owner LIVE `exclusive/shared/region/island` e registra `direct@L:C` em graph e `DirectAccessInst` em SIR; forwarding `direct → direct` e para `whisper` com no-escape preserva a origem e passou execução C11/LLVM, sem bookkeeping; borrows por argumento e receiver de método sobre owner `island` passam graph/SIR e execução C11, e o borrow por argumento passou LLVM até objeto no subset POD linear. `defer inspect(&shared_alias)` preserva o borrow no graph→SIR e coloca a chamada antes dos releases em cada early return; C11 executa defer com `direct`, `whisper` no-escape e argumentos escalares antes do drop. Retorno, campo/global e FFI opaca seguem fail-closed; ABI ARC LLVM, payloads/destrutores gerais, lifetime CFG geral, mutabilidade, alias graph e e2e amplo ainda faltam;
- [x] lowering backend-neutral de `quarantine`/`handover` para SIR por meio de `OwnershipDomainTransferInst`, preservando origem/destino e rejeitando fatos incompletos antes de qualquer backend;
- [x] ponte module-level `OwnershipModuleAnalysis → OwnershipModuleSIRPlan`, gerando plano por função que compõe domain transfers e shared/ARC sem placement CFG nem backend;
- [x] pipeline público `analyze_source_phase1` / `analyze_module_phase1` agora compõe automaticamente o snapshot semântico com `OwnershipModuleSIRPlan` em `Phase1CheckedModule`, mantendo Typed AST sem dependência direta de SIR;
- [x] placement SIR de `quarantine`/`handover`: além do subset linear, o generator emite markers source-stable em ramos estruturados com folhas de transferência seguidas de `return`; o plano semântico substitui os pontos nos blocos corretos após validar operação/origem/destino;
- [x] aplicação module-level transacional dos domain transfers: todos os planos por função são pré-validados contra o `SIRModule` antes da primeira mutação, com falha fechada para função/plano duplicado, função ausente ou marker incompatível;
- [x] placement ownership module-level unificado: domain transfers, `ShareInst`/`RetainInst` e cleanups ARC posicionáveis (return/break/continue/backedge) são pré-validados antes da primeira mutação; `share` usa identidade source-stable `share@L:C` comum ao par share/retain;
- [x] ponte pública SIR pós-check sem acoplamento reverso: `generate_checked_ownership_sir` consome o contrato `parsed_module + ownership_sir`, gera o `SIRModule` e aplica o placement ownership transacional em uma única operação;
- [x] `OwnershipDomainGraph` passou a ser a fonte canônica do lowering SIR de `quarantine`/`handover`; traces permanecem responsáveis pelo plano shared/ARC, eliminando revalidação concorrente de domínio no pipeline público;
- [x] identidade source-stable de domain transfer propagada end-to-end: eventos → `OwnershipDomainGraph` → `OwnershipDomainTransferInst`; placement usa `quarantine@L:C`/`handover@L:C` exatos em vez de depender da ordem dos markers;
- [x] placement de `share`/`retain` também usa identidade canônica `share@L:C` por lookup exato, rejeitando pontos ausentes/duplicados antes de qualquer mutação e sem depender da ordem do CFG;
- [x] cleanup ARC de scope normal (`function_exit`) possui placement real no único retorno sintético de fallthrough representável; explicit returns continuam usando cleanup source-stable próprio e múltiplos fallthrough returns são rejeitados fail-closed;
- [x] cleanup `function_exit` e cleanup de return explícito são colocados juntos quando ambos os caminhos existem, mantendo cada plano no retorno correspondente;
- [x] `OwnershipDomainGraph` materializa também o lado shared: transições canônicas EXCLUSIVE→SHARED e contas ARC function-scoped com owners, strong_refs e identidade `share@L:C`, rejeitando retain órfão/inconsistente;
- [x] lowering SIR de `share`/`retain` é dirigido pelas contas/transições do `OwnershipDomainGraph`; o trace fica restrito às obrigações path-sensitive de cleanup/defer, e divergências graph↔trace falham antes do placement;
- [x] primeiro contrato canônico de `whisper`: parâmetro `whisper T` é congelado no Typed AST como borrow imutável non-owning, não consome `sole` nem entra no OwnershipEnv como owner; storage/return/lifetime graph/runtime permanecem fail-closed;
- [x] calls e receivers diretos de parâmetros `whisper` registram borrows source-stable no Ownership Domain Graph; `exclusive/shared` LIVE são preservados sem move, `island` e formas indiretas são rejeitados, e o fato chega ao plano SIR como `WhisperBorrowInst` sem claim de lowering/runtime;
- [x] escape checks locais rejeitam retorno de referências derivadas por membro/cast, casts que apagam a forma de ponteiro, aliases retornados e encaminhamento sem contrato; leituras escalares seguem permitidas;
- [x] checker de produção prova summaries no-escape em ponto fixo para parâmetros por referência/ponteiro de funções com corpo; o maior ponto fixo admite ciclos recursivos fechados e remove candidatos cujo corpo ou dependências escapam; aliases `whisper` só podem ser encaminhados a parâmetros com summary verificado, inclusive em chamadas registradas por `defer`; extern, chamada indireta e ciclos com caminhos escapantes permanecem fail-closed;
- [x] Ownership Domain Graph e SIR preservam encaminhamento de parâmetro `whisper` para outro parâmetro `whisper` como borrow source-stable cujo source domain continua `whisper`; compilação e execução C11 validam encaminhamento em cadeia linear e em funções mutuamente recursivas provadas no-escape;
- [x] forwarding de `direct` para parâmetro `whisper` com summary no-escape preserva source domain `direct` no graph/SIR e passou execução nativa C11 e lowering LLVM até objeto;
- [x] backend C11 baixa parâmetros e receivers de método `whisper` internos com lifetime/no-escape verificados como `const T *`; leitura escalar foi compilada com warnings-as-errors e executada nativamente, enquanto storage, retorno e FFI continuam rejeitados;
- [ ] lifetime/weak invalidation em CFG e validação backend/runtime para `whisper` seguem pendentes;
- [ ] `handover` como operação formal de transferência entre bindings/domínios — contratos EXCLUSIVE → EXCLUSIVE, ISLAND → EXCLUSIVE e ISLAND → ISLAND preservam origem/destino no graph; C11 baixa bindings validados, suprime cleanup da origem e rearma cleanup/deinit no destino, com execução nativa confirmando uma destruição por owner. Handover sem destino continua fail-closed; outros domínios e e2e completo ainda faltam;
- [ ] `quarantine` como isolamento verificável antes de reuse/dispatch — `quarantine <binding>;` implementa EXCLUSIVE → ISLAND, exige source LIVE direto, bloqueia escape/move implícito, registra graph e C11 o baixa como transição estática sem custo de runtime; o gate de produção rejeita usos posteriores de aliases locais rastreáveis, inclusive os propagados para campos, falha fechado se aliases forem enviados a chamadas opacas ou armazenados fora do escopo, aceita aliases mortos antes da transição e distingue usos em ramos mutuamente exclusivos; teste C11 executa o ramo de quarantine e o ramo oposto que lê o alias, verificando destruição nos dois caminhos; joins ambíguos e loops com aliases do owner continuam conservadores; weak invalidation/runtime, CFG path-sensitive geral, reuse/dispatch e e2e amplo ainda faltam;
- [x] grafo canônico de ownership/domains no snapshot semântico para owners rastreados e transferências, incluindo direção explícita EXCLUSIVE→ISLAND e ISLAND→EXCLUSIVE e validação fail-closed de fatos incompletos, tipo/domínio de destino, resultado de merge, source points duplicados e colisões entre movimento, share e transições;
- [x] merge de Ownership Domain em branches exige domínio idêntico e registra LIVE/MOVED/MAYBE_MOVED no grafo;
- [x] contrato semântico backend-neutral para planejar `exclusive → shared` via `share`, exigindo owner LIVE e sem mutação/runtime implícito;
- [x] aplicação semântica de `exclusive → shared` no OwnershipEnv, preservando owner original como strong owner compartilhado;
- [x] criação explícita de alias strong compartilhado com incremento determinístico do reference accounting;
- [x] integração backend-neutral com Typed AST por meio de `TypedShareExpression` para bindings inteiros;
- [x] membros, índices e temporários continuam fail-closed até existir contrato formal de aliasing parcial;
- [x] sintaxe pública `let alias = share owner;` com nó AST dedicado, typecheck e integração ao OwnershipEnv;
- [x] backend C11 tem lowering experimental para aliases locais múltiplos e imutáveis, com preflight graph/trace canônico, retain por alias e cleanup reverso; leituras de aliases externos em `if`/loops/`unsafe` possuem cleanup nativo em retornos, `break` e `continue`, e `if/else` terminal é aceito quando ambos os ramos retornam; shares locais com fallthrough/retorno limpam no escopo criador, inclusive em `for`/`while`/`loop`, em cada backedge normal e antes de `break`, `continue` e `return` aninhados; share de owner recebido por parâmetro também limpa no fallthrough da saída da função, com `defer` LIFO antes do release, validado por execução nativa. `defer` local no backedge continua fail-closed. O release final executa drop glue recursivo em ordem reversa para campos `sole` por valor através de wrappers e arrays multidimensionais, chamando hooks detached de owner/wrapper antes dos deinits de folhas; owners externos em blocos internos com fallthrough, hooks de deinit com descendentes owned que referenciam `self`, mutação/escape, CFG arbitrário e payloads com ponteiros continuam fail-closed;
- [x] C11 compila/executa aliases `shared` com payload escalar e struct POD aninhada sem ownership; cleanup recursivo para campos `sole/co-owned`, payloads gerais e CFG ainda permanece bloqueado;
- [x] plano semântico de cleanup para saída normal de função, com release reverso e destroy apenas no último strong owner;
- [x] cleanup path-sensitive de shared ownership em early-return e branches, sem contaminar o caminho de fallthrough;
- [x] integração semântica de shared ownership com `defer`: captura shared preserva LIVE, defers rodam em LIFO antes dos releases ARC e `sole` continua exigindo transferência;
- [x] C11 executa `defer receiver.readonly_method(scalar)` e bloco com uma chamada equivalente para alias local `shared` antes dos releases ARC em early return, `break` e `continue`, quando o método é interno, recebe `&self` imutável e o argumento não captura o alias shared; leitura do alias como argumento continua fail-closed;
- [x] C11 executa `defer internal_direct(&shared_alias, &shared_alias, scalar)` com parâmetros `direct`, `whisper` no-escape e escalares em cleanup paths de early return, continue e break, antes do release/destroy ARC e sem release duplicado; teste nativo cobre valor calculado por iteração e leitura pelo borrow `whisper`; o frontend rejeita a variante que escapa o argumento `whisper`, e receiver `direct` continua fail-closed;
- [ ] integração com runtime/backend;
- [x] moves e merges invariantes same-domain para `region/device/external` são validados no Ownership Domain Graph; handovers explícitos same-domain chegam ao SIR e cruzamentos implícitos são rejeitados;
- [ ] runtimes e protocolos de lifetime para `region`, transferência/completion CPU-device e ownership FFI para `external`;
- [x] loops exigem invariância de tipo, Ownership Domain e VarState no backedge para bindings visíveis;
- [x] contas shared criadas inteiramente dentro da iteração recebem cleanup determinístico antes do backedge;
- [x] break/continue possuem cleanup path-specific para shared locals, inclusive em branches aninhados, com defers LIFO antes dos releases e sem duplicar cleanup de backedge;
- [x] caminhos condicionais de break/continue são separados do fallthrough: um salto em um ramo não suprime o cleanup do backedge normal do outro ramo;
- [x] snapshots de OwnershipEnv em exits de loop preservam a validação de invariância sem contaminar o ambiente de fallthrough;
- [ ] integração completa com `defer`, cleanup e unwind/early-return de todos os recursos;
- [x] identidade source-stable de registros `defer` é preservada separadamente da identidade do control-exit, preparando lowering executável sem apagar payload;
- [x] `defer Name;` sobre owner shared possui operação SIR explícita (`DeferUseInst`) e placement antes de ARC em fallthrough, break/continue e early returns source-identified; defers registrados somente em um ramo não contaminam outros retornos;
- [x] payloads de chamadas diferidas validados semanticamente geram `CallInst` antes do ARC em break/continue e no fallthrough normal; `defer inspect(&shared_alias)` também chega por graph→SIR antes dos releases em cada early return estruturado, preservando `defer@L:C` e o `DirectAccessInst` source-stable. Transferência implícita `shared → sole` e formatos assign/try permanecem fail-closed;
- [x] `defer receiver.method(named_args)` gera `CallInst` com receiver e argumentos nomeados, preservando `defer@L:C` em break/continue e nos early returns estruturados suportados;
- [x] um bloco `defer { call(named_args); }` com exatamente uma chamada direta ou de método e bindings diretos preserva o payload e baixa para `CallInst` source-stable em break/continue e em cada early return;
- [ ] argumentos que recapturam aliases shared, argumentos complexos em `defer method`, blocos com múltiplas instruções e formatos assign/try permanecem fail-closed até payload tipado/lowering dedicado;
- [x] defer shared em fallthrough de bloco condicional/unsafe e backedge de loop sem placement lexical próprio é rejeitado fail-closed; defer branch-local nunca é anexado ao cleanup normal da função;
- [x] primeiro lowering backend-neutral de shared ownership para plano SIR explícito (`share/retain/release/destroy`), ainda sem placement CFG;
- [x] identidade source-stable para pontos de cleanup ownership em return/break/continue/backedge, preservada no plano SIR;
- [x] placement real de cleanup ARC imediatamente antes de `ReturnInst` identificado por `point_id`, com erro para pontos ausentes/duplicados;
- [x] gerador SIR protótipo preserva `point_id` em return terminal linear diretamente representável, sem fabricar CFG para retornos aninhados;
- [x] primeiro CFG estruturado para funções `void` com `if` booleano simples e retornos diretos, preservando `point_id` distinto por caminho;
- [x] sequência de `if` com condições booleanas de parâmetros e retornos antecipados diretos, seguida de retorno final, gera saídas e identidades `return@L:C` distintas no CFG, com placement ARC de release/destroy em cada saída;
- [x] comparações `==`, `!=`, `<`, `<=`, `>` e `>=` entre parâmetros inteiros baixam para `CompareInst` antes da aresta condicional; LLVM emite `icmp` signed/unsigned e o teste fonte→objeto compila; literais e expressões condicionais fora do subset permanecem rejeitados;
- [x] condições `!param` em `if` e `while` invertem as arestas de controle usando o valor SSA existente, mantendo IDs source-stable e placement de cleanup;
- [x] expressões booleanas `&&`/`||` sobre parâmetros e `!` baixam com curto-circuito em blocos SIR, preservando os destinos de return/break/continue e cleanup;
- [x] literais `true`/`false` em condições de `if`/`while` geram arestas SIR incondicionais ao destino escolhido, sem valor SSA fictício;
- [ ] expandir CFG estruturado além desse subset protótipo; produção baixa árvores aninhadas `if/else` com folhas `return` void, `return if` escalar com valores de parâmetros via `phi`, condições booleanas/comparações inteiras e markers de `share`/`quarantine`/`handover` nos blocos de origem, além de cleanup ARC em cada folha; joins de valores calculados, corpos arbitrários, integração geral de cleanup e demais terminadores ainda faltam;
- [x] integração direta `OwnershipTrace → plano SIR → placement` para retornos identificados, inclusive no CFG estruturado inicial de `if`;
- [x] placement ARC para `break`/`continue` em `BranchInst` source-identified, com validação fail-closed;
- [x] SIRGenerator emite CFG mínimo de `while` com `break`/`continue` source-identified e compatível com placement ARC;
- [x] identidade e placement ARC do backedge normal de `while`, distintos de `continue`;
- [x] placement ARC de return/break/continue/backedge é transacional: todos os pontos CFG são validados antes de qualquer mutação, inclusive no apply integrado;
- [ ] backend C11 correspondente ou rejeição explícita por domínio;
- [ ] testes positivos, negativos e end-to-end para cada domínio;
- [ ] promoção individual para `SUPPORTED` apenas após o gate completo.

### 3. Authority Domains

Capabilities e `@system`.

### 4. State Spaces

`space`, typestate e transitions.

### 5. Effects

Effect inference e restrições contextuais.

### 6. Flow

Dependency graph, structured concurrency e cancellation.

### 7. Execution Domains

CPU/SIMD inicialmente.

Esta fase também prepara o caminho para o backend nativo próprio:

- [x] modelo canônico tipado de targets x86-64/AArch64, ABI identificada, largura de ponteiro e endianness;
- [x] registro limitado de features x86-64/AArch64 validado por arquitetura, dependências normalizadas e encaminhamento para LLVM/Clang;
- [ ] contratos de calling convention independentes do C;
- [ ] representação explícita de registradores especiais, stack e ABI quando exigidos por `@system`;
- [ ] lowering de SIMD/intrinsics para operações alvo-específicas sem depender semanticamente de builtins C;
- [ ] regras de clobber, volatilidade, alinhamento e preservação de registradores;
- [ ] capacidade de declarar que uma operação só existe em determinados targets/features;
- [ ] testes diferenciais entre backend C11 de referência e lowering nativo para semânticas equivalentes;
- [ ] layout/ABI AArch64 certificado, intrinsics SIMD Sotlas e dispatch multi-versionado.

### 8. Heterogeneous Compute

GPU depois; NPU somente quando houver backend real.

O backend nativo de CPU é pré-requisito arquitetural para esta fase, mas não implica que GPU/NPU usem o mesmo instruction selector. Cada Execution Domain deverá possuir lowering próprio sob a mesma semântica de Typed AST/SIR.

### 9. Trust Domains

`trusted`, `unsafe`, `foreign`, `isolated`.

O efeito `ffi` distingue chamadas que cruzam `extern "C"` das demais chamadas
desconhecidas no summary de Effects. Isso registra a fronteira estrangeira no
SIR para contratos de backend; não fornece sandboxing nem prova isolamento.

### 10. Guarantees

`requires`, `ensures`, `guarantee`, proof reports.

O frontend inicial aceita `requires` booleano em funções com corpo e prova
chamadas quando todos os argumentos são constantes avaliáveis. Condições falsas
são rejeitadas estaticamente; condições sem prova estática são guardadas no
entry da função C11 com `abort()` se falharem. O comprovante source-stable e a
precondição seguem para o SIR; refinamento simbólico, `ensures` e declarações
`guarantee` seguem abertos.

### 11. Causality

`why`, `explain`, provenance.

### 12. Counterfactuals

`whatif`.

O primeiro subset de Counterfactuals consulta o impacto de uma stage marcada
como indisponível em um Flow tipado ou em seu plano canônico no SIR. A análise
propaga a indisponibilidade aos consumidores transitivos, preserva stages
independentes na ordem fonte e valida dependências e cronograma antes de
responder. Ela não executa funções nem simula efeitos, estado ou recuperação.
API: `analyze_sir_flow_stage_unavailability(module, flow, stage)`.

A primeira base de Transactions fornece uma auditoria estática dos efeitos de
um Flow SIR. Cada efeito precisa de uma política explícita: `reversible`,
`compensatable` ou `irreversible`; políticas ausentes, efeitos irreversíveis
e compensações sem função handler no SIR impedem a política declarada de
rollback de ser considerada satisfeita. Isso não comprova que um handler
reverte o efeito. A auditoria não executa handlers nem implementa snapshots,
inversas ou rollback. API: `analyze_sir_flow_transaction_effects(module,
flow, policies, handlers)`.

### 13. Transactions

`change`, rollback e compensations.

### 14. Intent

Planejamento declarativo sobre todas as fundações anteriores.

### 15. SIR completo

Representação integrada de Domains + Flow + Effects + Ownership + Causality.

O subset inicial de Flow já preserva no `SIRModule` um plano declarativo
reconciliado com assinaturas e summaries de efeitos. Chamadas executáveis no
CFG, integração de Ownership e execução pelo scheduler continuam pendentes.
O `SIRModule` também preserva comprovantes de chamadas que satisfizeram
precondições constantes verificadas pelo frontend.

Esta fase deve congelar a fronteira semântica que permite substituir C como transporte sem alterar a linguagem:

- [ ] todos os corpos e construções `SUPPORTED` representáveis no SIR;
- [ ] layouts, ownership, cleanup, effects e authority preservados antes do target lowering;
- [ ] operações target-independent separadas de intrinsics target-specific;
- [ ] ABI source-level não dependente de detalhes acidentais do backend C11;
- [ ] contratos verificáveis de entrada/saída para o target lowering;
- [ ] passes do SIR incapazes de apagar obrigações de safety/cleanup;
- [ ] serialização/inspeção suficiente para testar o SIR como fronteira estável.

### 16. Native Machine Backend — SOTLAS COMO CAMADA DE MÁQUINA

Objetivo arquitetural:

```text
Sotlas
  ↓
Typed AST / Sema
  ↓
SIR
  ↓
Target Lowering
  ↓
Machine/Object Code
  │
  └── opcional: --emit=asm
```

C11 permanece backend de bootstrap, referência, portabilidade e differential testing. Ele **não** é dependência semântica permanente da Sotlas.

Primeiro alvo recomendado: um backend nativo completo para uma arquitetura/ABI definida, antes de multiplicar targets.

Checklist:

- [ ] Target IR/lowering explícito após o SIR;
- [ ] definição de calling convention e ABI lowering;
- [ ] lowering de parâmetros, retornos, aggregates e tagged unions;
- [ ] stack-frame layout;
- [ ] lowering de loads/stores, branches, calls e arithmetic;
- [ ] instruction selection;
- [ ] representação de virtual registers;
- [ ] register allocation;
- [ ] spill/reload;
- [ ] callee-saved/caller-saved handling;
- [ ] prologue/epilogue;
- [ ] lowering nativo de `@system`, MMIO, atomics, interrupts e context switch onde suportado;
- [ ] relocations e symbol table;
- [ ] emissão de object code relocável;
- [ ] primeiro object format oficialmente suportado;
- [ ] linker integration sem depender de C como linguagem intermediária;
- [ ] `--emit=asm` como saída de inspeção produzida pelo próprio backend;
- [ ] `--emit=obj`/equivalente produzindo objeto nativo;
- [ ] testes golden de instruction selection;
- [ ] testes ABI contra código externo;
- [ ] differential testing contra C11 quando semanticamente aplicável;
- [ ] testes end-to-end de executáveis/bare-metal produzidos sem C intermediário;
- [ ] diagnóstico fail-closed para operações ainda não suportadas pelo target;
- [ ] debug/source mapping e unwind metadata nas fases de maturação do backend;
- [ ] segundo target somente após o primeiro backend demonstrar arquitetura reutilizável.

A meta não é transformar Sotlas em sintaxe de assembly. A meta é permitir que a mesma linguagem cubra kernel, bootloader, drivers, MMIO, interrupções, SIMD, context switch e runtime, enquanto também permanece adequada a engines, jogos, IA/HPC, desktop, servidores e aplicações.

Exemplo de destino arquitetural:

```sotlas
@system
fn reload_cr3(table: *rawphys PageTable) {
    ...
}
```

deve poder seguir conceitualmente:

```text
Sotlas
→ SIR
→ x86_64 target lowering
→ instruções x86-64
```

sem precisar virar C no caminho.

### 17. Tooling avançado

Flow View, Domain View, State View, Authority View, Causal Debugger e Safety Explorer.

Inclui também tooling específico do backend nativo:

- [ ] inspeção de SIR;
- [ ] inspeção do Target IR/lowering;
- [ ] `--emit=asm`;
- [ ] dump de register allocation;
- [ ] visualização de stack frames/ABI;
- [ ] source-to-instruction mapping;
- [ ] explicação de por que determinada instrução/lowering foi selecionada.

---

## A PERGUNTA QUE DEVE GUIAR O PROJETO

Não:

> “Que feature podemos adicionar à Sotlas?”

Mas:

> **“Que informação sobre um programa os compiladores atuais normalmente não conseguem representar de forma integrada, e o que podemos fazer quando essa informação passa a existir?”**

Essa pergunta deverá orientar a evolução da Sotlas.
