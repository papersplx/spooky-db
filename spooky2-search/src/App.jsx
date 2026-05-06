import { useState, useEffect, useRef, useMemo } from 'react';
import Fuse from 'fuse.js';
import SearchBox from './components/SearchBox';
import FilterPanel from './components/FilterPanel';
import ResultsList from './components/ResultsList';
import ProgramDetail from './components/ProgramDetail';
import StatsBar from './components/StatsBar';
import { loadAllPresets } from './data/loader';
import './App.css';

function getStateFromURL() {
  const params = new URLSearchParams(window.location.search);
  return {
    searchQuery: params.get('q') || 'Longevity',
    selectedModes: params.getAll('mode').length > 0 ? params.getAll('mode') : ['Remote'],
    selectedCollections: params.getAll('collection'),
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

  const [programs, setPrograms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadProgress, setLoadProgress] = useState(0);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [searchQuery, setSearchQuery] = useState(initialState.searchQuery);
  const [selectedCollections, setSelectedCollections] = useState(initialState.selectedCollections);
  const [selectedModes, setSelectedModes] = useState(initialState.selectedModes);
  const [collectionsList, setCollectionsList] = useState([]);
  const [collectionCounts, setCollectionCounts] = useState({});
  const [filtered, setFiltered] = useState([]);

  const skipURLUpdate = useRef(false);
  const fuseRef = useRef(null);

  const fuseOptions = useMemo(() => ({
    keys: [
      { name: 'name', weight: 0.7 },
      { name: 'description', weight: 0.3 },
      { name: 'collection', weight: 0.2 },
      { name: 'loaded_programs', weight: 0.3 },
    ],
    threshold: 0.3,
    includeScore: true,
  }), []);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const allPrograms = await loadAllPresets((progress) => {
          setLoadProgress(progress);
        });
        setPrograms(allPrograms);
        fuseRef.current = new Fuse(allPrograms, fuseOptions);
        const collections = [...new Set(allPrograms.map(p => p.collection))].sort();
        setCollectionsList(collections);
        const counts = {};
        allPrograms.forEach(p => {
          counts[p.collection] = (counts[p.collection] || 0) + 1;
        });
        setCollectionCounts(counts);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [fuseOptions]);

  useEffect(() => {
    if (!fuseRef.current) return;

    let results = fuseRef.current.search(searchQuery);

    if (selectedCollections.length > 0) {
      results = results.filter(r => selectedCollections.includes(r.item.collection));
    }

    if (selectedModes.length > 0) {
      results = results.filter(r => selectedModes.includes(r.item.mode));
    }

    setFiltered(results.map(r => ({ item: r.item, score: r.score })));
  }, [programs, searchQuery, selectedCollections, selectedModes]);

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
        <p>Loading frequency database...</p>
        {loadProgress > 0 && (
          <p className="progress">{Math.round(loadProgress * 100)}%</p>
        )}
      </div>
    );
  }

  if (error) {
    return (
      <div className="error">
        <h2>Error loading data</h2>
        <p>{error}</p>
        <p>Make sure the data files are available at {window.location.origin}/data/presets_all.json</p>
      </div>
    );
  }

  const modes = [...new Set(programs.map(p => p.mode).filter(Boolean))].sort();

  return (
    <div className="app">
      <header className="header">
        <h1>Spooky2 Frequency Search</h1>
          <p className="subtitle">
            Search {programs.length.toLocaleString()} frequency programs from Spooky2 preset collections
          </p>
      </header>

      <main className="main">
        <aside className="sidebar">
          <FilterPanel
            collections={collectionsList}
            collectionCounts={collectionCounts}
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
          </div>
          <ResultsList
            programs={filtered}
            selected={selected}
            onSelect={handleSelectProgram}
            onClearSelection={handleClearSelection}
            isSearchPending={false}
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
              programs={programs}
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
