# Winthor Data Deploy — MVP

Aplicação web local: **abrir projeto → subir arquivo → validar automaticamente →
tratar exceções → gerar script de INSERT Oracle** para rodar manualmente no banco
do cliente. O Winthor não expõe API — a carga é sempre via script SQL.

## Rodando

```bash
pip install -r requirements.txt --break-system-packages
PYTHONPATH=backend uvicorn app.api:app --reload
```

Abra `http://127.0.0.1:8000` no navegador. A própria API serve a interface.

## O que está implementado (real, testado — 21 testes)

| Etapa | Módulo | Status |
|---|---|---|
| Interface web (projeto/upload/exceções/script) | `frontend/index.html` | ✅ funcional |
| Projetos (isolamento por cliente) | `app/db.py` (`Project`) | ✅ funcional |
| Data Ingestion (CSV/Excel) + profiling automático de colunas | `app/ingestion/` | ✅ funcional |
| Canonical Model | `app/canonical/models.py` | ✅ funcional |
| Saneamento | `app/normalization/rules.py` | ✅ funcional |
| Auditoria (cadastro/integridade) | `app/validation/rules.py` | ✅ funcional |
| Deduplicação | `app/dedup/dedup.py` | ✅ funcional (fuzzy, O(n²)) |
| Persistência (SQLAlchemy/SQLite→Postgres) | `app/db.py`, `app/repository.py` | ✅ funcional |
| Exception Queue com aprovação/rejeição | `app/api.py` | ✅ funcional |
| Readiness Gate (bloqueia script com BLOCKER pendente) | `app/api.py` | ✅ funcional |
| **Gerador de script Oracle (Winthor Adapter)** | `app/winthor/oracle_generator.py` | ⚠️ obsoleto — ver pendência abaixo |
| **Wizard de aderência por segmento/subsegmento** | `app/winthor/adherence.py`, `mappings/winthor/segments.json` | ✅ funcional (config + API + UI) |
| **Derivação fiscal automática (PIS/COFINS por NCM)** | `app/winthor/pis_cofins_monofasico.py` | ⚠️ amostra ilustrativa, não valida fiscalmente |
| SPED/XML Fiscal Evidence Layer | — | ❌ não implementado |
| IA (classificação/sugestão) | — | ❌ não implementado (pontos de extensão isolados) |

## ⚠️ Mudança de arquitetura — Winthor NÃO usa INSERT SQL

O layout oficial (`DD_WINTHOR.md`, documento DA.RPI.010) confirma que a carga no
Winthor é feita por **arquivo texto delimitado** (`#` ou `;`, validado pelo programa
`VALIDADORMIGRACAO`) — não por script de INSERT direto no Oracle.

**`app/winthor/oracle_generator.py` está obsoleto** e precisa ser substituído por um
gerador de arquivo texto posicional, respeitando: sem zero à esquerda em campo
numérico, sem padding de espaço, decimal com ponto, data `DD/MM/YYYY`, campo
obrigatório nunca em branco mas também nunca substituído por espaço (só o
separador). Ainda não implementado — depende de fechar o mapeamento completo
dos ~40 campos do PCPRODUT primeiro (ver wizard de aderência abaixo).

## Wizard de aderência — por que existe

O layout do PCPRODUT tem ~40 campos, boa parte obrigatória, mas nem todo cliente
tem o processo correspondente (ex: endereçamento físico de estoque, paletização,
comissão por produto). Como o layout é posicional fixo, **o wizard não remove
campo do arquivo** — ele decide, por módulo de processo:

- Módulo **aplicável** ao cliente + campo obrigatório ausente → vira **BLOCKER**
  na Exception Queue (alguém precisa decidir).
- Módulo **não aplicável** → aplica o **default configurado** automaticamente
  (ex: `LASTROPAL=1`, conforme o próprio documento Winthor recomenda).
- Módulos fiscais obrigatórios por lei (NCM) nunca passam pelo wizard — são
  sempre exigidos.
- `PISCOFINSRETIDO` nunca é perguntado — é **derivado automaticamente do NCM**
  (é característica do produto, não escolha de processo do cliente).

Presets por segmento/subsegmento (`mappings/winthor/segments.json`) pré-marcam o
wizard com base em conhecimento de domínio de varejo/distribuição, mas o cliente
sempre pode sobrescrever por módulo.

**Pendência**: o wizard e o motor de aderência (`app/winthor/adherence.py`) estão
implementados e testados isoladamente, mas **ainda não estão acoplados ao
pipeline de import** (`/imports`). Isso exige primeiro estender a ingestão para
mapear os ~40 campos do PCPRODUT (hoje só ~10 campos canônicos são capturados),
senão toda importação dispararia BLOCKER em cascata para campos que a fonte de
dados do cliente nunca teve a intenção de fornecer.

## Fluxo de uso

1. Cria um projeto (nome do cliente) na sidebar.
2. Sobe um CSV de produtos — pipeline roda automaticamente (ingestão → saneamento →
   validação → dedup) e mostra Data Readiness Score.
3. Trata a fila de exceções: aprova ou rejeita cada uma (fica registrado quem decidiu).
4. Quando não há mais `BLOCKER` pendente, "Gerar script .sql" libera. Registros
   `REJECTED` ficam de fora do script; o resto vira `INSERT INTO <tabela> VALUES (...)`.
5. O `.sql` gerado é rodado manualmente no Oracle do cliente (fora desta aplicação —
   não há execução automática contra banco de produção, por design).

## ⚠️ Pendência crítica: mapping Winthor é placeholder E formato de saída está errado

`mappings/winthor/produto.json` (usado pelo `oracle_generator.py` obsoleto) tem
nomes de tabela/coluna que eram um chute. O layout oficial confirmou o schema
real de `PCPRODUT` (`mappings/winthor/pcprodut_modules.json` já reflete os campos
corretos, agrupados em módulos de aderência). Mas o formato de saída também
mudou: não é mais INSERT SQL, é arquivo texto delimitado. Ver seção acima.

## API

| Rota | Método | O que faz |
|---|---|---|
| `/projects` | POST / GET | Cria/lista projetos |
| `/projects/{id}/imports` | GET | Lotes de um projeto |
| `/imports` | POST (multipart: `project_id` + `file`) | Roda pipeline, persiste lote |
| `/imports/{id}/report` | GET | KPIs do lote |
| `/imports/{id}/products` | GET | Produtos do lote |
| `/exceptions?batch_id=&status=` | GET | Exception Queue |
| `/exceptions/{id}/resolve` | POST | Aprova/rejeita exceção |
| `/imports/{id}/readiness` | GET | Gate: há BLOCKER pendente? |
| `/imports/{id}/script` | GET | Gera e baixa o `.sql` (409 se houver BLOCKER pendente) |

Banco default é SQLite local (`winthor_data_deploy.db`); troque via `WINTHOR_DB_URL`
para apontar a um Postgres sem mudar código.

## Deploy

### Opção A — Docker (recomendado para VPS novo)

```bash
cp .env.example .env    # ajuste WINTHOR_DB_URL se for usar Postgres
docker compose up -d --build
```

Sobe em `http://<ip-do-vps>:8000`. Dados persistem nos volumes `winthor_data`/`winthor_output`.
Coloque um nginx/Caddy na frente para TLS (ver `deploy/nginx.conf` como referência,
mesmo usando Docker).

### Opção B — VPS sem Docker (systemd + nginx)

```bash
git clone <repo> /opt/winthor-data-deploy
cd /opt/winthor-data-deploy
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

sudo cp deploy/winthor-data-deploy.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now winthor-data-deploy

sudo cp deploy/nginx.conf /etc/nginx/sites-available/winthor-data-deploy
sudo ln -s /etc/nginx/sites-available/winthor-data-deploy /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Atualizações depois disso: `./deploy/deploy.sh` (pull + reinstala deps + roda testes +
reinicia serviço; não reinicia se os testes quebrarem).

### CI

`.github/workflows/tests.yml` roda a suíte a cada push/PR.

## Testes

```bash
PYTHONPATH=backend python3 -m pytest backend/tests/ -v
```

## Saídas geradas em `output/` (via CLI, alternativa à interface web)

```bash
python3 cli.py sample_data/produtos_exemplo.csv --out output/
```

- `cadastro_canonico.json` — todos os produtos no modelo canônico, com status
- `excecoes.json` — Exception Queue (o que exige decisão humana)
- `audit_log.jsonl` — uma linha por transformação aplicada (rastreabilidade)
- `relatorio_qualidade.json` — KPIs (Data Readiness Score, Exception Rate, etc.)

## Decisões de design e por quê

1. **`description_raw` nunca é sobrescrito.** Guardrail do documento ("preservar o dado
   original"). `description` é sempre derivado, com proveniência.
2. **Toda transformação grava `FieldProvenance`** (regra, origem, confiança, evidência).
   Sem isso, "rastreabilidade" é só uma palavra no slide.
3. **Validação de EAN usa checksum real (GTIN)**, não regex de tamanho. Cadastros legados
   quase sempre têm EAN "com a cara certa" mas dígito verificador errado — é o tipo de erro
   que review manual não pega e o algoritmo pega em O(1).
4. **Dedup é O(n²) de propósito no MVP.** O documento já prevê blocking por família/marca
   para escalar — implementar isso antes de ter um piloto real com volume é otimização
   prematura. Está documentado no código onde trocar.
5. **IA está deliberadamente ausente**, não esquecida. O princípio do documento (seção 34)
   é "IA só onde aumenta produtividade real". Os pontos de extensão (sugestão de NCM,
   matching de duplicatas ambíguas, normalização de descrição fora do dicionário de regras)
   ficam isolados em módulos próprios — plugar um classificador depois não exige reescrever
   o pipeline.

## Gaps do documento original que este código expõe

- Não há definição de **quem resolve conflito entre duas fontes de evidência** (ex: SPED
  diz NCM X, cadastro diz NCM Y, XML diz NCM Z). O `FieldProvenance.confidence` dá a base
  para isso, mas falta a regra de arbitragem — provavelmente: XML de NF-e emitida > SPED >
  cadastro manual, por ser o dado mais próximo da operação real.
- KPI "Horas humanas por 1.000 registros válidos" (seção 27) não tem fonte de dado — nada
  no pipeline mede tempo de decisão humana na Exception Queue. Precisa de timestamp de
  entrada/saída da fila por registro.
