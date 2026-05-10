import { tool } from "@kilocode/plugin";

/**
 * Categorize Spooky2 Telegram preset files into known categories.
 *
 * No LLM API calls — purely keyword-based matching with word-boundary awareness.
 * Designed to integrate with the extract_and_postprocess.py / integrate_telegram.py pipeline.
 *
 * Usage by coding agent:
 *   Import and call categorizePreset(fileContent, fileName, collectionPath)
 *   to get { category, matchMethod, matchKeyword } for each preset.
 */

// ---------------------------------------------------------------------------
// Keyword-to-Category Mapping (ordered by priority — first match wins)
// ---------------------------------------------------------------------------

const CATEGORY_KEYWORDS = [
  // [Keywords, Category] — more specific / compound entries first.
  // First match in table order wins; place more specific keywords before general ones.
  [["morgellons", "lyme"], "Morgellons & Lyme Support"],
  [["bacteria", "bacterial"], "Bacteria"],
  [["antiviral", "anti.viral", "antibacterial"], "Infection"],
  [["parasite", "worm", "protozoa"], "Parasites"],
  [["cancer", "tumor", "oncology"], "Cancer"],
  [["inflammation", "anti.inflammatory"], "Inflammation"],
  [["autoimmune", "lupus", "rheumatoid"], "Autoimmune"],
  [["allergy", "histamine", "allergen"], "Allergies"],
  [["detox", "liver", "cleanse"], "Detox"],
  [["colon", "gut", "stomach"], "Digestive System"],
  [["lung", "sinus", "breath", "respiratory"], "Respiratory System"],
  [["heart", "cardiovascular", "blood.pressure"], "Cardiovascular System"],
  [["brain", "nerve", "neural", "cognition"], "Nervous System"],
  [["musculoskeletal", "bone", "joint", "tendon"], "Musculoskeletal System"],
  [["thyroid", "adrenal", "hormone", "gland"], "Endocrine System"],
  [["kidney", "bladder", "urinary"], "Urinary System"],
  [["fertility", "reproductive"], "Reproductive System"],
  [["skin", "hair", "nail", "derm"], "Skin and Hair"],
  [["eye", "ear", "hearing", "vision"], "Eyes and Ears"],
  [["dental", "tooth", "gum"], "Dental"],
  [["anxiety", "depression", "stress", "mood"], "Mental Health"],
  [["sleep", "insomnia"], "Sleep"],
  [["wound", "injury", "surgery", "recovery"], "Injury and Recovery"],
  [["pain", "headache", "migraine"], "Pain Management"],
  [["scalar.energy", "scalar"], "Scalar"],
  [["energy", "fatigue", "vitality", "stamina", "mitochondria"], "Energy and Fatigue"],
  [["athletic", "performance", "focus", "peak"], "Performance"],
  [["meditation", "mindfulness", "relaxation"], "Meditation"],
  [["emotional", "trauma", "relationship"], "Emotional"],
  [["spiritual", "chakra", "energy.work"], "Spiritual"],
  [["emf", "shielding", "grounding"], "Protection"],
  [["biofeedback", "scenar"], "Biofeedback"],
  [["zapper", "beck", "microcurrent"], "Zapper"],
  [["rife", "rife.frequency"], "Rife"],
  [["immune", "immunity", "immun"], "Immune System"],
  [["blood.sugar", "anemia", "clot", "hematology"], "Blood"],
  [["lymph", "lymphatic"], "Lymphatic System"],
  [["cortisol", "estrogen", "testosterone"], "Hormones"],
  [["candida", "fungal", "fungi", "mold"], "Fungi"],
  [["hiv", "aids"], "HIV/AIDS"],
  [["malaria"], "Malaria"],
  [["generatorx", "generator x"], "GeneratorX"],
  [["sample.digitizer", "sample digitizer"], "Sample Digitizer"],
  [["spooky.pulse", "spookypulse"], "Spooky Pulse"],
  [["virus"], "Viruses"],
];

// Directories that imply a category from the collection path
const COLLECTION_CATEGORY_HINTS = {
  detox: "Detox",
  immune: "Immune System",
  digestive: "Digestive System",
  respiratory: "Respiratory System",
  cardiovascular: "Cardiovascular System",
  nervous: "Nervous System",
  musculoskeletal: "Musculoskeletal System",
  endocrine: "Endocrine System",
  urinary: "Urinary System",
  reproductive: "Reproductive System",
  skin: "Skin and Hair",
  dental: "Dental",
  mental: "Mental Health",
  sleep: "Sleep",
  energy: "Energy and Fatigue",
  pain: "Pain Management",
  inflammation: "Inflammation",
  infection: "Infection",
  parasites: "Parasites",
  bacteria: "Bacteria",
  viruses: "Viruses",
  fungi: "Fungi",
  cancer: "Cancer",
  blood: "Blood",
  lymphatic: "Lymphatic System",
  hormones: "Hormones",
  allergies: "Allergies",
  autoimmune: "Autoimmune",
  injury: "Injury and Recovery",
  performance: "Performance",
  meditation: "Meditation",
  emotional: "Emotional",
  spiritual: "Spiritual",
  protection: "Protection",
  scalar: "Scalar",
  biofeedback: "Biofeedback",
  zapper: "Zapper",
  rife: "Rife",
};

const KNOWN_MODES = new Set(["Contact", "Remote", "Plasma", "Coil", "Scalar", "Laser", "Other"]);

// ---------------------------------------------------------------------------
// Parsing helpers
// ---------------------------------------------------------------------------

/**
 * Build a word-boundary regex for a keyword.
 * Dotted keywords like "blood.pressure" match with flexible non-word separators.
 */
function buildKeywordRegex(keyword) {
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const parts = escaped.split("\\.");
  if (parts.length === 1) {
    return new RegExp(`\\b${parts[0]}\\b`, "i");
  }
  // Multi-part: allow any non-word chars between parts (spaces, hyphens, etc.)
  const pattern = parts.map(p => `\\b${p}\\b`).join("\\W+");
  return new RegExp(`\\b${pattern}\\b`, "i");
}

/**
 * Test normalized text variants to handle hyphenated forms.
 * "anti-viral" should match "antiviral", "blood-pressure" should match "blood.pressure".
 */
function matchAnywhere(text, regex) {
  if (!text) return false;
  // Try with hyphens → spaces (handles "blood-pressure" → "blood pressure")
  if (regex.test(text.replace(/[-–—]/g, " "))) return true;
  // Try with hyphens removed (handles "anti-viral" → "antiviral")
  if (regex.test(text.replace(/[-–—]/g, ""))) return true;
  return false;
}

/**
 * Extract the preset name from raw file content.
 * Returns the name string or null.
 */
function extractName(content, fileName) {
  // Modern format: PresetName="..."
  const presetNameMatch = content.match(/PresetName\s*=\s*"([^"]+)"/i);
  if (presetNameMatch && presetNameMatch[1].trim()) {
    return presetNameMatch[1].trim();
  }

  // Legacy format: List2="..." (if short enough to be a name)
  const list2Match = content.match(/List2\s*=\s*"([^"]+)"/i);
  if (list2Match) {
    const val = list2Match[1].trim();
    if (val.length < 120 && !val.includes("=")) {
      // First line/paragraph only
      const firstLine = val.split("\n")[0].trim();
      if (firstLine.length > 0 && firstLine.length < 100) {
        return firstLine;
      }
    }
  }

  // CustomName field
  const customNameMatch = content.match(/CustomName\s*=\s*"([^"]+)"/i);
  if (customNameMatch && customNameMatch[1].trim()) {
    return customNameMatch[1].trim();
  }

  // Fall back to filename stem
  const stem = fileName.replace(/\.[^.]+$/, "").replace(/_/g, " ");
  return stem;
}

/**
 * Extract the description from raw file content.
 */
function extractDescription(content) {
  // Modern: Preset_Notes or CustomName
  const notesMatch = content.match(/Preset_Notes\s*=\s*"((?:[^"\\]|\\.)*)"/i);
  if (notesMatch && notesMatch[1].trim()) {
    return notesMatch[1].trim();
  }

  // Legacy: full List2 value (used as description when too long for a name)
  const list2Match = content.match(/List2\s*=\s*"((?:[^"\\]|\\.)*)"/i);
  if (list2Match) {
    return list2Match[1].trim();
  }

  return "";
}

/**
 * Extract the raw frequency code from file content.
 */
function extractFrequencyCode(content) {
  // Modern: Loaded_Frequencies
  const freqMatch = content.match(/Loaded_Frequencies\s*=\s*"((?:[^"\\]|\\.)*)"/i);
  if (freqMatch && freqMatch[1].trim()) {
    return freqMatch[1].trim();
  }

  // Legacy: List4
  const list4Match = content.match(/List4\s*=\s*"((?:[^"\\]|\\.)*)"/i);
  if (list4Match) {
    return list4Match[1].trim();
  }

  return "";
}

// ---------------------------------------------------------------------------
// Core categorization
// ---------------------------------------------------------------------------

/**
 * Search text for keyword matches from the category mapping table.
 * Returns the first matching { category, keyword } or null.
 */
function findCategoryMatch(text) {
  if (!text) return null;
  for (const [keywords, category] of CATEGORY_KEYWORDS) {
    for (const keyword of keywords) {
      const regex = buildKeywordRegex(keyword);
      if (matchAnywhere(text, regex)) {
        return { category, matchKeyword: keyword };
      }
    }
  }
  return null;
}

/**
 * Categorize a preset from its raw content, filename, and collection path.
 *
 * @param {string} content - Raw text content of the .txt preset file
 * @param {string} fileName - Filename (used for name extraction)
 * @param {string} collectionPath - Collection path like "Proven/Contact" or "Unproven/Remote"
 * @returns {{ category: string|null, matchMethod: string|null, matchKeyword: string|null }}
 */
function categorizePreset(content, fileName, collectionPath) {
  const name = extractName(content, fileName);
  const description = extractDescription(content);
  const code = extractFrequencyCode(content);

  // Step 1: Name matching
  if (name) {
    const result = findCategoryMatch(name);
    if (result) {
      return { ...result, matchMethod: "name" };
    }
  }

  // Step 2: Description matching
  if (description) {
    const result = findCategoryMatch(description);
    if (result) {
      return { ...result, matchMethod: "description" };
    }
  }

  // Step 3: Frequency code matching
  if (code) {
    const result = findCategoryMatch(code);
    if (result) {
      return { ...result, matchMethod: "frequency_code" };
    }
  }

  // Step 4: Raw content matching (fallback for plain text or unrecognized formats)
  if (content) {
    const result = findCategoryMatch(content);
    if (result) {
      return { ...result, matchMethod: "content" };
    }
  }

  // Step 5: Collection path hint (soft fallback)
  if (collectionPath) {
    const pathLower = collectionPath.toLowerCase();
    for (const [dir, cat] of Object.entries(COLLECTION_CATEGORY_HINTS)) {
      if (pathLower.includes(dir.toLowerCase())) {
        return { category: cat, matchMethod: "collection_path", matchKeyword: dir };
      }
    }
  }

  // Step 6: No match
  return { category: null, matchMethod: null, matchKeyword: null };
}

// ---------------------------------------------------------------------------
// Batch processing for pipeline integration
// ---------------------------------------------------------------------------

/**
 * Categorize multiple programs from presets_all.json.
 * Only processes programs where category is null or empty.
 *
 * @param {Array} programs - Array of program objects from presets_all.json
 * @returns {{ categorized: number, results: Array, report: Array }}
 */
function categorizeAllPrograms(programs) {
  let categorized = 0;
  const report = [];

  const updated = programs.map(prog => {
    if (prog.category) {
      // Already categorized
      report.push({
        name: prog.name,
        id: prog.id,
        category: prog.category,
        status: "already_categorized",
        matchMethod: null,
        matchKeyword: null,
      });
      return prog;
    }

    const result = categorizePreset(prog.code || "", prog.preset_file || "", prog.collection || "");
    if (result.category) categorized++;

    report.push({
      name: prog.name,
      id: prog.id,
      category: result.category,
      status: result.category ? "categorized" : "uncategorized",
      matchMethod: result.matchMethod,
      matchKeyword: result.matchKeyword,
    });

    return { ...prog, category: result.category };
  });

  return { categorized, programs: updated, report };
}

// ---------------------------------------------------------------------------
// Kilo tool definition
// ---------------------------------------------------------------------------

export default {
  name: "categorize-presets",
  description: "Categorize Spooky2 presets from Telegram into known collection categories (Detox, Bacteria, Viruses, etc.) using keyword-based matching.",

  tool: {
    categorize: tool({
      description: "Categorize a Spooky2 preset file by analyzing its name, description, and frequency code for known category keywords. Returns the category, match method, and matched keyword.",
      args: {
        content: tool.schema.string().describe("Raw text content of the .txt preset file"),
        fileName: tool.schema.string().default("").describe("Filename of the preset file"),
        collectionPath: tool.schema.string().default("").describe("Collection path e.g. 'Proven/Contact' or 'Unproven/Remote'"),
      },
      async execute(args) {
        const result = categorizePreset(args.content, args.fileName, args.collectionPath);
        return JSON.stringify(result);
      },
    }),

    batchCategorize: tool({
      description: "Categorize all uncategorized programs in presets_all.json. Processes each program's code, name, and collection fields.",
      args: {
        programsJson: tool.schema.string().describe("JSON string of the programs array from presets_all.json"),
      },
      async execute(args) {
        const programs = JSON.parse(args.programsJson);
        const result = categorizeAllPrograms(Array.isArray(programs) ? programs : programs.programs || []);
        return JSON.stringify({
          categorized: result.categorized,
          total: result.programs.length,
          report: result.report,
        });
      },
    }),
  },
};