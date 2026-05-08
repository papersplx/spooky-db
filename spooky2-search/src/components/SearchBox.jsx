import { useState, useEffect, useRef } from 'react';
import './SearchBox.css';

function SearchBox({ query, onSearch }) {
  const [value, setValue] = useState(query || '');
  const wrapperRef = useRef(null);
  const isInitialized = useRef(false);

  useEffect(() => {
    if (!isInitialized.current) {
      isInitialized.current = true;
      return;
    }
    setValue(query || '');
  }, [query]);

  useEffect(() => {
    if (!isInitialized.current) return;
    
    const debounceRef = setTimeout(() => {
      onSearch(value);
    }, 300);

    return () => clearTimeout(debounceRef);
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
