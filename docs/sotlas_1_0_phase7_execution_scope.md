# Sotlas 1.0 — Phase 7 Execution Domains Scope

**Atualizado em:** 2026-09-26
**Status:** IN PROGRESS  
**Último baseline verde certificado:** `ff5f433` — CI #598 `success`

## Subset de targets x86-64 e AArch64

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

Funções podem declarar `@target_feature(avx2, ...)`. A declaração chega ao SIR;
LLVM valida arquitetura e exige que o target escolhido contenha cada feature.
O backend C11 rejeita a anotação até oferecer suporte equivalente.

## Limites atuais

- os targets AArch64 Linux/freestanding ELF, Windows COFF e Darwin Mach-O possuem ABI, largura de ponteiro, endianness e data layouts específicos do LLVM;
- features AArch64 `aes`, `crc`, `lse`, `sha2`, `sve` e `sve2` são validadas, com `sve2` implicando `sve`;
- o registro de features continua limitado e ainda não implementa intrinsics SIMD Sotlas;
- `host` mantém o triple interno legado, sem detecção dinâmica do host;
- `@target_feature` valida requisitos por função, mas não fornece intrinsics,
  detecção dinâmica nem dispatch multi-versionado;
- ABI além de identificação do target e data layout não é validada integralmente;
- não há ainda suporte a intrinsics SIMD Sotlas, dispatch multi-versionado,
  constraints/clobbers por domínio, ou lowering heterogêneo;
- targets não suportados são rejeitados em vez de inferidos.

## Verificações

- normalização e dependências de CPU features;
- rejeição de triple e feature desconhecidos;
- preservação de `@target_feature` no SIR, aceitação/rejeição por target e gate C11;
- IR textual preserva target e atributos selecionados;
- emissão direta de LLVM IR a partir de fonte aceita configuração de target.
- presets e target features AArch64 aparecem em LLVM IR e são encaminhados a Clang sem flags específicas de x86.
- data layouts AArch64 ELF, COFF e Mach-O são conferidos por triple e emitidos no LLVM IR.

Este pacote fecha apenas uma fatia executável da Fase 7 e não declara a fase
completa.
