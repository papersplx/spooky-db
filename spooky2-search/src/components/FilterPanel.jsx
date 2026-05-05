import { useState, useRef, useEffect, useMemo } from 'react';
import './FilterPanel.css';

export default function FilterPanel({
  collections,
  collectionCounts = {},
  selectedCollections,
  onToggleCollection,
  modes,
  selectedModes,
  onToggleMode,
  onClearFilters,
}) {
  const [visibleCount, setVisibleCount] = useState(20);
  const listRef = useRef(null);
  const sentinelRef = useRef(null);

  const displayNames = useMemo(() => {
    const lastPartCount = {};
    collections.forEach(coll => {
      const last = coll.split('/').pop();
      lastPartCount[last] = (lastPartCount[last] || 0) + 1;
    });
    const map = {};
    collections.forEach(coll => {
      const parts = coll.split('/');
      const last = parts.pop();
      if (lastPartCount[last] === 1) {
        map[coll] = last;
        return;
      }
      let display = last;
      let idx = parts.length - 1;
      while (idx >= 0) {
        display = `${parts[idx]}/${display}`;
        const isUnique = !collections.some(other => other !== coll && other.endsWith(display));
        if (isUnique) {
          map[coll] = display;
          return;
        }
        idx--;
      }
      map[coll] = coll;
    });
    return map;
  }, [collections]);

  useEffect(() => {
    const list = listRef.current;
    const sentinel = sentinelRef.current;
    if (!list || !sentinel) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && visibleCount < collections.length) {
          setVisibleCount(prev => Math.min(prev + 20, collections.length));
        }
      },
      { root: list, rootMargin: '0px', threshold: 0.1 }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [visibleCount, collections.length]);

  return (
    <div className="filter-panel">
      <h3>Filters</h3>

      <div className="filter-section">
        <div className="filter-header">
          <h4>Collections</h4>
          <button className="clear-link" onClick={onClearFilters}>
            Clear all
          </button>
        </div>
        <div className="filter-options" ref={listRef}>
          {collections.slice(0, visibleCount).map(coll => (
            <label key={coll} className="checkbox-label">
              <input
                type="checkbox"
                checked={selectedCollections.includes(coll)}
                onChange={() => onToggleCollection(coll)}
              />
              <span className="checkbox-text" title={coll}>
                {displayNames[coll] || coll.split('/').pop()}
                {collectionCounts[coll] ? ` (${collectionCounts[coll]})` : ''}
              </span>
            </label>
          ))}
          {visibleCount < collections.length && (
            <div ref={sentinelRef} className="sentinel">
              Loading more...
            </div>
          )}
        </div>
        <div className="filter-info">
          <small>
            Showing {Math.min(visibleCount, collections.length)} of {collections.length} collections
          </small>
        </div>
      </div>

      <div className="filter-section">
        <h4>Mode</h4>
        <div className="filter-options">
          {modes.map(mode => (
            <label key={mode} className="checkbox-label">
              <input
                type="checkbox"
                checked={selectedModes.includes(mode)}
                onChange={() => onToggleMode(mode)}
              />
              <span>{mode}</span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}
