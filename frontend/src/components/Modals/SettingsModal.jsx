import { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { uploadDocument, getDocuments, deleteDocument } from '../../api/client';

const XIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
);
const TrashIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="3,6 5,6 21,6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
  </svg>
);

export default function SettingsModal() {
  const { state, dispatch, toast } = useApp();
  const [docs, setDocs]           = useState([]);
  const [docsLoaded, setDocsLoaded] = useState(false);
  const [uploading, setUploading] = useState(false);

  const close = () => {
    dispatch({ type: 'SHOW_SETTINGS', payload: false });
  };

  const loadDocs = async () => {
    if (docsLoaded) return;
    try {
      const list = await getDocuments();
      setDocs(list);
      setDocsLoaded(true);
    } catch {}
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    try {
      const doc = await uploadDocument(file);
      setDocs(prev => [doc, ...prev]);
      toast(`"${file.name}" uploaded (${doc.chunk_count} chunks)`, 'success');
    } catch (err) {
      toast('Upload failed: ' + err.message, 'error');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleDeleteDoc = async (id, name) => {
    if (!confirm(`Delete "${name}"?`)) return;
    try {
      await deleteDocument(id);
      setDocs(prev => prev.filter(d => d.id !== id));
      toast('Document deleted', 'info');
    } catch {
      toast('Delete failed', 'error');
    }
  };

  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Settings</h2>
          <button className="icon-btn" onClick={close}><XIcon /></button>
        </div>
        <div className="modal-body">

          {/* Model */}
          <div className="modal-group">
            <label className="modal-label">Default Model</label>
            <select
              className="modal-select"
              value={state.selectedModel}
              onChange={e => dispatch({ type: 'SET_MODEL', payload: e.target.value })}
            >
              {(state.models.length ? state.models : [state.selectedModel]).map(m => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>

          {/* Temperature */}
          <div className="modal-group">
            <label className="modal-label">Temperature
              <span style={{ color: 'var(--green)', marginLeft: 8 }}>{state.temperature}</span>
            </label>
            <div className="range-row">
              <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>0</span>
              <input
                type="range" min="0" max="2" step="0.05"
                className="range-slider"
                value={state.temperature}
                onChange={e => dispatch({ type: 'SET_TEMP', payload: parseFloat(e.target.value) })}
              />
              <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>2</span>
            </div>
            <span className="modal-hint">Higher = more creative. Lower = more focused.</span>
          </div>

          {/* System prompt */}
          <div className="modal-group">
            <label className="modal-label">System Prompt</label>
            <textarea
              className="modal-input"
              style={{ minHeight: 80, resize: 'vertical' }}
              placeholder="You are a helpful assistant…"
              value={state.systemPrompt}
              onChange={e => dispatch({ type: 'SET_SYS', payload: e.target.value })}
            />
            <span className="modal-hint">Applied at the start of every conversation.</span>
          </div>

          {/* RAG Documents */}
          <div className="modal-group">
            <label className="modal-label">RAG Documents</label>
            <span className="modal-hint">Upload .txt or .md files to ask the AI about their contents.</span>
            <label
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                padding: '8px 14px', marginTop: 6,
                background: 'var(--bg-hover)',
                border: '1px solid var(--border-md)',
                borderRadius: 'var(--r-sm)',
                cursor: uploading ? 'wait' : 'pointer',
                fontSize: 13, fontWeight: 500,
              }}
              onClick={loadDocs}
            >
              {uploading ? 'Uploading…' : '+ Upload File'}
              <input
                type="file"
                accept=".txt,.md,.csv,.json"
                style={{ display: 'none' }}
                onChange={handleFileUpload}
                disabled={uploading}
              />
            </label>

            {docsLoaded && docs.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 8 }}>
                {docs.map(d => (
                  <div key={d.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', background: 'var(--bg-hover)', borderRadius: 'var(--r-sm)', fontSize: 13 }}>
                    <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.filename}</span>
                    <button
                      style={{ color: 'var(--red)', display: 'flex', alignItems: 'center' }}
                      onClick={() => handleDeleteDoc(d.id, d.filename)}
                    >
                      <TrashIcon />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Danger zone */}
          <div style={{ paddingTop: 12, borderTop: '1px solid var(--border)' }}>
            <label className="modal-label" style={{ marginBottom: 8, display: 'block' }}>Danger Zone</label>
            <button
              className="btn-danger"
              onClick={() => {
                if (!confirm('Clear ALL conversation history? This cannot be undone.')) return;
                fetch('/api/conversations').then(r => r.json()).then(convs => {
                  Promise.all(convs.map(c => fetch(`/api/conversations/${c.id}`, { method: 'DELETE' })))
                    .then(() => {
                      dispatch({ type: 'SET_CONVERSATIONS', payload: [] });
                      dispatch({ type: 'SET_CURRENT', payload: null });
                      dispatch({ type: 'SET_MESSAGES', payload: [] });
                      close();
                      toast('All conversations deleted', 'info');
                    });
                });
              }}
            >
              Clear All Conversations
            </button>
          </div>

        </div>
      </div>
    </div>
  );
}
