# Guia Oficial de Submissão ao GitHub Linguist para a Linguagem Sotlas
## Normas, Passo a Passo do Pull Request e Estratégia de Adoção Global

Este guia documenta o processo normativo e técnico para registrar formalmente a linguagem **Sotlas** no repositório central do **GitHub Linguist** ([github-linguist/linguist](https://github.com/github-linguist/linguist)).

O **Linguist** é o motor de código aberto do GitHub responsável por:
1. Detectar as linguagens presentes em qualquer repositório Git;
2. Colorir a barra de composição percentual de linguagens no topo do repositório;
3. Aplicar *Syntax Highlighting* nativo nas páginas de visualização de código da interface web do GitHub;
4. Indexar buscas de código filtradas por linguagem (`language:sotlas`).

---

## 1. Matriz de Requisitos Formais do GitHub Linguist

Para aceitar uma nova linguagem no arquivo central `lib/linguist/languages.yml`, a equipe mantenedora do GitHub Linguist exige a satisfação estrita de 4 pilares:

| Requisito | Exigência Formal do Linguist | Situação no Ecossistema Sotlas | Status |
| :--- | :--- | :--- | :--- |
| **1. Amostras Reais** | Arquivos de código real em `samples/<Linguagem>/` (sem exemplos triviais como Hello World) | Três amostras canônicas produzidas:<br>• `kernel_driver.sotlas` (hardware/MMIO)<br>• `data_structures.sotlas` (coleções/discern)<br>• `network_stack.sotlas` (rede zero-copy/async) | **Atendido (100%)** |
| **2. Gramática TextMate** | Gramática pública JSON/YAML sob licença permissiva aberta (MIT ou Apache 2.0) | Disponível publicamente no repositório oficial da organização:<br>[`https://github.com/Sotlas/vscode-sotlas`](https://github.com/Sotlas/vscode-sotlas)<br>Arquivo: `syntaxes/sotlas.tmLanguage.json` | **Atendido (100%)** |
| **3. Configuração YAML** | Definição estruturada em `lib/linguist/languages.yml` com cor HEX, extensões e escopo | Arquivo canônico preparado em [`spec/linguist/languages.yml`](file:///c:/Projetos/LangSotlas/spec/linguist/languages.yml)<br>Cor: `#8b5cf6` (violeta oficial), Escopo: `source.sotlas` | **Atendido (100%)** |
| **4. Massa Crítica de Uso** | Pelo menos **200 repositórios públicos únicos** no GitHub OU **2.000 arquivos públicos indexáveis** | Repositórios públicos criados sob a organização [`https://github.com/Sotlas`](https://github.com/Sotlas). Enquanto a meta de 200 repositórios externos é consolidada, aplica-se a regra de `.gitattributes`. | **Roteiro em Execução** |

---

## 2. Como Ter Reconhecimento Imediato Hoje (Regra `.gitattributes`)

Enquanto a comunidade externa de desenvolvedores cria repositórios públicos na linguagem, qualquer projeto no GitHub (incluindo repositórios do BakenOS e de bibliotecas Sotlas) pode forçar o GitHub a identificar, contabilizar nas estatísticas do repositório e colorir os arquivos `.sotlas` imediatamente adicionando um arquivo `.gitattributes` na raiz:

```gitattributes
# .gitattributes
*.sotlas linguist-language=Rust linguist-detectable=true
*.sth    linguist-language=C    linguist-detectable=true
```

> [!TIP]
> O GitHub lê o arquivo `.gitattributes` a cada push no branch padrão (`main`). Com as diretivas acima, o GitHub trata todos os arquivos `.sotlas` como código executável nativo, computando nas barras de estatística de linguagem e aplicando coloração de sintaxe de alta precisão.

Quando o Pull Request no Linguist for aceito e mesclado, os repositórios passam a usar a diretiva nativa:
```gitattributes
*.sotlas linguist-language=Sotlas linguist-detectable=true
*.sth    linguist-language=Sotlas linguist-detectable=true
```

---

## 3. Passo a Passo Técnico para Enviar o Pull Request no GitHub Linguist

Quando a meta de visibilidade pública for atingida, execute o procedimento abaixo para submeter o PR oficial:

### Passo 3.1: Fazer Fork do Repositório
1. Acesse [https://github.com/github-linguist/linguist](https://github.com/github-linguist/linguist) e clique em **Fork**.
2. Clone o fork na sua máquina local:
   ```bash
   git clone https://github.com/<SEU_USUARIO>/linguist.git
   cd linguist
   git checkout -b add-sotlas-language
   ```

### Passo 3.2: Adicionar a Linguagem ao `lib/linguist/languages.yml`
Abra o arquivo `lib/linguist/languages.yml` e adicione o bloco abaixo em **ordem alfabética estrita** (entre `Solidity` e `SourcePawn` ou na posição alfabética correspondente à letra **S**):

```yaml
Sotlas:
  type: programming
  color: "#8b5cf6"
  aliases:
    - sotlas
    - baken-sotlas
  extensions:
    - ".sotlas"
    - ".sth"
  tm_scope: source.sotlas
  ace_mode: c_cpp
  codemirror_mode: clike
  language_id: 994821
```

> [!IMPORTANT]
> O campo `language_id` deve ser um número inteiro positivo único. O bot do Linguist (`Linguist Bot`) ou os mantenedores sugerirão o ID sequencial exato durante a revisão do PR.

### Passo 3.3: Copiar as Amostras Canônicas
Copie os arquivos de amostra preparados para a pasta `samples/Sotlas/` do fork do Linguist:
```bash
mkdir -p samples/Sotlas
cp /c/Projetos/LangSotlas/samples/Sotlas/*.sotlas samples/Sotlas/
```

Os 3 arquivos copiados serão:
- `samples/Sotlas/kernel_driver.sotlas`
- `samples/Sotlas/data_structures.sotlas`
- `samples/Sotlas/network_stack.sotlas`

### Passo 3.4: Adicionar a Gramática em `vendor/README.md`
No arquivo `vendor/README.md` do Linguist, adicione a entrada apontando para o repositório aberto da gramática:
```markdown
- [Sotlas](https://github.com/Sotlas/vscode-sotlas)
```

### Passo 3.5: Executar os Testes do Linguist Localmente
O Linguist utiliza Ruby e Docker. Para rodar a verificação de sanidade local:
```bash
# Executando via Bundler / Rake:
bundle install
bundle exec rake test
```
Ou valide a sanidade com o script de validação próprio incluído no repositório Sotlas:
```bash
py -3 scripts/verify_linguist.py
```

### Passo 3.6: Criar o Commit e Abrir o Pull Request
```bash
git add lib/linguist/languages.yml samples/Sotlas vendor/README.md
git commit -m "Add support for Sotlas language"
git push origin add-sotlas-language
```

Abra o Pull Request no GitHub com a seguinte descrição estruturada:

```markdown
### Language Name
Sotlas

### Link to the language official website
https://sotlas.org / https://github.com/Sotlas

### URL to an open source grammar
https://github.com/Sotlas/vscode-sotlas (syntaxes/sotlas.tmLanguage.json)

### Examples of code in public repositories
- https://github.com/Sotlas/sotlas
- https://github.com/Sotlas/vscode-sotlas
- https://github.com/Sotlas/docs
- https://github.com/Sotlas/rfcs

### Description
Sotlas is a high-performance, deterministic systems programming language designed for bare-metal, operating systems kernels, and safety-critical infrastructure, featuring memory capability safety and zero-cost abstraction semantics.
```

---

## 4. Script de Autoverificação Contínua

O repositório disponibiliza o utilitário [`scripts/verify_linguist.py`](file:///c:/Projetos/LangSotlas/scripts/verify_linguist.py) que valida automaticamente:
- A sintaxe e compilação nativa de todas as amostras via `bin/sotlas.exe`;
- A integridade JSON da gramática TextMate;
- O preenchimento de todos os campos normativos do YAML.

Para executar a verificação a qualquer momento:
```bash
py -3 scripts/verify_linguist.py
```
Resultado esperado: `[SUCESSO] Todos os requisitos de submissão ao GitHub Linguist atendidos!`
