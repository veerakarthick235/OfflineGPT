/* API client — all calls proxied through Vite to http://localhost:8000 */

const BASE = '/api';
const BASE_URL = BASE;  // alias for explicit use in FormData fetches

async function req(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const r = await fetch(`${BASE}${path}`, opts);
  if (!r.ok) throw new Error(await r.text());
  if (r.status === 204) return null;
  return r.json();
}

// ── Conversations ────────────────────────────────────────
export const getConversations   = ()          => req('GET',    '/conversations');
export const createConversation = (data = {}) => req('POST',   '/conversations', data);
export const getConversation    = (id)        => req('GET',    `/conversations/${id}`);
export const updateConversation = (id, data)  => req('PATCH',  `/conversations/${id}`, data);
export const deleteConversation = (id)        => req('DELETE', `/conversations/${id}`);

// ── Ollama Models ────────────────────────────────────────
export const getModels = () => req('GET', '/models');
export const getStatus = () => req('GET', '/models/status');
export const getHealth = () => req('GET', '/health');

// ── Search ───────────────────────────────────────────────
export const semanticSearch = (q, limit = 10) =>
  req('GET', `/search?q=${encodeURIComponent(q)}&limit=${limit}`);

// ── Documents (RAG) ──────────────────────────────────────
export const getDocuments   = ()     => req('GET',    '/documents');
export const deleteDocument = (id)   => req('DELETE', `/documents/${id}`);
export const ragQuery       = (body) => req('POST',   '/rag/query', body);
export const getRagStatus   = ()     => req('GET',    '/rag/status');

export async function uploadDocument(file) {
  const fd = new FormData();
  fd.append('file', file);
  const r = await fetch(`${BASE}/documents`, { method: 'POST', body: fd });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

// ── Image / Model Manager ────────────────────────────────
export const getImageStatus   = ()     => req('GET',    '/images/status');
export const getImageModels   = ()     => req('GET',    '/images/models');
export const loadImageModel   = (id)   => req('POST',   `/images/models/${id}/load`);
export const unloadImageModel = ()     => req('POST',   '/images/models/unload');
export const deleteImageModel = (id)   => req('DELETE', `/images/models/${id}`);
export const generateImage    = (body) => req('POST',   '/images/generate', body);
export const getImageGallery  = ()     => req('GET',    '/images/gallery');

// ── Memory ───────────────────────────────────────────────
export const getMemoryFacts        = ()              => req('GET',    '/memory/facts');
export const addMemoryFact         = (body)          => req('POST',   '/memory/facts', body);
export const deleteMemoryFact      = (id)            => req('DELETE', `/memory/facts/${id}`);
export const clearMemoryFacts      = ()              => req('DELETE', '/memory/facts');
export const getMemorySummaries    = ()              => req('GET',    '/memory/summaries');
export const getMemoryStatus       = ()              => req('GET',    '/memory/status');
export const summarizeConversation = (convId, model = 'llama3.2') =>
  req('POST', `/memory/summaries/${convId}?model=${model}`);

// ── Agent ─────────────────────────────────────────────────
export const getAgentTools  = ()     => req('GET',  '/agent/tools');
export const classifyIntent = (body) => req('POST', '/agent/classify', body);

// ── Code Execution ────────────────────────────────────────
export const runCode          = (body) => req('POST', '/exec/run', body);
export const getExecHistory   = (convId, limit = 20) =>
  req('GET', `/exec/history${convId ? `?conversation_id=${convId}&limit=${limit}` : `?limit=${limit}`}`);
export const getExecution     = (id)   => req('GET', `/exec/${id}`);
export const getSupportedLangs= ()     => req('GET', '/exec/languages');

// ── Attachments ───────────────────────────────────────────
export const uploadAttachments = (files, conversationId) => {
  const form = new FormData();
  files.forEach(f => form.append('files', f));
  if (conversationId) form.append('conversation_id', conversationId);
  return fetch(`${BASE_URL}/attachments/upload`, {
    method:  'POST',
    headers: { Accept: 'application/json' },
    body:    form,
  }).then(r => r.json());
};
export const listAttachments    = (convId) =>
  req('GET', `/attachments${convId ? `?conversation_id=${convId}` : ''}`);
export const getAttachmentStatus= (id) => req('GET', `/attachments/${id}/status`);
export const deleteAttachment   = (id) => req('DELETE', `/attachments/${id}`);

// ── Repository Intelligence ───────────────────────────────────────────
export const listRepos      = ()           => req('GET',    '/repo');
export const getRepo        = (id)         => req('GET',    `/repo/${id}`);
export const deleteRepo     = (id)         => req('DELETE', `/repo/${id}`);
export const searchRepo     = (body)       => req('POST',   '/repo/search', body);
export const getRepoSymbols = (id, type)   =>
  req('GET', `/repo/${id}/symbols${type ? `?symbol_type=${type}` : ''}`);
export const getFileContext = (id, path)   =>
  req('GET', `/repo/${id}/files?path=${encodeURIComponent(path)}`);

export async function indexRepo(path, name, onEvent) {
  const r = await fetch(`/api/repo/index`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ path, name }),
  });
  if (!r.ok) throw new Error(await r.text());

  const reader = r.body.getReader();
  const dec    = new TextDecoder();
  let   buf    = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop();
    for (const line of lines) {
      const s = line.trim();
      if (!s.startsWith('data:')) continue;
      try { onEvent?.(JSON.parse(s.slice(5).trim())); } catch {}
    }
  }
}

// ── Streaming chat (SSE via fetch) ───────────────────────
export async function streamChat(payload, callbacks) {
  const {
    onUserMessage,
    onImageGenerating,
    onImageDone,
    onChunk,
    onDone,
    onTitleUpdate,
    onError,
    // Phase 3 — Agent tool events
    onToolStart,
    onToolResult,
    onToolError,
  } = callbacks;

  const ctrl = new AbortController();

  try {
    const res = await fetch(`${BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: ctrl.signal,
    });

    if (!res.ok) {
      onError?.(new Error(`HTTP ${res.status}`));
      return ctrl;
    }

    const reader = res.body.getReader();
    const dec    = new TextDecoder();
    let   buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += dec.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // keep incomplete last line

      for (const line of lines) {
        const s = line.trim();
        if (!s.startsWith('data:')) continue;
        try {
          const ev = JSON.parse(s.slice(5).trim());
          switch (ev.type) {
            case 'user_message':     onUserMessage?.(ev.message);      break;
            case 'image_generating': onImageGenerating?.(ev);           break;
            case 'image_done':       onImageDone?.(ev);                 break;
            case 'chunk':            onChunk?.(ev.content);             break;
            case 'done':             onDone?.(ev.message);              break;
            case 'title_update':     onTitleUpdate?.(ev);               break;
            case 'error':            onError?.(new Error(ev.content));  break;
            // Phase 3 — Agent tool events
            case 'tool_start':       onToolStart?.(ev);                 break;
            case 'tool_result':      onToolResult?.(ev);                break;
            case 'tool_error':       onToolError?.(ev);                 break;
          }
        } catch { /* partial JSON — ignore */ }
      }
    }
  } catch (err) {
    if (err.name !== 'AbortError') onError?.(err);
  }

  return ctrl;
}
