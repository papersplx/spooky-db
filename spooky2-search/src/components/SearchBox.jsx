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
    <div className="search-box-wrapper">
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
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M7 5.67L2.67 1.34L1.34 2.67L5.67 7L1.34 11.33L2.67 12.66L7 8.33L11.33 12.66L12.66 11.33L8.33 7L12.66 2.67L11.33 1.34L7 5.67Z" fill="currentColor"/>
          </svg>
        </button>
      )}
    </div>
  );
}

export default SearchBox;
