# AGENTS.md

## Objetivo do repositório

Este repositório implementa um fluxo de engenharia de prompts para o caso de
uso "Bug Report -> User Story" com LangChain e LangSmith.

O sistema deve ser capaz de:

1. fazer pull de prompts ruins do Prompt Hub;
2. persistir esses prompts localmente em YAML;
3. refatorar o prompt com técnicas explícitas;
4. fazer push da nova versão para o LangSmith;
5. avaliar a qualidade com métricas customizadas;
6. atingir `>= 0.9` em cada métrica obrigatória.

## Prioridades do projeto

Quando houver conflito entre referências, siga esta ordem:

1. desafio;
2. estrutura existente do repositório;
3. boas práticas de engenharia;
4. guia complementar.

## Estrutura e fonte de verdade

- `datasets/bug_to_user_story.jsonl` é a fonte de verdade do dataset.
- `src/dataset.py` deve apenas carregar e adaptar esse arquivo.
- `prompts/bug_to_user_story_v2.yml` é o prompt otimizado principal.
- `prompts/bug_to_user_story_v1.yml` representa a baseline de baixa qualidade.
- `prompts/raw_prompts.yml` guarda a versão crua puxada do LangSmith.

## Regras de engenharia

- Python 3.9+
- Código simples, pequeno e previsível
- Scripts CLI devem funcionar via `python .\src\<arquivo>.py` no PowerShell
- Nunca commitar `.env`
- Sempre manter `.env.example` atualizado
- Evitar duplicação do dataset em arquivos Python quando o JSONL já existir
- Não alterar o dataset para facilitar as métricas
- Não esconder regras em scripts soltos fora de `src/`
- Todo texto voltado a desenvolvedores ou usuários em comentários, prompts,
  mensagens CLI e documentação deve estar em pt-BR com acentuação correta

## Regras do prompt

O prompt otimizado deve:

- definir uma persona clara;
- usar `system_prompt` e `user_prompt` de forma explícita;
- conter exemplos few-shot;
- impor formato previsível de saída;
- cobrir edge cases;
- evitar inventar fatos ausentes no bug report;
- preservar detalhes técnicos e impacto de negócio quando informados.

## Metadados mínimos do prompt otimizado

`prompts/bug_to_user_story_v2.yml` deve conter:

- `name`
- `description`
- `metadata.version`
- `metadata.techniques`
- `metadata.author`
- `metadata.target_format`
- `metadata.status`
- `system_prompt`
- `few_shot_examples`
- `user_prompt`

## Regras de avaliação

As métricas obrigatórias são:

- `Tone Score`
- `Acceptance Criteria Score`
- `User Story Format Score`
- `Completeness Score`

Critério de pronto:

- todas as métricas `>= 0.9`;
- média geral `>= 0.9`;
- testes locais passando;
- prompt publicado no LangSmith;
- README descrevendo técnicas e fluxo.

## Fluxo de trabalho recomendado

1. executar `python .\src\pull_prompts.py`;
2. revisar `prompts/bug_to_user_story_v1.yml`;
3. editar `prompts/bug_to_user_story_v2.yml`;
4. executar `pytest .\tests\test_prompts.py`;
5. executar `python .\src\push_prompts.py`;
6. executar `python .\src\evaluate.py`;
7. iterar até todas as métricas passarem.

## Boas práticas

- Preferir iterações pequenas no prompt.
- Documentar decisões no `README.md`.
- Manter metadados e tags coerentes entre YAML e LangSmith.
- Tratar erros com mensagens claras.
- Não quebrar o suporte a OpenAI e Google.
