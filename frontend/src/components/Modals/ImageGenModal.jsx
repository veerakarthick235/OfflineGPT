import { useState, useEffect, useRef } from 'react';
import { useApp } from '../../context/AppContext';

const XIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
);
const ImageIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="3" y="3" width="18" height="18" rx="2"/>
    <circle cx="8.5" cy="8.5" r="1.5"/>
    <polyline points="21,15 16,10 5,21"/>
  </svg>
);
const SparkleIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2l2.4 7.6H22l-6.4 4.6 2.4 7.8L12 17.4 6 22l2.4-7.8L2 9.6h7.6z"/>
  </svg>
);
const DownloadIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
    <polyline points="7,10 12,15 17,10"/><line x1="12" y1="15" x2="12" y2="3"/>
  </svg>
);
const GalleryIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="2" y="3" width="7" height="7" rx="1"/><rect x="15" y="3" width="7" height="7" rx="1"/>
    <rect x="2" y="14" width="7" height="7" rx="1"/><rect x="15" y="14" width="7" height="7" rx="1"/>
  </svg>
);

const PRESETS = [
  { label: 'Photorealistic', suffix: ', photorealistic, 8k, detailed, studio lighting' },
  { label: 'Anime',          suffix: ', anime style, vibrant colors, detailed lineart' },
  { label: 'Oil Painting',   suffix: ', oil painting, impressionist, canvas texture' },
  { label: 'Cyberpunk',      suffix: ', cyberpunk, neon lights, rain, dark city' },
  { label: 'Watercolor',     suffix: ', watercolor painting, soft edges, pastel colors' },
  { label: 'Pixel Art',      suffix: ', pixel art, 16-bit, retro game style' },
];

const SIZES = [
  { label: '512×512  (Fast)', w: 512,  h: 512  },
  { label: '768×512  (Wide)', w: 768,  h: 512  },
  { label: '512×768  (Tall)', w: 512,  h: 768  },
  { label: '768×768  (Sq.)',  w: 768,  h: 768  },
  { label: '1024×512 (Banner)',w:1024, h: 512  },
];

export default function ImageGenModal() {
  const { dispatch, toast } = useApp();

  const [status, setStatus]         = useState(null);     // { available, backend }
  const [prompt, setPrompt]         = useState('');
  const [negPrompt, setNegPrompt]   = useState('low quality, blurry, nsfw, watermark');
  const [selectedPreset, setPreset] = useState(null);
  const [sizeIdx, setSizeIdx]       = useState(0);
  const [steps, setSteps]           = useState(20);
  const [cfg, setCfg]               = useState(7);
  const [seed, setSeed]             = useState(-1);
  const [generating, setGenerating] = useState(false);
  const [result, setResult]         = useState(null);   // { b64, backend, ... }
  const [tab, setTab]               = useState('generate'); // 'generate' | 'gallery'
  const [gallery, setGallery]       = useState([]);

  const close = () => dispatch({ type: 'SHOW_IMAGEGEN', payload: false });

  /* check backend status */
  useEffect(() => {
    fetch('/api/images/status').then(r => r.json()).then(setStatus).catch(() => setStatus({ available: false }));
  }, []);

  /* load gallery when switching tab */
  useEffect(() => {
    if (tab === 'gallery') {
      fetch('/api/images/gallery').then(r => r.json()).then(setGallery).catch(() => {});
    }
  }, [tab]);

  const finalPrompt = () => {
    const preset = PRESETS.find(p => p.label === selectedPreset);
    return prompt + (preset ? preset.suffix : '');
  };

  const handleGenerate = async () => {
    if (!prompt.trim()) return toast('Enter a prompt first', 'error');
    if (!status?.available) return toast('No image backend running', 'error');
    const size = SIZES[sizeIdx];
    setGenerating(true);
    setResult(null);
    try {
      const r = await fetch('/api/images/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt:           finalPrompt(),
          negative_prompt:  negPrompt,
          width:            size.w,
          height:           size.h,
          steps,
          cfg_scale:        cfg,
          seed,
        }),
      });
      if (!r.ok) {
        const err = await r.json();
        throw new Error(err.detail || 'Generation failed');
      }
      const data = await r.json();
      setResult(data);
      toast('Image generated!', 'success');
    } catch (err) {
      toast(err.message, 'error', 6000);
    } finally {
      setGenerating(false);
    }
  };

  const handleDownload = () => {
    if (!result?.url) return;
    const a = document.createElement('a');
    a.href = result.url;
    a.download = `offlinegpt-${Date.now()}.png`;
    a.click();
  };

  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="modal" style={{ maxWidth: 660 }} onClick={e => e.stopPropagation()}>

        {/* ── Header ── */}
        <div className="modal-header">
          <h2 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: '#a855f7' }}><ImageIcon /></span>
            Image Generation
            {status && (
              <span style={{
                fontSize: 11, fontWeight: 500, padding: '2px 8px',
                borderRadius: 99,
                background: status.available ? 'rgba(16,185,129,.15)' : 'rgba(239,68,68,.12)',
                color: status.available ? '#10b981' : '#ef4444',
                marginLeft: 4,
              }}>
                {status.available ? `${status.backend === 'sdwebui' ? 'SD WebUI' : 'ComfyUI'} connected` : 'No backend'}
              </span>
            )}
          </h2>
          <button className="icon-btn" onClick={close}><XIcon /></button>
        </div>

        {/* ── Tabs ── */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', padding: '0 20px' }}>
          {['generate', 'gallery'].map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              padding: '10px 16px', fontSize: 13, fontWeight: 500,
              color: tab === t ? 'var(--text)' : 'var(--text-dim)',
              borderBottom: tab === t ? '2px solid #a855f7' : '2px solid transparent',
              marginBottom: -1, textTransform: 'capitalize',
              transition: 'color .15s',
            }}>
              {t === 'gallery' ? <><GalleryIcon /> Gallery</> : <><SparkleIcon style={{ marginRight: 4 }}/> Generate</>}
            </button>
          ))}
        </div>

        {tab === 'generate' ? (
          <div className="modal-body">

            {/* No backend warning */}
            {status && !status.available && (
              <div style={{
                background: 'rgba(245,158,11,.1)', border: '1px solid rgba(245,158,11,.3)',
                borderRadius: 8, padding: '12px 14px', fontSize: 13, lineHeight: 1.6,
              }}>
                <strong>⚠️ No image backend detected</strong><br />
                Install one of the following, then reopen this dialog:
                <ul style={{ marginTop: 6, paddingLeft: 20, color: 'var(--text-dim)' }}>
                  <li><strong>AUTOMATIC1111 SD WebUI</strong> (port 7860) — <a href="https://github.com/AUTOMATIC1111/stable-diffusion-webui" target="_blank">github.com/AUTOMATIC1111</a></li>
                  <li><strong>ComfyUI</strong> (port 8188) — <a href="https://github.com/comfyanonymous/ComfyUI" target="_blank">github.com/comfyanonymous/ComfyUI</a></li>
                </ul>
              </div>
            )}

            {/* Prompt */}
            <div className="modal-group">
              <label className="modal-label">Prompt</label>
              <textarea
                className="modal-input"
                style={{ minHeight: 80, resize: 'vertical' }}
                placeholder="A serene mountain landscape at sunset, misty valleys, golden hour…"
                value={prompt}
                onChange={e => setPrompt(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && e.ctrlKey) handleGenerate(); }}
              />
              <span className="modal-hint">Ctrl+Enter to generate</span>
            </div>

            {/* Style presets */}
            <div className="modal-group">
              <label className="modal-label">Style Preset</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {PRESETS.map(p => (
                  <button key={p.label} onClick={() => setPreset(selectedPreset === p.label ? null : p.label)} style={{
                    padding: '5px 12px', borderRadius: 99, fontSize: 12, fontWeight: 500,
                    border: '1px solid',
                    borderColor:  selectedPreset === p.label ? '#a855f7' : 'var(--border-md)',
                    background:   selectedPreset === p.label ? 'rgba(168,85,247,.15)' : 'transparent',
                    color:        selectedPreset === p.label ? '#a855f7' : 'var(--text-dim)',
                    cursor: 'pointer', transition: 'all .15s',
                  }}>
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Size */}
            <div className="modal-group">
              <label className="modal-label">Size</label>
              <select className="modal-select" value={sizeIdx} onChange={e => setSizeIdx(+e.target.value)}>
                {SIZES.map((s, i) => <option key={i} value={i}>{s.label}</option>)}
              </select>
            </div>

            {/* Steps + CFG */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div className="modal-group">
                <label className="modal-label">Steps <span style={{ color:'var(--accent)' }}>{steps}</span></label>
                <input type="range" min="10" max="80" step="1" className="range-slider"
                  value={steps} onChange={e => setSteps(+e.target.value)} />
                <span className="modal-hint">Higher = better quality, slower</span>
              </div>
              <div className="modal-group">
                <label className="modal-label">CFG Scale <span style={{ color:'var(--accent)' }}>{cfg}</span></label>
                <input type="range" min="1" max="20" step="0.5" className="range-slider"
                  value={cfg} onChange={e => setCfg(+e.target.value)} />
                <span className="modal-hint">How strictly to follow prompt</span>
              </div>
            </div>

            {/* Negative prompt (collapsed by default) */}
            <details>
              <summary style={{ cursor: 'pointer', fontSize: 13, color: 'var(--text-dim)', userSelect: 'none' }}>
                Advanced options
              </summary>
              <div className="modal-group" style={{ marginTop: 10 }}>
                <label className="modal-label">Negative Prompt</label>
                <textarea className="modal-input" style={{ minHeight: 56, resize: 'vertical' }}
                  value={negPrompt} onChange={e => setNegPrompt(e.target.value)} />
              </div>
              <div className="modal-group">
                <label className="modal-label">Seed <span className="modal-hint">(-1 = random)</span></label>
                <input type="number" className="modal-input" value={seed} onChange={e => setSeed(+e.target.value)} />
              </div>
            </details>

            {/* Generate button */}
            <button
              onClick={handleGenerate}
              disabled={generating || !prompt.trim()}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                padding: '11px 20px', borderRadius: 8, fontSize: 14, fontWeight: 600,
                background: generating ? 'rgba(168,85,247,.3)' : 'linear-gradient(135deg,#7c3aed,#a855f7)',
                color: 'white', cursor: generating ? 'wait' : 'pointer',
                opacity: !prompt.trim() ? .4 : 1, transition: 'all .15s',
                border: 'none',
              }}
            >
              {generating ? (
                <>
                  <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⟳</span>
                  Generating…
                </>
              ) : (
                <><SparkleIcon /> Generate Image</>
              )}
            </button>

            {/* Result */}
            {result && (
              <div style={{ borderRadius: 10, overflow: 'hidden', border: '1px solid var(--border-md)' }}>
                <img
                  src={result.url}
                  alt={result.prompt}
                  style={{ width: '100%', display: 'block' }}
                />
                <div style={{
                  padding: '10px 14px', display: 'flex', alignItems: 'center',
                  justifyContent: 'space-between', background: 'var(--bg-hover)',
                }}>
                  <span style={{ fontSize: 12, color: 'var(--text-dim)', overflow: 'hidden',
                    textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }}>
                    {result.prompt} · {result.width}×{result.height} · {result.provider || result.backend}
                  </span>
                  <button onClick={handleDownload} style={{
                    display:'flex',alignItems:'center',gap:5,
                    fontSize:12,color:'var(--text-dim)',padding:'4px 10px',
                    borderRadius:4,background:'var(--bg-hover)',border:'none',cursor:'pointer',
                  }}>
                    <DownloadIcon /> Download
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          /* ── Gallery tab ── */
          <div className="modal-body">
            {gallery.length === 0 ? (
              <div style={{ textAlign:'center', color:'var(--text-dim)', padding:'32px 0', fontSize:13 }}>
                No images yet. Generate some!
              </div>
            ) : (
              <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(160px,1fr))', gap:10 }}>
                {gallery.map(img => (
                  <div key={img.filename} style={{ borderRadius:8, overflow:'hidden', border:'1px solid var(--border-md)', cursor:'pointer' }}
                    onClick={() => window.open(`/api/images/file/${img.filename}`, '_blank')}
                  >
                    <img src={`/api/images/file/${img.filename}`} alt={img.filename}
                      style={{ width:'100%', display:'block', aspectRatio:'1', objectFit:'cover' }} />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* spin keyframe */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
