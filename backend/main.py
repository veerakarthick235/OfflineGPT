from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .services import sqlite_db
from .services import image_library
from .services.stt  import whisper_service as stt_svc
from .services.rag  import incremental as rag_incremental
from .services.rag  import bm25_index   as rag_bm25
from .services.memory import conversation as mem_conv
from .services.memory import long_term    as mem_lt
from .services.repo    import symbol_store as repo_store
from .services.sandbox import execution_store as exec_store
from .services.attachments import attachment_store as att_store
from .routers import conversations, chat, models, search, documents, images, library, stt, rag, memory, agent, repo, code_exec, attachments


@asynccontextmanager
async def lifespan(app: FastAPI):
    await sqlite_db.init_db()
    await image_library.init_table()
    await rag_incremental.init_table()   # chunk hashes for incremental indexing
    await mem_conv.init_table()          # conversation memory summaries
    await mem_lt.init_table()            # long-term user facts
    await repo_store.init_tables()       # repository symbol index
    await exec_store.init_table()        # code execution history
    await att_store.init_table()         # attachment metadata
    print("[OK] SQLite ready (RAG + Memory + Repo + Exec + Attachments)")
    # Warm up BM25 index (loads from disk)
    _ = rag_bm25.get_index()
    print(f"[OK] BM25 index ready ({rag_bm25.get_index().chunk_count} chunks)")
    # Auto-load Whisper model if one is already downloaded
    try:
        from .services.stt.model_manager import is_downloaded
        for mid in ("base", "tiny", "small", "medium"):
            if is_downloaded(mid):
                await stt_svc.load_model(mid)
                break
    except Exception as e:
        print(f"[STT] auto-load skipped: {e}")
    yield
    print("[BYE] Shutting down")


app = FastAPI(
    title="OfflineGPT API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversations.router)
app.include_router(chat.router)
app.include_router(models.router)
app.include_router(search.router)
app.include_router(documents.router)
app.include_router(images.router)
app.include_router(library.router)
app.include_router(stt.router)
app.include_router(rag.router)
app.include_router(memory.router)
app.include_router(agent.router)
app.include_router(repo.router)
app.include_router(code_exec.router)
app.include_router(attachments.router)


@app.get("/api/health")
async def health():
    from .services import ollama as ol
    return {"status": "ok", "ollama": await ol.is_online()}


@app.get("/")
async def root():
    return {"message": "OfflineGPT API v2.0 — http://localhost:5173"}
