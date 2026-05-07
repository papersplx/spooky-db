import { useState, useEffect, useRef } from 'react';
import './SearchBox.css';

function SearchBox({ query, onSearch }) {
  const [value, setValue] = useState(query || '');
  const debounceRef = useRef(null);
  const wrapperRef = useRef(null);

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

  const handleClear = () => {
    setValue('');
    if (wrapperRef.current) {
      const input = wrapperRef.current.querySelector('input');
      if (input) input.focus();
    }
  };

  return (
    <div className="search-box" ref={wrapperRef}>
      <input
        type="text"
        className="search-input"
        placeholder="Search frequencies by name or description..."
        value={value}
        onChange={(e) => setValue(e.target.value)}
        autoFocus
      />
      <button
        className={`clear-btn ${value ? 'visible' : ''}`}
        onClick={handleClear}
        aria-label="Clear search"
      >
        ×
      </button>
    </div>
  );
}

export default SearchBox;
