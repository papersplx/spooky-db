/**
 * Parse Spooky2 frequency code string into structured tokens.
 * Mirrors the Python parser logic.
 */

// Waveform names mapping
export const WAVEFORM_NAMES = {
  0: 'Sine',
  1: 'Square',
  2: 'Triangle',
  3: 'Reverse Sawtooth',
  4: 'Sawtooth',
};

export function parseFrequencyCode(code) {
  const tokens = [];
  let current = {
    waveform: null,
    amplitude: null,
    offset: null,
    gate: null,
    factor: null,
    constant: null,
    molecular: null,
    basePairs: null,
  };

  const parts = code.split(',').map(p => p.trim()).filter(p => p);

  for (const part of parts) {
    if (!part) continue;

    // Bacon-encoded frequency (starts with ~)
    if (part.startsWith('~')) {
      tokens.push({
        type: 'bacon',
        raw: part,
        waveform: current.waveform,
        amplitude: current.amplitude,
        offset: current.offset,
        gate: current.gate,
        factor: current.factor,
        constant: current.constant,
        molecular: current.molecular,
        basePairs: current.basePairs,
      });
      continue;
    }

    // Sweep: "100-200" or "100-200=1800"
    const sweepMatch = part.match(/^(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)(?:=(\d+))?$/);
    if (sweepMatch) {
      const start = parseFloat(sweepMatch[1]);
      const end = parseFloat(sweepMatch[2]);
      const dwell = sweepMatch[3] ? parseInt(sweepMatch[3], 10) : null;
      tokens.push({
        type: 'sweep',
        freq: start,
        endFreq: end,
        dwell,
        waveform: current.waveform,
        amplitude: current.amplitude,
        offset: current.offset,
        gate: current.gate,
        factor: current.factor,
        constant: current.constant,
        molecular: current.molecular,
        basePairs: current.basePairs,
      });
      continue;
    }

    // Dwell: "300=600"
    const dwellMatch = part.match(/^(\d+(?:\.\d+)?)=(\d+)$/);
    if (dwellMatch) {
      const freq = parseFloat(dwellMatch[1]);
      const dwell = parseInt(dwellMatch[2], 10);
      tokens.push({
        type: 'frequency',
        freq,
        dwell,
        waveform: current.waveform,
        amplitude: current.amplitude,
        offset: current.offset,
        gate: current.gate,
        factor: current.factor,
        constant: current.constant,
        molecular: current.molecular,
        basePairs: current.basePairs,
      });
      continue;
    }

    // Plain frequency number (integer or decimal)
    if (/^\d+(?:\.\d+)?$/.test(part)) {
      tokens.push({
        type: 'frequency',
        freq: parseFloat(part),
        waveform: current.waveform,
        amplitude: current.amplitude,
        offset: current.offset,
        gate: current.gate,
        factor: current.factor,
        constant: current.constant,
        molecular: current.molecular,
        basePairs: current.basePairs,
      });
      continue;
    }

    // Modifier commands: Wx, Ax, Ox (or ox), Gx, Fx, Cx, Mx, Bx
    const wMatch = part.match(/^W(\d+)$/i);
    if (wMatch) {
      current.waveform = parseInt(wMatch[1], 10);
      continue;
    }

    const aMatch = part.match(/^A(\d+)$/);
    if (aMatch) {
      current.amplitude = parseInt(aMatch[1], 10);
      continue;
    }

    const oMatch = part.match(/^[Oo](-?\d+)$/);
    if (oMatch) {
      current.offset = parseInt(oMatch[1], 10);
      continue;
    }

    const gMatch = part.match(/^G([01])$/);
    if (gMatch) {
      current.gate = parseInt(gMatch[1], 10);
      continue;
    }

    const fMatch = part.match(/^F(\d+)$/i);
    if (fMatch) {
      current.factor = parseInt(fMatch[1], 10);
      continue;
    }

    const cMatch = part.match(/^C(\d+)$/i);
    if (cMatch) {
      current.constant = parseInt(cMatch[1], 10);
      continue;
    }

    const mMatch = part.match(/^M(\d+)$/i);
    if (mMatch) {
      current.molecular = parseInt(mMatch[1], 10);
      continue;
    }

    const bMatch = part.match(/^B(\d+)$/i);
    if (bMatch) {
      current.basePairs = parseInt(bMatch[1], 10);
      continue;
    }

    // Unknown token - preserve as raw
    tokens.push({
      type: 'raw',
      raw: part,
      waveform: current.waveform,
      amplitude: current.amplitude,
      offset: current.offset,
      gate: current.gate,
      factor: current.factor,
      constant: current.constant,
      molecular: current.molecular,
      basePairs: current.basePairs,
    });
  }

  return tokens;
}

/**
 * Format a frequency token into a human-readable string.
 */
export function formatToken(token) {
  const parts = [];

  if (token.type === 'sweep') {
    parts.push(`${token.freq} - ${token.endFreq} Hz`);
    if (token.dwell) parts.push(`dwell ${token.dwell}s`);
  } else if (token.type === 'frequency') {
    parts.push(`${token.freq} Hz`);
    if (token.dwell) parts.push(`dwell ${token.dwell}s`);
  } else if (token.type === 'bacon') {
    parts.push(`Encoded: ${token.raw}`);
  } else if (token.type === 'raw') {
    parts.push(token.raw);
  }

  if (token.waveform !== null && token.waveform !== undefined) {
    const name = WAVEFORM_NAMES[token.waveform] || `W${token.waveform}`;
    parts.push(name);
  }
  if (token.amplitude !== null && token.amplitude !== undefined) {
    parts.push(`${token.amplitude}V`);
  }
  if (token.offset !== null && token.offset !== undefined) {
    parts.push(`offset ${token.offset}%`);
  }
  if (token.gate !== null && token.gate !== undefined) {
    parts.push(token.gate ? 'Gate ON' : 'Gate OFF');
  }
  if (token.factor !== null) parts.push(`F${token.factor}`);
  if (token.constant !== null) parts.push(`C${token.constant}`);
  if (token.molecular !== null) parts.push(`M${token.molecular}`);
  if (token.basePairs !== null) parts.push(`B${token.basePairs}`);

  return parts.join(', ');
}

/**
 * Calculate total duration of a frequency code in seconds.
 * Uses dwell times from tokens, or defaultDwell if not specified.
 */
export function calculateDuration(tokens, defaultDwell = 180) {
  if (!tokens || tokens.length === 0) return 0;
  let total = 0;
  for (const token of tokens) {
    const dwell = token.dwell || defaultDwell;
    if (token.type === 'sweep') {
      total += dwell;
    } else if (token.type === 'frequency' || token.type === 'bacon' || token.type === 'raw') {
      total += dwell;
    }
  }
  return total;
}

/**
 * Get primary waveform from tokens (most common waveform used).
 */
export function getPrimaryWaveform(tokens) {
  const counts = {};
  tokens.forEach(t => {
    if (t.waveform !== null && t.waveform !== undefined) {
      counts[t.waveform] = (counts[t.waveform] || 0) + 1;
    }
  });
  if (Object.keys(counts).length === 0) return null;
  return parseInt(Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0], 10);
}

/**
 * Detect if program has wobble (frequency or amplitude variation).
 */
export function detectWobble(tokens) {
  if (!tokens || tokens.length < 2) return false;
  const freqs = tokens.filter(t => t.type === 'frequency' && t.freq).map(t => t.freq);
  const amplitudes = tokens.filter(t => t.amplitude !== null).map(t => t.amplitude);
  const hasFreqWobble = freqs.length >= 2 && new Set(freqs).size > 1;
  const hasAmpWobble = amplitudes.length >= 2 && new Set(amplitudes).size > 1;
  return hasFreqWobble || hasAmpWobble;
}
