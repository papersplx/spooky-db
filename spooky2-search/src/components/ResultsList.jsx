import { useState, useEffect, useMemo } from 'react';
import './ResultsList.css';

function ResultsList({ programs, selected, onSelect, onClearSelection, isSearchPending, totalResults, onPageChange }) {
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 20;

  useEffect(() => {
    setCurrentPage(1);
  }, [programs]);

  const totalPages = Math.ceil(totalResults / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const pageItems = programs.slice(startIndex, startIndex + pageSize);

  const displayList = useMemo(() => {
    return pageItems.map(result => ({
      program: result.item || result,
    }));
  }, [pageItems]);

  const goToPage = (page) => {
    const newPage = Math.max(1, Math.min(page, totalPages));
    setCurrentPage(newPage);
    if (onPageChange) onPageChange(newPage);
  };

  const renderPagination = () => {
    if (totalPages <= 1) return null;
    const pages = [];
    const maxVisible = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);
    if (endPage - startPage + 1 < maxVisible) {
      startPage = Math.max(1, endPage - maxVisible + 1);
    }

    if (startPage > 1) {
      pages.push(1);
      if (startPage > 2) pages.push('...');
    }
    for (let i = startPage; i <= endPage; i++) {
      pages.push(i);
    }
    if (endPage < totalPages) {
      if (endPage < totalPages - 1) pages.push('...');
      pages.push(totalPages);
    }

    return (
      <div className="pagination">
        <button
          className="page-btn"
          disabled={currentPage === 1}
          onClick={() => goToPage(currentPage - 1)}
        >
          Previous
        </button>
        {pages.map((page, idx) => (
          typeof page === 'number' ? (
            <button
              key={idx}
              className={`page-btn ${page === currentPage ? 'active' : ''}`}
              onClick={() => goToPage(page)}
            >
              {page}
            </button>
          ) : (
            <span key={idx} className="page-ellipsis">...</span>
          )
        ))}
        <button
          className="page-btn"
          disabled={currentPage === totalPages}
          onClick={() => goToPage(currentPage + 1)}
        >
          Next
        </button>
      </div>
    );
  };

  return (
    <div className="results-list">
      <div className="results-header">
        <h2>Results ({totalResults})</h2>
        {isSearchPending && <div className="search-spinner" />}
        {totalPages > 1 && (
          <span className="page-info">
            Page {currentPage} of {totalPages}
          </span>
        )}
      </div>

      <div className="results-items">
        {displayList.length === 0 ? (
          <div className="no-results">
            <p>No programs match your criteria.</p>
            <button className="clear-btn" onClick={onClearSelection}>
              Clear filters
            </button>
          </div>
        ) : (
          displayList.map(({ program }, index) => (
            <div
              key={program.id || `result-${index}`}
              className={`result-item ${selected?.id === program.id ? 'selected' : ''}`}
              onClick={() => onSelect(program)}
            >
              <div className="result-name">
                {program.name}
                {program.entry_type === 'preset' && (
                  <span className="entry-badge preset">chain</span>
                )}
              </div>
              <div className="result-meta">
                <span className="result-collection">{program.collection}</span>
                {program.mode && !program.collection.toLowerCase().includes(program.mode.toLowerCase()) && (
                  <span className="result-mode">{program.mode}</span>
                )}
                {program.entry_type === 'preset' && (
                  <span className="result-type">preset</span>
                )}
              </div>
              <div className="result-description">
                {program.description?.slice(0, 120)}
                {program.description?.length > 120 ? '...' : ''}
              </div>
            </div>
          ))
        )}
      </div>

      {renderPagination()}
    </div>
  );
}

export default ResultsList;
