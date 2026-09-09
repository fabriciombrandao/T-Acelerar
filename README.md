# T-Acelerar — Módulo Winthor

Aplicação web: **abrir projeto → subir arquivo → validar automaticamente →
tratar exceções → gerar arquivo de carga** (texto oficial Winthor ou SQL
alternativo). Parte da plataforma **T-Acelerar** — acelerador de projetos
de implantação TOTVS, com módulos plugáveis por ERP. Este é o primeiro
módulo, específico do Winthor; a estrutura (`app/winthor/` isolado do
núcleo genérico — auth, projetos, Exception Queue, pipeline) já comporta
outros módulos (ex: `app/protheus/`) no mesmo repositório quando existirem.

## Rodando local (sem Docker, dev solo)

Backend e frontend são containers separados em produção — local, sem
Docker, roda os dois processos à parte:

```bash
# Terminal 1 — backend
pip install -r requirements.txt --break-system-packages
PYTHONPATH=backend uvicorn app.api:app --reload

# Terminal 2 — frontend (arquivo estático, qualquer servidor serve)
cd frontend && python3 -m http.server 8080
```

Abra `http://127.0.0.1:8080`. CORS já está liberado no backend pra esse
cenário (ver comentário em `api.py`). Login/dados ficam em SQLite local
(`tacelerar.db`) automaticamente — não precisa configurar nada
pra esse modo.

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
| **Dois formatos de exportação: texto oficial + SQL** | `app/winthor/text_file_generator.py`, `app/winthor/oracle_generator.py` | ✅ funcional |
| **Wizard de aderência por segmento/subsegmento** | `app/winthor/adherence.py`, `mappings/winthor/segments.json` | ✅ funcional (config + API + UI) |
| **Autenticação (login, JWT, admin/consultor)** | `app/auth.py` | ✅ funcional |
| **Derivação fiscal automática (PIS/COFINS por NCM)** | `app/winthor/pis_cofins_monofasico.py` | ⚠️ amostra ilustrativa, não valida fiscalmente |
| SPED/XML Fiscal Evidence Layer | — | ❌ não implementado |
| IA (classificação/sugestão) | — | ❌ não implementado (pontos de extensão isolados) |

## Onde a aplicação roda — decisão registrada

Time de >5 consultores, projetos de clientes diferentes em paralelo →
**VPS compartilhado**, não local. Isso trouxe dois pré-requisitos que passam
a ser obrigatórios (não "melhoria futura"):

1. **Autenticação** — sem isso, qualquer pessoa com a URL do VPS mexe em
   dado de cliente de qualquer projeto. Implementado (`app/auth.py`).
2. **Postgres, não SQLite** — SQLite trava com escrita concorrente de vários
   consultores ao mesmo tempo. `docker-compose.{prod,dev,teste}.yml` já
   assumem Postgres como padrão para este perfil (SQLite continua sendo o
   default só para desenvolvimento local sozinho, sem Docker).

## Autenticação e hierarquia de acesso

Modelo fechado, sem auto-cadastro, com 3 papéis:

| Papel | Cria usuários | Vê projetos de |
|---|---|---|
| **Diretor** | Qualquer papel (coordenador direto; analista precisa de `manager_email` apontando pra um coordenador) | Todos |
| **Coordenador** | Só `analista`, automaticamente atribuído à própria equipe (`manager_id` = ele mesmo) | Ele mesmo + toda a equipe (analistas sob ele) |
| **Analista** | Ninguém | Só ele mesmo |

Analistas da mesma equipe **não** veem projeto uns dos outros — só o
coordenador acima e o diretor enxergam a equipe inteira.

**Primeiro setup (uma vez só, por ambiente) — cria o primeiro DIRETOR:**
```bash
curl -X POST http://127.0.0.1:8020/api/auth/bootstrap-admin \
  -H "Content-Type: application/json" \
  -d '{"email":"diretor@empresa.com","name":"Fulano","password":"...",
       "bootstrap_secret":"<TACELERAR_BOOTSTRAP_SECRET do .env>"}'
```
Esse endpoint só funciona **uma vez** — depois que existe qualquer usuário no
banco, ele sempre retorna 409, mesmo com o secret certo.

**Depois disso**, login normal (`POST /api/auth/login`, form `username`+`password`,
retorna JWT). O diretor cria coordenadores:
```bash
curl -X POST http://127.0.0.1:8020/api/users -H "Authorization: Bearer <token-diretor>" \
  -H "Content-Type: application/json" \
  -d '{"email":"coord@empresa.com","name":"Coordenador","password":"...","role":"coordenador"}'
```
E cada coordenador cria os próprios analistas (não precisa de `manager_email`
— vira automaticamente a equipe de quem criou):
```bash
curl -X POST http://127.0.0.1:8020/api/users -H "Authorization: Bearer <token-coordenador>" \
  -H "Content-Type: application/json" \
  -d '{"email":"analista@empresa.com","name":"Analista","password":"...","role":"analista"}'
```

Token expira em 12h. Todo o resto da API exige `Authorization: Bearer <token>`.
`resolved_by` na Exception Queue vem do usuário autenticado — não é mais
texto livre enviado pelo cliente, é dado de auditoria de verdade.

**Atribuição de projeto**: por padrão, quem cria um projeto vira `owner`.
`owner_email` no `POST /projects` permite atribuir a outra pessoa, mas só
dentro do que você já enxergaria (diretor: qualquer um; coordenador: a
própria equipe; analista: só ele mesmo — tentar atribuir a outro dá 403).

## Dois formatos de saída, por decisão deliberada

`GET /imports/{id}/script?format=texto|sql` — os dois convivem, não é migração
de um pro outro:

- **`texto` (default)** — o formato que o documento DA.RPI.010 realmente descreve:
  campos separados por `#` (ou `;`), separador também no fim da linha, sem
  padding de espaço, sem zero à esquerda, datas `DD/MM/YYYY`. É o que o
  `VALIDADORMIGRACAO` do Winthor espera. Layout completo (40 campos, ordem
  exata) em `mappings/winthor/pcprodut_layout.json`.
- **`sql`** — INSERT Oracle, mantido como alternativa para cenários onde o
  time prefere carregar direto via banco. **Mapping ainda placeholder**
  (`mappings/winthor/produto.json`) — não usar em produção sem validar
  tabela/colunas reais primeiro.

Os dois puxam do mesmo `ProductRecord` persistido — não há duplicação de lógica
de negócio, só formatação de saída diferente.

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

## ⚠️ Pendência: mapping do formato SQL ainda é placeholder

`mappings/winthor/produto.json` (usado só pelo `format=sql`) tem nomes de
tabela/coluna que eram um chute — ainda não confirmados. O `format=texto`
já usa o layout oficial confirmado (`pcprodut_layout.json`) e é o caminho
recomendado até validar o mapping SQL.

## API

Todas as rotas de negócio ficam sob `/api` — nginx roteia `/api/*` pro
container de backend e o resto (`/`) pro container de frontend (ver
`deploy/nginx-servicos-*.conf`). `/health`, `/docs`, `/redoc` e
`/openapi.json` ficam fora do prefixo `/api` de propósito, igual ao
padrão TNORTEANDO — são rotas de infraestrutura/introspecção, não de
negócio.

| Rota | Método | O que faz |
|---|---|---|
| `/health` | GET | Healthcheck (sem auth) — usado pelo Docker |
| `/api/auth/bootstrap-admin` | POST | Cria o primeiro diretor (só funciona uma vez) |
| `/api/auth/login` | POST (form) | Login, retorna JWT |
| `/api/auth/me` | GET | Dados do usuário autenticado |
| `/api/users` | POST / GET | Diretor/coordenador cria/lista pessoas da equipe |
| `/api/projects` | POST / GET | Cria/lista projetos |
| `/api/projects/{id}/imports` | GET | Lotes de um projeto |
| `/api/imports` | POST (multipart: `project_id` + `file`) | Sobe arquivo, dispara processamento |
| `/api/imports/{id}` | GET | Status do lote (polling: PENDING/PROCESSING/DONE/FAILED) |
| `/api/imports/{id}/report` | GET | KPIs do lote |
| `/api/imports/{id}/products` | GET | Produtos do lote (paginado) |
| `/api/exceptions?batch_id=&status=&limit=&offset=` | GET | Exception Queue (paginado) |
| `/api/exceptions/{id}/resolve` | POST | Aprova/rejeita exceção |
| `/api/imports/{id}/readiness` | GET | Gate: há BLOCKER pendente? |
| `/api/imports/{id}/script?format=texto\|sql` | GET | Gera e baixa o arquivo de carga |

Todas as rotas `/api/*` acima (exceto `/api/auth/login` e
`/api/auth/bootstrap-admin`) exigem `Authorization: Bearer <token>`.

Banco default é SQLite local (`tacelerar.db`) — só para dev solo,
sem Docker. Em qualquer ambiente com mais de uma pessoa, usar Postgres via
`TACELERAR_DB_URL` (`docker-compose.{prod,dev,teste}.yml` já vêm configurados assim).

## Deploy

### Estrutura: 3 ambientes, padrão TNORTEANDO

Este VPS já roda o TNORTEANDO com 3 ambientes completos (prod/dev/teste),
cada um em seu próprio checkout git, container/rede/volume nomeados
explicitamente. Seguimos exatamente essa convenção — **não** um único
compose com profiles.

```
/opt/tacelerar/
├── prod/    (checkout git próprio + .env próprio)
├── dev/     (checkout git próprio + .env próprio)
└── teste/   (checkout git próprio + .env próprio)
```

Cada ambiente é um `git clone` separado do mesmo repositório — não é
symlink nem worktree, é uma cópia própria, exatamente como o TNORTEANDO
está montado hoje. Isso evita qualquer risco de um `.env` vazar pra
ambiente errado.

### Nomenclatura (mesmo padrão deles)

| | Deles (referência) | Nosso |
|---|---|---|
| Diretório | `/opt/tnorteando/{env}/` | `/opt/tacelerar/{env}/` |
| Compose project | `tnorteando-{env}` | `tacelerar-{env}` |
| Container | `tnorteando-{env}-backend` | `tacelerar-{env}-backend` |
| Rede | `net-tnorteando-{env}` | `net-tacelerar-{env}` |
| Porta backend (127.0.0.1 só) | 8010/8011/8012 | **8020/8021/8022** (prod/dev/teste) |
| Porta frontend (127.0.0.1 só) | 3010/3011/3012 | **3020/3021/3022** (prod/dev/teste) |
| Domínio | `tnorteando.com.br` / `desenv....` / `teste....` | `servicos.tnorteando.com.br` (prod) / dev e teste: a decidir quando forem ativados |

Sem `celery-beat` do nosso lado — não temos tarefa agendada/periódica, só
processamento sob demanda (import de arquivo).

### Escopo atual: só produção

Decisão registrada: por enquanto só `prod` sobe de verdade, com domínio e
TLS. `docker-compose.dev.yml` e `docker-compose.teste.yml` já existem no
repo (mesma estrutura, recurso bem mais baixo, prontos pra quando forem
necessários), mas **não sobem agora** — sem domínio próprio, sem certbot
rodado pra eles. Quando precisar, é o mesmo passo a passo abaixo trocando
`prod` por `dev`/`teste`, mais decidir o domínio deles nessa hora.

### Passo a passo — produção

**1. Checkout:**
```bash
sudo mkdir -p /opt/tacelerar
cd /opt/tacelerar
sudo git clone https://github.com/fabriciombrandao/T-Acelerar.git prod
cd prod
```

**2. Criar diretórios de dado (bind mount, não volume nomeado — igual ao padrão deles, mais fácil de inspecionar/backupar):**
```bash
sudo mkdir -p /opt/tacelerar/prod/data/{postgres,redis,uploads}
sudo mkdir -p /opt/tacelerar/prod/logs
```

**3. Configurar `.env`:**
```bash
cp .env.example .env
nano .env
```
Preencher: `POSTGRES_PASSWORD`, `TACELERAR_DB_URL` (mesma senha, duplicada —
ver comentário no `.env.example` explicando por quê), `TACELERAR_JWT_SECRET`
e `TACELERAR_BOOTSTRAP_SECRET` (gerar com `python3 -c "import secrets; print(secrets.token_hex(32))"`).

**4. Subir:**
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

**5. Confirmar saúde:**
```bash
docker compose -f docker-compose.prod.yml ps
curl http://127.0.0.1:8020/health
```

**6. Criar o primeiro DIRETOR:**
```bash
curl -X POST http://127.0.0.1:8020/api/auth/bootstrap-admin \
  -H "Content-Type: application/json" \
  -d '{"email":"voce@totvs.com","name":"Seu Nome","password":"...",
       "bootstrap_secret":"<o TACELERAR_BOOTSTRAP_SECRET deste .env>"}'
```

**7. nginx (host, fora do Docker — igual ao padrão deles):**
```bash
sudo cp deploy/nginx-servicos-prod.conf /etc/nginx/sites-available/tacelerar-prod
sudo ln -s /etc/nginx/sites-available/tacelerar-prod /etc/nginx/sites-enabled/
sudo certbot --nginx -d servicos.tnorteando.com.br
sudo nginx -t && sudo systemctl reload nginx
```
(Confirma que o DNS de `servicos.tnorteando.com.br` já aponta pro IP do
VPS antes desse passo — certbot precisa disso pra validar o domínio.)

### Orçamento de CPU — só prod, por enquanto

VPS medido: 4 núcleos, TNORTEANDO já roda 3 ambientes completos (ocioso em
~18% de 1 núcleo em uso normal, com pico observado de 2,7GB RAM no worker
de produção deles). Só `prod` da nossa stack, no pior caso de CPU (tudo no
teto ao mesmo tempo):

| Serviço | db | redis | backend | frontend | worker | **total** |
|---|---|---|---|---|---|---|
| prod | 0.5 | 0.25 | 0.5 | 0.1 | 1.0 | **2.35 de 4 núcleos** |

Bem mais folgado que o cenário com os 3 ambientes juntos (que chegava a
3,95 de 4). Se no futuro dev/teste entrarem em uso constante, revisitar
essa conta antes de deixá-los rodando 24/7 — a matemática dos 3 juntos já
está documentada no histórico do commit `df61887`, caso precise depois.

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
4. **Dedup usa blocking + sorted neighborhood, não O(n²) puro.** Testado até
   200 mil produtos no pior caso (tudo num balde só): 4,2s. Detalhe e trade-offs
   documentados em `app/dedup/dedup.py`.
5. **IA está deliberadamente ausente**, não esquecida. O princípio do documento (seção 34)
   é "IA só onde aumenta produtividade real". Os pontos de extensão (sugestão de NCM,
   matching de duplicatas ambíguas, normalização de descrição fora do dicionário de regras)
   ficam isolados em módulos próprios — plugar um classificador depois não exige reescrever
   o pipeline.
6. **Uma aplicação só, não uma por ERP.** Decisão explícita do time: quando um segundo
   conector (ex: Protheus) existir, ele entra como `app/<erp>/` no mesmo repositório e no
   mesmo deploy — não vira um novo conjunto de containers/domínio/banco. A distinção de
   qual ERP um projeto usa vira um campo no `Project` (ainda não existe, porque só há um
   conector até agora — adicionar esse campo antes de ter um segundo caso real seria
   desenhar às cegas). `app/winthor/` já está isolado do núcleo genérico (auth, projetos,
   Exception Queue, pipeline) exatamente para não exigir reescrita quando esse dia chegar.

## Gaps do documento original que este código expõe

- Não há definição de **quem resolve conflito entre duas fontes de evidência** (ex: SPED
  diz NCM X, cadastro diz NCM Y, XML diz NCM Z). O `FieldProvenance.confidence` dá a base
  para isso, mas falta a regra de arbitragem — provavelmente: XML de NF-e emitida > SPED >
  cadastro manual, por ser o dado mais próximo da operação real.
- KPI "Horas humanas por 1.000 registros válidos" (seção 27) não tem fonte de dado — nada
  no pipeline mede tempo de decisão humana na Exception Queue. Precisa de timestamp de
  entrada/saída da fila por registro.
