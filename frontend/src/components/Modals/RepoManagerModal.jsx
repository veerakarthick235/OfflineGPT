import { useState, useEffect, useRef } from 'react';
import { listRepos, indexRepo, deleteRepo, getRepoSymbols, searchRepo } from '../../api/client';
import './RepoManagerModal.css';

export default function RepoManagerModal({ onClose }) {
  const [repos,       setRepos]       = useState([]);
  const [activeTab,   setActiveTab]   = useState('repos');   // repos | index | search
  const [indexPath,   setIndexPath]   = useState('');
  const [indexName,   setIndexName]   = useState('');
  const [indexing,    setIndexing]    = useState(false);
  const [indexLog,    setIndexLog]    = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults,setSearchResults] = useState(null);
  const [searching,   setSearching]   = useState(false);
  const [selectedRepo,setSelectedRepo]= useState(null);
  const [symbols,     setSymbols]     = useState([]);
  const logEndRef = useRef();

  useEffect(() => { loadRepos(); }, []);
  useEffect(() => { logEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [indexLog]);

  async function loadRepos() {
    try {
      const data = await listRepos();
      setRepos(data.repos || []);
    } catch {}
  }

  async function handleIndex() {
    if (!indexPath.trim()) return;
    setIndexing(true);
    setIndexLog([{ phase: 'init', status: 'Starting…' }]);
    try {
      await indexRepo(indexPath.trim(), indexName.trim() || undefined, (ev) => {
        setIndexLog(prev => [...prev, ev]);
      });
      await loadRepos();
      setActiveTab('repos');
    } catch (err) {
      setIndexLog(prev => [...prev, { phase: 'error', status: err.message }]);
    } finally {
      setIndexing(false);
    }
  }

  async function handleDelete(repoId) {
    if (!confirm('Delete this repository index?')) return;
    try {
      await deleteRepo(repoId);
      setRepos(r => r.filter(x => x.id !== repoId));
      if (selectedRepo?.id === repoId) setSelectedRepo(null);
    } catch {}
  }

  async function handleSelectRepo(repo) {
    setSelectedRepo(repo);
    try {
      const data = await getRepoSymbols(repo.id);
      setSymbols(data.symbols || []);
    } catch {}
  }

  async function handleSearch() {
    if (!searchQuery.trim()) return;
    setSearching(true);
    setSearchResults(null);
    try {
      const data = await searchRepo({
        query:   searchQuery.trim(),
        repo_id: selectedRepo?.id || undefined,
        top_k:   6,
      });
      setSearchResults(data);
    } catch (err) {
      setSearchResults({ error: err.message });
    } finally {
      setSearching(false);
    }
  }

  const phaseIcon = (phase) => ({
    init: '🔄', walk: '📂', indexing: '⚙️', saving: '💾',
    embedding: '🧠', done: '✅', error: '❌',
  })[phase] || '•';

  return (
    <div className="repo-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="repo-modal">
        {/* Header */}
        <div className="repo-header">
          <div className="repo-header-left">
            <span className="repo-icon">💻</span>
            <div>
              <h2>Repository Intelligence</h2>
              <p>Index and search your codebases</p>
            </div>
          </div>
          <button className="repo-close" onClick={onClose}>✕</button>
        </div>

        {/* Tabs */}
        <div className="repo-tabs">
          {['repos','index','search'].map(tab => (
            <button
              key={tab}
              className={`repo-tab ${activeTab === tab ? 'active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {{ repos: '📦 Repositories', index: '➕ Index New', search: '🔍 Search Code' }[tab]}
            </button>
          ))}
        </div>

        <div className="repo-body">

          {/* ── Repos tab ─────────────────────────────────── */}
          {activeTab === 'repos' && (
            <div className="repos-list">
              {repos.length === 0 ? (
                <div className="repo-empty">
                  <div className="repo-empty-icon">📁</div>
                  <p>No repositories indexed yet.</p>
                  <button className="btn-accent" onClick={() => setActiveTab('index')}>
                    Index your first repo →
                  </button>
                </div>
              ) : repos.map(repo => (
                <div
                  key={repo.id}
                  className={`repo-card ${selectedRepo?.id === repo.id ? 'selected' : ''}`}
                  onClick={() => handleSelectRepo(repo)}
                >
                  <div className="repo-card-left">
                    <div className="repo-card-name">{repo.name}</div>
                    <div className="repo-card-path">{repo.path}</div>
                    <div className="repo-card-stats">
                      <span>📄 {repo.file_count} files</span>
                      <span>⚡ {repo.symbol_count} symbols</span>
                      <span>🔤 {repo.language}</span>
                    </div>
                  </div>
                  <button
                    className="repo-delete-btn"
                    onClick={e => { e.stopPropagation(); handleDelete(repo.id); }}
                    title="Remove index"
                  >🗑️</button>
                </div>
              ))}

              {/* Symbol panel for selected repo */}
              {selectedRepo && symbols.length > 0 && (
                <div className="symbols-panel">
                  <h3>Symbols in {selectedRepo.name}</h3>
                  <div className="symbols-list">
                    {symbols.slice(0, 60).map(s => (
                      <div key={s.id} className="symbol-row">
                        <span className={`sym-badge sym-${s.symbol_type}`}>{s.symbol_type}</span>
                        <span className="sym-name">{s.symbol_name || '—'}</span>
                        <span className="sym-file">{s.file_path}:{s.start_line}</span>
                      </div>
                    ))}
                    {symbols.length > 60 && (
                      <div className="symbols-more">+{symbols.length - 60} more symbols</div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Index tab ─────────────────────────────────── */}
          {activeTab === 'index' && (
            <div className="index-form">
              <div className="form-group">
                <label>Repository Path</label>
                <input
                  className="repo-input"
                  placeholder="C:\Users\you\my-project  or  /home/you/project"
                  value={indexPath}
                  onChange={e => setIndexPath(e.target.value)}
                  disabled={indexing}
                />
                <span className="input-hint">Full absolute path to the project directory</span>
              </div>
              <div className="form-group">
                <label>Name (optional)</label>
                <input
                  className="repo-input"
                  placeholder="my-project"
                  value={indexName}
                  onChange={e => setIndexName(e.target.value)}
                  disabled={indexing}
                />
              </div>
              <button
                className="btn-accent btn-index"
                onClick={handleIndex}
                disabled={indexing || !indexPath.trim()}
              >
                {indexing ? '⚙️ Indexing…' : '🚀 Start Indexing'}
              </button>

              {indexLog.length > 0 && (
                <div className="index-log">
                  {indexLog.map((ev, i) => (
                    <div key={i} className={`log-line log-${ev.phase}`}>
                      <span className="log-icon">{phaseIcon(ev.phase)}</span>
                      <span className="log-msg">{ev.status}</span>
                      {ev.progress && ev.total && (
                        <div className="log-bar">
                          <div
                            className="log-bar-fill"
                            style={{ width: `${Math.round(ev.progress / ev.total * 100)}%` }}
                          />
                        </div>
                      )}
                    </div>
                  ))}
                  <div ref={logEndRef} />
                </div>
              )}
            </div>
          )}

          {/* ── Search tab ────────────────────────────────── */}
          {activeTab === 'search' && (
            <div className="code-search">
              <div className="search-bar">
                <input
                  className="repo-input"
                  placeholder="how does authentication work?  /  find function login"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSearch()}
                  disabled={searching}
                />
                <button
                  className="btn-accent"
                  onClick={handleSearch}
                  disabled={searching || !searchQuery.trim()}
                >
                  {searching ? '…' : '🔍'}
                </button>
              </div>

              {repos.length > 0 && (
                <div className="repo-filter">
                  <label>Repo:</label>
                  <select
                    value={selectedRepo?.id || ''}
                    onChange={e => setSelectedRepo(repos.find(r => r.id === e.target.value) || null)}
                  >
                    <option value="">All repos</option>
                    {repos.map(r => (
                      <option key={r.id} value={r.id}>{r.name}</option>
                    ))}
                  </select>
                </div>
              )}

              {searchResults?.error && (
                <div className="search-error">⚠️ {searchResults.error}</div>
              )}

              {searchResults && !searchResults.error && (
                <div className="search-results">
                  <div className="results-meta">
                    Found {searchResults.total || 0} code chunks
                    {searchResults.symbols?.length > 0 && ` (${searchResults.symbols.length} exact matches)`}
                  </div>
                  {searchResults.merged?.map((chunk, i) => (
                    <div key={i} className="code-chunk-card">
                      <div className="chunk-header">
                        <span className={`sym-badge sym-${chunk.symbol_type}`}>{chunk.symbol_type}</span>
                        <span className="chunk-name">{chunk.symbol_name || chunk.file_path}</span>
                        <span className="chunk-file">{chunk.file_path}:{chunk.start_line}</span>
                        <span className={`match-type-badge ${chunk.match_type}`}>{chunk.match_type}</span>
                      </div>
                      <pre className="chunk-code">
                        <code>{(chunk.code || chunk.text || '').slice(0, 600)}</code>
                      </pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
