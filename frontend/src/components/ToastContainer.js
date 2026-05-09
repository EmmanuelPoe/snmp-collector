import React from 'react';

const ICONS = {
  success: '✓',
  error:   '✕',
  warning: '⚠',
  info:    'ℹ',
};

export default function ToastContainer({ toasts, onDismiss }) {
  if (toasts.length === 0) return null;

  return (
    <div className="toast-container">
      {toasts.map(toast => (
        <div key={toast.id} className={`toast toast-${toast.type}`}>
          <span style={{ color: typeColor(toast.type), fontSize: 13, flexShrink: 0 }}>
            {ICONS[toast.type]}
          </span>
          <span className="toast-message">{toast.message}</span>
          <button className="toast-dismiss" onClick={() => onDismiss(toast.id)}>×</button>
        </div>
      ))}
    </div>
  );
}

function typeColor(type) {
  const map = {
    success: 'var(--color-success)',
    error:   'var(--color-error)',
    warning: 'var(--color-warning)',
    info:    'var(--color-info)',
  };
  return map[type] || 'var(--color-text-secondary)';
}
