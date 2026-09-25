# Sotlas 1.0 — Release Scope

**Atualizado em:** 2026-09-24  
**Objetivo:** impedir que o roadmap técnico infinito impeça um release estável da linguagem.

## Princípio de produto

Sotlas 1.0 não precisa implementar toda combinação teórica prevista pela arquitetura. O 1.0 precisa entregar um núcleo útil, coerente, seguro e executável para o conjunto explicitamente declarado como suportado.

A regra de release é:

> Um caso ainda não suportado pode falhar fechado. Um caso aceito pelo compilador não pode produzir semântica incorreta, ownership incorreto, lifetime incorreto, double-free, leak estrutural conhecido ou lowering inventado.

Portanto, `não suportado ainda` e `bloqueador do 1.0` não são sinônimos.

## Política de versões

### Sotlas 1.0

Fecha o contrato mínimo estável da linguagem:

- sintaxe e semântica centrais coerentes;
- ownership/lifetime corretos no subset declarado `SUPPORTED`;
- unsupported shapes rejeitados fail-closed antes de lowering incorreto;
- pelo menos um caminho backend executável para as capacidades declaradas suportadas;
- regressões de segurança/correção tratadas como blockers;
- documentação distingue `SUPPORTED`, `PREVIEW` e `UNSUPPORTED`.

### Sotlas 1.0.x

Pode ampliar e refinar sem mudar a identidade da linguagem:

- novos casos estruturados dentro de features existentes;
- mais payloads/layouts;
- mais combinações de CFG;
- melhor cobertura de runtime/backend;
- diagnósticos melhores;
- otimizações;
- mais testes e2e;
- generalizações que preservem o contrato do 1.0.

### Sotlas 1.1+

Recebe expansões maiores:

- capacidades novas;
- semânticas adicionais de domínio;
- generalizações que alterem contratos públicos;
- novos backends/ABIs amplos;
- combinações avançadas que não sejam necessárias para o núcleo 1.0.

## Fase 2 — critério de saída para o 1.0

A Fase 2 pode ser considerada encerrada para fins do roadmap 1.0 quando os blockers abaixo estiverem fechados. Não é necessário esgotar todos os refinamentos listados em `sotlas_implementation_status.md`.

### BLOCKER 1.0

- [x] `exclusive` / `sole`: ownership linear, move, use-after-move, joins e contratos básicos estáveis.
- [x] ownership/domain graph canônico e source-stable para as transições já aceitas.
- [x] unsupported domain/lowering shapes falham fechado em vez de inventar semântica.
- [x] `shared`: modelo backend-neutral de ARC, retain/release/destroy e cleanup path-sensitive no subset estruturado já suportado.
- [ ] congelar e certificar explicitamente o **subset `shared` suportado no 1.0**, sem exigir CFG/payloads arbitrários.
- [x] `region`: lifetime topology, CFG path-sensitive, call/return interprocedural, identidade de iteração, N operações ownership-taking, arena slots/epochs/origins, reaching-flow acíclico, fluxo intra-iteração, recorrência loop-carried e alternativas activation-scoped.
- [ ] `region`: definir e executar um **runtime/e2e mínimo do subset 1.0**, sem exigir allocator/CFG geral para todos os casos.
- [ ] `island` + `quarantine` + `handover`: congelar o subset 1.0 já implementado e garantir pelo menos um caminho e2e representativo de isolamento → transferência → cleanup único.
- [ ] `direct` + `whisper`: congelar o subset 1.0 de borrow call-scoped/no-escape e garantir que storage/escape/FFI não suportados continuem fail-closed.
- [ ] matriz e2e mínima da Fase 2: programas representativos do subset `SUPPORTED` devem atravessar frontend → Typed AST → graph/SIR → backend de referência e executar corretamente.
- [ ] documentação pública deve indicar claramente quais formas de `device` e `external` são `PREVIEW`/`UNSUPPORTED` no 1.0 em vez de bloquear o release inteiro.

### DEFER 1.0.x

Os itens abaixo são melhorias importantes, mas não impedem o 1.0 quando o compilador rejeita corretamente as formas ainda não suportadas:

- CFG arbitrário para ARC/shared;
- todos os payloads/layouts possíveis em `shared`;
- assignments e blocos complexos sobre aliases shared;
- combinações profundas de defer + shared + controle arbitrário;
- arena `region` para toda topologia de CFG possível;
- merges de arena altamente path-dependent ainda não certificáveis;
- combinação geral de activation-scoped flow + ciclos/recursão;
- cobertura e2e ampla de toda combinação `region`;
- weak invalidation geral de `whisper`;
- `direct` em todas as formas ABI/backend;
- todas as combinações possíveis de `handover` entre domínios;
- invalidation/runtime amplo de `quarantine`;
- mensagens de diagnóstico e ergonomia adicionais.

### DEFER 1.1+

- runtime/sincronização geral de `device` e transfer CPU↔device para todos os casos;
- ABI/lifetime geral de `external` para layouts arbitrários;
- generalizações de domínio que exijam novo contrato público;
- backends adicionais que não sejam necessários para o release inicial;
- features novas que não sejam parte do núcleo estável 1.0.

## Regra de classificação

Antes de implementar uma lacuna da Fase 2, responder nesta ordem:

1. O caso pode produzir código incorreto ou ownership/lifetime incorreto no subset que já aceitamos?
   - **sim:** BLOCKER 1.0.
2. O caso é necessário para um exemplo básico/documentado da feature funcionar no backend de referência?
   - **sim:** BLOCKER 1.0.
3. O compilador pode rejeitar esse caso de forma clara e fail-closed sem quebrar o subset suportado?
   - **sim:** DEFER 1.0.x ou 1.1.
4. A mudança apenas amplia generalidade, otimização, ergonomia ou cobertura?
   - **sim:** não bloquear o 1.0.

## Regra de desenvolvimento

A disciplina de baseline continua obrigatória:

```text
baseline verde
    ↓
1 blocker 1.0 ou 1 pacote coerente
    ↓
testes reais
    ↓
CI verde
    ↓
novo baseline
```

Não contornar testes, não relaxar invariantes para obter CI verde e não transformar unsupported behavior em lowering silencioso.

## Estado atual de `region`

O modelo semântico já ultrapassou a descrição antiga de "arena/lifetime pendente". No baseline atual existem:

- owner origins canônicos;
- arena slots e epochs simbólicos;
- constraints de identidade;
- reaching-flow acíclico;
- N operações ownership-taking por iteração;
- corte canônico de backedge;
- fluxo intra-iteração em ciclos;
- recorrência de identidade loop-carried;
- activation IDs por call site;
- alternativas de entrada activation-scoped;
- integração checked no closed interprocedural plan.

Assim, o próximo objetivo do 1.0 não é continuar generalizando a prova indefinidamente. É transformar o subset já certificado em um caminho runtime/e2e mínimo e documentado.