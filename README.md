# Sirex RWA Dashboard

Real-time analytics dashboard for Ondo Finance tokenized assets (OUSG & USDY) with AI-powered market intelligence.

🌐 **Live**: https://aicetro.com

## Features

### 📊 Ondo Pulse
- Real-time TVL tracking for OUSG and USDY
- Holder analytics and whale monitoring with Arkham labels
- Transfer volume and activity trends
- APY history and concentration metrics
- NAV deviation tracking
- AI-generated market commentary

### 🌍 Event Radar
- Global news monitoring via GDELT
- Geopolitical risk assessment
- Event correlation with market movements
- Real-time stress level indicators

### 🧪 Scenario Lab
- Multi-agent market simulation (20 AI agents)
- 4 different LLM models for diverse perspectives
- 2-round consensus building with cross-model interaction
- Institutional, retail, bot, and regulatory agent profiles
- Scenario-based forecasting

## Tech Stack

- **Backend**: FastAPI, Python 3.11
- **Frontend**: HTMX, TailwindCSS, Chart.js, Leaflet
- **Data Sources**: Dune Analytics, GDELT, Arkham Intelligence
- **AI Models**: OpenRouter (GPT-4o-mini, Qwen 2.5, Nemotron, Trinity)
- **Database**: SQLite with async support (aiosqlite)
- **Deployment**: Docker, Nginx with SSL/TLS

## Quick Start

### Prerequisites
- Docker & Docker Compose
- API Keys:
  - Dune Analytics API key
  - OpenRouter API key
  - Arkham Intelligence API key (optional)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/MixasV/ondo.git
cd ondo
```

2. Copy environment file and configure:
```bash
cp .env.example .env
nano .env
```

Add your API keys:
```env
DUNE_API_KEY=your_dune_key
OPENROUTER_API_KEY=your_openrouter_key
ARKHAM_API_KEY=your_arkham_key
```

3. Start the application:
```bash
docker-compose up -d
```

4. Access the dashboard:
```
http://localhost
```

## Configuration

### Automatic Data Updates
- Data refreshes automatically every hour in background
- Manual updates available via "Manual Update" button in UI
- Progress tracking with 12-stage update process

### Agent Profiles
20 AI agents with different perspectives:
- **5 agents**: Nvidia Nemotron (institutional investors, retail)
- **5 agents**: Arcee Trinity (DeFi bots, fund managers, regulators)
- **5 agents**: OpenAI GPT-4o-mini (investment banks, market makers, pension funds)
- **5 agents**: Qwen 2.5 (DeFi protocols, macro traders, quant funds)

Edit `agents/profiles.json` to customize agent behavior.

### Nginx Configuration
- SSL certificates managed via Let's Encrypt
- Automatic renewal configured
- 300s timeout for long-running simulations

## Development

### Project Structure
```
.
├── app/
│   ├── analysis/          # AI commentary & simulation
│   │   ├── commentary.py  # Market commentary generation
│   │   ├── metrics.py     # Stress level calculations
│   │   └── simulation.py  # Multi-agent simulation
│   ├── data/              # Data clients
│   │   ├── dune.py        # Dune Analytics API
│   │   ├── gdelt.py       # GDELT news API
│   │   ├── arkham.py      # Arkham Intelligence API
│   │   ├── prices.py      # Price data
│   │   ├── cache.py       # SQLite cache layer
│   │   └── health.py      # Data health monitoring
│   ├── static/            # CSS & JS
│   ├── templates/         # HTML templates
│   ├── config.py          # Configuration
│   └── main.py            # FastAPI app
├── agents/
│   └── profiles.json      # Agent configurations
├── cron/
│   └── update_data.py     # Scheduled data updates
├── data/
│   ├── cache.db           # SQLite database
│   └── address_labels.json # Cached address labels
├── docker-compose.yml
├── Dockerfile
├── nginx.conf
└── requirements.txt
```

### Running Locally (without Docker)
```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python run.py
```

Access at `http://localhost:8000`

### Manual Data Update
```bash
python cron/update_data.py
```

## API Endpoints

- `GET /` - Main dashboard
- `GET /api/metrics` - Get current metrics (JSON)
- `GET /api/events` - Get recent events (JSON)
- `POST /api/simulate` - Run market simulation
- `POST /api/update` - Trigger manual data update
- `GET /api/update/status` - Get update progress
- `GET /api/health` - Data health monitoring
- `GET /api/commentary` - AI market commentary

## Deployment

### Production Setup

1. Configure domain DNS (A records pointing to server IP)
2. Install Docker and Docker Compose on server
3. Copy project files to server
4. Configure `.env` with production API keys
5. Run deployment:

```bash
cd /root/Dune
docker-compose up -d --build
```

6. Configure SSL with Let's Encrypt:
```bash
certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com
mkdir -p ssl
cp /etc/letsencrypt/live/yourdomain.com/*.pem ssl/
docker-compose restart
```

### Monitoring

View logs:
```bash
docker-compose logs -f
```

Check data health:
```bash
curl https://yourdomain.com/api/health
```

Check update status:
```bash
curl https://yourdomain.com/api/update/status
```

## Features in Detail

### Data Health Monitoring
- Tracks freshness and latency of all data sources
- Automatic error detection and recovery
- Health status available via `/api/health` endpoint

### Multi-Agent Simulation
- **Round 1**: Independent agent responses based on scenario
- **Round 2**: Agents see responses from other models and adjust
- Cross-model interaction for diverse perspectives
- Consensus building with confidence scoring

### AI Commentary
- Automatically generated market analysis
- Considers on-chain metrics, news events, and whale activity
- Cached for 1 hour to reduce API costs
- Force refresh available via API parameter

## Data Sources

- **Dune Analytics** - On-chain metrics (supply, holders, transfers, APY)
- **GDELT** - Global news events with geolocation
- **Arkham Intelligence** - Address labels and entity identification
