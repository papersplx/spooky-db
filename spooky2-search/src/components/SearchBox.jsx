import { useState, useEffect, useRef } from 'react';
import './SearchBox.css';

function SearchBox({ query, onSearch }) {
  const [value, setValue] = useState(query || '');
  const debounceRef = useRef(null);

  const DEBOUNCE_MS = 300;

  useEffect(() => {
    setValue(query || '');
  }, [query]);

  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(() => {
      onSearch(value);
    }, DEBOUNCE_MS);

    return () => clearTimeout(debounceRef.current);
  }, [value, onSearch]);

  return (
    <div className="search-box">
      <input
        type="text"
        className="search-input"
        placeholder="Search frequencies by name or description..."
        value={value}
        onChange={(e) => setValue(e.target.value)}
        autoFocus
      />
      {value && (
        <button
          className="clear-btn"
          onClick={() => setValue('')}
          aria-label="Clear search"
        >
          ×
        </button>
      )}
    </div>
  );
}

export default SearchBox;
