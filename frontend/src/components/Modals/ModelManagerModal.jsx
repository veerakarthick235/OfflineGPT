import { useState, useEffect, useRef } from 'react';
import { useApp } from '../../context/AppContext';

/* ── Icons ─────────────────────────────────────────────────── */
const XIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
);
const DownloadIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
    <polyline points="7,10 12,15 17,10"/><line x1="12" y1="15" x2="12" y2="3"/>
  </svg>
);
const TrashIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="3,6 5,6 21,6"/>
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
  </svg>
);
const LoadIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="23,4 23,10 17,10"/>
    <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
  </svg>
);
const UnloadIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
);
const CheckIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
    <polyline points="20,6 9,17 4,12"/>
  </svg>
);
const MicIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
    <line x1="12" y1="19" x2="12" y2="23"/>
    <line x1="8"  y1="23" x2="16" y2="23"/>
  </svg>
);

/* ── Tag colours ────────────────────────────────────────────── */
const TAG_COLORS = {
  'fast':            { bg: 'rgba(16,185,129,.15)',  color: '#10b981' },
  'high-quality':    { bg: 'rgba(99,102,241,.15)',  color: '#818cf8' },
  'gpu-recommended': { bg: 'rgba(245,158,11,.12)',  color: '#f59e0b' },
  'cpu-friendly':    { bg: 'rgba(34,197,94,.15)',   color: '#22c55e' },
  'classic':         { bg: 'rgba(156,163,175,.12)', color: '#9ca3af' },
  'photorealistic':  { bg: 'rgba(59,130,246,.15)',  color: '#60a5fa' },
  'artistic':        { bg: 'rgba(168,85,247,.15)',  color: '#c084fc' },
  'popular':         { bg: 'rgba(239,68,68,.12)',   color: '#f87171' },
  'anime':           { bg: 'rgba(236,72,153,.15)',  color: '#f472b6' },
  'illustration':    { bg: 'rgba(251,146,60,.12)',  color: '#fb923c' },
  'recommended':     { bg: 'rgba(16,185,129,.15)',  color: '#10b981' },
  'balanced':        { bg: 'rgba(99,102,241,.15)',  color: '#818cf8' },
  'accurate':        { bg: 'rgba(59,130,246,.15)',  color: '#60a5fa' },
  'lightweight':     { bg: 'rgba(34,197,94,.15)',   color: '#22c55e' },
};

function Tag({ label }) {
  const s = TAG_COLORS[label] || { bg: 'rgba(255,255,255,.08)', color: 'var(--text-dim)' };
  return (
    <span style={{
      fontSize:10, fontWeight:600, padding:'2px 7px', borderRadius:99,
      background:s.bg, color:s.color, textTransform:'uppercase', letterSpacing:'0.05em',
    }}>{label}</span>
  );
}

function StatusBadge({ downloaded, loaded }) {
  if (loaded) return (
    <span style={{ fontSize:11, fontWeight:600, padding:'2px 8px', borderRadius:99,
      background:'rgba(16,185,129,.18)', color:'#10b981',
      display:'inline-flex', alignItems:'center', gap:4 }}>
      <CheckIcon/> Active
    </span>
  );
  if (downloaded) return (
    <span style={{ fontSize:11, fontWeight:600, padding:'2px 8px', borderRadius:99,
      background:'rgba(99,102,241,.15)', color:'#818cf8' }}>
      Downloaded
    </span>
  );
  return (
    <span style={{ fontSize:11, fontWeight:500, padding:'2px 8px', borderRadius:99,
      background:'rgba(255,255,255,.06)', color:'var(--text-dim)' }}>
      Not Downloaded
    </span>
  );
}

/* ── Generic model card (shared by both tabs) ─────────────── */
function ModelCard({ model, downloading, onDownload, onDelete, onLoad, onUnload, accent='#7c3aed' }) {
  const dlProgress = model.downloading;
  const isDownloading = typeof dlProgress === 'number' || downloading;

  return (
    <div style={{
      border: `1px solid ${model.loaded ? 'rgba(16,185,129,.35)' : 'var(--border-md)'}`,
      borderRadius:12, padding:'16px 18px',
      background: model.loaded ? 'rgba(16,185,129,.06)' : 'var(--bg-hover)',
      transition:'border-color .2s',
    }}>
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:10, marginBottom:8 }}>
        <div>
          <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:5 }}>
            <span style={{ fontSize:15, fontWeight:600 }}>{model.name}</span>
            <StatusBadge downloaded={model.downloaded} loaded={model.loaded} />
          </div>
          <div style={{ display:'flex', flexWrap:'wrap', gap:4 }}>
            {(model.tags || []).map(t => <Tag key={t} label={t}/>)}
          </div>
        </div>
        <div style={{ textAlign:'right', flexShrink:0 }}>
          <div style={{ fontSize:13, fontWeight:600 }}>{model.size_label || `~${model.size_mb} MB`}</div>
          {model.downloaded && model.disk_label && (
            <div style={{ fontSize:11, color:'var(--text-dim)', marginTop:2 }}>{model.disk_label} on disk</div>
          )}
        </div>
      </div>

      <p style={{ fontSize:13, color:'var(--text-dim)', lineHeight:1.6, marginBottom:12 }}>
        {model.description}
      </p>

      {/* Progress */}
      {isDownloading && (
        <div style={{ marginBottom:10 }}>
          <div style={{ fontSize:12, color:'var(--text-dim)', marginBottom:4 }}>
            Downloading… {typeof dlProgress === 'number' ? `${dlProgress}%` : ''}
          </div>
          <div style={{ height:4, background:'rgba(255,255,255,.08)', borderRadius:99, overflow:'hidden' }}>
            <div style={{
              height:'100%', width:`${dlProgress||0}%`,
              background:`linear-gradient(90deg,${accent},${accent}cc)`,
              borderRadius:99, transition:'width .5s ease',
            }}/>
          </div>
        </div>
      )}

      {/* Actions */}
      <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
        {!model.downloaded && !isDownloading && (
          <button onClick={() => onDownload(model.id)} style={{
            display:'flex', alignItems:'center', gap:5,
            padding:'6px 12px', borderRadius:6, fontSize:12, fontWeight:600,
            background:`linear-gradient(135deg,${accent},${accent}cc)`,
            color:'white', border:'none', cursor:'pointer',
          }}>
            <DownloadIcon/> Download {model.size_label || `~${model.size_mb} MB`}
          </button>
        )}
        {model.downloaded && !model.loaded && onLoad && (
          <button onClick={() => onLoad(model.id)} style={{
            display:'flex', alignItems:'center', gap:5,
            padding:'6px 12px', borderRadius:6, fontSize:12, fontWeight:600,
            background:'rgba(16,185,129,.15)', color:'#10b981',
            border:'1px solid rgba(16,185,129,.3)', cursor:'pointer',
          }}>
            <LoadIcon/> Load Model
          </button>
        )}
        {model.loaded && onUnload && (
          <button onClick={() => onUnload(model.id)} style={{
            display:'flex', alignItems:'center', gap:5,
            padding:'6px 12px', borderRadius:6, fontSize:12, fontWeight:500,
            background:'rgba(255,255,255,.06)', color:'var(--text-dim)',
            border:'1px solid var(--border-md)', cursor:'pointer',
          }}>
            <UnloadIcon/> Unload
          </button>
        )}
        {model.downloaded && (
          <button onClick={() => onDelete(model.id, model.name)} style={{
            display:'flex', alignItems:'center', gap:5,
            padding:'6px 10px', borderRadius:6, fontSize:12,
            background:'rgba(239,68,68,.08)', color:'#ef4444',
            border:'1px solid rgba(239,68,68,.2)', cursor:'pointer',
          }}>
            <TrashIcon/> Delete
          </button>
        )}
      </div>
    </div>
  );
}

/* ── Tab button ─────────────────────────────────────────────── */
function Tab({ label, icon, active, onClick, badge }) {
  return (
    <button onClick={onClick} style={{
      display:'flex', alignItems:'center', gap:6,
      padding:'8px 16px', borderRadius:8, fontSize:13, fontWeight:600,
      border:'none', cursor:'pointer',
      background: active ? 'rgba(124,58,237,.2)' : 'transparent',
      color: active ? '#c084fc' : 'var(--text-dim)',
      borderBottom: active ? '2px solid #7c3aed' : '2px solid transparent',
      transition:'all .18s',
    }}>
      {icon} {label}
      {badge && (
        <span style={{
          fontSize:10, padding:'1px 6px', borderRadius:99,
          background:'rgba(16,185,129,.2)', color:'#10b981', fontWeight:700,
        }}>{badge}</span>
      )}
    </button>
  );
}

/* ════════════════════════════════════════════════════════════ */
export default function ModelManagerModal() {
  const { dispatch, toast } = useApp();
  const [activeTab, setActiveTab] = useState('image'); // 'image' | 'stt'

  /* Image model state */
  const [imgModels,       setImgModels]       = useState([]);
  const [imgStatus,       setImgStatus]       = useState(null);
  const [imgLoading,      setImgLoading]      = useState(true);
  const [imgLoadingId,    setImgLoadingId]    = useState('');
  const [imgDownloading,  setImgDownloading]  = useState(new Set());

  /* STT model state */
  const [sttModels,       setSttModels]       = useState([]);
  const [sttLoading,      setSttLoading]      = useState(true);
  const [sttActiveModel,  setSttActiveModel]  = useState(null);
  const [sttDownloading,  setSttDownloading]  = useState(new Set());

  const evtSources = useRef({});

  const close = () => dispatch({ type: 'SHOW_MODELMANAGER', payload: false });

  /* ── Data refresh ────────────────────────────────────────── */
  const refreshImg = async () => {
    try {
      const [m, s] = await Promise.all([
        fetch('/api/images/models').then(r => r.json()),
        fetch('/api/images/status').then(r => r.json()),
      ]);
      setImgModels(m);
      setImgStatus(s);
    } catch {}
    finally { setImgLoading(false); }
  };

  const refreshStt = async () => {
    try {
      const [m, a] = await Promise.all([
        fetch('/api/stt/models').then(r => r.json()),
        fetch('/api/stt/models/active').then(r => r.json()),
      ]);
      setSttModels(m.map(mm => ({
        ...mm,
        size_label: `~${mm.size_mb < 1000 ? mm.size_mb + ' MB' : (mm.size_mb/1000).toFixed(1) + ' GB'}`,
        tags: mm.description.split('·').map(s => s.trim().split(' ')[0].toLowerCase()).filter(Boolean),
        loaded: a.loaded && a.model_id === mm.id,
      })));
      setSttActiveModel(a);
    } catch {}
    finally { setSttLoading(false); }
  };

  useEffect(() => {
    refreshImg();
    refreshStt();
    const timer = setInterval(() => { refreshImg(); refreshStt(); }, 6000);
    return () => {
      clearInterval(timer);
      Object.values(evtSources.current).forEach(es => es.close());
    };
  }, []);

  /* ── Image handlers ──────────────────────────────────────── */
  const handleImgDownload = async (modelId) => {
    setImgDownloading(prev => new Set([...prev, modelId]));
    const es = new EventSource(`/api/images/models/${modelId}/download`);
    evtSources.current[`img_${modelId}`] = es;
    es.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data);
        setImgModels(prev => prev.map(m => m.id === modelId ? { ...m, downloading: ev.progress ?? null } : m));
        if (ev.type === 'done' || ev.type === 'error') {
          es.close();
          setImgDownloading(prev => { const s = new Set(prev); s.delete(modelId); return s; });
          if (ev.type === 'done') toast(`${modelId} downloaded!`, 'success');
          else toast(`Download failed: ${ev.message}`, 'error', 6000);
          refreshImg();
        }
      } catch {}
    };
    es.onerror = () => {
      es.close();
      setImgDownloading(prev => { const s = new Set(prev); s.delete(modelId); return s; });
      toast('Download connection error', 'error');
    };
  };

  const handleImgLoad = async (modelId) => {
    setImgLoadingId(modelId);
    toast(`Loading ${modelId}… this may take a minute`, 'info', 8000);
    try {
      const r = await fetch(`/api/images/models/${modelId}/load`, { method: 'POST' });
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail); }
      toast(`${modelId} loaded!`, 'success');
      await refreshImg();
    } catch (err) { toast(`Load failed: ${err.message}`, 'error', 8000); }
    finally { setImgLoadingId(''); }
  };

  const handleImgUnload = async () => {
    try {
      await fetch('/api/images/models/unload', { method: 'POST' });
      toast('Model unloaded', 'info');
      await refreshImg();
    } catch { toast('Unload failed', 'error'); }
  };

  const handleImgDelete = async (modelId, name) => {
    if (!confirm(`Delete "${name}" from disk?`)) return;
    try {
      await fetch(`/api/images/models/${modelId}`, { method: 'DELETE' });
      toast(`${name} deleted`, 'info');
      await refreshImg();
    } catch { toast('Delete failed', 'error'); }
  };

  /* ── STT handlers ────────────────────────────────────────── */
  const handleSttDownload = async (modelId) => {
    setSttDownloading(prev => new Set([...prev, modelId]));
    const es = new EventSource(`/api/stt/models/${modelId}/download`);
    evtSources.current[`stt_${modelId}`] = es;
    es.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data);
        setSttModels(prev => prev.map(m => m.id === modelId ? { ...m, downloading: ev.progress ?? 5 } : m));
        if (ev.status === 'done' || ev.status === 'error') {
          es.close();
          setSttDownloading(prev => { const s = new Set(prev); s.delete(modelId); return s; });
          if (ev.status === 'done') toast(`Whisper ${modelId} downloaded & loaded!`, 'success');
          else toast(`Download failed: ${ev.message}`, 'error', 6000);
          refreshStt();
        }
      } catch {}
    };
    es.onerror = () => {
      es.close();
      setSttDownloading(prev => { const s = new Set(prev); s.delete(modelId); return s; });
      toast('STT download error', 'error');
    };
  };

  const handleSttLoad = async (modelId) => {
    toast(`Loading Whisper ${modelId}…`, 'info', 5000);
    try {
      const r = await fetch(`/api/stt/models/${modelId}/load`, { method: 'POST' });
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail); }
      toast(`Whisper ${modelId} loaded!`, 'success');
      await refreshStt();
    } catch (err) { toast(`Load failed: ${err.message}`, 'error', 8000); }
  };

  const handleSttDelete = async (modelId, name) => {
    if (!confirm(`Delete Whisper "${name}" from disk?`)) return;
    try {
      await fetch(`/api/stt/models/${modelId}`, { method: 'DELETE' });
      toast(`${name} deleted`, 'info');
      await refreshStt();
    } catch { toast('Delete failed', 'error'); }
  };

  /* ── counts for badges ───────────────────────────────────── */
  const imgDownloadedCount = imgModels.filter(m => m.downloaded).length;
  const sttDownloadedCount = sttModels.filter(m => m.downloaded).length;

  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="modal" style={{ maxWidth:640, maxHeight:'88vh' }}
        onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div className="modal-header">
          <h2 style={{ display:'flex', alignItems:'center', gap:8 }}>
            🤖 Model Manager
          </h2>
          <button className="icon-btn" onClick={close}><XIcon/></button>
        </div>

        {/* Tabs */}
        <div style={{ display:'flex', gap:4, padding:'0 20px', borderBottom:'1px solid var(--border-md)' }}>
          <Tab
            label="Image Models"
            icon="🖼️"
            active={activeTab === 'image'}
            onClick={() => setActiveTab('image')}
            badge={imgDownloadedCount > 0 ? imgDownloadedCount : null}
          />
          <Tab
            label="STT Models"
            icon={<MicIcon/>}
            active={activeTab === 'stt'}
            onClick={() => setActiveTab('stt')}
            badge={sttDownloadedCount > 0 ? sttDownloadedCount : null}
          />
        </div>

        <div className="modal-body">

          {/* ── IMAGE TAB ─────────────────────────────────────── */}
          {activeTab === 'image' && (
            <>
              {imgStatus && (
                <div style={{ fontSize:12, color:'var(--text-dim)', marginBottom:8 }}>
                  Provider: <strong style={{ color:'var(--text)' }}>{imgStatus.provider}</strong>
                  {imgStatus.loaded_model && <> · Active: <strong style={{ color:'#10b981' }}>{imgStatus.loaded_model}</strong></>}
                  {!imgStatus.diffusers_ready && (
                    <span style={{ color:'#f59e0b', marginLeft:8 }}>
                      ⚠️ Install diffusers to enable image generation
                    </span>
                  )}
                </div>
              )}

              {imgStatus && !imgStatus.diffusers_ready && (
                <div style={{ marginBottom:12, padding:'12px 14px', background:'rgba(245,158,11,.1)',
                  border:'1px solid rgba(245,158,11,.25)', borderRadius:8, fontSize:13 }}>
                  <strong>⚠️ Image libraries not installed.</strong><br/>
                  <code style={{ background:'rgba(0,0,0,.3)', padding:'4px 8px', borderRadius:4, display:'inline-block', marginTop:4 }}>
                    pip install diffusers transformers accelerate torch
                  </code>
                </div>
              )}

              <p style={{ fontSize:13, color:'var(--text-dim)', marginBottom:12 }}>
                Download a model once — no internet needed afterwards.
                Type <em>"generate an image of…"</em> in chat.
              </p>

              {imgLoading ? (
                <div style={{ textAlign:'center', color:'var(--text-dim)', padding:40 }}>Loading…</div>
              ) : (
                <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
                  {imgModels.map(m => (
                    <ModelCard
                      key={m.id} model={m}
                      downloading={imgDownloading.has(m.id)}
                      onDownload={handleImgDownload}
                      onDelete={handleImgDelete}
                      onLoad={handleImgLoad}
                      onUnload={handleImgUnload}
                      accent="#7c3aed"
                    />
                  ))}
                </div>
              )}
            </>
          )}

          {/* ── STT TAB ───────────────────────────────────────── */}
          {activeTab === 'stt' && (
            <>
              <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:12,
                padding:'10px 14px', background:'rgba(99,102,241,.08)',
                border:'1px solid rgba(99,102,241,.2)', borderRadius:8, fontSize:13 }}>
                <span>🎙️</span>
                <span style={{ color:'var(--text-dim)' }}>
                  <strong style={{ color:'var(--text)' }}>Offline Speech-to-Text</strong> — powered by <strong>faster-whisper</strong>.
                  No internet required. Download <strong>Whisper Base</strong> to get started (~145 MB).
                  {sttActiveModel?.loaded && (
                    <span style={{ marginLeft:8, color:'#10b981', fontWeight:600 }}>
                      ✓ Active: {sttActiveModel.model_id}
                    </span>
                  )}
                </span>
              </div>

              {sttLoading ? (
                <div style={{ textAlign:'center', color:'var(--text-dim)', padding:40 }}>Loading…</div>
              ) : (
                <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
                  {sttModels.map(m => (
                    <ModelCard
                      key={m.id} model={m}
                      downloading={sttDownloading.has(m.id)}
                      onDownload={handleSttDownload}
                      onDelete={(id, name) => handleSttDelete(id, name)}
                      onLoad={handleSttLoad}
                      onUnload={null}   // STT keeps model loaded until replaced
                      accent="#4f46e5"
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
