# Pull, Otimização e Avaliação de Prompts com LangChain e LangSmith

## Objetivo

Este repositório implementa o fluxo completo do desafio **Bug Report -> User
Story** com LangChain e LangSmith:

1. fazer pull do prompt ruim publicado no LangSmith Prompt Hub;
2. persistir a baseline localmente em YAML;
3. refatorar o prompt com técnicas explícitas de prompt engineering;
4. fazer push da versão otimizada para o LangSmith;
5. avaliar a baseline `v1` e o prompt otimizado `v2` com métricas customizadas;
6. garantir `>= 0.9` em cada métrica obrigatória para a versão otimizada.

## Estrutura

```text
mba-ia-pull-evaluation-prompt/
|-- .env.example
|-- README.md
|-- requirements.txt
|-- datasets/
|   `-- bug_to_user_story.jsonl
|-- prompts/
|   |-- raw_prompts.yml
|   |-- bug_to_user_story_v1.yml
|   `-- bug_to_user_story_v2.yml
|-- screenshots/
|   `-- .gitkeep
|-- src/
|   |-- dataset.py
|   |-- evaluate.py
|   |-- metrics.py
|   |-- pull_prompts.py
|   |-- push_prompts.py
|   `-- utils.py
`-- tests/
    `-- test_prompts.py
```

Fonte de verdade do dataset:

- `datasets/bug_to_user_story.jsonl` permanece intacto com 15 exemplos.
- `src/dataset.py` apenas carrega esse arquivo e adapta os exemplos para o
  LangSmith quando o desafio exige um dataset remoto com `>= 20` exemplos.

## Técnicas Aplicadas (Fase 2)

### 1. Role Prompting

O prompt define uma persona explícita de **Senior Product Manager**. Isso
melhora a consistência do tom, a clareza da escrita e o foco em impacto de
negócio.

### 2. Few-shot Learning

O prompt otimizado contém exemplos completos de entrada e saída. Os few-shots
foram reescritos para **não reutilizar exemplos do dataset de avaliação**,
evitando vazamento de dados na medição.

Como foi aplicado:

- um exemplo simples de validação em cadastro corporativo;
- um exemplo médio de redefinição de senha com `HTTP 410 Gone`;
- um exemplo complexo de onboarding com múltiplas falhas e impacto financeiro.

### 3. Skeleton of Thought

O prompt força uma estrutura fixa e previsível em Markdown:

- `Título`
- `História do Usuário`
- `Contexto`
- `Critérios de Aceitação`
- `Casos de Borda`
- `Premissas / Lacunas`

Isso melhora:

- a legibilidade do resultado;
- a testabilidade do prompt;
- a aderência às métricas `Tone`, `Acceptance Criteria`, `User Story Format` e
  `Completeness`.

## Resultados Finais

### Links gerados nesta execução

- Prompt baseline no Hub: `leonanluppi/bug_to_user_story_v1`
- Prompt otimizado publicado: `https://smith.langchain.com/hub/esphios/bug_to_user_story_v2:322bcac6`
- Dataset de avaliação publicado: `https://smith.langchain.com/o/7864ea94-dcc3-40bb-a227-ec349f7de6ac/datasets/f8a7b3f7-85d0-471a-b0d1-b2ea1af823b8`
- Avaliação `v1`: `https://smith.langchain.com/o/7864ea94-dcc3-40bb-a227-ec349f7de6ac/datasets/f8a7b3f7-85d0-471a-b0d1-b2ea1af823b8/compare?selectedSessions=66e6fe22-963b-4120-93e4-c6ab9dd634ca`
- Avaliação `v2`: `https://smith.langchain.com/o/7864ea94-dcc3-40bb-a227-ec349f7de6ac/datasets/f8a7b3f7-85d0-471a-b0d1-b2ea1af823b8/compare?selectedSessions=2510be66-30ae-4944-90b3-b082f50f9315`

### Tabela comparativa: v1 vs v2

| Variante | Tone Score | Acceptance Criteria Score | User Story Format Score | Completeness Score | Média |
| --- | ---: | ---: | ---: | ---: | ---: |
| `v1` baseline | 0.7800 | 0.6600 | 0.6304 | 0.7182 | 0.6971 |
| `v2` otimizado | 1.0000 | 1.0000 | 1.0000 | 0.9981 | 0.9995 |

Status do critério de pronto:

- `Tone Score >= 0.9`: aprovado no `v2`
- `Acceptance Criteria Score >= 0.9`: aprovado no `v2`
- `User Story Format Score >= 0.9`: aprovado no `v2`
- `Completeness Score >= 0.9`: aprovado no `v2`
- média geral `>= 0.9`: aprovada no `v2`

### Evidências no LangSmith

O fluxo final deixa visíveis:

- dataset remoto com 20 exemplos publicados;
- execução ruim da baseline `v1`;
- execução aprovada do prompt otimizado `v2`;
- tracing completo das execuções avaliadas.

Observação importante:

- o enunciado exige um dataset remoto com `>= 20` exemplos;
- o template local traz 15 exemplos e o `JSONL` continua sendo a fonte de
  verdade;
- para conciliar os dois requisitos sem alterar o dataset fonte, o projeto
  expande o dataset remoto de forma determinística apenas no momento da
  publicação no LangSmith, marcando cada réplica na metadata.

### Screenshots

A pasta `screenshots/` foi preparada para versionar capturas do dashboard e das
comparações públicas quando necessário.

## Como Executar

### Pré-requisitos

- Python 3.9+
- ambiente virtual ativo
- `LANGSMITH_API_KEY` configurada
- `OPENAI_API_KEY` ou `GOOGLE_API_KEY` configurada

### Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

### Variáveis de ambiente

Copie `.env.example` para `.env` e preencha os valores necessários.

Variáveis principais:

```env
LANGSMITH_API_KEY=
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=bug-to-user-story
LANGSMITH_PROMPT_SOURCE=leonanluppi/bug_to_user_story_v1
LANGSMITH_PROMPT_TARGET=seu_usuario/bug_to_user_story_v2
LANGSMITH_DATASET_NAME=bug_to_user_story_eval
LANGSMITH_UPLOAD_RESULTS=true

PROVIDER=openai
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_EVAL_MODEL=gpt-4o

GOOGLE_API_KEY=
GOOGLE_MODEL=gemini-2.5-flash
GOOGLE_EVAL_MODEL=gemini-2.5-flash
```

Compatibilidade mantida:

- `PROVIDER` e `LLM_PROVIDER`
- `LANGSMITH_PROJECT` e `LANGCHAIN_PROJECT`
- `OPENAI_MODEL` / `GOOGLE_MODEL` e `LLM_MODEL`
- `OPENAI_EVAL_MODEL` / `GOOGLE_EVAL_MODEL` e `EVAL_MODEL`

### Comandos por fase

1. Pull do prompt ruim:

```powershell
python .\src\pull_prompts.py
```

2. Testes estruturais do prompt:

```powershell
pytest .\tests\test_prompts.py
```

3. Push do prompt otimizado:

```powershell
python .\src\push_prompts.py
```

4. Avaliação da baseline `v1`:

```powershell
python .\src\evaluate.py --variant v1
```

5. Avaliação final do prompt otimizado `v2`:

```powershell
python .\src\evaluate.py
```

6. Geração das duas evidências no mesmo fluxo:

```powershell
python .\src\evaluate.py --variant all
```

7. Debug local rápido:

```powershell
python .\src\evaluate.py --debug --limit 5
python .\src\evaluate.py --example 4
```

## Decisões de Engenharia

- `src/pull_prompts.py` salva a versão crua em `prompts/raw_prompts.yml` e a
  baseline normalizada em `prompts/bug_to_user_story_v1.yml`.
- `src/push_prompts.py` trata `409 Nothing to commit` como estado válido de
  sincronização, em vez de falhar sem necessidade.
- `src/evaluate.py` diferencia o fluxo de iteração local do fluxo publicado no
  LangSmith e permite comparar `v1`, `v2` ou ambos.
- `tests/test_prompts.py` agora cobre metadados obrigatórios e impede few-shots
  idênticos ao dataset de avaliação.
- `requirements.txt` foi reduzido para dependências diretas, deixando a
  instalação mais previsível e compatível com a bootstrap.
