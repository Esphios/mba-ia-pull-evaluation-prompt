# AGENTS.md

## Visão Geral

Este repositório implementa um fluxo de engenharia de prompts para o caso de uso
`Bug Report -> User Story` com LangChain e LangSmith.

O sistema deve ser capaz de:

1. fazer pull de prompts ruins do Prompt Hub;
2. persistir esses prompts localmente em YAML;
3. refatorar o prompt com técnicas explícitas;
4. fazer push da nova versão para o LangSmith;
5. avaliar a qualidade com métricas customizadas;
6. atingir `>= 0.9` em cada métrica obrigatória.

## Prioridade de Decisão

Quando houver conflito entre referências, siga esta ordem:

1. desafio;
2. estrutura existente do repositório;
3. boas práticas de engenharia;
4. documentação complementar.

## Tecnologias Principais

| Categoria | Tecnologia | Evidência | Uso |
| --- | --- | --- | --- |
| Runtime | Python 3.9+ | `README.md`, `requirements.txt` | scripts CLI |
| Framework LLM | LangChain | `requirements.txt`, `src/utils.py` | prompts e execução |
| Observabilidade | LangSmith | `requirements.txt`, `src/pull_prompts.py`, `src/push_prompts.py`, `src/evaluate.py` | prompt hub e avaliação |
| Provedores | OpenAI e Google GenAI | `.env.example`, `src/utils.py` | geração e avaliação |
| Testes | pytest | `tests/test_prompts.py` | validações estruturais |

## Estrutura e Fonte de Verdade

- `datasets/bug_to_user_story.jsonl`: fonte de verdade do dataset.
- `src/dataset.py`: deve apenas carregar e adaptar esse arquivo.
- `prompts/bug_to_user_story_v1.yml`: baseline de baixa qualidade.
- `prompts/bug_to_user_story_v2.yml`: prompt otimizado principal.
- `prompts/raw_prompts.yml`: versão crua puxada do LangSmith.
- `src/pull_prompts.py`, `src/push_prompts.py`, `src/evaluate.py`: fluxo operacional do desafio.

## Regras de Engenharia

- Python 3.9+.
- Código simples, pequeno e previsível.
- Scripts CLI devem funcionar via `python .\src\<arquivo>.py` no PowerShell.
- Nunca commite `.env`.
- Sempre mantenha `.env.example` atualizado.
- Evite duplicação do dataset em arquivos Python quando o JSONL já existir.
- Não altere o dataset para facilitar as métricas.
- Não esconda regras em scripts soltos fora de `src/`.
- Todo texto para desenvolvedores, prompts, mensagens CLI e documentação deve permanecer em pt-BR com acentuação correta.
- Não quebre o suporte a OpenAI e Google.

## Regras do Prompt

O prompt otimizado deve:

- definir uma persona clara;
- usar `system_prompt` e `user_prompt` de forma explícita;
- conter exemplos few-shot;
- impor formato previsível de saída;
- cobrir edge cases;
- evitar inventar fatos ausentes no bug report;
- preservar detalhes técnicos e impacto de negócio quando informados.

## Metadados Mínimos do Prompt Otimizado

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

## Regras de Avaliação

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

## Setup e Comandos

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
python .\src\pull_prompts.py
pytest .\tests\test_prompts.py
python .\src\push_prompts.py
python .\src\evaluate.py
python .\src\evaluate.py --variant all
```

## Fluxo de Trabalho Recomendado

1. executar `python .\src\pull_prompts.py`;
2. revisar `prompts/bug_to_user_story_v1.yml`;
3. editar `prompts/bug_to_user_story_v2.yml`;
4. executar `pytest .\tests\test_prompts.py`;
5. executar `python .\src\push_prompts.py`;
6. executar `python .\src\evaluate.py`;
7. iterar até todas as métricas passarem.

## Configuração e Convenções

- Variáveis e aliases suportados estão documentados em `.env.example` e `README.md`.
- O fluxo diferencia baseline local, prompt otimizado e publicação remota no LangSmith.
- O projeto lida explicitamente com o caso de `409 Nothing to commit` no push.
- Manter metadados e tags coerentes entre YAML e LangSmith evita drift entre prompt local e remoto.

## Boas Práticas

- Preferir iterações pequenas no prompt.
- Documentar decisões no `README.md`.
- Manter metadados e tags coerentes entre YAML e LangSmith.
- Tratar erros com mensagens claras.
- Validar o prompt antes de publicar.

## Peculiaridades do Projeto

- O dataset local pode ser expandido de forma determinística apenas no momento da publicação remota, conforme descrito no README.
- O projeto mistura requisitos de engenharia de prompts, publicação remota e avaliação quantitativa no mesmo fluxo.
- O histórico recente usa Conventional Commits de forma consistente (`feat:`, `docs:`, `chore:`).
