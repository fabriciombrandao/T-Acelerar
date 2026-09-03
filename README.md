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
| **Gerador de script Oracle (Winthor Adapter)** | `app/winthor/oracle_generator.py` | ✅ funcional |
| SPED/XML Fiscal Evidence Layer | — | ❌ não implementado |
| IA (classificação/sugestão) | — | ❌ não implementado (pontos de extensão isolados) |

## Fluxo de uso

1. Cria um projeto (nome do cliente) na sidebar.
2. Sobe um CSV de produtos — pipeline roda automaticamente (ingestão → saneamento →
   validação → dedup) e mostra Data Readiness Score.
3. Trata a fila de exceções: aprova ou rejeita cada uma (fica registrado quem decidiu).
4. Quando não há mais `BLOCKER` pendente, "Gerar script .sql" libera. Registros
   `REJECTED` ficam de fora do script; o resto vira `INSERT INTO <tabela> VALUES (...)`.
5. O `.sql` gerado é rodado manualmente no Oracle do cliente (fora desta aplicação —
   não há execução automática contra banco de produção, por design).

## ⚠️ Pendência crítica: mapping Winthor é placeholder

`mappings/winthor/produto.json` tem nomes de tabela/coluna **não confirmados**
(`PCPRODUT`, `CODPROD`, etc. — plausíveis para o layout Winthor, mas chutados).
**Não rodar este script contra um Oracle real antes de validar contra o
dicionário oficial** (próximos passos, item 1 do documento original). Trocar o
JSON depois de confirmado não exige mudar código — é só configuração.

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
