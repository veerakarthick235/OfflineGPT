import { useState, memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import CodeBlock from './CodeBlock';

/* ── Icons ─────────────────────────────────────────────────── */
const CopyIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="9" y="9" width="13" height="13" rx="2"/>
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
  </svg>
);
const CheckIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
    <polyline points="20,6 9,17 4,12"/>
  </svg>
);
const RegenIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="1,4 1,10 7,10"/>
    <path d="M3.51 15a9 9 0 1 0 .49-4.76"/>
  </svg>
);
const DownloadIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
    <polyline points="7,10 12,15 17,10"/><line x1="12" y1="15" x2="12" y2="3"/>
  </svg>
);

/* ── Copy helper ────────────────────────────────────────────── */
function useCopy() {
  const [copied, setCopied] = useState(false);
  const copy = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return { copied, copy };
}

/* CodeBlock is imported from ./CodeBlock — it has run button + syntax highlight */


/* ── Inline image bubble ─────────────────────────────────────── */
function InlineImage({ src, alt, prompt }) {
  const [loaded, setLoaded] = useState(false);
  const [error,  setError]  = useState(false);

  const handleDownload = () => {
    const a = document.createElement('a');
    a.href = src;
    a.download = `offlinegpt-${Date.now()}.png`;
    a.click();
  };

  return (
    <div style={{
      margin: '10px 0', borderRadius: 12, overflow: 'hidden',
      border: '1px solid rgba(255,255,255,.1)',
      background: 'rgba(0,0,0,.25)',
      display: 'inline-block', maxWidth: '100%',
    }}>
      {error ? (
        <div style={{ padding: '16px 20px', color: 'var(--text-dim)', fontSize: 13 }}>
          ⚠️ Image could not load: {src}
        </div>
      ) : (
        <>
          {!loaded && (
            <div style={{
              width: 320, height: 200, display: 'flex', alignItems: 'center',
              justifyContent: 'center', color: 'var(--text-dim)', fontSize: 13,
            }}>
              <span style={{ animation: 'pulse 1.5s ease-in-out infinite' }}>Loading image…</span>
            </div>
          )}
          <img
            src={src}
            alt={alt || prompt || 'Generated image'}
            onLoad={() => setLoaded(true)}
            onError={() => setError(true)}
            style={{
              display: loaded ? 'block' : 'none',
              maxWidth: '100%', maxHeight: 520,
              borderRadius: 0,
            }}
          />
          {loaded && (
            <div style={{
              padding: '8px 12px', display: 'flex', alignItems: 'center',
              justifyContent: 'space-between', borderTop: '1px solid rgba(255,255,255,.07)',
            }}>
              <span style={{ fontSize: 11, color: 'var(--text-dim)', fontStyle: 'italic', maxWidth: '80%',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {prompt || alt}
              </span>
              <button onClick={handleDownload} style={{
                display: 'flex', alignItems: 'center', gap: 4,
                fontSize: 11, color: 'var(--text-dim)', padding: '3px 8px',
                borderRadius: 4, background: 'rgba(255,255,255,.05)',
                border: 'none', cursor: 'pointer',
              }}>
                <DownloadIcon /> Save
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ── Markdown components — intercept ![img](/api/images/...) ─── */
function buildMdComponents() {
  return {
    code({ node, inline, className, children, ...props }) {
      const match = /language-(\w+)/.exec(className || '');
      const code  = String(children).replace(/\n$/, '');
      if (!inline && match) return <CodeBlock language={match[1]} code={code} />;
      // Non-fenced inline code
      return <code className={className} {...props}>{children}</code>;
    },
    // Render images from /api/images/* as InlineImage
    img({ src, alt }) {
      if (src && (src.startsWith('/api/images/') || src.startsWith('http://localhost:8000/api/images/'))) {
        return <InlineImage src={src} alt={alt} prompt={alt} />;
      }
      return <img src={src} alt={alt} style={{ maxWidth: '100%' }} />;
    },
  };
}

const mdComponents = buildMdComponents();

/* ── AI Avatar ──────────────────────────────────────────────── */
const AIAvatar = () => (
  <div className="ai-avatar">
    <svg width="13" height="13" viewBox="0 0 24 24" fill="white">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
  </div>
);

/* ── Generating indicator ────────────────────────────────────── */
export function ImageGeneratingIndicator({ prompt }) {
  return (
    <div className="message-wrapper assistant">
      <div className="ai-row">
        <AIAvatar />
        <div className="ai-content">
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '10px 14px', borderRadius: 10,
            background: 'rgba(168,85,247,.08)', border: '1px solid rgba(168,85,247,.2)',
          }}>
            <span style={{ fontSize: 18, animation: 'spin 2s linear infinite', display:'inline-block' }}>🎨</span>
            <div>
              <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>Generating image…</div>
              {prompt && (
                <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2, maxWidth: 340,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  "{prompt}"
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

/* ── Message ────────────────────────────────────────────────── */
function Message({ msg, onCopy, onRegenerate }) {
  const { copied, copy } = useCopy();
  const isUser = msg.role === 'user';

  const handleCopy = () => {
    copy(msg.content);
    onCopy?.();
  };

  return (
    <div className={`message-wrapper ${isUser ? 'user' : 'assistant'}`} data-id={msg.id}>
      {isUser ? (
        <>
          <div className="user-bubble">{msg.content}</div>
          <div className="msg-actions">
            <button className={`msg-action-btn ${copied ? 'success' : ''}`} onClick={handleCopy}>
              {copied ? <CheckIcon /> : <CopyIcon />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="ai-row">
            <AIAvatar />
            <div className="ai-content">
              <div className="ai-text">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                  {msg.content}
                </ReactMarkdown>
              </div>
            </div>
          </div>
          <div className="msg-actions">
            <button className={`msg-action-btn ${copied ? 'success' : ''}`} onClick={handleCopy}>
              {copied ? <CheckIcon /> : <CopyIcon />}
              {copied ? 'Copied' : 'Copy'}
            </button>
            {onRegenerate && (
              <button className="msg-action-btn" onClick={() => onRegenerate(msg)}>
                <RegenIcon /> Regenerate
              </button>
            )}
            <span className="msg-tokens">{msg.tokens || Math.ceil(msg.content.length / 4)} tokens</span>
          </div>
        </>
      )}
    </div>
  );
}

/* ── Streaming AI message ───────────────────────────────────── */
export function StreamingMessage({ content }) {
  return (
    <div className="message-wrapper assistant">
      <div className="ai-row">
        <AIAvatar />
        <div className="ai-content">
          <div className="ai-text">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
              {content}
            </ReactMarkdown>
            <span className="typing-cursor" />
          </div>
        </div>
      </div>
    </div>
  );
}

export default memo(Message);
