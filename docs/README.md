# Sotlas Documentation Map

**Status:** CANONICAL DOCUMENT ROUTER  
**Atualizado em:** 2026-09-30 (America/Fortaleza)

Este arquivo existe para impedir que decisões de arquitetura, implementação, status ou release sejam tomadas a partir de um único documento fora de contexto.

> Quando houver brecha, ausência de informação ou aparente contradição, use este mapa para localizar a autoridade correta antes de concluir qualquer coisa sobre o Sotlas.

---

## Documentos canônicos

| Documento | Função |
|---|---|
| [`sotlas_master_roadmap.md`](./sotlas_master_roadmap.md) | especificação mestra; visão arquitetural, semântica e conceitos da linguagem |
| [`sotlas_development_blueprint.md`](./sotlas_development_blueprint.md) | ordem de desenvolvimento, fundações compartilhadas, tracks verticais, dependências e gates |
| [`sotlas_full_implementation_plan.md`](./sotlas_full_implementation_plan.md) | backlog técnico amplo, gaps concretos e detalhe operacional do Kernel/Barecore Track K0–K14 |
| [`sotlas_implementation_status.md`](./sotlas_implementation_status.md) | fotografia do que está realmente COMPLETE/CERTIFIED/PREVIEW no escopo declarado |
| [`sotlas_release_roadmap.md`](./sotlas_release_roadmap.md) | política canônica de fechamento de marcos, freeze, hardening, versionamento e releases públicos |
| [`sotlas_m16_3_recursion_contract.md`](./sotlas_m16_3_recursion_contract.md) | contrato específico M16.3e para self/mutual recursion no ABI nativo; não substitui Master/Full Plan/Status |

---

# 1. Como os documentos se relacionam

```text
                    SOTLAS MASTER ROADMAP
                     arquitetura / semântica
                              │
                              ▼
                 DEVELOPMENT BLUEPRINT
           fundações / ordem / tracks / dependências
                              │
                 ┌────────────┴────────────┐
                 ▼                         ▼
      FULL IMPLEMENTATION PLAN       VERTICAL TRACKS
       backlog técnico / gaps      APP / UI / GAME / AI
          M16 / K0–K14            HPC / K / DATA / MEDIA
                 │                         │
                 └────────────┬────────────┘
                              ▼
                 IMPLEMENTATION STATUS
                 realidade certificada
                              │
                              ▼
                    RELEASE ROADMAP
             corte / hardening / publicação
                              │
                              ▼
                     PUBLIC RELEASE
```

Contratos técnicos específicos, como [`sotlas_m16_3_recursion_contract.md`](./sotlas_m16_3_recursion_contract.md), ficam **entre** o Full Plan e a implementação concreta: detalham uma decisão delimitada, mas continuam subordinados ao Master/Blueprint e não podem promover status sem o Implementation Status + gates.

Nenhuma seta significa que o documento de baixo pode redefinir a semântica do documento de cima. Cada arquivo possui autoridade apenas sobre sua dimensão.

---

# 2. Qual documento consultar?

## “O que este conceito significa no Sotlas?”

Consulte primeiro:

1. [`sotlas_master_roadmap.md`](./sotlas_master_roadmap.md)
2. depois o Blueprint para entender dependências e ordem;
3. Full Plan para saber o que ainda falta implementar;
4. Implementation Status para saber se já está certificado.

## “O que implementamos agora?”

Consulte:

1. [`sotlas_development_blueprint.md`](./sotlas_development_blueprint.md)
2. [`sotlas_full_implementation_plan.md`](./sotlas_full_implementation_plan.md)
3. [`sotlas_implementation_status.md`](./sotlas_implementation_status.md)

Se o trabalho estiver perto de fechamento público, consulte também o Release Roadmap.

## “O que realmente funciona hoje?”

Consulte:

1. [`sotlas_implementation_status.md`](./sotlas_implementation_status.md)
2. testes/gates e baseline verde correspondente;
3. Full Plan para limites ainda abertos.

Não inferir suporte amplo apenas porque o Master ou Blueprint descreve a visão futura.

## “Quando podemos lançar?”

Consulte:

1. [`sotlas_release_roadmap.md`](./sotlas_release_roadmap.md)
2. Implementation Status;
3. Blueprint para dependências do ciclo;
4. Full Plan para gaps/blockers;
5. Master Roadmap quando houver nova semântica.

## “Como funciona a recursão nativa do M16.3?”

Consulte em conjunto:

1. [`sotlas_m16_3_recursion_contract.md`](./sotlas_m16_3_recursion_contract.md) — contrato específico do ABI nativo;
2. Master Roadmap — restrições semânticas/perfis que podem proibir recursão não limitada;
3. Full Implementation Plan — posição do item dentro de M16.3;
4. Implementation Status + gates — se o contrato já está certificado;
5. Release Roadmap — quando esse avanço pode participar de fechamento/publicação.

Regra: permitir recursão no backend de propósito geral **não** autoriza recursão não limitada em perfis realtime/kernel/determinísticos que imponham outro contrato.

## “Como funciona a criação de kernel/OS?”

Consulte em conjunto:

1. [`sotlas_development_blueprint.md`](./sotlas_development_blueprint.md) — Trilha K e fundações F/IR/BE/RT;
2. [`sotlas_full_implementation_plan.md`](./sotlas_full_implementation_plan.md) — detalhe K0–K14 e M16.x;
3. [`sotlas_master_roadmap.md`](./sotlas_master_roadmap.md) — Ownership, Authority, Effects, Execution, Trust, SIR e demais semânticas;
4. [`sotlas_release_roadmap.md`](./sotlas_release_roadmap.md) — quando um avanço kernel/systems pode virar claim público.

Regra: M16/backend não é sinônimo de kernel completo. Kernel bootável exige o gate E2E definido no track K.

## “Como funciona a criação de apps?”

Consulte em conjunto:

1. [`sotlas_development_blueprint.md`](./sotlas_development_blueprint.md) — APP0–APP4, RT0–RT6 e fundações F/IR/BE;
2. [`sotlas_full_implementation_plan.md`](./sotlas_full_implementation_plan.md) — gaps de tipos, runtime, strings, containers, ABI, stdlib e backend;
3. Master Roadmap — semântica geral;
4. Release Roadmap — ciclo R-APP e gate de publicação.

## “Como funciona UI/animação/desktop?”

Consulte:

1. Blueprint UI0–UI9 + APP3;
2. RT/event loop;
3. NUM/SIMD;
4. Heterogeneous/GPU quando necessário;
5. Release Roadmap R-UI.

Não colocar animação, wallpaper, compositor ou UI de produto dentro do compilador ou do kernel core.

## “Como funciona game/realtime?”

Consulte:

1. Blueprint GAME G0–G14;
2. NUM/SIMD;
3. RT/concurrency;
4. Heterogeneous/GPU;
5. Release Roadmap R-REALTIME.

Não usar claim “AAA ready” antes do gate específico.

## “Como funciona AI/HPC/GPU/NPU?”

Consulte:

1. Blueprint H, AI e HPC;
2. Master Roadmap para Execution/Ownership/Authority/Effects/Trust;
3. Full Plan para gaps técnicos;
4. Release Roadmap R-HET.

Claims de tensor, inference, training, GPU e NPU permanecem separados.

## “Como funciona self-host/toolchain soberana?”

Consulte:

1. Blueprint SH0–SH5;
2. BE object/linker;
3. Full Plan;
4. Release Roadmap R-SOV.

Não remover Stage 0 antes da paridade/fixed point exigida.

---

# 3. Tracks verticais são consumidores da mesma linguagem

Sotlas possui uma única fundação horizontal.

```text
F / IR / BE / RT / NUM / H
          │
          ├── APP
          ├── UI
          ├── GAME
          ├── AI
          ├── HPC
          ├── KERNEL
          ├── DATA / NETWORK
          ├── MEDIA
          ├── WEB
          └── SELF-HOST / TOOLING
```

Se uma vertical exigir algo ausente:

1. identificar se é primitiva geral ou detalhe de biblioteca/produto;
2. se for geral, implementar na fundação adequada;
3. preservar semântica no SIR/runtime/backend;
4. criar gates próprios;
5. só então usar na vertical.

Baken, uma aplicação, uma engine ou um runtime de IA podem ser provas/consumidores, mas não podem definir bypass privado dentro da linguagem.

---

# 4. Regra de autoridade em aparentes conflitos

Use esta ordem por tipo de pergunta:

| Tipo de conflito | Autoridade primária |
|---|---|
| significado/semântica | Master Roadmap |
| ordem/dependência/milestone | Development Blueprint |
| tarefa/gap técnico | Full Implementation Plan |
| estado atual/certificação | Implementation Status + gates |
| release/versionamento/publicação | Release Roadmap |

Se a autoridade primária estiver incompleta, consultar as demais e **atualizar a brecha documental**. Não preencher silenciosamente a lacuna com uma decisão ad hoc.

---

# 5. Regra de manutenção desta rede

Sempre que uma decisão estrutural alterar mais de um documento:

- atualizar os documentos afetados no mesmo bloco lógico quando possível;
- adicionar cross-reference em vez de duplicar longas especificações;
- evitar duas fontes normativas para a mesma regra;
- preservar histórico quando uma decisão antiga ainda for relevante;
- manter estados `CERTIFIED`, `PARTIAL`, `PREVIEW`, `PLANNED` e similares coerentes com a evidência.

O objetivo é que cada documento possa encaminhar o leitor para a fonte correta quando sua própria responsabilidade terminar.

---

# 6. Release flow resumido

```text
MASTER
  ↓
BLUEPRINT
  ↓
IMPLEMENTAÇÃO / FULL PLAN
  ↓
STATUS + GATES
  ↓
MILESTONE CLOSURE
  ↓
RELEASE ROADMAP
  ↓
FREEZE / HARDENING / RC
  ↓
PUBLIC RELEASE
  ↓
PRÓXIMO CICLO
```

Para detalhes obrigatórios de lançamento, consultar [`sotlas_release_roadmap.md`](./sotlas_release_roadmap.md).
