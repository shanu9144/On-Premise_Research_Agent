# Fieldnotes: a web research agent

Ask a question, get a short **cited digest** and a **source trail**, and keep every answer in a private history. The agent searches the web through a budget-aware, provider-neutral layer (Tavily, Exa, Firecrawl), then writes the digest with an LLM (Groq's free tier, or a local Ollama model).

- **Cited answers:** claims reference numbered sources, and sources stay visible.
- **Cost-aware search:** it picks one provider by capability and remaining budget, and falls back only on failure.
- **Saved history:** SQLite locally, Turso (free hosted SQLite) when deployed. Full digests load only when you open them.
- **Free to run:** Groq, Tavily and Turso all have free tiers.

## Quick start (Windows PowerShell)

Requires Python 3.12+ and Node 20.19+ (or 22.12+).

**1. Backend**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env        # then fill in GROQ_API_KEY and TAVILY_API_KEY
.\.venv\Scripts\python.exe research_agent.py      # API on http://127.0.0.1:8000
```

**2. Frontend** (in a second terminal)

```powershell
cd frontend
npm install
npm run dev                         # http://localhost:5173
```

The frontend talks to `http://127.0.0.1:8000` by default. Set `VITE_API_URL` in `frontend/.env.local` to point elsewhere.

**Using a local model instead of Groq:** install [Ollama](https://ollama.com), run `ollama pull qwen3.5:4b`, and leave `GROQ_API_KEY` empty (or set `LLM_PROVIDER=ollama`).

**Without any search key**, Tavily's rate-limited keyless mode still works (about 10 searches a day), which is enough to try it out.

## Configuration

Settings come from environment variables, which override the git-ignored `.env`. See [.env.example](.env.example) for a template.

| Variable | Purpose | Default |
|---|---|---|
| `GROQ_API_KEY` | Enables Groq as the LLM ([get a free key](https://console.groq.com/keys)) | unset: uses Ollama |
| `GROQ_MODEL` | Groq model | `openai/gpt-oss-120b` |
| `LLM_PROVIDER` | Force `groq` or `ollama` | auto |
| `TAVILY_API_KEY`, `TAVILY_DAILY_BUDGET`, `TAVILY_MONTHLY_BUDGET` | Tavily search and credit budgets | keyless |
| `EXA_API_KEY`, `EXA_DAILY_BUDGET`, `EXA_MONTHLY_BUDGET`, `EXA_RESERVE` | Exa search. Disabled until both budgets are above 0 (USD) | disabled |
| `FIRECRAWL_API_KEY`, `FIRECRAWL_DAILY_BUDGET`, `FIRECRAWL_MONTHLY_BUDGET` | Firecrawl scrape and crawl | disabled |
| `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN` | Store history in Turso instead of local SQLite | local SQLite |
| `HISTORY_DB` | Path of the local history database | `.research_agent/history.sqlite3` |
| `CORS_ORIGINS` | Comma-separated frontend origins, no trailing slash | `http://localhost:5173,http://127.0.0.1:5173` |
