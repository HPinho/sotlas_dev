# Sotlas — Especificação Semântica Formal

> **Versão:** 0.5.1 · **Status:** Rascunho Normativo
> Esta especificação documenta os contratos semânticos que o compilador Sotlas
> verifica em tempo de compilação. É o documento de referência para desenvolvedores
> de ferramentas, contribuidores do compilador e autores de bibliotecas.

---

## 1. Módulos e Escopos

### 1.1 Estrutura de Módulo

Todo arquivo Sotlas começa com uma declaração de módulo:

```
[ TargetDeclaration ]
ModuleDeclaration
{ ImportDeclaration }
{ TopLevelDeclaration }
```

`TargetDeclaration` seleciona o perfil de compilação:
- `barecore;` — freestanding: firmware, kernel, drivers. Sem ARC, sem alocação dinâmica.
- `target native;` — aplicação hospedada no SO. ARC disponível.
- `target web;` — compilado para WebAssembly.

**Regra:** O perfil `barecore` ativa um conjunto de restrições verificadas estaticamente (ver §5).

### 1.2 Resolução de Símbolos

A resolução de símbolos é feita em duas passagens:

1. **Passagem 1** — coleta todos os símbolos de topo de escopo (structs, classes, funções, constantes, specs, enums, registradores, aliases de tipo).
2. **Passagem 2** — verifica corpos de funções, resolvendo referências contra o escopo global + escopos locais aninhados.

**Regra:** Um símbolo deve ser declarado antes de ser referenciado em expressões. A exceção são declarações de topo de escopo mutuamente recursivas, que são visíveis entre si após a Passagem 1.

---

## 2. Sistema de Tipos

### 2.1 Tipos Primitivos

| Sotlas     | C equivalente  | Bits | Sinal     |
|------------|---------------|------|-----------|
| `Bool`     | `_Bool`        | 1    | —         |
| `UInt8`    | `uint8_t`      | 8    | unsigned  |
| `Int8`     | `int8_t`       | 8    | signed    |
| `UInt16`   | `uint16_t`     | 16   | unsigned  |
| `Int16`    | `int16_t`      | 16   | signed    |
| `UInt32`   | `uint32_t`     | 32   | unsigned  |
| `Int32`    | `int32_t`      | 32   | signed    |
| `UInt64`   | `uint64_t`     | 64   | unsigned  |
| `Int64`    | `int64_t`      | 64   | signed    |
| `USize`    | `size_t`       | 64   | unsigned  |
| `ISize`    | `intptr_t`     | 64   | signed    |
| `Float32`  | `float`        | 32   | —         |
| `Float64`  | `double`       | 64   | —         |
| `Char`     | `uint32_t`     | 32   | Unicode   |
| `Void`     | `void`         | —    | —         |

**Tipos SIMD nativos:**
`f32x4`, `f32x8`, `f64x2`, `f64x4`, `u8x16`, `u8x32`, `i32x4`, `i32x8`, `i64x2`, `i64x4`

### 2.2 Tipos Compostos

- **`struct`** — tipo por valor, copiável por padrão (exceto `sole struct`).
- **`class`** — tipo por referência com herança e ARC (proibido em `barecore`).
- **`mesh`** — estrutura de dados segura para composição de múltiplos traits.
- **`enum`** — tipo soma discriminado com variantes.
- **`spec`** — protocolo/interface (equivalente a trait).
- **`register`** — tipo de registro de hardware com campos de bits.

### 2.3 Tipos com Limites (Bounded Types)

```sotlas
let safe_idx: UInt32.bound[0..255] = value;
```

O compilador verifica estaticamente que o valor inicial satisfaz o limite. Verificações em runtime são geradas para atribuições não constantes.

### 2.4 Tipos Genéricos (`forge`)

```sotlas
struct Container forge<T> { pub item: T; }
fn wrap forge<T>(val: T) -> Container forge<T> { ... }
```

**Regras:**
- Parâmetros de tipo são resolvidos no corpo da declaração que os contém.
- Bounds de spec (`forge<T: Hashable>`) são verificados no ponto de instanciação.
- Monomorphização é feita pelo codegen (não há type erasure).

---

## 3. Sistema de Ownership SRG (Scoped Reference Graph)

O SRG é o sistema de gerenciamento de memória e ownership de Sotlas. É verificado estaticamente, sem custo em runtime (exceto ARC para `co-owned`).

### 3.1 Modificadores de Ownership

| Modificador  | Semântica                                                       | Move? | Cópia? |
|-------------|------------------------------------------------------------------|-------|--------|
| (nenhum)    | Cópia por valor (primitivos e structs sem `sole`)               | Não   | Sim    |
| `sole`      | Propriedade exclusiva. Move na atribuição/chamada.              | Sim   | Não    |
| `co-owned`  | Referência contada (ARC). Compartilhamento seguro.              | Não   | Sim (ref) |
| `island`    | Isolamento total. Não pode cruzar fronteiras de thread/enclave. | Sim   | Não    |
| `whisper`   | Referência imutável emprestada. Não move, não modifica.         | Não   | Não    |
| `direct`    | Acesso direto a memória física (uso em barecore).               | Sim   | Não    |

### 3.2 Move Semantics

**Regra:** Quando uma variável `sole` é atribuída, passada por valor, ou transferida via `handover`, seu estado muda de `LIVE` para `MOVED`. Qualquer acesso posterior é um erro de compilação.

```sotlas
sole struct File { pub fd: Int32; }
fn close(f: sole File) -> Void { ... }

fn main() -> Void {
    let f = File { fd: 3 };
    close(f);        // move: f agora é MOVED
    let x = f.fd;   // ERRO: uso de 'f' após transferência
}
```

**Estados de variável no dataflow:**

| Estado          | Descrição                                              |
|----------------|--------------------------------------------------------|
| `LIVE`          | Variável está viva e pode ser usada                   |
| `MOVED`         | Variável foi transferida — uso é erro                 |
| `MAYBE_MOVED`   | Movida em um ramo de `if` sem `else` — uso é erro     |
| `BORROWED_IMMUT`| Emprestada imutavelmente (whisper) — modificação proibida |
| `BORROWED_MUT`  | Emprestada mutavelmente — segundo empréstimo proibido |

### 3.3 Move em Ramos Condicionais

```sotlas
fn main(cond: Bool) -> Void {
    let f = File { fd: 1 };
    if cond { close(f); }   // f é MAYBE_MOVED após o if
    let x = f;               // ERRO: f pode ter sido transferido
}
```

**Regra:** Se uma variável `sole` é movida em exatamente um ramo de um `if/else`, ela recebe estado `MAYBE_MOVED` no ponto de convergência. Uso posterior é erro.

**Regra:** Se movida em ambos os ramos, recebe estado `MOVED` no ponto de convergência.

### 3.4 Move em Laços

**Regra:** Mover uma variável `sole` dentro de um `while` ou `for` sem reinicializá-la a cada iteração é um erro de compilação. O compilador detecta que o recurso não pode ser recuperado na segunda iteração.

### 3.5 Instrução `handover`

`handover expr;` transfere explicitamente a propriedade de uma variável `sole`. É equivalente a um move, mas documentado explicitamente no código.

**Regra:** `handover` só pode ser aplicado a variáveis com tipo `sole`. Aplicar a tipos copiáveis é erro.

### 3.6 Instrução `quarantine`

`quarantine expr;` isola uma variável como `island`, impedindo que ela cruce fronteiras de thread ou enclave.

---

## 4. Topologia de Ponteiros

Sotlas classifica ponteiros por sua topologia física/virtual, permitindo ao compilador detectar conversões incorretas de endereços.

### 4.1 Qualificadores de Topologia

| Qualificador  | Descrição                                      | Uso Típico                     |
|--------------|------------------------------------------------|-------------------------------|
| `*rawphys`   | Ponteiro para endereço físico de hardware      | MMIO, DMA, acesso direto      |
| `*virtmap`   | Ponteiro para endereço virtual mapeado         | Memória mapeada via MMU       |
| `*portwire`  | Ponteiro para porta I/O (isolado de memória)   | `__inb`/`__outb` em x86      |
| `*dmazone`   | Ponteiro para região de DMA (coerência cache)  | Buffers de DMA                |
| `*voidzero`  | Ponteiro nulo tipado (mais seguro que null)    | Valores sentinela              |
| `*mut T`     | Ponteiro mutável regular                       | Uso geral                     |
| `*const T`   | Ponteiro imutável                              | Uso geral                     |

### 4.2 Regras de Compatibilidade de Topologia

**Regra:** Ponteiros de topologias diferentes **não podem ser atribuídos implicitamente entre si**. A conversão requer chamada explícita de função de tradução.

```sotlas
fn f(phys: *rawphys UInt32) -> Void {
    let virt: *virtmap UInt32 = phys; // ERRO: topologia incompatível (*rawphys → *virtmap)
}
```

**Conversões corretas:**
- `*rawphys` → `*virtmap`: via `mmu_map(phys_addr)` (função do kernel)
- `*virtmap` → `*rawphys`: via `virt_to_phys(virt_addr)`
- Qualquer → `*const`: conversão implícita permitida se topologia for compatível

---

## 5. Restrições do Perfil `barecore`

O perfil `barecore` é usado para código freestanding (kernel, firmware, drivers). O compilador ativa as seguintes verificações adicionais:

### 5.1 Construtos Proibidos em `barecore`

| Construto     | Motivo da Proibição                                   |
|--------------|------------------------------------------------------|
| `co-owned`   | Usa ARC (contagem de referência), implica alocação    |
| `class`      | Herança dinâmica com vtable, implica ponteiro de heap |
| `String`     | Tipo dinâmico com alocação                           |
| `Vec`        | Vetor dinâmico com alocação                          |
| `Box`        | Box pointer com alocação                             |
| `async/await`| Suspensão de coroutine requer alocador               |

### 5.2 Construtos Permitidos em `barecore`

`sole`, `direct`, `island`, `whisper`, `*rawphys`, `*virtmap`, `*portwire`, `*dmazone`, `[T; N]` (arrays fixos), `register`, `trapfn`, `emit` (asm inline), `clinch/revert`, `quench`.

---

## 6. Efeitos de Hardware

O compilador rastreia efeitos de hardware introduzidos por funções e os propaga para funções chamadoras.

### 6.1 Tabela de Efeitos

| Efeito      | Keyword/Construto que o introduz              | Proibido em     |
|------------|----------------------------------------------|----------------|
| `ALLOC`    | `co-owned`, `class`, `Vec`, alocação dinâmica | `irqfree`, `trapfn` |
| `BLOCKING` | Primitivas de sincronização bloqueantes       | `irqfree`, `trapfn` |
| `ASYNC`    | `await`, coroutines                           | `irqfree`, `trapfn` |
| `MMIO`     | Acesso via `*rawphys`, `emit` com I/O         | —              |
| `DMA`      | `*dmazone`, `dma_fence`, `dma_barrier`        | —              |
| `IRQ`      | Dentro de `trapfn`                            | —              |
| `UNSAFE`   | Bloco `unsafe { ... }`                        | —              |

### 6.2 Funções `irqfree`

Funções marcadas com `@irqfree` ou o qualificador `irqfree` **não podem** introduzir os efeitos `ALLOC`, `BLOCKING` ou `ASYNC`. O compilador verifica transitivamente — se uma função `irqfree` chama outra que introduz esses efeitos, é um erro de compilação.

### 6.3 Funções `trapfn` (Interrupt Service Routines)

`trapfn` é o equivalente a ISR (Interrupt Service Routine). São automaticamente `irqfree`, `@system`, e têm `irq` como efeito inicial. As mesmas proibições de `irqfree` se aplicam, com mensagens de erro específicas.

---

## 7. Seções Críticas de Hardware

### 7.1 `clinch { ... } revert { ... }`

Equivalente a try/catch para seções críticas de hardware:
- O corpo de `clinch` é executado com proteções de hardware ativas.
- O corpo de `revert` é executado se o `clinch` falhar (ex: violação de acesso).

### 7.2 `quench { ... }`

Desativa interrupções durante o bloco, garantindo atomicidade em nível de hardware.

### 7.3 `gate(cond) { ... }`

Executa o bloco apenas se `cond` for verdadeiro em tempo de runtime. Equivalente a um `if` com semântica de barreira de memória.

---

## 8. Segurança de Blocos `unsafe`

**Regra:** Operações com `asm inline` (`emit`), aritmética de ponteiro bruta e acesso a ponteiros `*rawphys` ou `*portwire` requerem estar dentro de um bloco `unsafe { ... }` ou em uma função marcada com `@system`.

```sotlas
fn safe_wrapper() -> Void {
    unsafe {
        emit("nop"); // permitido dentro de unsafe
    }
}

@system
fn kernel_op() -> Void {
    emit("hlt"); // permitido em @system sem bloco unsafe
}
```

**Regra:** Blocos `unsafe` podem ser aninhados. O contador de profundidade é rastreado pelo compilador. Sair de todos os níveis de `unsafe` restaura as verificações completas de segurança.

---

## 9. `comptime` — Avaliação em Tempo de Compilação

```sotlas
comptime {
    const CACHE_LINE: UInt32 = 64;
    const MAX_PROCS: UInt32 = 256;
}
```

**Regra:** Expressões dentro de `comptime` devem ser completamente determináveis em tempo de compilação. Não podem referenciar variáveis de runtime.

**Aplicações:** Cálculo de constantes, validação de tamanhos de estruturas, const-generics.

---

## 10. Spec (Protocolos / Traits)

### 10.1 Definição

```sotlas
spec Hashable {
    fn hash() -> UInt64;
}
```

### 10.2 Implementação

```sotlas
struct Key adopts Hashable {
    pub value: UInt64;
    fn hash() -> UInt64 { return self.value; }
}
```

### 10.3 Bounds em Generics

```sotlas
fn hash_it forge<T: Hashable>(item: T) -> UInt64 {
    return item.hash();
}
```

**Regra:** Quando um tipo concreto é usado como argumento genérico com bound `forge<T: SomeSpec>`, o compilador verifica que o tipo declara `adopts SomeSpec`. Se não, é um erro de compilação.

---

## 11. Discern — Pattern Matching Exaustivo

```sotlas
enum Status { Ok, Err, Pending }
fn handle(s: Status) -> Void {
    discern s {
        Ok    => { ... }
        Err   => { ... }
        // ERRO: 'Pending' não coberto, sem wildcard
    }
}
```

**Regra:** `discern` sobre um `enum` é **exaustivo**: todas as variantes devem ser cobertas, ou um wildcard `_` deve ser fornecido. Variantes faltantes são reportadas como erro de compilação.

---

## 12. Escopo de Retorno e Escape de Referências

**Regra:** Referências (`&x`, `whisper x`) a variáveis locais de pilha **não podem escapar** do escopo da função via `return`. O compilador detecta escapes de referências de pilha.

```sotlas
fn leak() -> *mut UInt32 {
    let x: UInt32 = 42;
    return &x; // ERRO: referência a variável local 'x' não pode escapar
}
```

---

## 13. Sumário de Códigos de Erro

| Código   | Descrição                                                         |
|---------|------------------------------------------------------------------|
| `E0001` | Símbolo não declarado                                            |
| `E0002` | Tipo não declarado                                               |
| `E0100` | Topologia de ponteiro incompatível                               |
| `E0200` | Uso de variável `sole` após transferência (use-after-move)       |
| `E0201` | `handover` aplicado a tipo não-`sole`                            |
| `E0202` | Variável `sole` movida dentro de laço sem reinicialização        |
| `E0300` | Construto proibido em módulo `barecore`                          |
| `E0400` | Spec bound não satisfeito pelo tipo concreto                     |
| `E0500` | `discern` não exaustivo: variantes não cobertas                  |
| `E0600` | Referência a variável local escapando do escopo via `return`     |
| `E0700` | Assembly inline fora de contexto `unsafe` ou `@system`           |
| `E0712` | Efeito `ALLOC` proibido em contexto `irqfree`/`trapfn`          |
| `E0713` | Efeito `BLOCKING` proibido em contexto `irqfree`/`trapfn`       |
| `E0714` | Efeito `ASYNC` proibido em contexto `irqfree`/`trapfn`          |
