# ForgeOS — System Architecture

ForgeOS is an Autonomous Multi-Agent Software Engineering Operating System built to plan, implement, test, audit, and document software requirements.

---

## 1. System Topology & Agent Hierarchy

ForgeOS divides work using a coordinate-and-execute structure. Hermes serves as the supervisor while domain-specific agents run implementation, quality testing, security, and technical writing.

```mermaid
graph TD
    User([User Request]) --> Hermes[Hermes Agent: Orchestrator & Planner]
    
    subgraph Core System Orchestration
        Hermes --> Router[Intelligent Model Router]
        Hermes --> SkillEng[Claude-Style Skill Engine]
        Hermes --> DB[(JSON database Store)]
    end
    
    subgraph Execution Loop
        Hermes --> Dev[Developer Agent]
        Dev --> OpenClaw[OpenClaw Executor]
        OpenClaw --> QA[QA Agent]
        QA --> Sec[Security Agent]
        Sec --> Doc[Documentation Agent]
    end

    subgraph External Interfaces
        Hermes -.-> Slack[Slack channels]
        Dev -.-> Slack
        QA -.-> Slack
        Sec -.-> Slack
        Doc -.-> Slack
        
        Dev -.-> GitHub[(GitHub Repo)]
        Doc -.-> GitHub
    end
```

---

## 2. Dynamic Agent Workflow (Data Flow)

The typical lifecycle of a goal submitted to ForgeOS transitions across defined Slack channels and columns in the Kanban board:

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Hermes as Hermes (PO & Orchestrator)
    participant Dev as Developer Agent (OpenClaw)
    participant QA as QA Agent (Pytest/Ruff)
    participant Sec as Security Agent (Bandit/Semgrep)
    participant Doc as Documentation Agent
    participant Slack as Slack Channels

    User->>Slack: Submit goal in "#sprint-main"
    Hermes->>Slack: Acknowledge & plan sprint in "#sprint-main"
    Note over Hermes: Classifies skills & routes LLMs
    Hermes->>Hermes: Decompose into Kanban Tasks
    Hermes->>Slack: Assign task to OpenClaw in "#agent-coder"
    
    activate Dev
    Dev->>Slack: Acknowledge assignment in "#agent-coder"
    Note over Dev: Writes code files in workspace & runs tests
    Dev->>Slack: Post execution reports & logs in "#agent-log"
    Dev->>QA: Handoff Task (Review -> Testing)
    deactivate Dev

    activate QA
    Note over QA: Executes pytest & ruff checks
    QA->>Slack: Post status in "#agent-qa" & "#ci-cd"
    QA->>Sec: Handoff Task (Testing -> Security)
    deactivate QA

    activate Sec
    Note over Sec: Audit code for vulnerabilities
    Sec->>Slack: Post status in "#agent-security"
    Sec->>Doc: Handoff Task (Security -> Documentation)
    deactivate Sec

    activate Doc
    Note over Doc: Generates README.md, API.md, CHANGELOG.md
    Doc->>Slack: Request review in "#human-review" & post summary in "#sprint-main"
    deactivate Doc

    Hermes->>Slack: Summarize progress in "#sprint-main"
```

---

## 3. Intelligent Model Routing

The Model Router dynamically selects the model based on task complexity (expected LOC, reasoning, ambiguity, dependencies):

```mermaid
graph TD
    Task[Task Requirements] --> Parse[Evaluate Complexity Metrics]
    Parse --> |LOC < 100, Low Reasoning| Qwen[Qwen2.5-Coder]
    Parse --> |LOC > 100 or Medium Reasoning| DeepSeek[DeepSeek V3]
    Parse --> |High Architectural Impact or Ambiguity| GPT[GPT-OSS-120B]
    
    Qwen --> Log[Record: Model, Reason, Est. Cost, Tokens, Confidence]
    DeepSeek --> Log
    GPT --> Log
    Log --> DB[(JSON database Store)]
```

---

## 4. Claude-Style Skill Engine

- **Skill Directory Structure**:
  - `skills/<skill_name>/SKILL.md`: Details capabilities.
  - `skills/<skill_name>/rules.md`: Strict coding rules.
  - `skills/<skill_name>/checklist.md`: Verifications required before handoff.
- **Dynamic Loading**:
  - Hermes parses the user query and identifies keywords.
  - Only matching skills are loaded into the LLM system prompt.
  - Unnecessary skills are excluded to save token cost and prevent LLM confusion.

---

## 5. Memory Persistence Layer

ForgeOS retains historical context in `memory/memory.json` to prevent repetitive errors:
1. **Architectural Decisions**: Records system-wide configurations and tech stack agreements.
2. **Remediated Bug Fixes**: Logs linter/compiler failures and details how they were fixed.
3. **Successful Workflows**: Tracks prompt configurations that produced valid results.

---

## 6. How to Integrate Slack & GitHub Model Context Protocol (MCP)

Model Context Protocol (MCP) is a protocol developed by Anthropic that allows agents to declare client/server connections and consume remote tool configurations.

ForgeOS provides an `MCPManager` (located in `backend/app/mcp/client.py`) that can spawn official Slack and GitHub MCP servers over `stdio` transport, query their list of tools, and run them when API credentials are provided.

### Integration Steps

#### Step 1: Prepare Node.js & npx
Ensure Node.js v18+ is installed on the host system, as MCP servers are launched using `npx`.

#### Step 2: Configure Environment Variables
Add your live credentials to the `.env` file in the root directory:

```bash
# Enable live execution instead of simulation
SIMULATION_MODE=false

# Slack Bot token with chat:write, channels:read permissions
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token

# GitHub token with repo access
GITHUB_TOKEN=ghp_yourgithubtoken
GITHUB_REPOSITORY=your-github-username/your-repo-name
```

#### Step 3: Run the Services
When ForgeOS boots via Docker Compose or manually, `MCPManager` automatically identifies that `SIMULATION_MODE=false` and credentials are set:
1. It launches the GitHub MCP server subprocess:
   `npx -y @modelcontextprotocol/server-github`
2. It launches the Slack MCP server subprocess:
   `npx -y @modelcontextprotocol/server-slack`
3. Hermes and Developer agents will then automatically route all repository write commands and Slack notifications through these MCP tool proxies rather than standard HTTP requests.
