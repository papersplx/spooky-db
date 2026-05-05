import Fuse from 'fuse.js';

export function createSearchEngine(programs) {
  const fuse = new Fuse(programs, {
    keys: [
      { name: 'name', weight: 0.5 },
      { name: 'description', weight: 0.2 },
      { name: 'loaded_programs', weight: 0.3 },
    ],
    threshold: 0.1,  // Stricter threshold (was 0.3)
    includeMatches: true,
    includeScore: true,
    ignoreLocation: true,
    minMatchCharLength: 3,  // Ignore single/double char matches (was 2)
    sortFn: (a, b) => {
      if (a.score === 0 && b.score > 0) return -1;
      if (b.score === 0 && a.score > 0) return 1;
      return a.score - b.score;
    },
  });

  return fuse;
}

/**
 * Enhanced search with mode/type prefix detection.
 * - If mode prefix (C, R, P, etc.) in query, filter by those modes
 * - Boost name matches over description matches
 * - Filter out poor substring matches for short queries
 */
export function performSearch(programs, fuse, query, selectedCollections, selectedModes) {
  if (!fuse || !query || query.trim() === '') {
    // No search query, apply collection/mode filters only
    return programs.filter(p => {
      if (selectedCollections.length && !selectedCollections.includes(p.collection)) return false;
      if (selectedModes.length && !selectedModes.includes(p.mode)) return false;
      return true;
    }).map(p => ({ item: p, score: 0 }));
  }

  const q = query.trim().toLowerCase();

  // Detect mode keywords in query
  const modeKeywords = {
    'Contact': ['c)', '(c)', 'contact', 'cx ', ' cx', '(cx)'],
    'Remote': ['r)', '(r)', 'remote', 'rx ', ' rx', '(rx)'],
    'Plasma': ['p)', '(p)', 'plasma', 'px ', ' px', '(px)'],
    'Coil': ['m)', '(m)', 'coil', 'pemf', 'mx ', ' mx', '(mx)'],
    'Scalar': ['s)', '(s)', 'scalar', 'sx ', ' sx', '(sx)'],
    'Laser': ['l)', '(l)', 'laser', 'cold laser', 'lx ', ' lx', '(lx)'],
  };

  let forcedMode = null;
  for (const [mode, keywords] of Object.entries(modeKeywords)) {
    if (keywords.some(kw => q.includes(kw))) {
      forcedMode = mode;
      break;
    }
  }

  // Detect specific program type keywords
  const typeKeywords = {
    'preset': ['preset', 'chain', 'protocol'],
    'program': ['program', 'freq', 'hz'],
  };
  let forcedType = null;
  for (const [type, keywords] of Object.entries(typeKeywords)) {
    if (keywords.some(kw => q.includes(kw))) {
      forcedType = type;
      break;
    }
  }

  // For very short queries that look like mode prefixes, skip Fuse and filter directly
  const isModePrefix = /^[crpslm]$/i.test(q) || /^[crpslm]\)$/i.test(q);

  let results;
  if (isModePrefix && forcedMode) {
    // Direct mode filter - no Fuse needed
    results = programs
      .filter(p => {
        if (p.mode.toLowerCase() !== forcedMode.toLowerCase()) return false;
        if (selectedCollections.length && !selectedCollections.includes(p.collection)) return false;
        if (selectedModes.length && !selectedModes.includes(p.mode)) return false;
        return true;
      })
      .map(p => ({ item: p, score: 0 }));
  } else {
    // Use Fuse search
    results = fuse.search(query);

    // Apply filters
    results = results.filter(result => {
      const p = result.item;
      if (selectedCollections.length && !selectedCollections.includes(p.collection)) return false;
      if (selectedModes.length && !selectedModes.includes(p.mode)) return false;
      if (forcedMode && p.mode.toLowerCase() !== forcedMode.toLowerCase()) return false;
      if (forcedType && p.entry_type !== forcedType) return false;

      // Filter out poor matches for short queries
      if (q.length <= 2 && result.score > 0.05) return false;

      return true;
    });
  }

  // Boost results where query appears in name (higher relevance)
  results.forEach(result => {
    const name = (result.item.name || '').toLowerCase();
    const qLower = q.toLowerCase();
    if (name.startsWith(qLower)) {
      result.score = (result.score || 0) * 0.5;  // boost prefix matches
    } else if (name.includes(qLower)) {
      result.score = (result.score || 0) * 0.7;  // boost name matches
    }
  });

  // Re-sort after boosting
  results.sort((a, b) => (a.score || 0) - (b.score || 0));

  return results;
}
