# O que o Compilador Sotlas Garante em Tempo de Compilação

> Este documento descreve as **propriedades de segurança verificadas estaticamente**
> pelo compilador Sotlas. Cada garantia listada aqui é aplicada em tempo de compilação —
> se uma dessas regras for violada, o código não compila.

---

## Sumário das Garantias

| Garantia | Verificação | Análoga em |
|---|---|---|
| Sem uso após liberação (use-after-free) | Move semantics + dataflow SRG | Rust borrow checker |
| Sem double-free | Estado `MOVED` rastreado por variável | Rust |
| Sem ponteiros dangling (stack escape) | Análise de escape de referências | Rust |
| Ponteiros de topologia corretamente usados | Verificação de topologia em atribuições | Novo em Sotlas |
| Sem alocação dinâmica em contexto de IRQ | Rastreamento de efeitos (`ALLOC` bloqueado) | Ada SPARK |
| Sem operações bloqueantes em ISR | Rastreamento de efeitos (`BLOCKING` bloqueado) | Ada SPARK |
| `unsafe` explicitamente delimitado | Contador de profundidade de `unsafe` | Rust |
| Pattern matching exaustivo | Verificação de variantes de `enum` em `discern` | Rust, Haskell |
| Registradores de hardware sem sobreposição de bits | Verificação de campos de bit em `register` | Novo em Sotlas |
| Módulos `barecore` sem construtos dinâmicos | Verificação de perfil de alvo | Zig (freestanding) |
| Spec bounds satisfeitos em generics | Verificação de bounds em ponto de instanciação | Rust traits |

---

## 1. Sem Use-After-Free (Uso Após Liberação)

Sotlas rastreia o estado de cada variável `sole` em todos os caminhos de execução possíveis.

### O que é garantido

- Uma variável `sole` que foi movida (por atribuição, passagem por valor, ou `handover`) **não pode ser usada** em nenhum caminho de execução posterior.
- O compilador detecta moves em ramos condicionais e propaga o estado `MAYBE_MOVED` corretamente.
- Tentativas de usar um recurso após liberação são erros de compilação com localização exata.

### Exemplo: código rejeitado

```sotlas
sole struct DatabaseConn { pub id: UInt64; }
fn close(conn: sole DatabaseConn) -> Void { ... }

fn main() -> Void {
    let conn = DatabaseConn { id: 1 };
    close(conn);           // conn foi movido
    let id = conn.id;     // ERRO: uso de 'conn' após transferência
}
```

```
error[E0200]: uso de variável 'sole' 'conn' após transferência (handover)
  --> main.sotlas:7:14
   |
5  |     close(conn);
   |           ---- transferência ocorrida aqui
6  |     let id = conn.id;
   |              ^^^^ use-after-move
   = help: se você precisa acessar o valor após a chamada, retorne-o da função ou use 'whisper'
```

---

## 2. Sem Double-Free

O sistema de ownership garante que um recurso `sole` só pode ser liberado uma vez.

### O que é garantido

Quando um recurso `sole` chega ao fim do seu escopo sem ter sido movido, o compilador chama automaticamente o destrutor (`deinit`) exatamente uma vez.

### Comparativo com C/C++

```c
// C: double-free possível em runtime
FILE *f = fopen("x", "r");
fclose(f);
fclose(f);  // undefined behavior — segfault ou corrupção de heap
```

```sotlas
// Sotlas: double-free impossível em tempo de compilação
sole struct File { pub fd: Int32; }
fn close(f: sole File) -> Void { ... }

fn main() -> Void {
    let f = File { fd: 1 };
    close(f);   // f transferido
    close(f);   // ERRO: compilação falha aqui
}
```

---

## 3. Sem Ponteiros Dangling (Stack Escape)

### O que é garantido

Referências (`&x`, `whisper x`) a variáveis locais de pilha não podem escapar do escopo da função via `return` ou atribuição a variáveis de escopo maior.

### Exemplo: código rejeitado

```sotlas
fn get_pointer() -> *mut Int32 {
    let x: Int32 = 42;
    return &x;  // ERRO: referência a variável local 'x' não pode escapar
}
```

```
error[E0600]: referência a variável local de pilha 'x' não pode escapar do escopo da função
  --> lib.sotlas:3:12
   |
2  |     let x: Int32 = 42;
   |         - declarada aqui
3  |     return &x;
   |            ^^ escapando aqui
```

---

## 4. Ponteiros de Topologia Corretamente Usados

Esta é uma garantia **exclusiva de Sotlas**, não presente em Rust, C ou Zig.

### O que é garantido

Ponteiros físicos (`*rawphys`), virtuais (`*virtmap`), de porta I/O (`*portwire`) e de DMA (`*dmazone`) são tipos distintos. O compilador proíbe atribuições incorretas entre topologias.

### Por que isso importa

Em código de kernel, confundir endereços físicos com virtuais é uma das causas mais frequentes de bugs de segurança e corrupção de memória em kernels C.

### Exemplo: código rejeitado

```sotlas
fn map_mmio(phys: *rawphys UInt32) -> Void {
    let virt: *virtmap UInt32 = phys;  // ERRO: topologia incompatível
}
```

```
error[E0100]: topologia incompatível: '*rawphys' não pode ser atribuído a '*virtmap'
  --> driver.sotlas:2:30
   |
2  |     let virt: *virtmap UInt32 = phys;
   |                                 ^^^^ tipo: *rawphys UInt32
   = help: Use a função de mapeamento do kernel para converter endereços físicos em virtuais:
   = help:   let virt = mmu_map(phys);
```

### Comparativo com C

```c
// C: zero verificação de topologia
volatile uint32_t *phys = (uint32_t *)0xFEE00000;  // endereço físico LAPIC
volatile uint32_t *virt = phys;  // ERRO silencioso: sem MMU, acesso causa fault
```

---

## 5. Sem Alocação Dinâmica em Contextos de IRQ

### O que é garantido

Funções marcadas com `@irqfree` ou `trapfn` (ISRs) **não podem** usar — direta ou transitivamente — operações que introduzem o efeito `ALLOC`. O compilador rastreia efeitos de hardware transitivamente por toda a árvore de chamadas.

### Exemplo: código rejeitado

```sotlas
fn allocate_buffer() -> co-owned UInt8 {  // efeito: ALLOC
    ...
}

@irqfree
fn timer_handler() -> Void {
    let buf = allocate_buffer();  // ERRO: ALLOC em irqfree
}
```

```
error[E0712]: alocação dinâmica (efeito 'alloc') é proibida em contexto irqfree
  --> isr.sotlas:6:15
   |
3  | fn allocate_buffer() -> co-owned UInt8 {
   |    ------------------- introduz efeito 'alloc'
...
6  |     let buf = allocate_buffer();
   |               ^^^^^^^^^^^^^^^^^ efeito 'alloc' propagado aqui
```

---

## 6. Pattern Matching Exaustivo

### O que é garantido

`discern` sobre um `enum` deve cobrir **todas** as variantes. O compilador lista as variantes faltantes no erro.

### Exemplo: código rejeitado

```sotlas
enum Status { Ok, Err, Timeout }

fn handle(s: Status) -> UInt32 {
    discern s {
        Status::Ok  => { return 0; }
        Status::Err => { return 1; }
        // ERRO: Status::Timeout não coberto
    }
}
```

```
error[E0500]: discern não exaustivo: variantes ausentes: Timeout
  --> handler.sotlas:4:5
   |
4  |     discern s {
   |     ^^^^^^^ padrões não exaustivos
   = help: adicione um caso para 'Status::Timeout' ou use um wildcard '_'
```

---

## 7. Registradores de Hardware sem Sobreposição de Bits

### O que é garantido

Campos de um `register` não podem sobrepor bits entre si. O compilador verifica ranges de bits na declaração.

### Exemplo: código rejeitado

```sotlas
register ControlReg: UInt32 {
    enable:  bit[0],
    mode:    bit[0..3],  // ERRO: bit 0 já pertence a 'enable'
    timeout: bit[4..7],
}
```

```
error: register 'ControlReg' field 'mode' overlaps bit 0 with field 'enable'
```

---

## 8. Módulos `barecore` sem Construtos Dinâmicos

### O que é garantido

Em módulos `barecore`, o compilador proíbe todos os construtos que dependem de alocação dinâmica ou herança virtual.

| Código | Motivo |
|---|---|
| `co-owned` | Usa ARC (alocação interna) |
| `class` | Vtable dinâmica (ponteiro de heap) |
| `String` (dinâmica) | Alocação de heap |
| `Vec` (dinâmico) | Alocação de heap |
| `async/await` | Coroutines precisam de stack alocada |

Código `barecore` que compila tem garantia de **zero alocação implícita**.

---

## 9. Comparativo com Outras Linguagens

| Garantia | C | C++ | Rust | Zig | **Sotlas** |
|---|---|---|---|---|---|
| Sem use-after-free | ❌ | ❌ (parcial) | ✅ | ⚠️ manual | ✅ |
| Sem double-free | ❌ | ❌ | ✅ | ⚠️ manual | ✅ |
| Sem dangling refs | ❌ | ❌ | ✅ | ⚠️ | ✅ |
| Topologia de ponteiros | ❌ | ❌ | ❌ | ❌ | ✅ |
| Rastreamento de efeitos de HW | ❌ | ❌ | ❌ | ❌ | ✅ |
| Pattern matching exaustivo | ❌ | ❌ | ✅ | ✅ | ✅ |
| Registrador sem sobreposição de bits | ❌ | ❌ | ❌ | ⚠️ | ✅ |
| Freestanding sem runtime | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 10. O que o Compilador NÃO Garante

Para ser transparente, estas propriedades **não** são verificadas atualmente:

- **Liberdade de deadlock** — sincronização entre threads não é verificada estaticamente.
- **Terminação** — o compilador não verifica se loops terminam.
- **Ausência de overflow aritmético** — exceto em tipos com bounds explícitos.
- **Segurança de código dentro de blocos `unsafe`** — dentro de `unsafe`, a responsabilidade é do programador.

---

> Sotlas v0.5.1 · [Spec Semântica Completa](../spec/sotlas_semantics.md) · [Gramática EBNF](../spec/sotlas_grammar.ebnf)
