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
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M6 4.575L1.575 0.15L0.15 1.575L4.575 6L0.15 10.425L1.575 11.85L6 7.425L10.425 11.85L11.85 10.425L7.425 6L11.85 1.575L10.425 0.15L6 4.575Z" fill="currentColor"/>
          </svg>
        </button>
      )}
    </div>
  );
}

export default SearchBox;
