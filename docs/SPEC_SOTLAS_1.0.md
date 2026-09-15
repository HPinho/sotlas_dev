# Especificação Formal da Linguagem Sotlas 1.0
## (General-Purpose Systems Programming Language)

**Versão**: 1.0.0-dev  
**Status**: Estável / Especificação Formal  
**Arquiteturas Alvo**: x86_64, aarch64, wasm32  
**Perfis de Execução**: Hosted (Userland) e Freestanding (Bare-metal / Kernel)

---

## 1. Princípios de Design e Filosofia

O **Sotlas** é uma linguagem de tipagem estática e compilação nativa desenhada para desenvolvimento de software de alta performance, desde aplicações comuns de usuário (CLIs, servidores, ferramentas, jogos) até software de sistemas (kernels, drivers e firmware embarcado).

1. **Desacoplamento Completo**: A semântica central da linguagem é 100% agnóstica de sistema operacional ou hardware específico.
2. **Posse Pragmática (Pragmatic Ownership)**: Em vez de um borrow-checker complexo com anotações de tempo de vida intrincadas, Sotlas adota tipos afins explícitos (`sole` com `handover`) e compartilhamento transparente (`co-owned`/ARC).
3. **Controle Estrito de Memória**: O programador decide onde cada byte reside (stack, arena, heap do SO ou memória física).
4. **Sondas Nativas (`probe`)**: A validação de invariantes e asserções é tratada como um operador de primeira classe na gramática.
5. **Zero-Libc por Padrão**: A linguagem não força links dinâmicos ocultos, permitindo portabilidade universal.

---

## 2. Perfis de Compilação (Target Profiles)

A especificação define dois perfis de execução sem alterar a gramática base da linguagem:

```sotlas
target native;   // Perfil Hospedado (Userland / Desktop / Servidor)
target barecore; // Perfil Freestanding (Kernel / Firmware / Bare-Metal)
```

| Característica | `target native` (Hosted) | `target barecore` (Freestanding) |
| :--- | :--- | :--- |
| **Ambiente** | Windows, Linux, macOS | Bare-metal, Bootloaders, Kernels |
| **Heap Padrão** | Alocador do SO (`malloc`/`free`) ou Arena | Pool estático ou alocador registrado |
| **Pânico** | Formatação e mensagem em `stderr` + `abort()` | Loop infinito com instrução `hlt`/`wfi` |
| **Extensões `@system`** | Disponíveis via FFI ou emulação | Habilitadas nativamente |

---

## 3. Sistema de Tipos

### 3.1 Tipos Primitivos
* **Inteiros com sinal**: `i8`, `i16`, `i32`, `i64`, `isize`
* **Inteiros sem sinal**: `u8`, `u16`, `u32`, `u64`, `usize`
* **Ponto flutuante IEEE 754**: `f32`, `f64`
* **Booleano**: `bool` (`true` ou `false`)
* **Vazio**: `void`
* **Sentinela Nula**: `null`

### 3.2 Ponteiros e Referências
* `*const T`: Ponteiro bruto imutável.
* `*mut T`: Ponteiro bruto mutável.
* `&T`: Referência imutável segura.
* `&mut T`: Referência mutável exclusiva.

### 3.3 Estruturas e Enumerações
```sotlas
pub struct Ponto {
    pub x: i32,
    pub y: i32,
}

pub enum Resposta {
    Sucesso(u32),
    Falha(i32),
    Pendente
}
```

---

## 4. Modelo de Posse (Ownership & Memory Graph)

O modelo de posse do Sotlas é desenhado para fazer sentido tanto em aplicações de alto nível quanto em kernels:

### 4.1 `sole` (Posse Única / Tipo Linear)
Uma estrutura declarada como `sole struct` representa um recurso exclusivo que não pode ser duplicado implicitamente. A transferência é feita com `handover`:

```sotlas
pub sole struct Arquivo {
    pub descriptor: i32,
}

pub fn fechar_arquivo(f: Arquivo) {
    // f passa a ser o único responsável pelo fechamento
}

pub fn exemplo() {
    let mut arq: Arquivo = 0;
    arq.descriptor = 3;

    // Transfere a posse explicitamente:
    fechar_arquivo(handover arq);

    // O uso de 'arq' após o handover é considerado erro semântico
}
```

### 4.2 `co-owned` (Propriedade Compartilhada com Contagem de Referência)
Representa estruturas que possuem múltiplos proprietários simultâneos (como nós de um grafo ou conexões compartilhadas). O runtime gerencia incrementos e decrementos atômicos transparentemente via ARC.

### 4.3 `direct` (Alocação em Valor / Inline)
Valores com semântica de cópia direta (stack-allocated ou membros embutidos sem ponteiro).

### 4.4 `island` (Isolamento de Concorrência / Modelo de Atores)
Regiões de memória isoladas garantindo que dados não sejam acessados concorrentemente sem sincronização explícita via fila de mensagens.

---

## 5. Controle de Fluxo e Expressões

### 5.1 Pattern Matching com `discern`
Casamento de padrões exaustivo e tipado para enums e variantes:

```sotlas
discern valor {
    case Status::Ativo => {
        // tratamento
    }
    case Status::Falha => {
        // tratamento
    }
    case _ => {
        // fallback
    }
}
```

### 5.2 Sondas de Asserção (`probe`)
Sondas verificam invariantes em tempo de execução. Se a condição for falsa, o programa aciona o manipulador de pânico imediatamente:

```sotlas
probe tamanho > 0, "O tamanho do buffer deve ser estritamente positivo";
```

### 5.3 Escopos com Descarte (`defer`)
O bloco `defer` garante a execução de limpeza na saída do escopo léxico:

```sotlas
let ptr: *mut u8 = arena_alloc(&mut arena, 128);
defer {
    arena_restore(&mut arena, mark);
}
```

---

## 6. Extensões Opcionais de Sistemas (`@system` / `system::*`)

Recursos voltados exclusivamente a bare-metal, kernels e drivers residem nesta camada e exigem contexto `@system` ou bloco `unsafe`:

1. **Ponteiros de Topologia**:
   * `*rawphys T`: Endereço físico direto (ignora MMU).
   * `*dmazone T`: Memória física contígua com garantia de coerência DMA.
   * `*virtmap T`: Memória virtual mapeada em tabela de páginas.
   * `*portwire T`: Linha de barramento de porta I/O (x86 in/out).
   * `*voidzero T`: Sentinela de armadilha para endereçamento nulo.
2. **Blindagem de Interrupções (`clinch` / `revert`)**:
   * Desabilita interrupções de hardware com restauração automática de flags da CPU na saída do bloco.
3. **Atômicos de Hardware (`pulse` / `pivot`)**:
   * `pulse`: Barreira de memória física (fence).
   * `pivot`: Operação Compare-And-Swap (CAS) atômica.

---

## 7. Conformidade e Implementação

Qualquer compilador compatível com Sotlas 1.0 deve:
1. Rejeitar transferências de tipos `sole` que não utilizem `handover`.
2. Garantir execução estrita de blocos `defer` na ordem inversa de declaração (LIFO).
3. Produzir binários nativos autônomos operáveis tanto em modo hospedado quanto em modo bare-metal.
