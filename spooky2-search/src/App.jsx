import { useState, useEffect, useRef } from 'react';
import SearchBox from './components/SearchBox';
import FilterPanel from './components/FilterPanel';
import ResultsList from './components/ResultsList';
import ProgramDetail from './components/ProgramDetail';
import StatsBar from './components/StatsBar';
import { searchPrograms, getProgram, getCollections } from './data/loader';
import './App.css';

function getStateFromURL() {
  const params = new URLSearchParams(window.location.search);
  return {
    searchQuery: params.get('q') || 'Longevity',
    selectedModes: params.getAll('mode').length > 0 ? params.getAll('mode') : ['Remote'],
    selectedCollections: params.getAll('collection'),
    selectedProgramId: params.get('program') || null,
  };
}

function updateURL(state) {
  const params = new URLSearchParams();
  if (state.searchQuery && state.searchQuery !== 'Longevity') params.set('q', state.searchQuery);
  state.selectedModes.forEach(m => params.append('mode', m));
  state.selectedCollections.forEach(c => params.append('collection', c));
  if (state.selectedProgramId) params.set('program', state.selectedProgramId);
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
  const [filtered, setFiltered] = useState([]);
  const [isSearchPending, setIsSearchPending] = useState(false);
  const [totalPrograms, setTotalPrograms] = useState(0);

  const skipURLUpdate = useRef(false);

  useEffect(() => {
    const fetchCollections = async () => {
      try {
        const collections = await getCollections();
        const counts = {};
        const names = new Set();
        collections.forEach(({ collection, count }) => {
          names.add(collection);
          counts[collection] = (counts[collection] || 0) + parseInt(count);
        });
        setCollectionsList([...names].sort());
        setCollectionCounts(counts);
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
    setIsSearchPending(true);
    const timer = setTimeout(async () => {
      try {
        const results = await searchPrograms({
          q: searchQuery,
          mode: selectedModes,
          collection: selectedCollections,
          limit: 20,
        });
        setFiltered(results.map(p => ({ item: p })));
      } catch (err) {
        setError(err.message);
      } finally {
        setIsSearchPending(false);
      }
    }, 300); // Debounce search
    return () => clearTimeout(timer);
  }, [searchQuery, selectedCollections, selectedModes, loading]);

  useEffect(() => {
    const handlePopState = () => {
      skipURLUpdate.current = true;
      const state = getStateFromURL();
      setSearchQuery(state.searchQuery);
      setSelectedModes(state.selectedModes);
      setSelectedCollections(state.selectedCollections);
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
    });
  }, [searchQuery, selectedModes, selectedCollections, selected]);

  const handleSearch = (query) => {
    setSearchQuery(query);
  };

  const handleSelectCollection = (collection) => {
    setSelectedCollections(prev =>
      prev.includes(collection)
        ? prev.filter(c => c !== collection)
        : [...prev, collection]
    );
  };

  const handleSelectMode = (mode) => {
    setSelectedModes(prev =>
      prev.includes(mode)
        ? prev.filter(m => m !== mode)
        : [...prev, mode]
    );
  };

  const handleSelectProgram = (program) => {
    setSelected(program);
  };

  const handleSearchForProgram = (programName) => {
    setSearchQuery(programName);
    setSelected(null);
  };

  const handleClearSelection = () => {
    setSelected(null);
  };

  const handleClearFilters = () => {
    setSelectedCollections([]);
    setSelectedModes([]);
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

  const modes = [...new Set(filtered.map(p => p.mode).filter(Boolean))].sort();

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
            selectedCollections={selectedCollections}
            onToggleCollection={handleSelectCollection}
            modes={modes}
            selectedModes={selectedModes}
            onToggleMode={handleSelectMode}
            onClearFilters={handleClearFilters}
          />
        </aside>

        <section className="search-results">
          <SearchBox query={searchQuery} onSearch={handleSearch} />
          <div className="results-header">
            <StatsBar
              total={filtered.length}
              query={searchQuery}
            />
            {isSearchPending && <div className="search-spinner" />}
          </div>
          <ResultsList
            programs={filtered}
            selected={selected}
            onSelect={handleSelectProgram}
            onClearSelection={handleClearSelection}
            isSearchPending={isSearchPending}
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
