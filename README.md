# ForgeOS — AI Engineering Operating System

ForgeOS is a production-quality Multi-Agent AI Engineering Operating System designed to automate software development lifecycles. Orchestrated by Hermes and executed via OpenClaw, it plans, implements, quality-tests, audits, and documents features.

---

## 🚀 Key Features

- **Multi-Agent Coordination**: Hermes orchestrates, Developer implements, QA verifies, Security audits, and Documentation writes.
- **Intelligent Model Router**: Explains and executes model routing (Qwen2.5-Coder, DeepSeek V3, GPT-OSS-120B) based on task complexity.
- **Claude-style Skill Engine**: Dynamically loads only relevant skill directories into context, logging every loaded skill.
- **Real-Time Kanban & Stats Dashboard**: A sleek dark engineering theme displaying live columns, token usage, coverages, and Slack feeds.
- **Model Context Protocol (MCP)**: Supports native tool integrations with official Slack and GitHub MCP servers.

---

## 🛠️ Tech Stack

- **Frontend**: React 19, Vite, TailwindCSS, TypeScript, Lucide Icons
- **Backend**: FastAPI (Python 3.11), Pydantic v2, JSON Database Store
- **Containers**: Docker & Docker Compose
- **Orchestration**: Hermes & OpenClaw

---

## 📁 Repository Structure

```
forge2/
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI App Entrypoint
│   │   ├── config.py           # Configuration Settings
│   │   ├── db/                 # Persistent store files
│   │   ├── agents/             # Hermes, Developer, QA, Security, Doc agents
│   │   ├── skills/             # Dynamic skill engine
│   │   ├── router/             # Model router
│   │   ├── slack/              # Slack webhook client
│   │   ├── github/             # GitHub client
│   │   ├── mcp/                # Slack & GitHub MCP stdio clients
│   │   └── health/             # Health checker
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx             # Main React Dashboard
│   │   ├── index.css
│   │   └── main.tsx
│   ├── Dockerfile
│   ├── tailwind.config.js
│   └── package.json
├── skills/                     # Skill templates (fastapi, testing, security, etc.)
├── docker-compose.yml
├── .env.example
├── ARCHITECTURE.md             # In-depth architectural designs
└── README.md
```

---

## ⚙️ Quick Start

### 1. Prerequisite
- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)

### 2. Configure Environment
Clone the environment template to create the `.env` configuration file:
```bash
cp .env.example .env
```

### 3. Run ForgeOS
Launch the system utilizing Docker Compose:
```bash
docker compose up --build
```

- **Frontend Dashboard**: [http://localhost:3000](http://localhost:3000)
- **FastAPI Backend API Swagger**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## ⚙️ Running Locally (Without Docker)

### Backend Setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

---

## 🛡️ Live Slack & GitHub MCP Integration

For detailed instructions on configuring live integrations, please consult the [Slack & GitHub MCP guide in ARCHITECTURE.md](file:///home/mirage/Projects/forge2/ARCHITECTURE.md#6-how-to-integrate-slack--github-model-context-protocol-mcp).
