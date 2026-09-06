import React from 'react';

/**
 * A minimal progress bar used for the SLA indicator.
 * `percent` should be a number between 0 and 100.
 */
export default function MiniProgressBar({ percent = 0 }) {
  const clamped = Math.min(100, Math.max(0, percent));
  return (
    <div className="mini-progress-bar" style={{
      height: '4px',
      borderRadius: '2px',
      backgroundColor: 'var(--bg-muted)',
      overflow: 'hidden',
    }}>
      <div style={{
        width: `${clamped}%`,
        height: '100%',
        backgroundColor: 'var(--accent-blue)',
        transition: 'width 0.3s ease',
      }} />
    </div>
  );
}
