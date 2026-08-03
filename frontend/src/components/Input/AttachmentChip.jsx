import './AttachmentChip.css';

const TYPE_ICONS = {
  pdf:      '📄',
  image:    '🖼️',
  data:     '📊',
  slides:   '📊',
  document: '📝',
  code:     '💻',
  archive:  '📦',
  unknown:  '📎',
};

const STATUS_COLORS = {
  uploading:  'var(--text-dim)',
  processing: '#f59e0b',
  ready:      'var(--text)',
  error:      '#ef4444',
};

export default function AttachmentChip({ attachment, onRemove }) {
  const icon   = TYPE_ICONS[attachment.file_type] || '📎';
  const status = attachment.status || 'ready';
  const color  = STATUS_COLORS[status] || 'var(--text)';

  // Truncate long filenames
  const name = attachment.original_name || attachment.filename || 'file';
  const displayName = name.length > 24 ? name.slice(0, 21) + '…' + name.slice(-4) : name;

  return (
    <div className={`attach-chip ${status}`} title={name}>
      <span className="attach-chip-icon">{icon}</span>
      <div className="attach-chip-info">
        <span className="attach-chip-name" style={{ color }}>{displayName}</span>
        {status !== 'ready' && (
          <span className="attach-chip-status">
            {status === 'uploading'  && '⬆ Uploading…'}
            {status === 'processing' && <><span className="attach-spin">⟳</span> Processing…</>}
            {status === 'error'      && '✗ Failed'}
          </span>
        )}
      </div>
      <button
        className="attach-chip-remove"
        onClick={() => onRemove(attachment.id)}
        title="Remove"
        aria-label="Remove attachment"
      >
        ×
      </button>
    </div>
  );
}
