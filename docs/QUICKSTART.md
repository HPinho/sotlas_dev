# Guia de Introdução ao Sotlas (Quickstart)

Este guia descreve o subconjunto Stage-0 verificado da Sotlas. Recursos de roadmap e exemplos de design são identificados como experimentais; os exemplos numerados em `examples/` são a referência executável.

---

## 1. O que é o Sotlas?

O compilador Stage-0 aceita um subconjunto experimental que evolui em direção à linguagem descrita no roadmap. O contrato estável ainda não foi declarado para Sotlas 1.0; consulte `docs/sotlas_implementation_status.md` para os gates e limites atuais.

---

## 2. Seu Primeiro Programa: "Olá, Mundo!"

O exemplo verificado está em `examples/01_hello_systems/main.sotlas`. Para testar sua instalação, execute:

```sotlas
python -m sotlas.cli check examples/01_hello_systems/main.sotlas
python -m sotlas.cli compile examples/01_hello_systems/main.sotlas --emit-c -o hello.c
```

### Executando diretamente (requer compilador C no PATH):
```bash
sotlas_native run hello.sotlas
```

### Compilando para executável nativo (requer toolchain LLVM/C configurada):
```bash
sotlas_native hello.sotlas -o hello.exe
./hello.exe
```

---

## 3. Gerenciamento de Projetos com `Sotlas.toml`

O compilador nativo inclui seu próprio gerenciador de pacotes:

### Criar um Novo Projeto:
```bash
sotlas_native new meu_projeto
cd meu_projeto
```

A estrutura do projeto criada é:
```text
meu_projeto/
├── Sotlas.toml          # Manifesto do projeto
├── src/
│   └── main.sotlas      # Ponto de entrada
```

### Compilar e Rodar:
```bash
sotlas_native build
sotlas_native test
```

---

## 4. Recursos em desenvolvimento

As seções abaixo descrevem intenção de design e não são exemplos executáveis do contrato Stage-0. Para o estado implementado, use `docs/sotlas_implementation_status.md` e `examples/manifest.json`.

### 4.1 Tipos `sole` e Semântica de Movimentação (`handover`)
Recursos que possuem apenas um dono (como descritores de arquivo, buffers de rede e conexões) usam `sole struct`. Ao passar a posse para outra variável ou função, usamos `handover`:

```sotlas
pub sole struct Conexao {
    pub fd: u64,
    pub ativa: bool,
}

pub fn consumir_conexao(c: Conexao) {
    // Agora 'c' é o único dono do recurso
}

pub fn main() -> i32 {
    let mut c: Conexao = 0;
    c.fd = 8080;
    c.ativa = true;

    // A posse é transferida explicitamente; o identificador antigo deixa de ser dono
    consumir_conexao(handover c);
    return 0;
}
```

### 4.2 Pattern Matching com `discern`
O casamento de padrões é exaustivo e seguro:

```sotlas
pub enum Status {
    Pendente = 0,
    Processando = 1,
    Concluido = 2,
    Erro = 3
}

pub fn avaliar_status(s: Status) -> i32 {
    discern s {
        case Status::Pendente => {
            return 1;
        }
        case Status::Processando => {
            return 2;
        }
        case Status::Concluido => {
            return 0;
        }
        case Status::Erro => {
            return -1;
        }
        case _ => {
            return 99;
        }
    }
}
```

### 4.3 Alocação Eficiente em Arena (`core::alloc`)
Para aplicações como parsers, compiladores e processamento em lote, use arenas para alocar rapidamente e liberar tudo de uma só vez:

```sotlas
import core::alloc::*;

static mut g_memoria: [u8; 4096] = 0;

pub fn main() -> i32 {
    let mut arena: ArenaAllocator = arena_new(g_memoria as *mut u8, 4096);

    // Alocações rápidas sequenciais (bump pointer)
    let buffer_temporario: *mut u8 = arena_alloc(&mut arena, 256);

    // Salva estado e restaura
    let mark: usize = arena_save(&arena);
    let scratch: *mut u8 = arena_alloc(&mut arena, 1024);
    arena_restore(&mut arena, mark); // Devolve os 1024 bytes instantaneamente!

    // Libera a arena inteira em O(1)
    arena_reset(&mut arena);
    return 0;
}
```

---

## 5. Ferramental Integrado

| Comando | Descrição |
| :--- | :--- |
| `sotlas_native run <arquivo.sotlas>` | Compila e roda instantaneamente |
| `sotlas_native <arquivo.sotlas> -o <saida.exe>` | Gera binário de máquina executável |
| `sotlas_native <arquivo.sotlas> -o <saida.c>` | Emite código-fonte C11 legível e estrito |
| `sotlas_native test` | Executa todos os testes nativos com probes |
| `sotlas_native fmt` | Formata o código do projeto |
| `sotlas_native lint` | Analisador estático de boas práticas |
| `sotlas_native new <nome>` | Cria um novo projeto com manifesto |
| `sotlas_native build` | Compila o projeto baseado em `Sotlas.toml` |

---

## 6. Próximos Passos
* Consulte a [Especificação Formal Sotlas 1.0](SPEC_SOTLAS_1.0.md) como documento de design, não como garantia de suporte integral.
* Explore a pasta `examples/` para aplicações de rede, jogos, CLI e parsers em Sotlas puro.
