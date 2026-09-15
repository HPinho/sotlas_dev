# Sotlas for Visual Studio Code & Open VSX

Extensão oficial de suporte para a linguagem de programação **Sotlas** (`.sotlas`, `.sth`).

**Sotlas** é uma linguagem de programação moderna, segura e expressiva de propósito geral e sistemas — projetada com infinitas possibilidades, desde o mais baixo nível (bare-metal, kernels monolíticos/microkernels, drivers e embarcados) até o alto nível (engines de jogos, ferramentas de linha de comando, serviços de rede e aplicativos).

---

## Recursos Principais

- **Diagnósticos Nativos em Tempo Real (Zero Dependências)**:
  - Sublinhados vermelhos para erros de sintaxe (chaves/parênteses/colchetes desbalanceados, strings não fechadas, ponto e vírgula ausentes, tipos incorretos).
  - Sublinhados amarelos para avisos de código e boas práticas de estruturação.
  - Funciona imediatamente em 100% dos computadores (Windows, Linux, macOS) assim que instalado, sem requerer Python ou binários externos instalados.
- **Navegação de Símbolos e Outline**:
  - Árvore de navegação no painel *Outline* do editor e menu rápido de símbolos (`Ctrl+Shift+O`).
- **Documentação ao Passar o Mouse (Hover Tooltips)**:
  - Explicações conceituais ricas para palavras-chave (`sole`, `co-owned`, `rawphys`, `barecore`, `quarantine`, `discern`, `guard`, etc.).
- **Realce de Sintaxe Completo**:
  - Palavras-chave de controle e fluxo: `discern`, `match`, `if`, `guard`, `defer`, etc.
  - Palavras-chave de declaração e arquitetura: `forge`, `enclave`, `fn`, `trapfn`, `struct`, `mesh`, `barecore`.
  - Ponteiros de Topologia e Segurança Física: `*rawphys`, `*virtmap`, `*portwire`, `*dmazone`, `*voidzero`.
  - Operadores de Registradores e Bits: `.slit[lo..hi]`, `.notch[n]`, `.strand[len]`.
  - Primitivas SRG & Concorrência: `pulse`, `probe`, `clinch`, `rebound`, `quarantine`.
- **Servidor de Linguagem (LSP) Integrado**:
  - Autocompletar inteligente para instruções, registradores e funções da biblioteca base.
  - Informações de tipo e documentação ao passar o mouse (*Hover*).
  - Formatação automática de código (*Format Document*).
  - Ir para Definição (*Go to Definition*).
- **Ferramentas de Desenvolvimento e Comandos Integrados**:
  - `Sotlas: Compilar Pacote Atual` (`sotlas.build`)
  - `Sotlas: Verificar Tipos e Sintaxe` (`sotlas.check`)
  - `Sotlas: Formatar Arquivo Atual` (`sotlas.format`)
  - `Sotlas: Abrir Sotlas Studio (Navegador)` (`sotlas.studio`)
  - `Sotlas: Iniciar Terminal Interativo (REPL)` (`sotlas.repl`)
  - `Sotlas: Emitir WebAssembly (.wat)` (`sotlas.dumpWasm`)
  - `Sotlas: Reiniciar Servidor de Linguagem (LSP)` (`sotlas.restartServer`)

---

## Requisitos

Para que o LSP e os comandos funcionem, instale a toolchain do Sotlas e garanta que `sotlas` esteja acessivel no seu `PATH`:

```powershell
# No Windows (PowerShell):
irm https://raw.githubusercontent.com/HPinho/LangSotlas/main/packaging/install.ps1 | iex
```

```bash
# No Linux / macOS:
curl -fsSL https://raw.githubusercontent.com/HPinho/LangSotlas/main/packaging/install.sh | bash
```

---

## Configuracoes

| Configuracao | Padrao | Descricao |
| :--- | :--- | :--- |
| `sotlas.compilerPath` | `"sotlas"` | Caminho para o binario executavel do compilador Sotlas. |

---

## Empacotamento e Instalacao Local (.vsix)

Para gerar o pacote instalavel da extensao:

```bash
cd editors/vscode
npm install
npm run compile
npx @vscode/vsce package
```

Isto gera o arquivo `sotlas-0.3.0.vsix`. Para instalar no seu VS Code imediatamente:

```bash
code --install-extension sotlas-0.3.0.vsix
```

---

## Licenca

Distribuido sob a licenca Apache 2.0 com LLVM Exception.
Copyright (c) 2026 Hiago Pinho e contribuidores do projeto Sotlas.
