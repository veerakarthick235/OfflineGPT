import './ToolActivityIndicator.css';

const STATUS_COLORS = {
  running: 'var(--accent)',
  done:    '#22c55e',
  error:   '#ef4444',
};

const STATUS_DOTS = {
  running: <span className="tool-pulse" />,
  done:    null,
  error:   null,
};

export default function ToolActivityIndicator({ activity }) {
  if (!activity) return null;

  const { icon = '⚡', label = '', status = 'running' } = activity;
  const color = STATUS_COLORS[status] || STATUS_COLORS.running;

  return (
    <div className="tool-activity-wrap">
      <div className="tool-activity-card" style={{ '--tool-color': color }}>
        <span className="tool-activity-icon">{icon}</span>
        <span className="tool-activity-label">{label}</span>
        {STATUS_DOTS[status]}
        {status === 'running' && (
          <span className="tool-activity-spinner" />
        )}
      </div>
    </div>
  );
}
