# Sotlas — Release Roadmap

**Status:** CANONICAL RELEASE GUIDE  
**Atualizado em:** 2026-09-30 (America/Fortaleza)  
**Aplica-se a:** linguagem, compilador, runtimes, stdlib, toolchain, extensões oficiais e releases públicas do ecossistema Sotlas  
**Fonte arquitetural:** [`sotlas_master_roadmap.md`](./sotlas_master_roadmap.md)  
**Ordem de desenvolvimento:** [`sotlas_development_blueprint.md`](./sotlas_development_blueprint.md)  
**Backlog e gaps técnicos:** [`sotlas_full_implementation_plan.md`](./sotlas_full_implementation_plan.md)  
**Estado certificado:** [`sotlas_implementation_status.md`](./sotlas_implementation_status.md)  
**Mapa dos documentos:** [`README.md`](./README.md)

---

## 0. Regra canônica de lançamentos

Este documento é a autoridade para **quando e como uma atualização pública do Sotlas pode ser lançada**.

> O Sotlas não esperará a implementação de toda a visão de longo prazo para publicar novas versões. O desenvolvimento será organizado em ciclos de capacidades coerentes. Quando um conjunto de marcos formar uma entrega verificável, documentada e com gates verdes, ele poderá ser fechado como release público; depois disso, o desenvolvimento avança para o próximo conjunto de capacidades.

Essa regra é permanente enquanto este documento possuir status `CANONICAL RELEASE GUIDE`.

Nenhum roadmap técnico substitui este arquivo para decisões de corte de release. Ao mesmo tempo, este arquivo **não substitui** a especificação semântica, o plano técnico, os tracks verticais ou a realidade certificada.

Se houver lacuna, ambiguidade ou informação aparentemente contraditória, é obrigatório consultar a rede documental definida na seção 2 antes de tomar uma decisão.

---

# 1. Princípios de release

## 1.1 Releases são orientados por capacidade, não por calendário

Sotlas não deve lançar uma versão apenas porque passou determinado número de dias.

Um release de feature nasce quando existe uma capacidade coerente que pode ser explicada, testada e demonstrada de ponta a ponta.

Exemplos de capacidades coerentes:

- backend nativo e ABI suficientemente fechados para o escopo declarado;
- caminho systems/freestanding verificável;
- criação de aplicações reais;
- runtime/stdlib hosted utilizável;
- UI e aplicações gráficas;
- concorrência/networking;
- realtime/game/HPC;
- heterogeneous compute;
- self-host/toolchain sovereignty.

## 1.2 Não esperar o roadmap inteiro

O Master Roadmap é uma visão de longo prazo. Ele não é uma lista que precisa chegar a 100% para que uma nova versão pública exista.

A política correta é:

```text
DESENVOLVER
    ↓
FECHAR MARCO COERENTE
    ↓
FEATURE FREEZE CURTO
    ↓
HARDENING / CORREÇÕES
    ↓
GATES E2E + CI VERDE
    ↓
DOCUMENTAR ESCOPO REAL
    ↓
PUBLICAR
    ↓
ABRIR PRÓXIMO CICLO
```

## 1.3 Correções e melhorias continuam entre releases grandes

Durante qualquer ciclo ativo, podem continuar entrando:

- bug fixes;
- regressões corrigidas;
- diagnósticos melhores;
- performance sem perda de correção;
- documentação;
- LSP/VS Code/Open VSX;
- tooling;
- hardening de features já existentes;
- features pequenas que respeitem a arquitetura;
- novos verbetes Sotlas quando possuírem semântica própria justificada.

Essas melhorias não podem desviar silenciosamente o objetivo do ciclo principal.

## 1.4 Nenhum release pode depender de gambiarra

Continuam obrigatórias as regras gerais do projeto:

- não enfraquecer/remover testes para obter verde;
- corrigir regressão antes de avançar feature work;
- formas não suportadas falham fechado;
- não criar bypass específico para Baken, app, game, IA ou qualquer consumidor;
- uma primitiva descoberta por um consumidor deve ser promovida como capacidade geral quando for parte da linguagem/toolchain;
- `PREVIEW` não pode ser anunciado como suporte geral.

---

# 2. Rede documental obrigatória

Os documentos abaixo formam um sistema. Nenhum deles deve ser interpretado isoladamente quando a decisão ultrapassa sua responsabilidade.

| Documento | Pergunta principal que responde | Autoridade |
|---|---|---|
| [`sotlas_master_roadmap.md`](./sotlas_master_roadmap.md) | **O que Sotlas é e quais semânticas/arquiteturas deve possuir?** | arquitetura e semântica mestra |
| [`sotlas_development_blueprint.md`](./sotlas_development_blueprint.md) | **Em que ordem construir e como as trilhas dependem umas das outras?** | execução do desenvolvimento e tracks |
| [`sotlas_full_implementation_plan.md`](./sotlas_full_implementation_plan.md) | **O que falta tecnicamente e quais gaps concretos estão abertos?** | backlog técnico amplo; detalhes K0–K14 |
| [`sotlas_implementation_status.md`](./sotlas_implementation_status.md) | **O que está realmente certificado agora?** | realidade operacional do escopo declarado |
| [`sotlas_release_roadmap.md`](./sotlas_release_roadmap.md) | **Quando um conjunto pode virar release e como publicá-lo?** | política e gates de lançamento |
| [`README.md`](./README.md) | **Qual documento consultar quando falta contexto?** | mapa/roteamento documental |

## 2.1 Regra de resolução de lacunas

Quando uma informação não estiver no documento atual:

```text
semântica / significado de feature
        → Master Roadmap

ordem / dependência / track vertical
        → Development Blueprint

gap técnico / tarefa concreta / kernel K0–K14
        → Full Implementation Plan

estado real / certificado / preview
        → Implementation Status + testes/CI

release / corte / freeze / publicação / versionamento
        → Release Roadmap
```

Se dois documentos parecerem divergir, eles não devem ser “reconciliados por suposição”. Deve-se verificar qual deles possui autoridade sobre aquela dimensão e atualizar os documentos relacionados quando a decisão arquitetural mudar.

## 2.2 Obrigação de sincronização

Uma mudança importante que afete mais de uma dimensão deve atualizar a rede documental correspondente.

Exemplos:

- nova semântica → Master + Blueprint/Full Plan quando alterar dependências;
- novo milestone ou track → Blueprint + Full Plan + Release Roadmap se alterar um ciclo público;
- fechamento de capacidade → Implementation Status + Release Roadmap;
- mudança no gate de kernel → Full Plan + Blueprint K + Release Roadmap quando afetar claim público;
- mudança de escopo de apps/UI/game/AI/HPC → Blueprint + Release Roadmap;
- release público → changelogs, status, manifests e este roadmap quando o ciclo mudar.

---

# 3. Relação com as fases, fundações e tracks

O release roadmap **não cria uma segunda arquitetura**.

Ele agrupa marcos existentes em entregas públicas.

A relação geral é:

```text
MASTER ROADMAP
     ↓
Fases semânticas / arquitetura da linguagem
     ↓
DEVELOPMENT BLUEPRINT
     ├── F / IR / BE / RT / NUM / H
     ├── APP
     ├── UI
     ├── GAME
     ├── AI
     ├── HPC
     ├── KERNEL
     ├── DATA / NETWORK
     ├── MEDIA
     ├── WEB
     ├── SELF-HOST
     └── TOOLING
     ↓
FULL IMPLEMENTATION PLAN
     ↓
trabalho concreto + gaps + K0–K14 + M16.x
     ↓
IMPLEMENTATION STATUS / TESTS / CI
     ↓
RELEASE ROADMAP
     ↓
PUBLIC RELEASE
```

Uma vertical nunca ganha semântica paralela. APP, UI, GAME, AI, KERNEL e demais tracks consomem as mesmas fundações compartilhadas.

---

# 4. Modelo de ciclos públicos

Os nomes abaixo representam **famílias de capacidade**, não números de versão fixos.

O número real será escolhido apenas no fechamento do release conforme a seção 9.

## R-SYS — Machine, Systems e Kernel-Enabling Foundation

**Estado:** CICLO ATIVO.

Fontes principais:

- Master Roadmap: Fases 15–16 e semânticas de memória/authority/execution necessárias;
- Blueprint: F, IR, BE e Trilha K;
- Full Plan: M16.x e K0–K14;
- Implementation Status: evidência do que já está certificado.

Objetivo público:

> Entregar uma fundação nativa/systems substancial e verificável, capaz de sustentar código nativo real e desbloquear progressivamente freestanding/kernel sem transformar Sotlas numa linguagem específica de kernel.

O ciclo atual pode fechar um release **antes de K14**. A claim pública precisa distinguir:

- backend nativo funcional;
- kernel-enabling/freestanding foundation;
- kernel bootável, que somente pode ser anunciado quando o gate K correspondente — em especial o caminho até K7 — estiver certificado.

Critérios mínimos do corte devem ser congelados no início do release hardening. O corte deve incluir um subconjunto coerente de M16/BE com E2E real, seus contratos ABI/backend e os gates systems que forem anunciados.

Não é permitido anunciar “kernel support” apenas porque `kernel_main` existe ou porque M16 avançou.

### Depois de R-SYS

O desenvolvimento principal migra para capacidades de aplicação, mantendo hardening systems/kernel em paralelo.

---

## R-APP — Application Foundation

Fontes principais:

- Blueprint: APP0–APP4;
- RT1–RT6;
- F1/F3/F4 conforme necessário;
- IR/BE hosted;
- Full Plan para gaps de tipos, strings, containers, ABI e runtime.

Objetivo público:

> Tornar possível escrever, testar, compilar e distribuir uma aplicação hosted representativa em Sotlas usando runtime/stdlib reais, sem adapters privados do exemplo.

Prioridades típicas:

- entry/main model estável;
- allocator hosted;
- strings/slices;
- collections baseline;
- error/result model;
- filesystem/path/environment/time;
- process/runtime services essenciais;
- package/build artifact utilizável;
- aplicação CLI representativa E2E;
- networking/threads quando fizerem parte do corte escolhido.

O release não exige que APP4 inteiro esteja perfeito em todas as plataformas. O scope publicado deve listar exatamente os targets e APIs certificados.

---

## R-UI — Graphics, Desktop e UI Foundation

Fontes principais:

- Blueprint: UI0–UI9 + APP3;
- RT5/event loop;
- NUM/SIMD quando necessário;
- H para aceleração GPU posterior.

Objetivo público:

> Provar aplicações gráficas Sotlas com window/event lifecycle, rendering surface, input e frame scheduling reais, mantendo UI/compositor fora do compilador e fora do kernel core.

Claims de animação fluida exigem os gates de frame clock/frame pacing definidos no Blueprint.

---

## R-CONC — Concurrency, Networking e Services

Fontes principais:

- RT4–RT6;
- APP2;
- DATA D1–D3;
- Effects/Authority/Trust relevantes.

Objetivo público:

> Consolidar threads/atomics/synchronization, event-driven IO, sockets e workloads de serviço de forma coerente com ownership/effects.

---

## R-REALTIME — Game, Media e Performance-Oriented Runtime

Fontes principais:

- GAME;
- MEDIA;
- NUM/SIMD;
- RT concurrency;
- Heterogeneous quando necessário.

Objetivo público:

> Entregar fundações reutilizáveis de realtime, memória previsível, timing, SIMD, áudio/rendering/task workloads e provas progressivas de engine.

Nunca usar “AAA ready” antes do gate G14.

---

## R-HET — GPU/NPU, AI e HPC

Fontes principais:

- H0–H4;
- AI0–AI11;
- HPC0–HPC4;
- NUM0–NUM4;
- Ownership `device`, Authority, Effects e Trust.

Objetivo público:

> Consolidar execution providers, device memory, kernels e workloads numéricos/AI com claims separados para CPU, GPU, NPU, inference e training.

Nunca condensar tudo em “AI supported”.

---

## R-SOV — Self-host e Toolchain Sovereignty

Fontes principais:

- SH0–SH5;
- BE object writer/linker;
- TOOL;
- build/package infrastructure.

Objetivo público:

> Aumentar progressivamente a parcela do compilador/toolchain escrita ou controlada pelo próprio Sotlas, sem remover Stage 0 ou dependências antes da paridade comprovada.

---

# 5. Tracks paralelos não esperam uns pelos outros artificialmente

Os ciclos públicos fornecem foco, mas não transformam o desenvolvimento numa fila rígida.

Exemplo:

```text
R-SYS ativo
   ├── principal: M16 / BE / object / ABI
   ├── paralelo: K hardening
   ├── paralelo: bug fixes
   ├── paralelo: ownership/effects hardening
   ├── paralelo: LSP/editor/docs
   └── preparação segura de RT/APP
```

Depois:

```text
R-APP ativo
   ├── principal: runtime + app foundation
   ├── systems/kernel continuam recebendo correções
   ├── backend continua amadurecendo
   ├── editor/tooling continua evoluindo
   └── UI pode iniciar dependências que já estejam desbloqueadas
```

A prioridade principal muda; a arquitetura compartilhada não é congelada.

---

# 6. Estados de um ciclo de release

Cada release de feature percorre explicitamente estes estados:

## OPEN DEVELOPMENT

- feature work ativo;
- escopo ainda pode ser ajustado;
- previews não são claims públicos de suporte geral.

## MILESTONE CLOSURE

- identifica-se um conjunto coerente de marcos suficientemente fechado;
- dependências e gaps restantes são classificados;
- decide-se o que entra e o que fica para o próximo ciclo.

## RELEASE SCOPE FREEZE

Cria-se um escopo explícito com:

- capacidades incluídas;
- targets incluídos;
- APIs/keywords incluídos;
- previews incluídos mas claramente rotulados;
- exclusões conhecidas;
- gates obrigatórios.

Após esse ponto, feature creep não entra sem reabrir formalmente o scope.

## HARDENING

Prioridade muda para:

1. regressões;
2. bugs;
3. diagnostics;
4. cross-backend consistency;
5. E2E;
6. performance regressions relevantes;
7. documentação;
8. packaging/editor.

## RELEASE CANDIDATE

Exige:

- baseline verde identificada;
- changelog candidato;
- artefatos candidatos;
- matriz de suporte explícita;
- exemplos usando somente suporte do release;
- previews rotulados.

## PUBLIC RELEASE

Somente depois do checklist da seção 7.

## POST-RELEASE

- registrar baseline/tag/artefatos;
- corrigir regressões publicadas com prioridade;
- iniciar próximo ciclo;
- carregar gaps não fechados para Full Plan/Blueprint, sem apagá-los.

---

# 7. Gate obrigatório de release público

Nenhuma release pública de feature deve ser tratada como fechada sem verificar, conforme aplicável:

## Arquitetura e linguagem

- [ ] scope compatível com o Master Roadmap;
- [ ] semântica nova documentada;
- [ ] nenhum verbete novo existe apenas como renome de conceito convencional sem justificativa;
- [ ] parser/Typed AST/semantic checks coerentes;
- [ ] formas inválidas diagnosticadas;
- [ ] unsupported permanece fail-closed.

## IR/backend/runtime

- [ ] SIR/Target IR/runtime contract preserva a semântica necessária;
- [ ] backend/provider real existe para os claims anunciados;
- [ ] ABI/layout/lifetime definidos quando aplicáveis;
- [ ] positive tests;
- [ ] negative tests;
- [ ] E2E representativo;
- [ ] differential tests quando múltiplos backends compartilham o claim.

## Qualidade

- [ ] CI completo verde na baseline candidata;
- [ ] nenhuma regressão conhecida classificada como blocker permanece aberta;
- [ ] testes não foram removidos/enfraquecidos para obter verde;
- [ ] stress/performance gates relevantes não regrediram sem explicação.

## Documentação

- [ ] `sotlas_implementation_status.md` reflete o estado real;
- [ ] `sotlas_full_implementation_plan.md` mantém os gaps não fechados;
- [ ] Blueprint continua coerente com a ordem/tracks;
- [ ] este Release Roadmap identifica o ciclo ativo/seguinte quando necessário;
- [ ] CHANGELOG atualizado;
- [ ] support matrix atualizada;
- [ ] exemplos não apresentam PREVIEW como stable;
- [ ] migration notes quando houver incompatibilidade.

## Tooling/ecossistema

- [ ] CLI/reporting coerente;
- [ ] LSP/editor reconhece sintaxe pública nova relevante;
- [ ] VS Code package/changelog coerentes;
- [ ] Visual Studio Marketplace e Open VSX recebem o mesmo conteúdo funcional quando a release inclui atualização de extensão;
- [ ] smoke test do VSIX/package relevante;
- [ ] manifests não possuem número de versão contraditório.

---

# 8. Releases de manutenção entre marcos

Não é obrigatório esperar o próximo grande ciclo para corrigir usuários.

Podem existir releases intermediários para:

- bug crítico;
- regressão;
- diagnóstico;
- documentação;
- editor/LSP;
- packaging;
- performance sem alteração semântica incompatível;
- pequena feature já completamente suportada e compatível com o ciclo vigente.

Esses releases não devem fingir fechamento de uma vertical que ainda está em construção.

## 8.1 Hotfix emergencial

Falha crítica/security/release-breaking pode gerar hotfix fora da cadência de feature, mas nunca autoriza:

- ignorar os testes relevantes;
- ocultar regressão;
- alterar semântica silenciosamente;
- publicar um artefato diferente entre marketplaces sem registrar a diferença.

---

# 9. Política de versionamento

## 9.1 O número é consequência do scope

Este roadmap deliberadamente **não fixa agora** qual será o número de cada ciclo.

A ordem é:

```text
fechar capacidade
      ↓
congelar scope
      ↓
analisar compatibilidade e maturidade
      ↓
escolher número de versão
      ↓
sincronizar manifests/changelogs
      ↓
release candidate
      ↓
publicar
```

O número não deve dirigir a arquitetura.

## 9.2 Sincronização obrigatória

Antes de publicar, auditar pelo menos:

- versão da distribuição/compilador;
- versão declarada da linguagem/contract quando existir separadamente;
- `CHANGELOG.md` principal;
- `editors/vscode/package.json`;
- `editors/vscode/CHANGELOG.md`;
- nome do VSIX;
- tag/release Git;
- Marketplace;
- Open VSX;
- documentação pública.

Se linguagem e extensão usarem versionamento independente, essa independência deve ser explícita; não podem parecer a mesma versão quando representam artefatos diferentes.

---

# 10. Política de verbetes próprios do Sotlas

A identidade da linguagem deve nascer de semântica, não de troca cosmética de nomes.

Um novo verbete/keyword próprio pode ser considerado quando:

1. representa semântica que Sotlas realmente trata de maneira distinta;
2. melhora leitura e comunicação do contrato;
3. possui definição suficientemente precisa;
4. atravessa os layers relevantes;
5. possui diagnostics e testes;
6. é registrado no Master Roadmap e na documentação pública pertinente.

Se Sotlas implementa exatamente um conceito convencional sem diferença semântica útil, o termo convencional deve ser preferido.

Verbetes já existentes como `sole`, `whisper`, `handover`, `island`, `mould` e `probe` não constituem licença para inventar palavras sem necessidade arquitetural.

Um release que introduza novo verbete deve explicar:

- por que ele existe;
- sua semântica;
- como difere de conceitos próximos;
- seu custo/efeito runtime quando houver;
- shapes suportados;
- shapes ainda fail-closed.

---

# 11. Claims públicos por vertical

Release notes devem usar claims granulares.

## Kernel

Distinguir:

- source contract;
- freestanding object;
- linker/image;
- boot QEMU/firmware;
- runtime/kernel subsystems.

Só chamar kernel bootável depois do gate E2E correspondente.

## Apps

Distinguir:

- CLI baseline;
- hosted runtime;
- filesystem/network;
- desktop;
- cross-platform.

## UI

Distinguir:

- window creation;
- event/input;
- rendering;
- compositor;
- animation/frame pacing;
- GPU acceleration.

## Game

Distinguir linguagem adequada a workloads, engine foundation e gate AAA. Não antecipar G14.

## AI/HPC

Distinguir tensor API, CPU kernels, GPU/NPU, inference, autograd, training e distributed.

## Toolchain

Distinguir self-host source modules, Stage1, fixed point, backend próprio, object writer e linker.

---

# 12. Registro de um corte de release

Quando um release entrar em `RELEASE SCOPE FREEZE`, criar/atualizar documentação contendo no mínimo:

```text
Release candidate: <a definir>
Ciclo: R-...
Baseline candidata: <sha>
Targets certificados: ...
Capacidades SUPPORTED: ...
Capacidades PREVIEW: ...
Capacidades explicitamente fora do scope: ...
Gates obrigatórios: ...
Known limitations: ...
Migration notes: ...
Extension/tooling package: ...
```

Nenhuma limitação é apagada apenas para simplificar a release note.

---

# 13. Relação com o ciclo atual

Na criação deste documento, a linha principal está no ciclo **R-SYS**, com trabalho imediato no backend x86-64 Sotlas-owned / M16.x e dependências systems/kernel.

O avanço atual em calls/ABI é parte dessa fundação, mas M16 não deve ser interpretado como “kernel inteiro”. Ele é infraestrutura compartilhada também por apps, runtimes, engines e tooling nativo.

A intenção operacional acordada é:

```text
FECHAR UM MARCO SYSTEMS/NATIVE COERENTE
        ↓
HARDENING
        ↓
RELEASE PÚBLICO
        ↓
ABRIR R-APP COMO FOCO PRINCIPAL
        ↓
continuar kernel/backend hardening em paralelo
        ↓
FECHAR APPLICATION FOUNDATION
        ↓
NOVO RELEASE PÚBLICO
        ↓
seguir para UI/graphics e demais ciclos conforme dependências
```

O release de R-SYS não deve esperar a visão completa do Sotlas. O release de R-APP não deve esperar UI, game ou AI completos. Cada release afirma apenas o que seus gates provaram.

---

# 14. Regra final

> **Sempre seguiremos este roadmap para organizar lançamentos públicos do Sotlas.**

Mudanças nessa política precisam ser explícitas, documentadas e compatibilizadas com o Master Roadmap, Development Blueprint, Full Implementation Plan e Implementation Status.

A ausência de informação em um documento não autoriza inferência silenciosa: consulte a rede documental, encontre a autoridade adequada e, se a brecha for real, atualize os documentos antes de usar a nova interpretação como base de desenvolvimento ou release.
