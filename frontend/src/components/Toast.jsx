import { useApp } from '../context/AppContext';

export default function ToastStack() {
  const { state } = useApp();
  const { toasts } = state;

  if (!toasts.length) return null;

  return (
    <div className="toast-stack">
      {toasts.map(t => (
        <div key={t.id} className={`toast ${t.type}`}>{t.msg}</div>
      ))}
    </div>
  );
}
