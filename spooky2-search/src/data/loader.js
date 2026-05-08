/**
 * Data loading utilities for presets JSON.
 * Uses Render API for search to avoid large JSON and CORS issues.
 */

const API_BASE = 'https://spooky-db.onrender.com';

/**
 * Load programs via API.
 */
export async function loadAllPresets(onProgress) {
  if (onProgress) onProgress(0.5);
  try {
    const response = await fetch(`${API_BASE}/search?limit=50000`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const results = await response.json();
    if (onProgress) onProgress(1);
    return results;
  } catch (error) {
    console.error('Failed to load presets from API:', error);
    throw error;
  }
}

/**
 * Search programs via API.
 * Returns { results: [...], total: N }
 */
export async function searchPrograms({ q = '', mode = [], collection = [], limit = 100, offset = 0 } = {}, signal) {
  const params = new URLSearchParams();
  if (q) params.append('q', q);
  if (mode.length > 0) mode.forEach(m => params.append('mode', m));
  if (collection.length > 0) collection.forEach(c => params.append('collection', c));
  params.append('limit', limit);
  params.append('offset', offset);

  const response = await fetch(`${API_BASE}/search?${params.toString()}`, { signal });
  if (!response.ok) {
    throw new Error(`Search failed: ${response.status}`);
  }
  return response.json();
}

/**
 * Get a single program by ID.
 */
export async function getProgram(id) {
  const response = await fetch(`${API_BASE}/program?id=${encodeURIComponent(id)}`);
  if (!response.ok) {
    throw new Error(`Failed to load program: ${response.status}`);
  }
  return response.json();
}

/**
 * Get all collections with counts.
 */
export async function getCollections() {
  const response = await fetch(`${API_BASE}/collections`);
  if (!response.ok) {
    throw new Error(`Failed to load collections: ${response.status}`);
  }
  return response.json();
}
