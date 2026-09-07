import { useState, useEffect } from 'react';
import './HelpPage.css';

function HelpPage() {
  const [manifest, setManifest] = useState(null);
  const [error, setError] = useState(null);
  const [copiedFile, setCopiedFile] = useState(null);

  useEffect(() => {
    const manifestUrl = import.meta.env.BASE_URL + 'data/notebooklm-manifest.json';
    fetch(manifestUrl)
      .then(r => { if (!r.ok) throw new Error('Failed to load manifest'); return r.json(); })
      .then(setManifest)
      .catch(err => setError(err.message));
  }, []);

  const handleCopyPath = async (file) => {
    const path = `downloads/notebooklm/${file}`;
    await navigator.clipboard.writeText(path);
    setCopiedFile(file);
    setTimeout(() => setCopiedFile(null), 2000);
  };

  // Check if manifest might be stale (has categories but no URLs)
  const hasPendingUploads = manifest?.categories?.length > 0 && 
    manifest.categories.every(c => !c.download_url);

  if (error) {
    return (
      <div className="help-page">
        <h1>NotebookLM Setup Guide</h1>
        <div className="error-box">
          <p>Could not load download manifest: {error}</p>
          <p>Please run <code>python3 scripts/prepare_notebooklm_uploads.py</code> first.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="help-page">
      <header className="help-header">
        <h1>NotebookLM Setup Guide</h1>
        <p className="help-intro">
          Use Google's NotebookLM AI assistant to research Spooky2 frequency presets.
          Upload the preset files below as sources and ask questions about frequencies,
          programs, and treatment protocols.
        </p>
      </header>

      <section className="help-section">
        <h2>What is NotebookLM?</h2>
        <p>
          <a href="https://notebooklm.google.com" target="_blank" rel="noopener noreferrer">
            NotebookLM
          </a> is Google's AI-powered research tool. You upload documents (PDFs, text files, JSON, etc.)
          and it creates a knowledge base you can query with natural language questions.
        </p>
      </section>

      <section className="help-section">
        <h2>Setup Instructions</h2>
        <ol className="setup-steps">
          <li>
            <strong>Go to NotebookLM:</strong> Visit{' '}
            <a href="https://notebooklm.google.com" target="_blank" rel="noopener noreferrer">
              notebooklm.google.com
            </a> and sign in with your Google account.
          </li>
          <li>
            <strong>Create a new notebook:</strong> Click "New Notebook" to start fresh.
          </li>
          <li>
            <strong>Download preset files:</strong> Use the download links below to get the
            preset categories you're interested in.
          </li>
          <li>
            <strong>Upload as sources:</strong> In NotebookLM, click "Add Source" and upload
            the JSON files you downloaded.
          </li>
          <li>
            <strong>Start asking questions:</strong> Once uploaded, ask NotebookLM anything:
            <ul>
              <li>"What frequencies are used for detox?"</li>
              <li>"List all cancer-related programs with their dwell times"</li>
              <li>"Compare the DNA Bacteria and DNA Viruses presets"</li>
            </ul>
          </li>
        </ol>
      </section>

      <section className="help-section">
        <h2>Download Presets by Category</h2>
        <p className="section-note">
          Files are organized by category. Each is under 200MB (NotebookLM's limit).
          Download all or just the categories relevant to your research.
        </p>

        {hasPendingUploads && (
          <div className="warning-box">
            <strong>⚠️ Download URLs not configured yet</strong>
            <p>
              The preset files have been generated but upload links are missing.
              Run <code>python3 scripts/prepare_notebooklm_uploads.py</code> to regenerate,
              then upload the files from <code>downloads/notebooklm/</code> to your file host
              and update the <code>download_url</code> fields in <code>notebooklm-manifest.json</code>.
            </p>
          </div>
        )}

        {manifest === null ? (
          <div className="skeleton-grid">
            {[1, 2, 3, 4, 5, 6].map(i => (
              <div key={i} className="skeleton-card">
                <div className="skeleton-header">
                  <div className="skeleton-title"></div>
                  <div className="skeleton-size"></div>
                </div>
                <div className="skeleton-meta">
                  <div className="skeleton-line"></div>
                  <div className="skeleton-line short"></div>
                </div>
                <div className="skeleton-btn"></div>
              </div>
            ))}
          </div>
        ) : manifest.categories.length === 0 ? (
          <div className="empty-state">
            <p>No download files generated yet.</p>
            <p>Run <code>python3 scripts/prepare_notebooklm_uploads.py</code> to generate them.</p>
          </div>
        ) : (
          <div className="download-grid">
            {manifest.categories.map(cat => (
              <div key={cat.file} className="download-card">
                <div className="card-header">
                  <h3>{cat.name}</h3>
                  <span className="file-size">{cat.size_mb} MB</span>
                </div>
                <div className="card-meta">
                  <span>{cat.program_count.toLocaleString()} programs</span>
                  <span>{cat.source_files.length} source files</span>
                </div>
                {cat.download_url ? (
                  <a
                    href={cat.download_url}
                    className="download-btn"
                    target="_blank"
                    rel="noopener noreferrer"
                    download
                  >
                    Download {cat.file}
                  </a>
                ) : (
                  <div className="pending-badge">
                    <span>Upload pending</span>
                    <button
                      className={`copy-path-btn ${copiedFile === cat.file ? 'copied' : ''}`}
                      onClick={() => handleCopyPath(cat.file)}
                      title="Copy file path"
                    >
                      {copiedFile === cat.file ? '✓ Copied!' : '📋 Copy path'}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="help-section">
        <h2>Tips for Querying NotebookLM</h2>
        <ul className="tips-list">
          <li>Ask for specific frequency values: "What Hz frequencies are in the Detox category?"</li>
          <li>Request comparisons: "Compare dwell times between Cancer and Healing programs"</li>
          <li>Get summaries: "Summarize the JW Peptides collection"</li>
          <li>Find patterns: "Which programs use square waveform (W1)?"</li>
          <li>Cross-reference: "Which frequencies appear in both DNA_Bacteria and DNA_Viruses?"</li>
        </ul>
      </section>

      <section className="help-section">
        <h2>Data Format</h2>
        <p>
          Each JSON file contains an array of program objects with fields:{' '}
          <code>name</code>, <code>description</code>, <code>code</code>, <code>frequencies</code>,{' '}
          <code>collection</code>, <code>mode</code>, and more.
          NotebookLM will index all these fields for natural language search.
        </p>
      </section>
    </div>
  );
}

export default HelpPage;
