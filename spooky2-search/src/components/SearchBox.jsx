import { useState, useEffect, useRef, useImperativeHandle, forwardRef } from 'react';
import './SearchBox.css';

const SearchBox = forwardRef(({ query, onSearch }, ref) => {
  const [value, setValue] = useState(query || '');
  const wrapperRef = useRef(null);
  const onSearchRef = useRef(onSearch);

  onSearchRef.current = onSearch;

  useImperativeHandle(ref, () => ({
    cancelDebounce: () => {}
  }));

  useEffect(() => {
    setValue(query || '');
  }, [query]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      onSearchRef.current(value);
    }
  };

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
        onKeyDown={handleKeyDown}
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
