import './StatsBar.css';

function StatsBar({ total, query }) {
  return (
    <div className="stats-bar">
      <span className="stats-count">
        {total.toLocaleString()} result{total !== 1 ? 's' : ''}
        {query && <span> for "<strong>{query}</strong>"</span>}
      </span>
    </div>
  );
}

export default StatsBar;
