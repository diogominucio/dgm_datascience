# Blinds.com Price Monitor

Sistema de monitoramento de preços e promoções do site blinds.com com relatórios executivos de inteligência competitiva.

## Categorias Monitoradas

- **Cellular Shades**
- **Faux Wood Blinds**
- **Wood Blinds**
- **Roman Shades**
- **Roller Shades**

## Funcionalidades

- Scraping diário de preços e promoções
- Classificação em Price Tiers (MSRP e preço final)
- Armazenamento de histórico em CSV para análise de tendências
- Detecção automática de alterações de preço
- Análise de padrões semanais e mensais de promoções
- Relatório HTML executivo com análise de competidor
- Envio automático por e-mail
- Deployment via Cloudflare Workers (serverless)

## Price Tiers

| Tier | Faixa de Preço |
|------|---------------|
| Tier 1 | $0 - $70 |
| Tier 2 | $70 - $100 |
| Tier 3 | $100 - $150 |
| Tier 4 | $150 - $200 |
| Tier 5 | $200 - $300 |
| Tier 6 | $300+ |

## Setup — Execução Local (Python)

### 1. Instalar dependências

```bash
cd blinds_monitor
pip install -r requirements.txt
```

### 2. Configurar variáveis de ambiente

```bash
cp .env.example .env
# Editar .env com suas credenciais
```

Para enviar e-mails via Gmail, você precisa de uma **App Password**:
1. Acesse https://myaccount.google.com/apppasswords
2. Gere uma senha para "Mail"
3. Use essa senha no `SMTP_PASSWORD`

### 3. Executar

```bash
# Execução completa (scrape + relatório + email)
python main.py

# Apenas scraping
python main.py --scrape-only

# Apenas relatório (usando dados existentes)
python main.py --report-only

# Execução agendada (diário às 08:00)
python main.py --schedule
```

## Setup — Cloudflare Workers (Serverless)

### 1. Instalar Wrangler

```bash
npm install -g wrangler
wrangler login
```

### 2. Criar KV Namespace

```bash
cd cloudflare_worker
wrangler kv:namespace create PRICE_DATA
# Copie o ID gerado para wrangler.toml
```

### 3. Configurar secrets

```bash
wrangler secret put RECIPIENT_EMAIL
# Digite: Diogominucio@gmail.com
```

### 4. Deploy

```bash
wrangler deploy
```

O Worker será executado automaticamente todos os dias às 08:00 UTC via Cron Trigger.

### Endpoints

- `GET /` — Health check
- `GET /run` — Trigger manual do pipeline
- `GET /status` — Status com último snapshot

## Estrutura

```
blinds_monitor/
├── main.py              # Orchestrador principal
├── scraper.py           # Web scraper para blinds.com
├── price_analyzer.py    # Classificação de tiers e análise de tendências
├── report_generator.py  # Geração de relatórios HTML e envio de e-mail
├── config.py            # Configurações e categorias
├── requirements.txt     # Dependências Python
├── .env.example         # Template de variáveis de ambiente
├── templates/
│   └── email_report.html  # Template Jinja2 do relatório
├── data/                # Snapshots JSON e CSV histórico
├── reports/             # Relatórios HTML gerados
└── cloudflare_worker/   # Versão serverless para Cloudflare
    ├── wrangler.toml
    ├── package.json
    └── src/worker.js
```
