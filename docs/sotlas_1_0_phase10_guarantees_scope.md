# Sotlas 1.0 — Phase 10 Guarantees Scope

**Atualizado em:** 2026-09-26
**Status:** 🟡 IN PROGRESS
**Baseline de código:** `ff5f433` — CI #598 `success`

### Refinamento local de fluxo

Branches `if`/`else` e condições booleanas compostas agora fornecem fatos
exatos para provar precondições escalares em chamadas dinâmicas. O comprovante
SIR registra esses fatos. A análise descarta refinamentos após atribuição local
ao valor ou chamada potencialmente mutável; implicações aritméticas gerais e
refinamento entre funções continuam fora deste subset.

## Subset inicial de precondições

Funções podem declarar uma condição booleana antes do corpo:

```sotlas
fn divide_by(b: i32) -> i32
    requires b != 0
{
    return 84i32 / b;
}
```

O checker valida os nomes de parâmetros, operadores e tipo booleano. No subset
atual, `requires` só é aceito em funções com corpo verificado. O checker
percorre chamadas diretas, substitui parâmetros pelos argumentos constantes e
avalia comparações booleanas suportadas. Uma condição falsa é rejeitada. Se
argumentos dinâmicos impedirem a prova estática, o backend C11 guarda a condição
no início da função e chama `abort()` caso ela falhe.

Cada chamada aprovada produz um `ContractCallProof` com função alvo, localização
na fonte, predicado e valores usados. O comprovante é anexado ao `SIRModule` e
aparece no dump como `sir_proof`.

## Limites

- argumentos dinâmicos recebem guarda no callee; ainda não são provados por
  refinamento de fluxo quando o fluxo não contém fatos de branch exatos;
- declarações `extern` são rejeitadas, pois não há corpo local onde instalar a
  guarda;
- `ensures`, `guarantee` como declaração, refinamento simbólico e relatórios
  agregados de safety ainda não estão implementados;
- o avaliador de contratos aceita expressões escalares limitadas, sem chamadas,
  acesso a campos, indexing ou prova geral de teoremas.

## Gates

- teste positivo de prova constante em ambos os frontends de compile;
- chamadas com prova falsa falham estaticamente e argumentos dinâmicos recebem
  guarda C11;
- condição com tipo não booleano e contrato `extern` são rejeitados;
- função pública inclui guarda de entrada no C11;
- comprovante verificado sobrevive ao lowering do SIR canônico;
- CI roda `tests/test_sotlas_contract_frontend.py` como gate da Fase 10.

## Blockers de 1.0

- [x] sintaxe e validação tipada de `requires` em funções com corpo;
- [x] prova e rejeição de chamadas com argumentos constantes;
- [x] comprovante source-stable preservado no SIR;
- [x] prova por fatos exatos de branch para argumentos dinâmicos, com invalidação conservadora;
- [ ] refinamento de fluxo para provar argumentos dinâmicos;
- [ ] `ensures`, declaração `guarantee` e relatórios agregados de safety;
- [ ] matriz e2e de provas por backend/target.
