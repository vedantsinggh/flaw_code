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

---

## 🎓 Qualifier Starters Verification Guide

This system includes fully functional implementations for the Starter 1 and Starter 2 qualifiers.

### Starter 1 · OpenClaw Mastery (The Hands)
This loop demonstrates direct coding agent command, code execution, revision, and status reporting.
1. **Trigger Task**: Post a natural language coding task in `#sprint-main` (e.g. `"Create a Python script that calculates the factorial of 5"`).
2. **Execution & Log**: The Developer Agent (OpenClaw) will write the script under `forge/demo/<app_name>/main.py`, automatically execute it (using `subprocess` or LLM-based simulation if running in a restricted sandbox), and post the terminal output to `#agent-log`.
3. **Status Format**: The agent reports its progress to `#sprint-main` using the requested status format:
   - **What I Did**
   - **What's Left**
   - **What Needs Your Call**
4. **Code Revision**: Post a change request in `#sprint-main` (e.g. `"Change it to support floats instead"` or `"Add print statements"`). OpenClaw will automatically fetch the last task, modify the code, execute it, post the updated output to `#agent-log`, and re-report the status.

### Starter 2 · Hermes Agent Mastery (The Brain)
This loop demonstrates persistent memory recall, dynamic skill engine execution, plan-before-action planning, and event/schedule-based autonomous runs.
1. **Memory Recall**:
   - Tell Hermes a fact: Post `"Remember that my favorite programming language is Go"` in `#sprint-main`. Hermes will save this fact to `memory.json` and post a confirmation to `#agent-log`.
   - Ask Hermes to recall the fact: Post `"What is my favorite programming language?"`. Hermes will fetch the stored memory facts and answer you in `#sprint-main`.
2. **Automatic Skill Execution**:
   - Trigger a custom skill: Post `"Say hello to the NMG Labs team"`. The Skill Engine matches this to the `hello-world` skill trigger (configured under `skills/hello-world/SKILL.md`).
   - Action: Hermes automatically processes the skill, generates a friendly greeting, saves it to `greetings.md`, and logs the skill action to `#agent-log`.
3. **Plan Before Action**:
   - When a goal/sprint is initiated (e.g. `/forge sprint "Build a FastAPI CRUD app"`), Hermes decomposes the goal and posts a structured plan list overview to `#sprint-main` and `#agent-orchestrator` *before* committing or starting execution.
4. **Autonomous Run**:
   - The system schedules an autonomous run on startup. Five seconds after the server boots, it posts to `#sprint-main` (`⏰ Scheduled Event: Triggering daily autonomous health run`) and initiates an automated system report generation sprint.

