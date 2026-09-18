# Sotlas — GitHub Linguist Official Registration Package

Este diretório contém os artefatos de integração preparados para o comitê do **GitHub Linguist** ([github-linguist/linguist](https://github.com/github-linguist/linguist)).

---

## Estrutura do Pacote de Integração

1. **`spec/linguist/languages.yml`:**
   Fragmento YAML canônico para inserção em `lib/linguist/languages.yml` do Linguist.
2. **`samples/Sotlas/`:**
   Amostras reais e representativas de código da linguagem:
   - `kernel_driver.sotlas`: Driver de dispositivo MMIO/PCIe com `@system`, registradores de hardware, interrupções e `asm volatile`.
   - `data_structures.sotlas`: Coleções de baixo nível (`RingBuffer forge<T>`), casamento de padrões `discern` e controle estático de capacidade.
   - `network_stack.sotlas`: Protocolo de rede zero-copy, corrotinas `async`/`await` sem alocação no heap e posse `handover`.
3. **Gramática TextMate:**
   Hospedada publicamente sob licença Apache-2.0 / MIT em:
   - Repositório oficial da organização: [`https://github.com/Sotlas/vscode-sotlas`](https://github.com/Sotlas/vscode-sotlas)
   - Arquivo: `syntaxes/sotlas.tmLanguage.json` (`scopeName: source.sotlas`).
4. **Script de Verificação Automática:**
   - `scripts/verify_linguist.py`: Valida amostras, YAML e gramática TextMate.
