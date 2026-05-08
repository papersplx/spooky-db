import { useMemo } from 'react';
import StatsBar from './StatsBar';
import './ResultsList.css';

function ResultsList({ programs, selected, onSelect, onClearSelection, isSearchPending, totalResults, onPageChange, searchQuery, currentPage }) {
  const pageSize = 20;

  const totalPages = Math.ceil(totalResults / pageSize);

  const displayList = useMemo(() => {
    return programs.map(result => ({
      program: result.item || result,
    }));
  }, [programs]);

  const goToPage = (page) => {
    const newPage = totalPages > 0 ? Math.max(1, Math.min(page, totalPages)) : page;
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
              type="button"
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
        <StatsBar
          total={totalResults}
          query={searchQuery}
          currentPage={currentPage}
          pageSize={pageSize}
        />
        {isSearchPending && <div className="search-spinner" />}
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
