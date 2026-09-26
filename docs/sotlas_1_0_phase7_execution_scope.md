# Sotlas 1.0 — Phase 7 Execution Domains Scope

**Atualizado em:** 2026-09-25  
**Status:** IN PROGRESS  
**Último baseline verde certificado:** `c91b23a` — CI #577 `success`

## Subset de target x86-64

O modelo de target tipado reconhece triples x86-64 freestanding ELF, Linux
SysV, Windows MSVC, Darwin e o target interno `x86_64-pc-none`. Os aliases
`host` e `x86_64-freestanding` preservam os defaults anteriores. Cada target
carrega ABI, largura de ponteiro, endianness, CPU e data layout conhecido.

Features x86-64 habilitadas são validadas contra um registro explícito e
normalizadas com suas dependências (por exemplo, `avx2` implica `avx`); nomes
desconhecidos falham fechado. O LLVM IR recebe triple, data layout quando
conhecido e atributos de CPU/features. A toolchain também encaminha target e
features ao Clang nos caminhos de objeto C11, e o CLI expõe `--target` e
`--cpu-feature` repetível.

## Limites atuais

- o registro contém somente targets x86-64 e uma lista limitada de features;
- `host` mantém o triple interno legado, sem detecção dinâmica do host;
- ABI além de identificação do target e data layout não é validada integralmente;
- não há ainda suporte a intrinsics SIMD Sotlas, dispatch multi-versionado,
  constraints/clobbers por domínio, ou lowering heterogêneo;
- targets não suportados são rejeitados em vez de inferidos.

## Verificações

- normalização e dependências de CPU features;
- rejeição de triple e feature desconhecidos;
- IR textual preserva target e atributos selecionados;
- emissão direta de LLVM IR a partir de fonte aceita configuração de target.

Este pacote fecha apenas uma fatia executável da Fase 7 e não declara a fase
completa.
