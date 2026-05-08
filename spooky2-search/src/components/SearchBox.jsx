import { useState, useEffect, useRef, useImperativeHandle, forwardRef } from 'react';
import './SearchBox.css';

const SearchBox = forwardRef(({ query, onSearch }, ref) => {
  const [value, setValue] = useState(query || '');
  const wrapperRef = useRef(null);
  const isInitialized = useRef(false);
  const debounceRef = useRef(null);
  const onSearchRef = useRef(onSearch);

  onSearchRef.current = onSearch;

  useImperativeHandle(ref, () => ({
    cancelDebounce: () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
        debounceRef.current = null;
      }
    }
  }));

  useEffect(() => {
    if (!isInitialized.current) {
      isInitialized.current = true;
      return;
    }
    setValue(query || '');
  }, [query]);

  useEffect(() => {
    if (!isInitialized.current) return;

    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(() => {
      onSearchRef.current(value);
    }, 300);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [value]);

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
});

SearchBox.displayName = 'SearchBox';

export default SearchBox;
