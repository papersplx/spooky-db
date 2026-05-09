import './StatsBar.css';

function StatsBar({ total, query, currentPage, pageSize, programs }) {
  const start = total > 0 ? (currentPage - 1) * pageSize + 1 : 0;
  const end = Math.min(currentPage * pageSize, total);

  const breakdowns = programs.reduce((acc, p) => {
    acc.entry_type[p.entry_type] = (acc.entry_type[p.entry_type] || 0) + 1;
    acc.mode[p.mode] = (acc.mode[p.mode] || 0) + 1;
    return acc;
  }, { entry_type: {}, mode: {} });

  const entryTypes = Object.entries(breakdowns.entry_type);
  const modes = Object.entries(breakdowns.mode);

  return (
    <div className="stats-bar">
      <span className="stats-count">
        {start}-{end} of {total.toLocaleString()} result{total !== 1 ? 's' : ''}
        {query && <span> for "<strong>{query}</strong>"</span>}
      </span>
      <div className="stats-breakdown">
        <span className="stats-breakdown-label">Types:</span>
        {entryTypes.map(([type, count]) => (
          <span key={type} className="stats-badge">
            {type}: {count}
          </span>
        ))}
        <span className="stats-breakdown-label">Modes:</span>
        {modes.map(([mode, count]) => (
          <span key={mode} className="stats-badge">
            {mode}: {count}
          </span>
        ))}
      </div>
    </div>
  );
}

export default StatsBar;
