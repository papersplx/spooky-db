import { useMemo } from 'react';
import { calculateDuration, getPrimaryWaveform, detectWobble, WAVEFORM_NAMES } from '../utils/frequencyParser';
import './ProgramDetail.css';

function ProgramDetail({ program, onClose, onSearchProgram }) {

  const loadedProgramsList = useMemo(() => {
    if (!program.loaded_programs) return [];
    return program.loaded_programs
      .split(',')
      .map(p => p.trim())
      .filter(p => p);
  }, [program.loaded_programs]);

  const programDuration = useMemo(() => {
    if (!program.frequencies || program.frequencies.length === 0) return null;
    return calculateDuration(program.frequencies, program.default_dwell);
  }, [program.frequencies, program.default_dwell]);

  const primaryWaveform = useMemo(() => {
    if (!program.frequencies || program.frequencies.length === 0) return null;
    return getPrimaryWaveform(program.frequencies);
  }, [program.frequencies]);

  const hasWobble = useMemo(() => {
    if (!program.frequencies || program.frequencies.length === 0) return false;
    return detectWobble(program.frequencies);
  }, [program.frequencies]);

  const chainDurations = useMemo(() => {
    if (program.entry_type !== 'preset' || !program.frequencies) return [];
    return program.frequencies.map(f => calculateDuration([f], program.default_dwell));
  }, [program.frequencies, program.default_dwell, program.entry_type]);

  const totalChainDuration = useMemo(() => {
    if (chainDurations.length === 0) return null;
    return chainDurations.reduce((sum, d) => sum + d, 0);
  }, [chainDurations]);

  const formatDuration = (secs) => {
    if (!secs || secs === 0) return null;
    const mins = Math.floor(secs / 60);
    const s = secs % 60;
    if (mins === 0) return `${s}s`;
    return s > 0 ? `${mins}m ${s}s` : `${mins}m`;
  };

  return (
    <div className="program-detail">
      <div className="detail-header">
        <h2>{program.name}</h2>
        <button className="close-btn" onClick={onClose} aria-label="Close">
          ×
        </button>
      </div>

      <div className="detail-meta">
        <div className="meta-tags">
          <span className="tag collection">{program.collection}</span>
          {program.mode && !program.collection.toLowerCase().includes(program.mode.toLowerCase()) && (
            <span className="tag mode">{program.mode}</span>
          )}
          {program.category && <span className="tag category">{program.category}</span>}
          <span className="tag type">{program.entry_type}</span>
          {primaryWaveform !== null && (
            <span className="tag waveform-tag">
              {WAVEFORM_NAMES[primaryWaveform] || `W${primaryWaveform}`}
            </span>
          )}
          {hasWobble && <span className="tag wobble-tag">Wobble</span>}
        </div>
      </div>

      {program.description && (
        <div className="detail-description">
          <h4>Description</h4>
          <p>{program.description}</p>
        </div>
      )}

      {program.entry_type === 'preset' && loadedProgramsList.length > 0 ? (
        <div className="loaded-programs-chain">
          <div className="chain-header">
            <h4>Program Chain ({loadedProgramsList.length})</h4>
            {totalChainDuration && (
              <span className="chain-duration">
                Total: {formatDuration(totalChainDuration)}
              </span>
            )}
          </div>
          <div className="chain-list">
            {loadedProgramsList.map((progName, idx) => (
              <div
                key={idx}
                className="chain-item"
                onClick={() => onSearchProgram(progName)}
                title="Click to search for presets containing this program"
              >
                <span className="chain-index">{idx + 1}.</span>
                <span className="chain-name">{progName}</span>
                {chainDurations[idx] && (
                  <span className="chain-duration">
                    {formatDuration(chainDurations[idx])}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : program.code ? (
        <div className="program-info">
          {programDuration && (
            <div className="info-row">
              <span className="info-label">Duration:</span>
              <span className="info-value">{formatDuration(programDuration)}</span>
            </div>
          )}
          {primaryWaveform !== null && (
            <div className="info-row">
              <span className="info-label">Waveform:</span>
              <span className="info-value">
                {WAVEFORM_NAMES[primaryWaveform] || `W${primaryWaveform}`}
              </span>
            </div>
          )}
          {hasWobble && (
            <div className="info-row">
              <span className="info-value wobble-badge">Frequency/Amplitude Wobble Detected</span>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

export default ProgramDetail;
