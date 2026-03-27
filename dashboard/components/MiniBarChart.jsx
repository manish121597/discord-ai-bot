"use client";

export default function MiniBarChart({ items, title, emptyLabel }) {
  const maxValue = Math.max(...items.map((item) => item.value), 1);

  return (
    <div className="panel">
      <div className="panel-header">
        <h3>{title}</h3>
      </div>

      {!items.length ? (
        <p className="empty-state">{emptyLabel}</p>
      ) : (
        <div className="bar-list">
          {items.map((item) => (
            <div key={item.label} className="bar-row">
              <div className="bar-meta">
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
              <div className="bar-track">
                <div
                  className="bar-fill"
                  style={{ width: `${(item.value / maxValue) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
