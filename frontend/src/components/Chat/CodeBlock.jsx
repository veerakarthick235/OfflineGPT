import { useState, useCallback } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { runCode } from '../../api/client';
import { useApp } from '../../context/AppContext';
import './CodeBlock.css';

const LANG_ICONS = {
  python:     '🐍',
  javascript: '🟨',
  typescript: '🔷',
  jsx:        '⚛️',
  tsx:        '⚛️',
  sql:        '🗄️',
  bash:       '💲',
  sh:         '💲',
  go:         '🐹',
  rust:       '🦀',
  java:       '☕',
  css:        '🎨',
  html:       '🌐',
  json:       '📦',
  yaml:       '📄',
  markdown:   '📝',
};

const RUNNABLE = new Set(['python', 'javascript', 'js', 'sql', 'node', 'sqlite']);

function CopyIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <rect x="9" y="9" width="13" height="13" rx="2"/>
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
    </svg>
  );
}

function RunIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
      <polygon points="5,3 19,12 5,21"/>
    </svg>
  );
}

export default function CodeBlock({ code = '', language = 'text' }) {
  const { state } = useApp();
  const [copied,   setCopied]   = useState(false);
  const [running,  setRunning]  = useState(false);
  const [result,   setResult]   = useState(null);
  const [expanded, setExpanded] = useState(true);

  const lang       = language.toLowerCase();
  const isRunnable = RUNNABLE.has(lang);
  const icon       = LANG_ICONS[lang] || '📄';

  // Normalise language alias for Prism
  const prismLang = lang === 'js' ? 'javascript'
                  : lang === 'ts' ? 'typescript'
                  : lang === 'sh' ? 'bash'
                  : lang === 'sqlite' ? 'sql'
                  : lang;

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {}
  }, [code]);

  const handleRun = useCallback(async () => {
    if (running) return;
    setRunning(true);
    setResult(null);
    try {
      const res = await runCode({
        code,
        language:        lang === 'js' ? 'javascript' : lang,
        conversation_id: state.currentId || undefined,
        timeout:         10,
      });
      setResult(res);
      setExpanded(true);
    } catch (err) {
      setResult({
        success: false, error: err.message,
        stdout: '', stderr: err.message, duration_ms: 0,
      });
    } finally {
      setRunning(false);
    }
  }, [code, lang, running, state.currentId]);

  return (
    <div className="code-block-wrap">
      {/* Header */}
      <div className="code-block-header">
        <div className="code-block-lang">
          <span>{icon}</span>
          <span>{language || 'code'}</span>
        </div>
        <div className="code-block-actions">
          {isRunnable && (
            <button
              className={`code-run-btn ${running ? 'running' : ''}`}
              onClick={handleRun}
              disabled={running}
              title={`Run ${language} in sandbox`}
            >
              {running
                ? <span className="code-run-spinner" />
                : <RunIcon />}
              {running ? 'Running…' : 'Run'}
            </button>
          )}
          <button className="code-copy-btn" onClick={handleCopy} title="Copy code">
            <CopyIcon />
            {copied ? 'Copied!' : 'Copy'}
          </button>
        </div>
      </div>

      {/* Syntax-highlighted code */}
      <SyntaxHighlighter
        style={oneDark}
        language={prismLang}
        PreTag="pre"
        customStyle={{
          margin: 0,
          background: '#0d1117',
          borderRadius: 0,
          padding: '14px 16px',
          fontSize: '0.83rem',
          lineHeight: 1.6,
        }}
        codeTagProps={{
          style: { fontFamily: "'JetBrains Mono','Fira Code','Cascadia Code',monospace" },
        }}
      >
        {code}
      </SyntaxHighlighter>

      {/* Execution result panel */}
      {result && (
        <div className={`exec-result ${result.success ? 'success' : 'error'}`}>
          <div className="exec-result-header">
            <span className="exec-status-icon">{result.success ? '✅' : '❌'}</span>
            <span className="exec-status-label">
              {result.success ? 'Success' : 'Error'} — {result.duration_ms}ms
            </span>
            {result.truncated && (
              <span className="exec-truncated">⚠️ Output truncated</span>
            )}
            <button className="exec-toggle" onClick={() => setExpanded(v => !v)}>
              {expanded ? '▲' : '▼'}
            </button>
          </div>
          {expanded && (
            <div className="exec-output">
              {result.stdout && (
                <pre className="exec-stdout">{result.stdout}</pre>
              )}
              {result.stderr && (
                <pre className="exec-stderr">{result.stderr}</pre>
              )}
              {!result.stdout && !result.stderr && result.success && (
                <span className="exec-empty">✔ No output</span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
