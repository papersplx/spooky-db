import { useState, useEffect, useRef } from 'react';
import SearchBox from './components/SearchBox';
import FilterPanel from './components/FilterPanel';
import ResultsList from './components/ResultsList';
import ProgramDetail from './components/ProgramDetail';
import { searchPrograms, getProgram, getCollections, getTelegramUpdates } from './data/loader';
import './App.css';

function getStateFromURL() {
  const params = new URLSearchParams(window.location.search);
  const state = {
    searchQuery: params.get('q') || 'Longevity',
    selectedModes: params.getAll('mode').length > 0 ? params.getAll('mode') : ['Remote'],
    selectedCollections: params.getAll('collection'),
    selectedCategories: params.getAll('category'),
    selectedSources: params.getAll('source'),
    selectedProgramId: params.get('program') || null,
    page: parseInt(params.get('page') || 1),
  };
  return state;
}

function App() {
  const initialState = getStateFromURL();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [searchQuery, setSearchQuery] = useState(initialState.searchQuery);
  const [selectedCollections, setSelectedCollections] = useState(initialState.selectedCollections);
  const [selectedModes, setSelectedModes] = useState(initialState.selectedModes);
  const [selectedCategories, setSelectedCategories] = useState(initialState.selectedCategories || []);
  const [selectedSources, setSelectedSources] = useState(initialState.selectedSources || []);
  const [collectionsList, setCollectionsList] = useState([]);
  const [collectionCounts, setCollectionCounts] = useState({});
  const [modesList, setModesList] = useState([]);
  const [totalResults, setTotalResults] = useState(0);
  const [isSearchPending, setIsSearchPending] = useState(false);
  const [totalPrograms, setTotalPrograms] = useState(0);
  const [currentPage, setCurrentPage] = useState(initialState.page);
  const [telegramUpdates, setTelegramUpdates] = useState(null);

  const searchParamsRef = useRef({});
  const abortControllerRef = useRef(null);
  const searchBoxRef = useRef(null);

  const pageSize = 20;
  const CACHE_TTL = 7 * 24 * 60 * 60 * 1000; // 1 week in ms

  const getCacheKey = (query, modes, collections, sources, page) => {
    return JSON.stringify({ q: query, modes, collections, sources, page });
  };

  const getCachedResults = (key) => {
    try {
      const cached = localStorage.getItem(`search_cache_${key}`);
      if (!cached) return null;
      const data = JSON.parse(cached);
      if (Date.now() - data.timestamp > CACHE_TTL) {
        localStorage.removeItem(`search_cache_${key}`);
        return null;
      }
      return data;
    } catch {
      return null;
    }
  };

  const setCachedResults = (key, results, total) => {
    try {
      localStorage.setItem(`search_cache_${key}`, JSON.stringify({
        results,
        total,
        timestamp: Date.now()
      }));
    } catch (e) {
      console.warn('Cache write failed:', e);
    }
  };

  const [filtered, setFiltered] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await getCollections();
        // Handle both old format (array) and new format ({collections, sources})
        const collections = Array.isArray(data) ? data : (data.collections || []);
        const counts = {};
        const names = new Set();
        const modes = new Set();
        let total = 0;
        collections.forEach(({ collection, count, mode }) => {
          names.add(collection);
          counts[collection] = (counts[collection] || 0) + parseInt(count);
          if (mode) modes.add(mode);
          total += parseInt(count);
        });
        setCollectionsList([...names].sort());
        setCollectionCounts(counts);
        setModesList([...modes].sort());
        setTotalPrograms(total);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  fetchData();
}, []);

  useEffect(() => {
    const fetchTelegramUpdates = async () => {
      try {
        const updates = await getTelegramUpdates();
        setTelegramUpdates(updates);
      } catch {
        // Silently ignore — timestamps are informational
      }
    };
    fetchTelegramUpdates();
  }, []);

  useEffect(() => {
    const loadProgram = async () => {
      if (initialState.selectedProgramId) {
        try {
          const program = await getProgram(initialState.selectedProgramId);
          setSelected(program);
        } catch (err) {
          console.error('Failed to load program from URL:', err);
        }
      }
    };
    loadProgram();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const cacheKey = getCacheKey(searchQuery, selectedModes, selectedCollections, selectedSources, currentPage);
    const cached = getCachedResults(cacheKey);

    if (cached) {
      setFiltered(cached.results);
      setTotalResults(cached.total);
      setIsSearchPending(false);
      return;
    }

     const doSearch = async () => {
       setIsSearchPending(true);
       try {
         // Map UI source labels to API source/tag filters
         const sourceSet = new Set();
         const tagSet = new Set();
         selectedSources.forEach(s => {
           switch (s) {
             case 'Database':
               sourceSet.add('wine');
               break;
             case 'Telegram':
               sourceSet.add('telegram');
               break;
             case 'Proven':
               sourceSet.add('telegram');
               tagSet.add('Proven');
               break;
             case 'Unproven':
               sourceSet.add('telegram');
               tagSet.add('Unproven');
               break;
           }
         });
         const apiSource = Array.from(sourceSet);
         const apiTag = Array.from(tagSet);

         const result = await searchPrograms({
           q: searchQuery,
           mode: selectedModes,
           collection: selectedCollections,
           source: apiSource,
           tag: apiTag,
           limit: pageSize,
           offset: (currentPage - 1) * pageSize,
         }, controller.signal);
         const results = result.results || [];
         setCachedResults(cacheKey, results, result.total || 0);
         setFiltered(results);
         setTotalResults(result.total || 0);
       } catch (err) {
         if (err.name !== 'AbortError') {
           console.error('Search failed:', err);
           setFiltered([]);
         }
       } finally {
         setIsSearchPending(false);
       }
     };

    doSearch();

    return () => {
      controller.abort();
    };
  }, [searchQuery, selectedModes, selectedCollections, selectedSources, currentPage]);

  const handleSearch = (query) => {
    setSearchQuery(query);
    setCurrentPage(1);
    updateURL({ searchQuery: query, selectedModes, selectedCollections, selectedSources, selectedProgramId: null, page: 1 });
  };

  const handleSelectCollection = (collection) => {
    setSelectedCollections(prev => {
      const next = prev.includes(collection)
        ? prev.filter(c => c !== collection)
        : [...prev, collection];
      setCurrentPage(1);
      updateURL({ searchQuery, selectedModes, selectedCollections: next, selectedSources, selectedProgramId: selected?.id || null, page: 1 });
      return next;
    });
  };

  const handleSelectMode = (mode) => {
    setSelectedModes(prev => {
      const next = prev.includes(mode)
        ? prev.filter(m => m !== mode)
        : [...prev, mode];
      setCurrentPage(1);
      updateURL({ searchQuery, selectedModes: next, selectedCollections, selectedSources, selectedProgramId: selected?.id || null, page: 1 });
      return next;
    });
  };

  const handleSelectSource = (source) => {
    setSelectedSources(prev => {
      const next = prev.includes(source)
        ? prev.filter(s => s !== source)
        : [...prev, source];
      setCurrentPage(1);
      updateURL({ searchQuery, selectedModes, selectedCollections, selectedSources: next, selectedProgramId: selected?.id || null, page: 1 });
      return next;
    });
  };

  const handleSelectProgram = async (program) => {
    // Update URL immediately for back/forward navigation
    updateURL({ searchQuery, selectedModes, selectedCollections, selectedSources, selectedProgramId: program.id, page: currentPage });
    // Fetch full program details (including loaded_programs, frequencies, code) for the detail pane
    try {
      const full = await getProgram(program.id);
      setSelected(full);
    } catch (err) {
      console.error('Failed to load program details:', err);
      // Fall back to the partial program from search results
      setSelected(program);
    }
  };

  const handleSearchForProgram = (programName) => {
    setSearchQuery(programName);
    setSelected(null);
    setCurrentPage(1);
    updateURL({ searchQuery: programName, selectedModes, selectedCollections, selectedSources, selectedProgramId: null, page: 1 });
  };

  const handleClearSelection = () => {
    setSelected(null);
    updateURL({ searchQuery, selectedModes, selectedCollections, selectedSources, selectedProgramId: null, page: currentPage });
  };

  const handleClearFilters = () => {
    setSelectedCollections([]);
    setSelectedModes([]);
    setSelectedSources([]);
    setCurrentPage(1);
    updateURL({ searchQuery, selectedModes: [], selectedCollections: [], selectedSources: [], selectedProgramId: null, page: 1 });
  };

  const handlePageChange = (newPage) => {
    if (searchBoxRef.current) {
      searchBoxRef.current.cancelDebounce();
    }
    setCurrentPage(newPage);
    updateURL({ searchQuery, selectedModes, selectedCollections, selectedSources, selectedProgramId: selected?.id || null, page: newPage });
  };

  function updateURL(state) {
    const params = new URLSearchParams();
    if (state.searchQuery && state.searchQuery !== 'Longevity') params.set('q', state.searchQuery);
    (state.selectedModes || []).forEach(m => params.append('mode', m));
    (state.selectedCollections || []).forEach(c => params.append('collection', c));
    (state.selectedCategories || []).forEach(c => params.append('category', c));
    (state.selectedSources || []).forEach(s => params.append('source', s));
    if (state.selectedProgramId) params.set('program', state.selectedProgramId);
    if (state.page && state.page !== 1) params.set('page', state.page);
    const newURL = params.toString() ? `${window.location.pathname}?${params.toString()}` : window.location.pathname;
    window.history.pushState(state, '', newURL);
  }

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
        <p>Loading...</p>
        <p style={{ fontSize: '0.9em', color: '#666', marginTop: '0.5rem' }}>
          Initial queries can take up to 60 seconds to warm up the server.
        </p>
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
              sources={['Database', 'Telegram', 'Proven', 'Unproven']}
              selectedSources={selectedSources}
              onToggleSource={handleSelectSource}
              onClearFilters={handleClearFilters}
            />
        </aside>

          <section className="search-results">
            <SearchBox ref={searchBoxRef} query={searchQuery} onSearch={handleSearch} />
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
        {telegramUpdates && (
          <div className="telegram-updates">
            <strong>Last updated:</strong>
            {(() => {
              const entries = Object.entries(telegramUpdates).filter(([, ts]) => ts);
              if (entries.length === 0) {
                return <div style={{ marginTop: '2px', fontStyle: 'italic', color: 'var(--text-secondary)' }}>No data available</div>;
              }
               return entries.map(([source, ts]) => {
                 const date = new Date(ts);
                 const formatted = date.toLocaleDateString('en-US', {
                   year: 'numeric',
                   month: 'short',
                   day: 'numeric',
                 });
                 // Use friendly labels for known sources
                 let label;
                 switch (source) {
                   case 'Spooky2_PROVEN_FILES':
                     label = 'Proven (telegram)';
                     break;
                   case 'Spooky2_Unproven':
                     label = 'Unproven (telegram)';
                     break;
                   default:
                     // For .exe files: strip extension and date suffix, replace underscores with spaces
                     // e.g., "Spooky2_Presets_20260422.exe" -> "Spooky2 Presets"
                     let cleaned = source.replace(/\.exe$/i, '');
                     cleaned = cleaned.replace(/_\d{8,}$/, ''); // Remove trailing _YYYYMMDD date
                     label = cleaned.replace(/_/g, ' ');
                 }
                 return (
                   <div key={source} style={{ marginTop: '2px' }}>
                     {label}: {formatted}
                   </div>
                 );
               });
            })()}
          </div>
        )}
      </footer>
    </div>
  );
}

export default App;
