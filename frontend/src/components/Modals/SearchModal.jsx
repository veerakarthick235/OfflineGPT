import { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { semanticSearch } from '../../api/client';
import { useConversations } from '../../hooks/useConversations';

const SearchIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
  </svg>
);
const XIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
);

export default function SearchModal() {
  const { dispatch } = useApp();
  const { selectConversation } = useConversations();
  const [query, setQuery]     = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  const close = () => dispatch({ type: 'SHOW_SEARCH', payload: false });

  const doSearch = async (q) => {
    if (!q.trim()) { setResults([]); return; }
    setLoading(true);
    try {
      const data = await semanticSearch(q, 12);
      setResults(data.results || []);
    } catch { setResults([]); }
    finally { setLoading(false); }
  };

  const handleChange = (e) => {
    setQuery(e.target.value);
    clearTimeout(window._searchTimer);
    window._searchTimer = setTimeout(() => doSearch(e.target.value), 400);
  };

  const handleResultClick = (r) => {
    if (r.conversation_id) {
      selectConversation(r.conversation_id);
      close();
    }
  };

  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="modal" style={{ maxWidth: 560 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Semantic Search</h2>
          <button className="icon-btn" onClick={close}><XIcon /></button>
        </div>
        <div className="modal-body">
          <div className="search-modal-input-wrap">
            <SearchIcon />
            <input
              className="search-modal-input"
              placeholder="Search across all conversations by meaning…"
              value={query}
              onChange={handleChange}
              autoFocus
            />
            {loading && (
              <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>Searching…</span>
            )}
          </div>

          {results.length > 0 && (
            <div className="search-results">
              {results.map((r, i) => (
                <div key={i} className="search-result-item" onClick={() => handleResultClick(r)}>
                  <div className="sr-title">
                    {r.role === 'user' ? '👤 You' : '🤖 AI'} · {r.conversation_title || 'Untitled'}
                  </div>
                  <div className="sr-content">{r.content}</div>
                  <div className="sr-score">Similarity: {(r.score * 100).toFixed(0)}%</div>
                </div>
              ))}
            </div>
          )}

          {query && !loading && results.length === 0 && (
            <div style={{ textAlign: 'center', color: 'var(--text-dim)', fontSize: 13, padding: '16px 0' }}>
              No results found. Try different keywords.
            </div>
          )}

          {!query && (
            <div style={{ textAlign: 'center', color: 'var(--text-dim)', fontSize: 13, padding: '12px 0', lineHeight: 1.7 }}>
              Powered by ChromaDB vector embeddings.<br />
              Finds conversations by meaning, not just keywords.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
