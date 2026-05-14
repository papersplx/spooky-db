# Skill: Categorize Spooky2 Presets

Apply this skill when new Spooky2 preset `.txt` files are added to the dataset
and need to be assigned a **category** (the `category` field in the program JSON).

This is a **manual/rule-based** categorizer — no LLM API calls.

---

## Input

- A directory of `.txt` preset files (e.g. `data/presets/telegram_raw/`)
- Each file may be in one of two formats:
  - **Legacy**: `List2="description"` / `List4="frequency code"` lines
  - **Modern**: `[Preset]` sections with `"PresetName=..."` and `"Preset_Notes=..."` lines

## Output

- Each preset gets a `category` field assigned from the known category list below
- If a preset cannot be categorized, leave `category` as `null` or empty string
- Write results to a JSON report: `categorization_results.json`

## Known Categories (34)

```
Detox, Immune System, Digestive System, Respiratory System,
Cardiovascular System, Nervous System, Musculoskeletal System,
Endocrine System, Urinary System, Reproductive System,
Skin and Hair, Eyes and Ears, Dental, Mental Health,
Sleep, Energy and Fatigue, Pain Management, Inflammation,
Infection, Parasites, Bacteria, Viruses, Fungi,
Cancer, Blood, Lymphatic System, Hormones,
Allergies, Autoimmune, Injury and Recovery, Performance,
Meditation, Emotional, Spiritual, Protection,
Scalar, Biofeedback, Zapper, Rife
```

## Categorization Rules

### Step 1: Check the preset name for keyword matches

Match the **lowercase preset name** against these keyword-to-category hints.
Check for the keyword as a standalone word (not as a substring like "cancer" in "dancer"):

| Keyword(s)                  | Category                  |
|-----------------------------|---------------------------|
| detox, liver, cleanse       | Detox                     |
| colon, gut, stomach         | Digestive System          |
| lung, sinus, breath         | Respiratory System        |
| heart, blood pressure       | Cardiovascular System     |
| brain, nerve, neural, cognition | Nervous System         |
| bone, joint, muscle, tendon | Musculoskeletal System    |
| thyroid, adrenal, hormone, gland | Endocrine System     |
| kidney, bladder, urinary    | Urinary System            |
| fertility, reproductive     | Reproductive System       |
| skin, hair, nail, derm      | Skin and Hair             |
| eye, ear, hearing, vision   | Eyes and Ears             |
| dental, tooth, gum          | Dental                    |
| anxiety, depression, stress, mood | Mental Health        |
| sleep, insomnia             | Sleep                     |
| energy, fatigue, vitality, stamina, mitochondria | Energy and Fatigue |
| pain, headache, migraine    | Pain Management           |
| inflammation, anti-inflam   | Inflammation              |
| antiviral, antibacterial    | Infection                 |
| parasite, worm, protozoa    | Parasites                 |
| bacteria, bacterial         | Bacteria                  |
| virus, viral                | Viruses                   |
| fungi, fungal, candida, mold| Fungi                     |
| cancer, tumor, oncology     | Cancer                    |
| anemia, blood sugar, clot   | Blood                     |
| lymph, lymphatic            | Lymphatic System          |
| cortisol, estrogen, testosterone | Hormones             |
| allergy, histamine, allergen | Allergies                |
| lupus, MS, rheumatoid      | Autoimmune                |
| wound, injury, surgery, recovery | Injury and Recovery   |
| athletic, performance, focus, peak | Performance         |
| meditation, mindfulness, relaxation | Meditation         |
| emotional, trauma, relationship | Emotional             |
| spiritual, chakra, energy work | Spiritual              |
| emf, shielding, grounding  | Protection                |
| scalar                      | Scalar                    |
| biofeedback, scenar         | Biofeedback               |
| zapper, beck, microcurrent  | Zapper                    |
| rife, rife frequency        | Rife                      |

### Step 2: Check the description field

If the name didn't match, repeat Step 1 against the **description** text.

### Step 3: Check the frequency code content

If neither name nor description matched, scan the raw frequency code for
keywords from Step 1 (some presets encode the category name in the frequency
string itself).

### Step 4: Assign `null`

If no keyword matches after all three steps, set `category` to `null`.
These uncategorized presets should be flagged for manual review.

## Implementation Notes

- The keyword matching should be **word-boundary aware** — "cancer" should
  match "Cancer Support" but not "Dance Therapy"
- Use case-insensitive matching
- When multiple keywords match, pick the **first match** in the table above
- The `category` field in the existing `presets_all.json` data is used by the
  FilterPanel sidebar in the React app to group presets

## Example

```json
Input file content (legacy format):
  List2="Full Musculoskeletal Healing Contact"
  List4="7.83,7.83=600 W1 A09 O50 G1"

Output:
  {
    "name": "Full Musculoskeletal Healing Contact",
    "category": "Musculoskeletal System",
    "method": "keyword",
    "source": "name"
  }
```

## Integration

This skill is meant to be run as a manual step or invoked by a coding agent:

```bash
# After extracting Telegram presets:
python3 scripts/integrate_telegram.py

# Then assign categories:
# 1. Open data/presets/presets_all.json
# 2. For each program where category is null/empty, apply the rules above
# 3. Save the updated JSON

# Alternatively, use the fix_all_descriptions.py pipeline
# which already handles some category assignment
```
