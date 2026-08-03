import { useState, useEffect, useRef } from 'react';
import { useApp } from '../../context/AppContext';
import { getModels, getStatus } from '../../api/client';

const ChevronDown = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
    <polyline points="6,9 12,15 18,9"/>
  </svg>
);

const BellIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
    <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
  </svg>
);

const SettingsIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="3"/>
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
  </svg>
);

const SidebarToggleIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="3" width="18" height="18" rx="2"/>
    <line x1="9" y1="3" x2="9" y2="21"/>
  </svg>
);

export default function Header() {
  const { state, dispatch } = useApp();
  const [modelOpen, setModelOpen] = useState(false);
  const dropdownRef = useRef();

  // Load models + check status on mount and periodically
  useEffect(() => {
    const check = async () => {
      try {
        const { online } = await getStatus();
        dispatch({ type: 'SET_OLLAMA', payload: online });
        if (online) {
          const { models } = await getModels();
          dispatch({ type: 'SET_MODELS', payload: models });
        }
      } catch { dispatch({ type: 'SET_OLLAMA', payload: false }); }
    };
    check();
    const timer = setInterval(check, 20000);
    return () => clearInterval(timer);
  }, [dispatch]);

  // Close dropdown on outside click
  useEffect(() => {
    const h = (e) => { if (!dropdownRef.current?.contains(e.target)) setModelOpen(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  const selectModel = (m) => {
    dispatch({ type: 'SET_MODEL', payload: m });
    setModelOpen(false);
  };

  const modelList = state.models.length
    ? state.models
    : [state.selectedModel];

  return (
    <header className="chat-header">
      {/* ── Left: sidebar toggle ── */}
      <div className="header-left">
        <button
          className="icon-btn"
          onClick={() => dispatch({ type: 'TOGGLE_SIDEBAR' })}
          title="Toggle sidebar"
        >
          <SidebarToggleIcon />
        </button>
      </div>

      {/* ── Center: model selector ── */}
      <div className="header-center" ref={dropdownRef}>
        <button
          className="model-selector-btn"
          onClick={() => setModelOpen(v => !v)}
          title="Switch model"
        >
          {state.selectedModel.split(':')[0] || 'OfflineGPT'}
          <ChevronDown />
        </button>

        {modelOpen && (
          <div className="model-dropdown">
            {modelList.length === 0 ? (
              <div className="model-dropdown-empty">No models found — run <code>ollama pull llama3.2</code></div>
            ) : (
              modelList.map(m => (
                <div
                  key={m}
                  className={`model-dropdown-item ${m === state.selectedModel ? 'selected' : ''}`}
                  onClick={() => selectModel(m)}
                >
                  {m}
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* ── Right: status + actions ── */}
      <div className="header-right">
        <div className="status-indicator" title={state.ollamaOnline ? 'Ollama connected' : 'Ollama offline'}>
          <div className={`status-dot ${state.ollamaOnline ? 'online' : 'offline'}`} />
          <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>
            {state.ollamaOnline ? 'Online' : 'Offline'}
          </span>
        </div>
        <button
          className="icon-btn header-repo-btn"
          title="Repository Intelligence"
          onClick={() => dispatch({ type: 'SHOW_REPO', payload: true })}
        >
          💻
        </button>
        <button className="icon-btn" title="Notifications"><BellIcon /></button>
        <button
          className="icon-btn"
          title="Settings"
          onClick={() => dispatch({ type: 'SHOW_SETTINGS', payload: true })}
        >
          <SettingsIcon />
        </button>
      </div>
    </header>
  );
}
