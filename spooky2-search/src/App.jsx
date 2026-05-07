import { useState, useEffect, useRef } from 'react';
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

function updateURL(state) {
  const params = new URLSearchParams();
  if (state.searchQuery && state.searchQuery !== 'Longevity') params.set('q', state.searchQuery);
  state.selectedModes.forEach(m => params.append('mode', m));
  state.selectedCollections.forEach(c => params.append('collection', c));
  if (state.selectedProgramId) params.set('program', state.selectedProgramId);
  if (state.page && state.page !== 1) params.set('page', state.page);
  const newURL = params.toString() ? `${window.location.pathname}?${params.toString()}` : window.location.pathname;
  window.history.pushState(state, '', newURL);
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

  const skipURLUpdate = useRef(false);
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

  useEffect(() => {
    if (loading) return;

    const params = {
      q: searchQuery,
      mode: selectedModes,
      collection: selectedCollections,
      page: currentPage,
    };

    searchParamsRef.current = params;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsSearchPending(true);
    const timer = setTimeout(async () => {
      try {
        const response = await searchPrograms({
          q: params.q,
          mode: params.mode,
          collection: params.collection,
          limit: 20,
          offset: (params.page - 1) * 20,
        });
        if (!controller.signal.aborted) {
          setFiltered(response.results.map(p => ({ item: p })));
          setTotalResults(response.total);
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err.message);
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsSearchPending(false);
        }
      }
    }, 300);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [searchQuery, selectedCollections, selectedModes, loading, currentPage]);

  useEffect(() => {
    const handlePopState = () => {
      skipURLUpdate.current = true;
      const state = getStateFromURL();
      setSearchQuery(state.searchQuery);
      setSelectedModes(state.selectedModes);
      setSelectedCollections(state.selectedCollections);
      setCurrentPage(state.page);
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  useEffect(() => {
    if (skipURLUpdate.current) {
      skipURLUpdate.current = false;
      return;
    }
    updateURL({
      searchQuery,
      selectedModes,
      selectedCollections,
      selectedProgramId: selected?.id || null,
      page: currentPage,
    });
  }, [searchQuery, selectedModes, selectedCollections, selected, currentPage]);

  const handleSearch = (query) => {
    setSearchQuery(query);
    setCurrentPage(1);
  };

  const handleSelectCollection = (collection) => {
    setSelectedCollections(prev =>
      prev.includes(collection)
        ? prev.filter(c => c !== collection)
        : [...prev, collection]
    );
    setCurrentPage(1);
  };

  const handleSelectMode = (mode) => {
    setSelectedModes(prev =>
      prev.includes(mode)
        ? prev.filter(m => m !== mode)
        : [...prev, mode]
    );
    setCurrentPage(1);
  };

  const handleSelectProgram = (program) => {
    setSelected(program);
  };

  const handleSearchForProgram = (programName) => {
    setSearchQuery(programName);
    setSelected(null);
    setCurrentPage(1);
  };

  const handleClearSelection = () => {
    setSelected(null);
  };

  const handleClearFilters = () => {
    setSelectedCollections([]);
    setSelectedModes([]);
    setCurrentPage(1);
  };

  const handlePageChange = (newPage) => {
    setCurrentPage(newPage);
    skipURLUpdate.current = true;
    updateURL({
      searchQuery,
      selectedModes,
      selectedCollections,
      selectedProgramId: selected?.id || null,
      page: newPage,
    });
  };

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
