import { useState, useEffect, useCallback } from 'react';
import { useApp } from '../../context/AppContext';

/* ── Icons ──────────────────────────────────────────────── */
const XIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
);
const TrashIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="3,6 5,6 21,6"/>
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
  </svg>
);
const DownloadIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
    <polyline points="7,10 12,15 17,10"/><line x1="12" y1="15" x2="12" y2="3"/>
  </svg>
);
const GridIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
    <rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
  </svg>
);
const ListIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/>
    <line x1="8" y1="18" x2="21" y2="18"/>
    <line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/>
    <line x1="3" y1="18" x2="3.01" y2="18"/>
  </svg>
);
const SearchIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
  </svg>
);

/* ── Helpers ─────────────────────────────────────────────── */
function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
    + ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}
function fmtBytes(n) {
  if (!n) return '—';
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

/* ── Image card (grid) ───────────────────────────────────── */
function ImageCard({ img, onDelete, onOpen }) {
  const [hovered, setHovered] = useState(false);
  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        position: 'relative', borderRadius: 10, overflow: 'hidden',
        border: '1px solid var(--border-md)', cursor: 'pointer',
        aspectRatio: `${img.width}/${img.height}`,
        background: 'rgba(0,0,0,.4)',
      }}
    >
      <img
        src={img.url}
        alt={img.prompt}
        onClick={() => onOpen(img)}
        style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
      />
      {/* Overlay on hover */}
      {hovered && (
        <div style={{
          position: 'absolute', inset: 0,
          background: 'linear-gradient(to top, rgba(0,0,0,.85) 40%, transparent)',
          display: 'flex', flexDirection: 'column', justifyContent: 'flex-end',
          padding: '10px 10px 8px',
        }}>
          <div style={{ fontSize: 11, color: '#e5e7eb', lineHeight: 1.4,
            overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box',
            WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', marginBottom: 6 }}>
            {img.prompt}
          </div>
          <div style={{ display: 'flex', gap: 5 }}>
            <button onClick={(e) => { e.stopPropagation(); handleDownload(img); }} style={{
              flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
              padding: '5px 0', borderRadius: 5, fontSize: 11, fontWeight: 500,
              background: 'rgba(255,255,255,.15)', color: 'white', border: 'none', cursor: 'pointer',
            }}>
              <DownloadIcon /> Save
            </button>
            <button onClick={(e) => { e.stopPropagation(); onDelete(img.id); }} style={{
              padding: '5px 8px', borderRadius: 5,
              background: 'rgba(239,68,68,.2)', color: '#fca5a5',
              border: 'none', cursor: 'pointer',
            }}>
              <TrashIcon />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function handleDownload(img) {
  const a = document.createElement('a');
  a.href = img.url;
  a.download = `offlinegpt-${img.id}.png`;
  a.click();
}

/* ── Fullscreen lightbox ─────────────────────────────────── */
function Lightbox({ img, onClose, onDelete }) {
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(0,0,0,.92)',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
      }}
    >
      <img
        src={img.url}
        alt={img.prompt}
        onClick={e => e.stopPropagation()}
        style={{
          maxWidth: '90vw', maxHeight: '80vh',
          borderRadius: 8, boxShadow: '0 25px 80px rgba(0,0,0,.5)',
        }}
      />
      {/* Meta + Actions */}
      <div
        onClick={e => e.stopPropagation()}
        style={{
          marginTop: 16, maxWidth: 560, width: '90vw',
          background: 'rgba(30,30,30,.95)', borderRadius: 10,
          padding: '14px 18px', border: '1px solid rgba(255,255,255,.1)',
        }}
      >
        <p style={{ fontSize: 13, color: 'var(--text)', marginBottom: 8, lineHeight: 1.5 }}>
          {img.prompt}
        </p>
        <div style={{ display: 'flex', gap: 16, fontSize: 11, color: 'var(--text-dim)', flexWrap: 'wrap', marginBottom: 12 }}>
          <span>📐 {img.width}×{img.height}</span>
          <span>🔧 {img.model_id || img.provider}</span>
          <span>🎲 seed {img.seed}</span>
          <span>📦 {fmtBytes(img.file_bytes)}</span>
          <span>🕐 {fmtDate(img.created_at)}</span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => handleDownload(img)} style={{
            flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
            padding: '8px 0', borderRadius: 7, fontSize: 13, fontWeight: 500,
            background: 'rgba(168,85,247,.2)', color: '#c084fc',
            border: '1px solid rgba(168,85,247,.3)', cursor: 'pointer',
          }}>
            <DownloadIcon /> Download PNG
          </button>
          <button onClick={() => { onDelete(img.id); onClose(); }} style={{
            padding: '8px 14px', borderRadius: 7, fontSize: 13,
            background: 'rgba(239,68,68,.12)', color: '#f87171',
            border: '1px solid rgba(239,68,68,.2)', cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 5,
          }}>
            <TrashIcon /> Delete
          </button>
          <button onClick={onClose} style={{
            padding: '8px 14px', borderRadius: 7, fontSize: 13,
            background: 'rgba(255,255,255,.06)', color: 'var(--text-dim)',
            border: '1px solid var(--border-md)', cursor: 'pointer',
          }}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Main Library Modal ──────────────────────────────────── */
export default function LibraryModal() {
  const { dispatch, toast } = useApp();
  const [images, setImages]   = useState([]);
  const [stats,  setStats]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [view,   setView]     = useState('grid');    // 'grid' | 'list'
  const [query,  setQuery]    = useState('');
  const [lightbox, setLightbox] = useState(null);

  const close = () => dispatch({ type: 'SHOW_LIBRARY', payload: false });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [imgs, st] = await Promise.all([
        fetch('/api/library').then(r => r.json()),
        fetch('/api/library/stats').then(r => r.json()),
      ]);
      setImages(Array.isArray(imgs) ? imgs : []);
      setStats(st);
    } catch { toast('Failed to load library', 'error'); }
    finally { setLoading(false); }
  }, [toast]);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async (imgId) => {
    if (!confirm('Delete this image? This cannot be undone.')) return;
    try {
      const r = await fetch(`/api/library/${imgId}`, { method: 'DELETE' });
      if (!r.ok && r.status !== 204) throw new Error('Delete failed');
      toast('Image deleted', 'info');
      setImages(prev => prev.filter(i => i.id !== imgId));
      setStats(s => s ? { ...s, count: s.count - 1 } : s);
    } catch { toast('Failed to delete image', 'error'); }
  };

  const filtered = images.filter(img =>
    !query || img.prompt?.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <>
      <div className="modal-backdrop" onClick={close}>
        <div className="modal" style={{ maxWidth: 780, maxHeight: '90vh' }} onClick={e => e.stopPropagation()}>

          {/* Header */}
          <div className="modal-header">
            <div>
              <h2 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                🖼️ Image Library
                {stats && (
                  <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--text-dim)' }}>
                    {stats.count} images · {stats.total_label}
                  </span>
                )}
              </h2>
            </div>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              {/* Grid / List toggle */}
              <button onClick={() => setView('grid')} style={{
                padding: '5px 8px', borderRadius: 6,
                background: view === 'grid' ? 'rgba(168,85,247,.2)' : 'rgba(255,255,255,.05)',
                color: view === 'grid' ? '#c084fc' : 'var(--text-dim)',
                border: 'none', cursor: 'pointer',
              }}><GridIcon /></button>
              <button onClick={() => setView('list')} style={{
                padding: '5px 8px', borderRadius: 6,
                background: view === 'list' ? 'rgba(168,85,247,.2)' : 'rgba(255,255,255,.05)',
                color: view === 'list' ? '#c084fc' : 'var(--text-dim)',
                border: 'none', cursor: 'pointer',
              }}><ListIcon /></button>
              <button className="icon-btn" onClick={close}><XIcon /></button>
            </div>
          </div>

          <div className="modal-body">
            {/* Search bar */}
            <div style={{ position: 'relative', marginBottom: 14 }}>
              <span style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }}>
                <SearchIcon />
              </span>
              <input
                className="modal-input"
                style={{ paddingLeft: 32, marginBottom: 0 }}
                placeholder="Search by prompt…"
                value={query}
                onChange={e => setQuery(e.target.value)}
              />
            </div>

            {/* Content */}
            {loading ? (
              <div style={{ textAlign: 'center', color: 'var(--text-dim)', padding: 40 }}>
                Loading library…
              </div>
            ) : filtered.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '50px 20px' }}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>🎨</div>
                <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>
                  {query ? 'No images match your search' : 'No images yet'}
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-dim)' }}>
                  {query ? 'Try a different prompt.' : 'Type "Generate an image of…" in chat to create your first image.'}
                </div>
              </div>
            ) : view === 'grid' ? (
              /* Grid */
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                gap: 10,
              }}>
                {filtered.map(img => (
                  <ImageCard
                    key={img.id}
                    img={img}
                    onOpen={setLightbox}
                    onDelete={handleDelete}
                  />
                ))}
              </div>
            ) : (
              /* List */
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {filtered.map(img => (
                  <div key={img.id} style={{
                    display: 'flex', gap: 12, alignItems: 'center',
                    padding: '10px 12px', borderRadius: 8,
                    border: '1px solid var(--border)', background: 'var(--bg-hover)',
                  }}>
                    <img
                      src={img.url} alt={img.prompt}
                      onClick={() => setLightbox(img)}
                      style={{ width: 64, height: 64, objectFit: 'cover', borderRadius: 6, cursor: 'pointer', flexShrink: 0 }}
                    />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 3,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {img.prompt}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-dim)', display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                        <span>{img.width}×{img.height}</span>
                        <span>{img.model_id || img.provider}</span>
                        <span>{fmtBytes(img.file_bytes)}</span>
                        <span>{fmtDate(img.created_at)}</span>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 5, flexShrink: 0 }}>
                      <button onClick={() => handleDownload(img)} style={{
                        padding: '5px 8px', borderRadius: 5, fontSize: 12,
                        background: 'rgba(168,85,247,.12)', color: '#c084fc',
                        border: '1px solid rgba(168,85,247,.25)', cursor: 'pointer',
                        display: 'flex', alignItems: 'center', gap: 4,
                      }}>
                        <DownloadIcon /> Save
                      </button>
                      <button onClick={() => handleDelete(img.id)} style={{
                        padding: '5px 8px', borderRadius: 5,
                        background: 'rgba(239,68,68,.1)', color: '#f87171',
                        border: '1px solid rgba(239,68,68,.2)', cursor: 'pointer',
                      }}>
                        <TrashIcon />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Lightbox */}
      {lightbox && (
        <Lightbox
          img={lightbox}
          onClose={() => setLightbox(null)}
          onDelete={(id) => { handleDelete(id); setLightbox(null); }}
        />
      )}
    </>
  );
}
