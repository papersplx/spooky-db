import './StatsBar.css';

function StatsBar({ total, query, currentPage, pageSize }) {
  const start = total > 0 ? (currentPage - 1) * pageSize + 1 : 0;
  const end = Math.min(currentPage * pageSize, total);

  return (
    <div className="stats-bar">
      <span className="stats-count">
        {start}-{end} of {total.toLocaleString()} result{total !== 1 ? 's' : ''}
        {query && <span> for "<strong>{query}</strong>"</span>}
      </span>
    </div>
  );
}

export default StatsBar;
