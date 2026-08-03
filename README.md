# OfflineGPT v2

> A fully offline, private ChatGPT — runs entirely on your machine. No internet required. No data ever leaves your device.

**Stack:** React + Vite · Python FastAPI · SQLite · ChromaDB · Ollama

---

## Quick Start

### Prerequisites
| Tool | Download |
|------|----------|
| **Ollama** | https://ollama.com |
| **Python 3.10+** | https://python.org |
| **Node.js 18+** | https://nodejs.org |

### 1. Pull an AI model (one-time)
```bash
ollama pull llama3.2        # 2 GB — recommended
ollama pull mistral         # 4 GB
ollama pull llama3.1:8b     # 5 GB
```

### 2. Launch
```
Double-click  start.bat
```

The script installs all packages, starts both servers, and opens your browser automatically.

| Service | URL |
|---------|-----|
| App (React) | http://localhost:5173 |
| API (FastAPI) | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

---

## Features

### Core Chat
| Feature | Details |
|---------|---------|
| **Streaming responses** | Token-by-token SSE streaming from FastAPI → React |
| **Multiple conversations** | Full sidebar with history, rename, delete |
| **Model switcher** | Switch between any Ollama model mid-session |
| **Markdown rendering** | Tables, lists, bold, code — all rendered |
| **Syntax highlighting** | Code blocks with language detection |
| **Stop generation** | Cancel streaming at any time |
| **Copy / Regenerate** | On every AI message |
| **Temperature control** | Adjustable per conversation |
| **System prompt** | Custom persona per conversation |

### Phase 1 — Hybrid RAG
Upload documents and ask questions about them. Uses a **BM25 + semantic** hybrid search for best retrieval accuracy.
- Supported: `.txt`, `.md`, `.pdf`, `.docx`, and more
- Incremental indexing — only re-indexes changed files
- ChromaDB vector store + BM25 keyword fallback

### Phase 2 — Hierarchical Memory
The AI remembers across sessions — automatically.
- **Short-term:** Full conversation window with smart trimming
- **Mid-term:** Per-conversation summaries (auto-generated)
- **Long-term:** Persistent user facts extracted from chat (`name`, `preferences`, `projects`)
- Memory block injected into every system prompt

### Phase 3 — Agentic Tool Orchestration
The AI automatically selects and uses the right tool without you having to ask.

| Tool | Trigger |
|------|---------|
| `rag_search` | "What does the document say about…" |
| `image_generate` | "Create image of…" |
| `web_calculator` | Math expressions |
| `datetime` | "What time/date is it?" |
| `memory_recall` | "What do you know about me?" |

### Phase 4 — Repository Intelligence
Point the AI at an entire codebase — it understands structure, symbols, and dependencies.
- Indexes functions, classes, imports across 20+ languages
- Symbol search: find any function/class by name or description
- File-level context for code review and explanation
- Works with local folders or extracted ZIPs

### Phase 5 — Code Execution Sandbox
The AI writes code and runs it locally, incorporating real output into its response.
- Executes Python, JavaScript, Bash, and more
- Fully sandboxed subprocess with timeout
- No network access during execution
- Execution history per conversation

### Phase 6 — Universal Attachment Intelligence
Upload any file — the AI automatically detects the type and processes it correctly. Identical experience to ChatGPT attachments.

| File Type | Extensions | How it's processed |
|-----------|-----------|-------------------|
| **PDF** | `.pdf` | PyMuPDF page extraction + OCR fallback |
| **Word** | `.docx`, `.doc` | python-docx + table extraction |
| **PowerPoint** | `.pptx` | Slide text + speaker notes |
| **Spreadsheet** | `.csv`, `.xlsx`, `.xls` | pandas: stats, preview, correlations |
| **Data** | `.json`, `.xml` | Structured parsing + summary |
| **Images** | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp` | Ollama vision model (llava) |
| **Code** | `.py`, `.js`, `.ts`, `.java`, `.cpp`, `.go`, `.rs`, … | Symbol extraction + full source |
| **Text** | `.txt`, `.md`, `.rtf` | Encoding-aware extraction |
| **Archives** | `.zip` | Safe extraction + re-route each file |

**UX:** Single 📎 button → chips appear above input → AI reads files automatically when you send.

### Speech (STT)
- **Hold-to-speak** mic button (offline Whisper)
- Transcribes your voice locally — no cloud API
- Supports tiny / base / small / medium Whisper models
- Download models from the Models panel

### Image Generation
- Local diffusion models via HuggingFace Diffusers
- Just type `Create image of a sunset over mountains`
- Gallery of all generated images
- Works offline, no API key needed

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Shift + Enter` | New line |
| `Ctrl + /` | New chat |
| `Ctrl + K` | Semantic search |
| `Escape` | Close modals |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              React + Vite  :5173                    │
│  Sidebar · Chat · Input · Modals · Voice            │
└──────────────────────┬──────────────────────────────┘
                       │  REST + SSE  /api/*
┌──────────────────────▼──────────────────────────────┐
│              FastAPI  :8000                         │
│                                                     │
│  /api/chat/stream     ← SSE streaming chat          │
│  /api/attachments/*   ← file upload + processing    │
│  /api/documents/*     ← RAG document management     │
│  /api/memory/*        ← long-term memory            │
│  /api/repo/*          ← repository intelligence     │
│  /api/exec/*          ← code execution sandbox      │
│  /api/images/*        ← image generation            │
│  /api/stt/*           ← speech-to-text              │
│                                                     │
│  ┌─────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │   SQLite    │  │ ChromaDB │  │ Ollama :11434  │  │
│  │ (messages,  │  │ (vectors,│  │ (LLM, vision, │  │
│  │  memory,    │  │  RAG,    │  │  embeddings)  │  │
│  │  attachments│  │  attach) │  └───────────────┘  │
│  └─────────────┘  └──────────┘                     │
└─────────────────────────────────────────────────────┘
```

---

## File Structure

```
offlinegpt-v2/
├── start.bat                    ← One-click launcher
│
├── frontend/                    ← React + Vite
│   └── src/
│       ├── components/
│       │   ├── Chat/            ← Messages, streaming, tool indicators
│       │   ├── Header/          ← Model selector
│       │   ├── Input/           ← Pill input, 📎 attach, mic
│       │   ├── Modals/          ← Settings, search, STT, repo manager
│       │   └── Sidebar/         ← Conversation list
│       ├── hooks/               ← useChat, useConversations, useWhisperSTT
│       ├── context/             ← AppContext (global state)
│       └── api/                 ← client.js (fetch + SSE)
│
└── backend/                     ← FastAPI
    ├── main.py                  ← App entry point + lifespan
    ├── schemas.py               ← Pydantic request/response models
    ├── routers/                 ← One file per API group
    │   ├── chat.py              ← SSE streaming + agent + memory + attachments
    │   ├── attachments.py       ← File upload/process/delete
    │   ├── documents.py         ← RAG document management
    │   ├── memory.py            ← Memory facts + summaries
    │   ├── repo.py              ← Repository indexing + search
    │   ├── code_exec.py         ← Sandbox execution
    │   ├── images.py            ← Image generation
    │   └── stt.py               ← Whisper speech-to-text
    ├── services/
    │   ├── attachments/         ← Phase 6: file parsers + pipeline
    │   │   └── parsers/         ← pdf, docx, pptx, csv, image, code, zip
    │   ├── agent/               ← Phase 3: planner + executor
    │   ├── memory/              ← Phase 2: conversation + long-term memory
    │   ├── rag/                 ← Phase 1: BM25 + semantic hybrid
    │   ├── repo/                ← Phase 4: symbol indexer + chunker
    │   ├── sandbox/             ← Phase 5: code execution
    │   ├── stt/                 ← Whisper STT model manager
    │   ├── image/               ← Diffusers image generation
    │   ├── sqlite_db.py         ← All DB operations
    │   ├── chroma_db.py         ← Vector store operations
    │   └── ollama.py            ← Ollama API client
    └── data/                    ← Auto-created at first run
        ├── offlinegpt.db        ← SQLite database
        ├── chroma_db/           ← Vector embeddings
        └── uploads/             ← Uploaded attachments
```

---

## Optional: GPU Acceleration

For faster image generation and inference, install the CUDA version of PyTorch:

```bash
# CUDA 12.x
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

## Optional: Image Analysis (Vision)

To enable AI analysis of uploaded images:

```bash
ollama pull llava    # 4 GB — vision model
```

Without it, image uploads fall back to EXIF metadata extraction.

---

## Privacy

- **Zero telemetry** — no analytics, no tracking
- **Zero cloud** — no API calls to OpenAI, Google, or any external service
- **All data local** — conversations, files, embeddings, models stay on your machine
- **Air-gap safe** — works with no internet connection after initial model download
