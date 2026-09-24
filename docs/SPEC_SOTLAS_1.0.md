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

Quando a última referência forte é liberada, Sotlas executa primeiro o `deinit`
definido para o owner e depois destrói recursivamente seus campos `sole` por
valor na ordem inversa da declaração; arrays fixos owned, inclusive
multidimensionais, também são percorridos em ordem reversa em cada dimensão.
O hook `deinit` não substitui a
destruição automática dos campos. O lowering C11 experimental valida essa
ordem em payloads compartilhados, inclusive wrappers não `sole` com campos
`sole` quando o hook não referencia `self`; hooks que acessam o wrapper com
descendentes owned continuam fail-closed para evitar destruição dupla.

### 4.3 `direct` (Acesso SRG de Baixo Bookkeeping)
`direct` designa acesso/referência SRG de baixo bookkeeping para contextos de baixo nível. Não seleciona endereço físico nem substitui o contrato de lifetime: lifetime e segurança devem ser explícitos e combinam-se com a topologia do ponteiro. A definição anterior desta seção como alocação inline conflita com o contrato arquitetural atual e não deve ser usada para implementar o domínio; consulte `sotlas_master_roadmap.md`, seção “Gestão de Memória SRG”.

O primeiro contrato executável é deliberadamente restrito a parâmetros de função:

```sotlas
fn inspect(token: direct Token) -> u32 { return token.value; }
fn caller(token: Token) -> u32 { return inspect(&token); }
```

`direct T` nesse contexto é uma referência imutável válida apenas durante a
chamada. A origem deve ser um binding direto `exclusive` ou `shared` vivo; a
operação não move nem retém o owner. Chamadas livres e receivers de método
podem usar a mesma origem, inclusive mais de um parâmetro na mesma chamada;
aliases locais no frame são permitidos;
retorno, armazenamento em campo/global, captura por `defer`, FFI opaca e
encaminhamento sem prova no-escape são rejeitados. O C11 baixa esse subconjunto
para ponteiro const sem contagem de referências e tem execução nativa de cobertura.
O LLVM aceita fonte→objeto somente para chamadas lineares com owners `sole`
triviais; o graph canônico valida cada borrow e `DirectAccessInst` baixa como
no-op sem bookkeeping. Payloads com destrutores/ownership aninhado, ARC, CFG
amplo e escape permanecem rejeitados. Esta fatia não conclui `direct` nem
define ainda referências mutáveis, aliases locais ou lifetime graph geral.

### 4.4 `island` (Isolamento de Concorrência / Modelo de Atores)
Regiões de memória isoladas garantindo que dados não sejam acessados concorrentemente sem sincronização explícita via fila de mensagens.

### 4.5 `whisper` (Empréstimo Imutável Não Proprietário)
`whisper T` descreve uma referência imutável não proprietária a um `T`; ela não
retém, move nem prolonga a vida do owner. O owner deve permanecer vivo durante
toda a chamada que recebe o empréstimo. A forma inicial admitida é explícita e
direta:

```sotlas
fn inspect(token: whisper Token) -> void { return; }
fn caller(token: Token) -> void {
    inspect(&token);
}
```

O grafo de ownership registra a chamada e sua origem, sem criar um owner novo.
O subconjunto inicial admite fontes `exclusive` e `shared` comprovadamente
vivas, incluindo receiver direto de método; empréstimos de `island`, membros,
temporários, armazenamento, retorno ou captura exigem contratos próprios. A
implementação deve rejeitar qualquer caminho cujo lifetime ou ausência de
escape não consiga provar; suporte parcial no frontend não autoriza lowering de
backend.

O checker de produção valida escapes locais e deriva summaries no-escape por
ponto fixo para parâmetros de referência/ponteiro de funções com corpo. Um
empréstimo pode ser encaminhado somente se o parâmetro correspondente do alvo
possuir summary provado. Funções `extern`, chamadas indiretas, ciclos sem prova
e qualquer corpo que possa guardar, retornar ou exportar o alias permanecem
fail-closed. Essa prova ainda não substitui o lifetime graph path-sensitive,
a weak invalidation ou o runtime/backend de `whisper`.

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
