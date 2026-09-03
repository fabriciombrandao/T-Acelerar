# Guia de Padrões — Frontend (`frontend/index.html`)

Este documento define o padrão técnico e visual do frontend. **Supersede** uma
proposta anterior de JS puro (sem framework) — decidimos usar **Alpine.js**
em vez de manipulação manual de DOM, mantendo a mesma filosofia de "arquivo
único, sem build step, servido estaticamente pelo FastAPI".

## Stack

- **HTML + Alpine.js** (via CDN, sem bundler/npm/webpack)
- **CSS puro** com variáveis (`:root`), zero cor/raio/sombra hardcoded fora delas
- **Lucide** para ícones (via CDN)
- Servido por `StaticFiles` do FastAPI, mesmo processo da API (`app/api.py`)

### Por que Alpine.js e não JS puro

JS puro exigiria reimplementar manualmente (via `innerHTML` + template
literals) o que Alpine já resolve de graça: reatividade declarativa
(`x-show`, `x-for`, `x-model`, `x-text`) sem re-renderizar strings de HTML
inteiras a cada mudança de estado. Menos bug de escaping, menos código.

### Por que não htmx

Cotado antes, mas descartado a favor de manter uma única tecnologia de
front (Alpine) em vez de duas se complementando. Se a volumetria de dados
em tela crescer muito (tabelas com milhares de linhas renderizadas de uma
vez), reavaliar — htmx com paginação server-side pode valer a pena nesse
cenário específico. Hoje a paginação já é client-driven via Alpine
(`exceptionsOffset`/`exceptionsLimit`, ver abaixo), suficiente pro volume
atual.

## Design system (`:root`)

Toda cor, raio de borda e sombra usada no arquivo **tem que vir daqui**.
Se uma tela precisar de uma cor nova, a variável entra no `:root` primeiro
— nunca hardcoded no meio de uma regra CSS.

| Variável | Uso |
|---|---|
| `--bg-principal` / `--bg-card` | fundo da página / fundo de card, sidebar, inputs |
| `--border-color` | toda borda de 1px |
| `--texto-principal` / `--texto-secundario` / `--texto-terciario` | hierarquia de texto |
| `--cor-marca` / `--cor-marca-hover` / `--cor-marca-soft` | ação primária (botões, links, foco) |
| `--cor-sucesso` / `--cor-erro` / `--cor-aviso` / `--cor-bloqueio` (+ `-soft`) | status/severidade — mapeiam direto pros valores que já vêm da API (`DONE`, `FAILED`, `HIGH`, `BLOCKER`, etc.) |
| `--radius-md` / `--radius-sm` | raio de borda — md pra cards/seções, sm pra botões/inputs |
| `--shadow-sm` / `--shadow-md` | sombra leve (hover de linha) / sombra de modal-like (login) |
| `--sidebar-width` | largura fixa da sidebar |

Fonte é sempre a stack do sistema (`system-ui, -apple-system, ...`) — sem
Google Fonts, sem carregar tipografia externa.

## Arquitetura do arquivo

```
<style>          — design system + componentes (seções numeradas em comentário)
<body x-data="app()">
  ...HTML declarativo com x-show/x-for/x-model/x-on...
<script>
  const API = { ... }     — TODA chamada de rede passa por aqui
  function app() { ... }  — componente raiz Alpine: estado + métodos
  function refreshIcons() — chama lucide.createIcons() após mudança de DOM dinâmico
</script>
```

### `API` — camada de rede

Um único objeto com `request/get/postJson/postForm`. Nenhum componente faz
`fetch` direto (exceção: `login()` e `generateScript()`, que precisam de
controle fino sobre `Content-Type`/blob — documentado inline no código).
Erros de `401` viram `err.unauthorized = true`, tratado de forma central
pelo helper `call()` dentro de `app()` (desloga automaticamente).

### `app()` — estado e métodos

Tudo que a tela precisa exibir vive em `state` (os campos do objeto
retornado por `app()`). **Nunca ler valor direto do DOM** — sempre via
`x-model` escrevendo no estado, e os métodos leem `this.<campo>`, não
`document.getElementById(...).value`.

Agrupamento do estado (comentários `// ----------` no código):
`auth` → `navegação` → `projetos` → `wizard de aderência` → `lotes/upload`
→ `exceções (paginado)` → `equipe` → `ui (toast)`.

### Ícones (Lucide)

`<i data-lucide="nome-do-icone" style="width:Npx;height:Npx;"></i>` — a
lib varre o DOM procurando esses atributos e substitui pelo SVG. Como
Alpine insere/remove elementos dinamicamente (`x-if`, `x-for`), **é preciso
chamar `refreshIcons()` de novo toda vez que uma lista nova entrar em
tela** (ver `this.$nextTick(() => refreshIcons())` espalhado pelos métodos
que carregam listas). Esquecer isso faz o ícone aparecer como texto cru
(`<i data-lucide="...">`) em vez do SVG.

### Paginação

Padrão usado em `/exceptions` e `/products`: a API devolve a página pedida
(`?limit=&offset=`) e o total real no header `X-Total-Count`. O frontend
lê esse header (`resp.headers.get('X-Total-Count')`) pra montar
"Mostrando X–Y de Z" e habilitar/desabilitar Anterior/Próxima. Não pedir
a lista inteira de uma vez — em lote de 1M linhas isso trava o navegador.

### Autenticação

Token JWT salvo em `localStorage` (`winthor_token`) — persiste entre
reloads. Toda chamada autenticada passa o token pro `API.get/postJson/postForm`,
que injeta `Authorization: Bearer <token>`. `401` em qualquer chamada
desloga automaticamente (ver `call()`).

## Como pedir mudanças ao Claude a partir de agora

**Não pedir o arquivo inteiro de novo.** Conforme o `index.html` cresce, pedir
reescrita completa aumenta o risco de perda de trecho e gasta contexto à toa.
Pedir bloco específico:

> "Me dê só o CSS do componente `.stat-box`."
> "Me dê só o método `submitUpload` do `app()`, com tratamento de progresso."
> "Adicione uma seção nova no `<main>` para [X], não mexa no resto."

### Prompt base pra pedir uma tela/componente novo

> Atue como desenvolvedor frontend sênior focado em Alpine.js e CSS puro,
> sem framework/build step. O projeto é `frontend/index.html`, arquivo
> único, servido estaticamente pelo FastAPI.
>
> **Regras obrigatórias:**
> 1. Não invente cor nova — use as variáveis já declaradas no `:root`
>    (ver docs/FRONTEND_GUIDELINES.md). Se precisar de uma cor que não
>    existe, declare a variável primeiro, não use hex direto na regra.
> 2. Reatividade via Alpine (`x-show`, `x-for`, `x-model`, `x-text`,
>    `x-on`) — nunca `document.getElementById` pra ler/escrever valor.
> 3. Toda chamada de API passa pelo objeto `API` já existente
>    (`API.get/postJson/postForm`), nunca `fetch` solto num componente novo.
> 4. Se a tela usa ícone, é Lucide (`data-lucide="..."`) e precisa chamar
>    `refreshIcons()` depois de qualquer `x-for`/`x-if` que insira ícone
>    novo dinamicamente.
> 5. Entregue só os blocos pedidos (HTML do componente / CSS / métodos do
>    `app()`), não o arquivo inteiro, a menos que eu peça explicitamente.
>
> **O que preciso agora:** [descrição da tela/componente].

## Pendências conhecidas desta versão

- Sem paginação de lista de projetos/lotes/equipe (só exceções/produtos
  têm) — não é problema até o volume desses crescer muito (dezenas de
  milhares de projetos é cenário improvável).
- `generateScript()` e `login()` usam `fetch` direto em vez do objeto
  `API` — decisão deliberada, não descuido: um precisa de `blob()` em vez
  de `json()`, o outro precisa de `Content-Type` de form-urlencoded antes
  de existir token pra injetar. Documentado inline no código.
