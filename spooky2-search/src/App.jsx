import { useState, useEffect, useRef, useCallback } from 'react';
import SearchBox from './components/SearchBox';
import FilterPanel from './components/FilterPanel';
import ResultsList from './components/ResultsList';
import ProgramDetail from './components/ProgramDetail';
import { searchPrograms, getProgram, getCollections } from './data/loader';
import './App.css';

function getStateFromURL() {
  const params = new URLSearchParams(window.location.search);
  return {
    searchQuery: params.get('q') || 'Longevity',
    selectedModes: params.getAll('mode').length > 0 ? params.getAll('mode') : ['Remote'],
    selectedCollections: params.getAll('collection'),
    selectedProgramId: params.get('program') || null,
    page: parseInt(params.get('page') || '1'),
  };
}

function App() {
  const initialState = getStateFromURL();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [searchQuery, setSearchQuery] = useState(initialState.searchQuery);
  const [selectedCollections, setSelectedCollections] = useState(initialState.selectedCollections);
  const [selectedModes, setSelectedModes] = useState(initialState.selectedModes);
  const [collectionsList, setCollectionsList] = useState([]);
  const [collectionCounts, setCollectionCounts] = useState({});
  const [modesList, setModesList] = useState([]);
  const [filtered, setFiltered] = useState([]);
  const [totalResults, setTotalResults] = useState(0);
  const [isSearchPending, setIsSearchPending] = useState(false);
  const [totalPrograms, setTotalPrograms] = useState(0);
  const [currentPage, setCurrentPage] = useState(initialState.page);

  const searchParamsRef = useRef({});
  const abortControllerRef = useRef(null);

  useEffect(() => {
    const fetchCollections = async () => {
      try {
        const collections = await getCollections();
        const counts = {};
        const names = new Set();
        const modes = new Set();
        collections.forEach(({ collection, count, mode }) => {
          names.add(collection);
          counts[collection] = (counts[collection] || 0) + parseInt(count);
          if (mode) modes.add(mode);
        });
        setCollectionsList([...names].sort());
        setCollectionCounts(counts);
        setModesList([...modes].sort());
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    const loadInitialProgram = async () => {
      if (initialState.selectedProgramId) {
        try {
          const program = await getProgram(initialState.selectedProgramId);
          setSelected(program);
        } catch (err) {
          console.error('Failed to load program from URL:', err);
        }
      }
    };

    fetchCollections();
    loadInitialProgram();
  }, []);

  const handleSearch = useCallback((query) => {
    console.log('handleSearch called, setting page to 1');
    setSearchQuery(query);
    setCurrentPage(1);
    updateURL({ searchQuery: query, selectedModes, selectedCollections, selectedProgramId: selected?.id || null, page: 1 });
  }, [searchQuery, selectedModes, selectedCollections, selected]);

  const handleSelectCollection = (collection) => {
    setSelectedCollections(prev =>
      prev.includes(collection)
        ? prev.filter(c => c !== collection)
        : [...prev, collection]
    );
    setCurrentPage(1);
    updateURL({ searchQuery, selectedModes, selectedCollections, selectedProgramId: selected?.id || null, page: 1 });
  };

  const handleSelectMode = (mode) => {
    setSelectedModes(prev =>
      prev.includes(mode)
        ? prev.filter(m => m !== mode)
        : [...prev, mode]
    );
    setCurrentPage(1);
    updateURL({ searchQuery, selectedModes, selectedCollections, selectedProgramId: selected?.id || null, page: 1 });
  };

  const handleSelectProgram = (program) => {
    console.log('handleSelectProgram called, currentPage:', currentPage);
    setSelected(program);
    updateURL({ searchQuery, selectedModes, selectedCollections, selectedProgramId: program.id, page: currentPage });
  };

  const handleSearchForProgram = (programName) => {
    setSearchQuery(programName);
    setSelected(null);
    setCurrentPage(1);
    updateURL({ searchQuery: programName, selectedModes, selectedCollections, selectedProgramId: null, page: 1 });
  };

  const handleClearSelection = () => {
    console.log('handleClearSelection called, currentPage:', currentPage);
    setSelected(null);
    updateURL({ searchQuery, selectedModes, selectedCollections, selectedProgramId: null, page: currentPage });
  };

  const handleClearFilters = () => {
    setSelectedCollections([]);
    setSelectedModes([]);
    setCurrentPage(1);
    updateURL({ searchQuery, selectedModes:[], selectedCollections:[], selectedProgramId: null, page: 1 });
  };

  const handlePageChange = (newPage) => {
    console.log('handlePageChange called with:', newPage);
    setCurrentPage(newPage);
    updateURL({ searchQuery, selectedModes, selectedCollections, selectedProgramId: selected?.id || null, page: newPage });
  };

  function updateURL(state) {
    if (state.page === 1) {
      console.trace('updateURL with page:1 trace');
    }
    const params = new URLSearchParams();
    if (state.searchQuery && state.searchQuery !== 'Longevity') params.set('q', state.searchQuery);
    state.selectedModes.forEach(m => params.append('mode', m));
    state.selectedCollections.forEach(c => params.append('collection', c));
    if (state.selectedProgramId) params.set('program', state.selectedProgramId);
    if (state.page && state.page !== 1) params.set('page', state.page);
    const newURL = params.toString() ? `${window.location.pathname}?${params.toString()}` : window.location.pathname;
    console.log('updateURL called with state:', state, 'newURL:', newURL, 'currentURL:', window.location.pathname + window.location.search);
    console.log('PUSHING STATE:', newURL);
    window.history.pushState(state, '', newURL);
  }

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
        <p>Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error">
        <h2>Error</h2>
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="header">
        <h1>Spooky2 Frequency Search</h1>
          <p className="subtitle">
            Search {totalPrograms.toLocaleString()} frequency programs from Spooky2 preset collections
          </p>
      </header>

      <main className="main">
        <aside className="sidebar">
          <FilterPanel
            collections={collectionsList}
            collectionCounts={collectionCounts}
            selectedCollections={selectedCollections}
            onToggleCollection={handleSelectCollection}
            modes={modesList}
            selectedModes={selectedModes}
            onToggleMode={handleSelectMode}
            onClearFilters={handleClearFilters}
          />
        </aside>

          <section className="search-results">
            <SearchBox query={searchQuery} onSearch={handleSearch} />
            <ResultsList
            programs={filtered}
            selected={selected}
            onSelect={handleSelectProgram}
            onClearSelection={handleClearSelection}
            isSearchPending={isSearchPending}
            totalResults={totalResults}
            currentPage={currentPage}
            onPageChange={handlePageChange}
            searchQuery={searchQuery}
          />
          </section>
      </main>

      {selected && (
        <div className="detail-backdrop" onClick={handleClearSelection} />
      )}

      {selected && (
          <aside className="detail-panel" onClick={(e) => e.stopPropagation()}>
            <ProgramDetail
              program={selected}
              programs={filtered}
              onClose={handleClearSelection}
              onSearchProgram={handleSearchForProgram}
            />
          </aside>
      )}

      <footer className="footer">
        <p>
          Data extracted from Spooky2 installer. Spooky2 is a registered trademark.
          <a href="https://spooky2.com" target="_blank" rel="noopener noreferrer">
            Visit Spooky2
          </a>
        </p>
        <p className="disclaimer">
          Frequencies are for experimental purposes only. Not medical advice.
        </p>
      </footer>
    </div>
  );
}

export default App;
