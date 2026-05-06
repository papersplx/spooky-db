/**
 * Data loading utilities for presets JSON.
 */

const DATA_BASE_URL = 'https://github.com/papersplx/spooky-db/releases/download/data-v1';

/**
 * Load the combined presets data with progress tracking.
 * @param {Function} onProgress - Callback(progress) with 0-1 progress
 */
export async function loadAllPresets(onProgress) {
  const urls = [
    '/data/presets_all.json',
    `${DATA_BASE_URL}/presets_all.json`,
  ];

  let lastError;
  for (const url of urls) {
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const contentLength = response.headers.get('content-length');
      const total = contentLength ? parseInt(contentLength, 10) : 0;

      if (onProgress && total > 0 && response.body) {
        let loaded = 0;
        const reader = response.body.getReader();
        const chunks = [];

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          chunks.push(value);
          loaded += value.length;
          onProgress(loaded / total);
        }

        const blob = new Blob(chunks);
        const text = await blob.text();
        const data = JSON.parse(text);
        return data.programs;
      }

      const data = await response.json();
      return data.programs;
    } catch (error) {
      lastError = error;
      continue;
    }
  }

  console.error('Failed to load presets:', lastError);
  throw lastError;
}

/**
 * Load presets by collection (for lazy loading).
 * @param {string} collection - Collection name like "Factory/Detox/Contact"
 */
export async function loadCollectionPresets(collection) {
  const safeName = collection.replace('/', '_').replace('\\', '_');
  const response = await fetch(`/data/by_collection/${safeName}.json`);
  if (!response.ok) {
    throw new Error(`Failed to load collection ${collection}`);
  }
  const data = await response.json();
  return data.programs;
}

/**
 * Get list of available collections from the data file.
 */
export async function getCollectionsList() {
  try {
    const response = await fetch('/data/presets_all.json');
    const data = await response.json();

    // Extract unique collections
    const collections = new Set();
    for (const prog of data.programs) {
      if (prog.collection) {
        collections.add(prog.collection);
      }
    }
    return Array.from(collections).sort();
  } catch (error) {
    console.error('Failed to get collections:', error);
    return [];
  }
}
