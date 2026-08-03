import { useState, useRef, useEffect } from 'react';
import { useApp } from '../../context/AppContext';
import { useConversations } from '../../hooks/useConversations';

/* ── Icons (inline SVG) ─────────────────────────────────── */
const icons = {
  search:    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>,
  newChat:   <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>,
  library:   <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>,
  projects:  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>,
  scheduled: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12,6 12,12 16,14"/></svg>,
  plugins:   <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>,
  codex:     <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="16,18 22,12 16,6"/><polyline points="8,6 2,12 8,18"/></svg>,
  more:      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></svg>,
  collapse:  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>,
  pencil:    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>,
  trash:     <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3,6 5,6 21,6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>,
  check:     <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20,6 9,17 4,12"/></svg>,
  sidebarToggle: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="9" y1="3" x2="9" y2="21"/></svg>,
  models: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21,15 16,10 5,21"/></svg>,
};

const NAV_ITEMS = [
  { icon: 'library', label: 'Library', action: 'SHOW_LIBRARY' },
  { icon: 'models',  label: 'Models',  action: 'SHOW_MODELMANAGER' },
];

function timeGroup(ts) {
  if (!ts) return 'Older';
  const d = new Date(ts + (ts.includes('Z') ? '' : 'Z'));
  const now = new Date();
  const diff = now - d;
  if (diff < 86400000)  return 'Today';
  if (diff < 172800000) return 'Yesterday';
  if (diff < 604800000) return 'Previous 7 days';
  return 'Older';
}

/* ── Context menu ───────────────────────────────────────── */
function CtxMenu({ x, y, onRename, onDelete, onClose }) {
  useEffect(() => {
    const handler = () => onClose();
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [onClose]);

  return (
    <div className="ctx-menu" style={{ left: x, top: y }} onClick={e => e.stopPropagation()}>
      <button className="ctx-item" onClick={onRename}>{icons.pencil} Rename</button>
      <div className="ctx-divider" />
      <button className="ctx-item danger" onClick={onDelete}>{icons.trash} Delete</button>
    </div>
  );
}

/* ── Conversation item ──────────────────────────────────── */
function ConvItem({ conv, isActive, onSelect, onRename, onDelete }) {
  const [renaming, setRenaming] = useState(false);
  const [title, setTitle]   = useState(conv.title);
  const [ctxPos, setCtxPos] = useState(null);
  const inputRef = useRef();

  useEffect(() => { setTitle(conv.title); }, [conv.title]);
  useEffect(() => { if (renaming) { inputRef.current?.focus(); inputRef.current?.select(); } }, [renaming]);

  const handleMoreClick = (e) => {
    e.stopPropagation();
    setCtxPos({ x: e.clientX, y: e.clientY });
  };

  const handleRenameStart = () => {
    setCtxPos(null);
    setRenaming(true);
  };

  const handleRenameCommit = () => {
    setRenaming(false);
    if (title.trim() && title.trim() !== conv.title) onRename(conv.id, title.trim());
    else setTitle(conv.title);
  };

  return (
    <>
      <div
        className={`conv-item ${isActive ? 'active' : ''}`}
        onClick={() => !renaming && onSelect(conv.id)}
        title={conv.title}
      >
        {renaming ? (
          <input
            ref={inputRef}
            className="conv-title-input"
            value={title}
            onChange={e => setTitle(e.target.value)}
            onBlur={handleRenameCommit}
            onKeyDown={e => {
              if (e.key === 'Enter')  { e.preventDefault(); handleRenameCommit(); }
              if (e.key === 'Escape') { setRenaming(false); setTitle(conv.title); }
              e.stopPropagation();
            }}
            onClick={e => e.stopPropagation()}
            style={{ flex:1, background:'transparent', border:'none', outline:'1px solid rgba(255,255,255,0.25)', borderRadius:4, padding:'1px 4px', fontSize:13, color:'var(--text)' }}
          />
        ) : (
          <span className="conv-item-title">{conv.title}</span>
        )}
        {!renaming && (
          <div className="conv-item-actions">
            <button className="conv-action-btn" onClick={handleMoreClick} title="More">
              {icons.more}
            </button>
          </div>
        )}
      </div>

      {ctxPos && (
        <CtxMenu
          x={ctxPos.x} y={ctxPos.y}
          onRename={handleRenameStart}
          onDelete={() => { setCtxPos(null); onDelete(conv.id); }}
          onClose={() => setCtxPos(null)}
        />
      )}
    </>
  );
}

/* ── Main Sidebar ───────────────────────────────────────── */
export default function Sidebar() {
  const { state, dispatch } = useApp();
  const { conversations, currentId, loadConversations, selectConversation, newConversation, renameConversation, removeConversation } = useConversations();

  const { sidebarOpen } = state;

  const handleNewChat = async () => {
    await newConversation(state.selectedModel);
  };

  const handleDelete = async (id) => {
    if (!confirm('Delete this conversation?')) return;
    await removeConversation(id);
    if (currentId === id) selectConversation(null);
    loadConversations();
  };

  // Group conversations
  const groups = {};
  conversations.forEach(c => {
    const g = timeGroup(c.updated_at);
    (groups[g] = groups[g] || []).push(c);
  });
  const GROUP_ORDER = ['Today','Yesterday','Previous 7 days','Older'];

  return (
    <aside className={`sidebar ${sidebarOpen ? '' : 'collapsed'}`}>
      {/* ── Top row ── */}
      <div className="sidebar-top">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="white">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <span className="sidebar-logo-text">OfflineGPT</span>
        </div>
        <div className="sidebar-top-icons">
          <button className="icon-btn" onClick={() => dispatch({ type: 'SHOW_SEARCH', payload: true })} title="Search (Ctrl+K)">
            {icons.search}
          </button>
          <button className="icon-btn" onClick={handleNewChat} title="New chat (Ctrl+/)">
            {icons.newChat}
          </button>
        </div>
      </div>

      {/* ── Nav ── */}
      <nav className="sidebar-nav">
        <div className="nav-item active" onClick={handleNewChat}>
          <span className="nav-item-icon">{icons.newChat}</span>
          New chat
        </div>
        {NAV_ITEMS.map(item => (
          <div key={item.label} className="nav-item"
            onClick={() => item.action && dispatch({ type: item.action, payload: true })}
            style={{ cursor: item.action ? 'pointer' : 'default' }}
          >
            <span className="nav-item-icon">{icons[item.icon]}</span>
            {item.label}
          </div>
        ))}
      </nav>

      <div className="sidebar-divider" />

      {/* ── Recents ── */}
      <div className="sidebar-section-label">Recents</div>

      <div className="sidebar-conversations">
        {conversations.length === 0 ? (
          <div className="sidebar-empty">No conversations yet.<br />Start chatting!</div>
        ) : (
          GROUP_ORDER.filter(g => groups[g]).map(g => (
            <div key={g}>
              {g !== 'Today' && (
                <div style={{ fontSize: 11, color: 'var(--text-faint)', padding: '8px 10px 2px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  {g}
                </div>
              )}
              {groups[g].map(conv => (
                <ConvItem
                  key={conv.id}
                  conv={conv}
                  isActive={conv.id === currentId}
                  onSelect={selectConversation}
                  onRename={renameConversation}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          ))
        )}
      </div>

      {/* ── Profile ── */}
      <div className="sidebar-profile">
        <div className="profile-avatar">VK</div>
        <span className="profile-name">VEERA KARTHICK</span>
      </div>
    </aside>
  );
}
