# Sotlas 1.0 — Phase 3 Authority Domains Release Scope

**Atualizado em:** 2026-09-25  
**Status:** 100% ✅ no escopo Sotlas 1.0  
**Baseline certificado:** `3b5114fb99f25f2ac92f2346b2c7d5a31db277e4`  
**CI de certificação:** Sotlas CI & Toolchain Build Farm #557 — `success`

Este documento define o gate de release da **Fase 3 — Authority Domains**. Ele não reduz a arquitetura futura de Authority da linguagem; apenas separa o que precisa estar correto e suportado no Sotlas 1.0 do catálogo de capabilities e integrações que pode amadurecer em 1.0.x/1.1.

A regra central é a mesma usada para Ownership Domains:

> O Sotlas 1.0 não precisa suportar toda operação privilegiada imaginável. O subset declarado precisa estar correto, least-authority e fail-closed fora do contrato.

## Contrato 1.0 fechado

A Fase 3 é considerada concluída para o Sotlas 1.0 porque o caminho essencial de autoridade está fechado de ponta a ponta no compilador:

```text
@system(capability)
        ↓
parser / contrato canônico
        ↓
production frontend safety
        ↓
Phase-1 checked module
        ↓
AuthorityDomainPlan
        ↓
strict checked SIR
        ↓
AuthorityABIInst / source boundaries
        ↓
AuthoritySIRCertificate
        ↓
AuthoritySIRSafety
```

### Garantias do 1.0

- [x] `@system(capability)` possui contratos de authority nomeados e explícitos.
- [x] múltiplas capabilities podem ser declaradas sem transformar `@system` em privilégio global implícito.
- [x] bare `@system` permanece como modo legado irrestrito para compatibilidade, sem ser confundido com named authority.
- [x] `@interrupt` e `@naked` preservam o contexto privilegiado legado necessário aos caminhos já suportados.
- [x] chamadas para funções source `@system(...)` são fronteiras de abstração encapsuladas: o caller não herda nem precisa possuir a authority interna do callee.
- [x] chamadas diretas para ABI/intrinsics privilegiados são verificadas por least-authority no caller.
- [x] uma capability não concede automaticamente outra capability não declarada.
- [x] o frontend de produção (`check`/`compile_source`) aplica os mesmos contratos canônicos usados pelo planner de Authority.
- [x] `Phase1CheckedModule` carrega o plano canônico de Authority.
- [x] o Typed AST reconhece apenas os intrinsics ABI que já possuem contrato Authority nomeado e reutiliza as assinaturas canônicas de `bootstrap.BUILTIN_FUNCTIONS`.
- [x] o strict checked SIR preserva fronteiras source e facts ABI source-stable.
- [x] `AuthorityABIInst` representa authority ABI no SIR sem inventar efeito de runtime ou duplicar lowering físico do backend.
- [x] `AuthoritySIRCertificate` exige correspondência exata entre source plan e SIR.
- [x] `AuthoritySIRSafety` detecta remoção, inserção, divergência ou ampliação indevida de authority após certificação.
- [x] a entrada strict de Authority SIR está exposta pela API pública de produção.
- [x] intrinsics privilegiados sem contrato nomeado continuam fail-closed para callers named-only.

## Families ABI suportadas no gate 1.0

### `io.port`

- `__inb`
- `__outb`
- `__inw`
- `__outw`
- `__inl`
- `__outl`

### `cpu.interrupts`

- `__irq_save_disable`
- `__irq_restore`
- `__interrupts_enabled`
- `__cli`
- `__sti`

### `cpu.msr`

- `__rdmsr`
- `__wrmsr`

Essas families são representativas e suficientes para certificar o modelo de Authority Domains no 1.0. A conclusão da fase não significa que todo intrinsic de toda arquitetura já possui uma capability própria.

## O que fica para 1.0.x / 1.1

Os itens abaixo **não bloqueiam o Sotlas 1.0** enquanto permanecerem fora do subset `SUPPORTED` e fail-closed onde necessário:

- contracts nomeados para registradores de controle (`CR0`, `CR2`, `CR3`, `CR4`);
- TLB / `__invlpg`;
- GS / `swapgs` / modelos per-CPU;
- CPU halt e outras instruções privilegiadas ainda legadas;
- expansão do catálogo de atomics/hardware intrinsics;
- contracts Authority amplos para MMIO, DMA, IRQ controller e outros subsistemas;
- authority contracts gerais em FFI externo;
- generalização do bridge de Typed AST para assinaturas ABI não escalares;
- target-specific authority catalogs para outras arquiteturas;
- refinamentos adicionais de diagnóstico/ergonomia.

Se qualquer item acima revelar que um programa pertencente ao subset 1.0 pode adquirir authority implicitamente, cruzar uma fronteira privilegiada sem contrato ou sofrer lowering semanticamente incorreto, isso volta a ser regressão/blocker.

## Critério de soberania

Authority continua pertencendo à semântica Sotlas, não ao backend:

- backend não inventa privilege;
- ABI não amplia capability;
- `unsafe` não substitui `@system`;
- `@system` não substitui `unsafe`;
- source wrappers não vazam sua authority interna para callers;
- unsupported permanece explícito/fail-closed.

## Próximo estágio do roadmap

Com este gate certificado, **Fase 3 — Authority Domains está encerrada para o Sotlas 1.0**.

O roadmap principal avança para **Fase 4 — State Spaces** (`space`, typestate e transitions). Expansões de Authority continuam em pacotes 1.0.x/1.1 sem reabrir automaticamente a Fase 3.
