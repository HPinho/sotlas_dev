# Sotlas 1.0 — Release Scope

**Atualizado em:** 2026-09-24  
**Fase 2 / Ownership Domains:** **COMPLETE para o escopo Sotlas 1.0 ✅**  
**Baseline certificado:** `5075c6454c0e1f5830b3f0537d267f6fe289d122` — CI #536 `success`

## Princípio de produto

Sotlas 1.0 não precisa implementar toda combinação teórica prevista pela arquitetura. O 1.0 precisa entregar um núcleo útil, coerente, seguro e executável para o conjunto explicitamente declarado como suportado.

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

## Fase 2 — gate de saída do Sotlas 1.0

Todos os blockers definidos para o subset 1.0 estão fechados. O roadmap técnico amplo continua existindo, mas seus refinamentos não mantêm a Fase 2 aberta quando o compilador consegue rejeitar formas ainda não suportadas de maneira fail-closed.

### BLOCKER 1.0

- [x] `exclusive` / `sole`: ownership linear, move, use-after-move, joins e contratos básicos estáveis.
- [x] ownership/domain graph canônico e source-stable para as transições aceitas.
- [x] unsupported domain/lowering shapes falham fechado em vez de inventar semântica.
- [x] `shared`: modelo backend-neutral de ARC, retain/release/destroy e cleanup path-sensitive no subset estruturado suportado.
- [x] subset `shared` 1.0 congelado: aliases/ARC estruturados e cleanup nativo já cobertos; CFG/payloads arbitrários ficam fora do contrato 1.0.
- [x] `region`: lifetime topology, CFG path-sensitive, call/return interprocedural, identidade de iteração, N operações ownership-taking, arena slots/epochs/origins, reaching-flow, recorrência loop-carried e alternativas activation-scoped.
- [x] `region`: runtime/e2e mínimo 1.0 certificado por prova backend-neutral completa + C11 com cleanup determinístico.
- [x] `island` + `quarantine` + `handover`: isolamento e transferência têm caminhos C11 representativos; handover same-domain possui validação de cleanup/destruição.
- [x] `direct` + `whisper`: subset 1.0 de borrow call-scoped/no-escape certificado em C11; formas armazenáveis/FFI/weak gerais permanecem fora do contrato.
- [x] matriz e2e mínima da Fase 2: os subsets `SUPPORTED` possuem probes nativos executáveis na suíte principal.
- [x] `device` e `external` classificados abaixo como `PREVIEW`; sua generalização não bloqueia Sotlas 1.0.

## Matriz oficial de suporte — Ownership Domains no Sotlas 1.0

| Capacidade | Nível no 1.0 | Contrato congelado |
|---|---|---|
| `sole` / `exclusive` | **SUPPORTED** | ownership linear, move, invalidation/use-after-move, joins e cleanup no subset aceito |
| `shared` | **SUPPORTED** | ARC backend-neutral, retain/release/destroy, aliases e controle estruturado já certificado |
| `region` | **SUPPORTED** | by-value owners, handover, call/return interprocedural, arena/lifetime certificado no subset e C11 mínimo |
| `island` | **SUPPORTED** | quarantine, owner isolado e handover nos caminhos já certificados |
| `quarantine` | **SUPPORTED** | transição para isolamento nos shapes aceitos; extensões de invalidation ficam para 1.0.x |
| `handover` | **SUPPORTED** | transferências explicitamente certificadas; pares de domínio ainda não suportados falham fechado |
| `direct` | **SUPPORTED** | borrow call-scoped, zero bookkeeping, sem storage/escape |
| `whisper` | **SUPPORTED** | borrow const/non-owning call-scoped e forwarding aceito; weak refs gerais ficam para depois |
| `device` | **PREVIEW** | semântica/reference runtime existente pode evoluir; runtime/sync geral não faz parte do contrato estável 1.0 |
| `external` | **PREVIEW** | caminhos `repr(C)`/FFI existentes funcionam, mas ABI/layout/lifetime geral não faz parte do contrato estável 1.0 |

## Evidência de release no CI

A matriz principal executa os gates específicos e também os testes nativos históricos. Entre as evidências canônicas:

- `tests/test_sotlas_phase2_v1_region_release_gate.py`
  - arena flow completo no subset 1.0;
  - geração C11;
  - compilação com warnings-as-errors;
  - execução nativa e cleanup determinístico.
- `tests/test_sotlas_phase2_v1_borrow_release_gate.py`
  - `direct` call-scoped;
  - `whisper` const/non-owning;
  - C11 e execução nativa.
- `tests/sotlas_classes_arc_impl.py::test_shared_alias_chain_runs_with_native_arc_runtime`
  - alias chain e ARC nativo de `shared`.
- `tests/sotlas_classes_arc_impl.py::test_island_quarantine_handover_runs_through_c11`
  - quarantine → island → handover → valor restaurado.
- `tests/sotlas_classes_arc_impl.py::test_island_to_island_handover_runs_through_c11`
  - handover same-domain de `island` e contagem de destruições.

CI #536 passou C11, Python 3.10/3.11/3.12 em Ubuntu, Windows e macOS, além do snapshot de toolchain.

## DEFER 1.0.x

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

## DEFER 1.1+

- runtime/sincronização geral de `device` e transfer CPU↔device para todos os casos;
- ABI/lifetime geral de `external` para layouts arbitrários;
- generalizações de domínio que exijam novo contrato público;
- backends adicionais que não sejam necessários para o release inicial;
- features novas que não sejam parte do núcleo estável 1.0.

## Regra de classificação daqui em diante

Antes de trazer uma lacuna antiga da Fase 2 de volta para o caminho crítico:

1. O caso produz código incorreto ou ownership/lifetime incorreto no subset `SUPPORTED`?
   - **sim:** regressão/blocker do 1.0.
2. O caso é necessário para um exemplo básico documentado do subset `SUPPORTED`?
   - **sim:** blocker.
3. O compilador consegue rejeitá-lo de forma clara e fail-closed?
   - **sim:** backlog 1.0.x ou 1.1.
4. A mudança apenas amplia generalidade, otimização, ergonomia ou cobertura?
   - **sim:** não reabrir a Fase 2.

## Regra de desenvolvimento

```text
baseline verde
    ↓
1 blocker real ou 1 pacote coerente
    ↓
testes reais
    ↓
CI verde
    ↓
novo baseline
```

Não contornar testes, não relaxar invariantes para obter CI verde e não transformar unsupported behavior em lowering silencioso.

## Decisão de roadmap

**A Fase 2 — Ownership Domains está encerrada para o escopo Sotlas 1.0.**

Os refinamentos acima permanecem ativos como evolução pós-1.0. O desenvolvimento principal pode avançar para a Fase 3 sem apagar nem fingir que o backlog técnico deixou de existir.