import { useState, useRef, useCallback, useEffect } from 'react';
import { useApp } from '../../context/AppContext';
import { useChat } from '../../hooks/useChat';
import { useWhisperSTT } from '../../hooks/useWhisperSTT';
import { uploadAttachments, getAttachmentStatus, deleteAttachment } from '../../api/client';
import AttachmentChip from './AttachmentChip';
import './AttachmentChip.css';
import './AttachmentPreview.css';

/* ── Accepted file types ─────────────────────────────────── */
const ACCEPT = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/plain', 'text/markdown', 'text/csv', 'text/html', 'text/css',
  'application/json', 'application/xml', 'text/xml',
  'image/png', 'image/jpeg', 'image/webp', 'image/bmp', 'image/gif',
  'application/zip',
  '.py','.js','.ts','.jsx','.tsx','.java','.c','.cpp','.h','.cs',
  '.go','.rs','.rb','.php','.sql','.sh','.yaml','.yml','.toml','.md','.rtf',
].join(',');

const POLL_MS = 1500;

/* ── SVG icons ──────────────────────────────────────────── */
const AttachIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
  </svg>
);
const SendIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
    <line x1="22" y1="2" x2="11" y2="13"/>
    <polygon points="22,2 15,22 11,13 2,9 22,2"/>
  </svg>
);
const StopIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
    <rect x="3" y="3" width="18" height="18" rx="2"/>
  </svg>
);
function MicIcon({ listening }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke={listening ? '#a855f7' : 'currentColor'} strokeWidth="2">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
      <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
      <line x1="12" y1="19" x2="12" y2="23"/>
      <line x1="8"  y1="23" x2="16" y2="23"/>
    </svg>
  );
}
function OrbIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="9"/>
      <path d="M8 12 Q10 8 12 12 Q14 16 16 12"/>
    </svg>
  );
}

export default function MessageInput() {
  const { state, dispatch } = useApp();
  const { send, stop }      = useChat();

  const [value,       setValue]       = useState('');
  const [charCount,   setChar]        = useState(0);
  const [attachments, setAttachments] = useState([]);  // {id, original_name, file_type, status}
  const [isDragging,  setIsDragging]  = useState(false);

  const taRef        = useRef();
  const fileInputRef = useRef();
  const pollingRefs  = useRef({});

  const { isGenerating } = state;

  /* ── STT ────────────────────────────────────────────────── */
  const stt = useWhisperSTT();

  const handleMicDown = async () => {
    if (stt.recording || stt.transcribing) return;
    try { await stt.startRecording(); } catch { /* denied */ }
  };
  const handleMicUp = async () => {
    if (!stt.recording) return;
    try {
      const text = await stt.stopRecording();
      if (text?.trim()) {
        setValue(prev => (prev.trimEnd() + ' ' + text).trimStart());
        setChar(v => v + text.length + 1);
        setTimeout(() => taRef.current?.focus(), 0);
      }
    } catch { /* handled inside hook */ }
  };

  /* ── Auto-resize ─────────────────────────────────────────── */
  const autoResize = () => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 180) + 'px';
  };
  useEffect(() => { autoResize(); }, [value]);

  const handleChange = (e) => { setValue(e.target.value); setChar(e.target.value.length); };

  /* ── Attachment polling ──────────────────────────────────── */
  const _poll = useCallback((id) => {
    if (pollingRefs.current[id]) return;
    const iv = setInterval(async () => {
      try {
        const { status, error } = await getAttachmentStatus(id);
        setAttachments(prev => prev.map(a =>
          a.id === id ? { ...a, status, error_msg: error } : a
        ));
        if (status === 'ready' || status === 'error') {
          clearInterval(iv);
          delete pollingRefs.current[id];
        }
      } catch {
        clearInterval(iv);
        delete pollingRefs.current[id];
      }
    }, POLL_MS);
    pollingRefs.current[id] = iv;
  }, []);

  /* ── File upload ─────────────────────────────────────────── */
  const handleFiles = useCallback(async (fileList) => {
    const files = Array.from(fileList);
    if (!files.length) return;

    // Optimistic placeholders
    const placeholders = files.map(f => ({
      id:            `tmp_${Date.now()}_${Math.random()}`,
      filename:      f.name,
      original_name: f.name,
      file_type:     'unknown',
      status:        'uploading',
    }));
    setAttachments(prev => [...prev, ...placeholders]);

    try {
      const res      = await uploadAttachments(files, state.currentId);
      const uploaded = res.attachments || [];
      setAttachments(prev => [
        ...prev.filter(a => !a.id.startsWith('tmp_')),
        ...uploaded,
      ]);
      uploaded.forEach(att => {
        if (att.status !== 'ready') _poll(att.id);
      });
    } catch {
      setAttachments(prev =>
        prev.map(a => a.id.startsWith('tmp_') ? { ...a, status: 'error' } : a)
      );
    }
  }, [state.currentId, _poll]);

  const handleAttachClick = () => fileInputRef.current?.click();

  const handleFileInputChange = (e) => {
    handleFiles(e.target.files);
    e.target.value = '';
  };

  const handleRemove = useCallback(async (id) => {
    setAttachments(prev => prev.filter(a => a.id !== id));
    if (pollingRefs.current[id]) {
      clearInterval(pollingRefs.current[id]);
      delete pollingRefs.current[id];
    }
    if (!id.startsWith('tmp_')) {
      try { await deleteAttachment(id); } catch {}
    }
  }, []);

  /* ── Drag-and-drop ───────────────────────────────────────── */
  const handleDragOver  = (e) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = (e) => { if (!e.currentTarget.contains(e.relatedTarget)) setIsDragging(false); };
  const handleDrop      = (e) => {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  /* ── Send ────────────────────────────────────────────────── */
  const handleSend = useCallback(() => {
    if (!value.trim() || isGenerating) return;
    stt.cancel();
    const readyIds = attachments.filter(a => a.status === 'ready').map(a => a.id);
    send(value, readyIds);
    setValue('');
    setChar(0);
    setAttachments([]);
    if (taRef.current) taRef.current.style.height = 'auto';
  }, [value, isGenerating, attachments, send, stt]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const canSend = value.trim().length > 0 && !isGenerating;

  return (
    <div
      className={`input-area ${isDragging ? 'drag-over' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Drag-drop overlay */}
      {isDragging && (
        <div className="drag-overlay">
          <div className="drag-overlay-inner">
            <span className="drag-icon">📎</span>
            <span>Drop files to attach</span>
          </div>
        </div>
      )}

      <div className="input-container">
        <div className="input-pill">

          {/* Attachment preview chips (above textarea, inside pill) */}
          {attachments.length > 0 && (
            <div className="attachment-preview">
              {attachments.map(att => (
                <AttachmentChip key={att.id} attachment={att} onRemove={handleRemove} />
              ))}
            </div>
          )}

          <div className="input-row">
            {/* 📎 Attach button */}
            <button
              className="input-add-btn"
              title="Attach file (PDF, image, CSV, code, ZIP…)"
              onClick={handleAttachClick}
            >
              <AttachIcon />
            </button>

            {/* Textarea */}
            <textarea
              ref={taRef}
              className="input-textarea"
              placeholder={
                stt.recording    ? 'Recording…'    :
                stt.transcribing ? 'Transcribing…' :
                isDragging       ? 'Drop files to attach…' :
                'Ask anything'
              }
              value={value}
              onChange={handleChange}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={isGenerating}
              style={{ fontStyle: (stt.recording || stt.transcribing) ? 'italic' : 'normal' }}
            />

            {/* Right icons */}
            <div className="input-right-icons">
              {charCount > 0 && (
                <span style={{ fontSize: 11, color: 'var(--text-faint)', marginRight: 2 }}>
                  ~{Math.ceil(charCount / 4)}t
                </span>
              )}

              {/* Hold-to-speak mic */}
              <button
                className="input-mic-btn"
                title="Hold to speak (offline STT)"
                onMouseDown={handleMicDown}
                onMouseUp={handleMicUp}
                onTouchStart={(e) => { e.preventDefault(); handleMicDown(); }}
                onTouchEnd={(e) => { e.preventDefault(); handleMicUp(); }}
                style={{
                  color: stt.recording ? '#ef4444' : stt.transcribing ? '#f59e0b' : undefined,
                  position: 'relative',
                }}
              >
                <MicIcon listening={stt.recording} />
                {(stt.recording || stt.transcribing) && (
                  <span style={{
                    position: 'absolute', top: 4, right: 4,
                    width: 6, height: 6, borderRadius: '50%',
                    background: stt.recording ? '#ef4444' : '#f59e0b',
                    animation: 'orbPulse 1s ease-in-out infinite',
                  }} />
                )}
              </button>

              {/* Voice-mode orb */}
              <button
                className="input-mic-btn"
                title="Voice mode"
                onClick={() => dispatch({ type: 'SHOW_VOICE', payload: true })}
                style={{ color: 'rgba(168,85,247,.7)' }}
              >
                <OrbIcon />
              </button>

              {/* Send / Stop */}
              {isGenerating ? (
                <button className="stop-btn" onClick={stop} title="Stop generation">
                  <StopIcon />
                </button>
              ) : (
                <button className="send-btn" onClick={handleSend} disabled={!canSend} title="Send (Enter)">
                  <SendIcon />
                </button>
              )}
            </div>
          </div>
        </div>

        <p className="input-disclaimer">
          OfflineGPT can make mistakes. All data stays on your device.
        </p>
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={ACCEPT}
        onChange={handleFileInputChange}
        style={{ display: 'none' }}
      />

      <style>{`
        @keyframes orbPulse{0%,100%{opacity:.6;transform:scale(1)}50%{opacity:1;transform:scale(1.4)}}
      `}</style>
    </div>
  );
}
