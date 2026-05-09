#!/usr/bin/env python3
"""
LLM Auto-Categorization for Spooky2 Telegram Presets
====================================================

Uses an LLM (OpenAI-compatible API) to auto-categorize downloaded
preset files that couldn't be classified by keyword matching alone.

Supports:
- OpenAI API (openai.com)
- LM Studio local server (http://localhost:1234/v1)
- Any OpenAI-compatible endpoint

Usage:
    python3 scripts/categorize_presets.py --input data/presets/telegram_raw
    python3 scripts/categorize_presets.py --input data/presets/telegram_raw --dry-run
    python3 scripts/categorize_presets.py --input data/presets/telegram_raw --model llama-3.1-8b
"""

import os
import sys
import json
import argparse
import logging
import hashlib
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Known Spooky2 preset categories
KNOWN_CATEGORIES = [
    "Detox", "Immune System", "Digestive System", "Respiratory System",
    "Cardiovascular System", "Nervous System", "Musculoskeletal System",
    "Endocrine System", "Urinary System", "Reproductive System",
    "Skin and Hair", "Eyes and Ears", "Dental", "Mental Health",
    "Sleep", "Energy and Fatigue", "Pain Management", "Inflammation",
    "Infection", "Parasites", "Bacteria", "Viruses", "Fungi",
    "Cancer", "Blood", "Lymphatic System", "Hormones",
    "Allergies", "Autoimmune", "Injury and Recovery", "Performance",
    "Meditation", "Emotional", "Spiritual", "Protection",
    "Scalar", "Biofeedback", "Zapper", "Rife",
]

# Category descriptions for LLM context
CATEGORY_DESCRIPTIONS = {
    "Detox": "Detoxification, liver cleanse, heavy metals, chelation",
    "Immune System": "Immune boosting, immune modulation",
    "Digestive System": "Gut health, digestion, stomach, intestines",
    "Respiratory System": "Lungs, breathing, sinus, airways",
    "Cardiovascular System": "Heart, blood vessels, circulation, blood pressure",
    "Nervous System": "Brain, nerves, neural, cognition, memory",
    "Musculoskeletal System": "Bones, joints, muscles, tendons, ligaments",
    "Endocrine System": "Thyroid, adrenals, pancreas, hormones, glands",
    "Urinary System": "Kidneys, bladder, urinary tract",
    "Reproductive System": "Reproductive organs, fertility, sexual health",
    "Skin and Hair": "Skin conditions, hair, nails, dermatology",
    "Eyes and Ears": "Vision, hearing, eyes, ears",
    "Dental": "Teeth, gums, oral health, dental",
    "Mental Health": "Anxiety, depression, stress, mood, emotional balance",
    "Sleep": "Sleep disorders, insomnia, sleep quality",
    "Energy and Fatigue": "Energy, fatigue, vitality, stamina, mitochondria",
    "Pain Management": "Pain, inflammation, analgesia, headaches, migraines",
    "Inflammation": "Anti-inflammatory, swelling, inflammatory conditions",
    "Infection": "Antiviral, antibacterial, antifungal, general infection",
    "Parasites": "Parasite cleanse, worms, protozoa",
    "Bacteria": "Bacterial infections, specific bacteria",
    "Viruses": "Viral infections, specific viruses",
    "Fungi": "Fungal infections, candida, mold",
    "Cancer": "Cancer support, oncology, tumor",
    "Blood": "Blood health, anemia, blood sugar, clotting",
    "Lymphatic System": "Lymph nodes, lymphatic drainage, immune fluid",
    "Hormones": "Hormone balance, estrogen, testosterone, cortisol",
    "Allergies": "Allergic reactions, histamine, sensitivities",
    "Autoimmune": "Autoimmune conditions, lupus, MS, rheumatoid",
    "Injury and Recovery": "Wound healing, injury, surgery recovery",
    "Performance": "Athletic performance, focus, peak state",
    "Meditation": "Meditation, relaxation, mindfulness",
    "Emotional": "Emotional healing, trauma, relationships",
    "Spiritual": "Spiritual development, chakra, energy work",
    "Protection": "EMF protection, shielding, grounding",
    "Scalar": "Scalar energy, scalar devices",
    "Biofeedback": "Biofeedback, SCENAR, device protocols",
    "Zapper": "Zapper, Beck device, microcurrent",
    "Rife": "Rife frequency, rife machine, specific frequencies",
}

# Common suffixes in preset names that indicate category
NAME_CATEGORY_HINTS = {
    "detox": "Detox",
    "liver": "Detox",
    "colon": "Digestive System",
    "gut": "Digestive System",
    "stomach": "Digestive System",
    "lung": "Respiratory System",
    "sinus": "Respiratory System",
    "heart": "Cardiovascular System",
    "blood": "Blood",
    "brain": "Nervous System",
    "nerve": "Nervous System",
    "pain": "Pain Management",
    "energy": "Energy and Fatigue",
    "fatigue": "Energy and Fatigue",
    "sleep": "Sleep",
    "immune": "Immune System",
    "cancer": "Cancer",
    "parasite": "Parasites",
    "bacteria": "Bacteria",
    "virus": "Viruses",
    "fungi": "Fungi",
    "candida": "Fungi",
    "hormone": "Hormones",
    "thyroid": "Endocrine System",
    "joint": "Musculoskeletal System",
    "skin": "Skin and Hair",
    "dental": "Dental",
    "emf": "Protection",
    "scalar": "Scalar",
    "meditation": "Meditation",
    "chakra": "Spiritual",
    "allergy": "Allergies",
    "inflammation": "Inflammation",
    "wound": "Injury and Recovery",
    "athletic": "Performance",
    "focus": "Performance",
    "stress": "Mental Health",
    "anxiety": "Mental Health",
    "depression": "Mental Health",
    "bladder": "Urinary System",
    "kidney": "Urinary System",
    "eye": "Eyes and Ears",
    "ear": "Eyes and Ears",
    "hearing": "Eyes and Ears",
    "vision": "Eyes and Ears",
    "lymph": "Lymphatic System",
    "autoimmune": "Autoimmune",
    "lupus": "Autoimmune",
    "biofeedback": "Biofeedback",
    "zapper": "Zapper",
    "rife": "Rife",
}


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("categorize_presets")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)
    return logger


class LLMCategorizer:
    """LLM-based auto-categorizer for Spooky2 presets."""

    def __init__(
        self,
        api_base: str = "https://api.openai.com/v1",
        api_key: str = "",
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        max_tokens: int = 100,
        timeout: int = 30,
    ):
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._session = None

        if not self.api_key and not self.api_base.startswith("http://localhost"):
            print("WARNING: No API key provided and not using localhost. "
                  "Set OPENAI_API_KEY or specify --api-base and --api-key.")

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_prompt(
        self,
        name: str,
        description: str,
        code: str,
        existing_categories: List[str],
    ) -> str:
        """Build a zero-shot classification prompt."""
        categories_list = ", ".join(sorted(KNOWN_CATEGORIES))

        # Truncate code for context
        code_preview = code[:500] if code else "(no frequency code)"

        # Build few-shot examples
        examples = """Here are some examples:

Preset name: "Full Musculoskeletal Healing Contact"
Description: "Heals all musculoskeletal injuries and chronic pain"
Category: Musculoskeletal System

Preset name: "Candida Cleanse Scalar"
Description: "Eliminates candida overgrowth using scalar energy"
Category: Fungi

Preset name: "Lyme Support Remote Advanced"
Description: "Supports recovery from Lyme disease and coinfections"
Category: Parasites

Preset name: "EMF Protection Scalar"
Description: "Protects against electromagnetic field exposure"
Category: Protection

Preset name: "DNA Repair Plasma"
Description: "Repairs damaged DNA using plasma frequencies"
Category: Nervous System
"""

        prompt = f"""Classify this Spooky2 preset into one of the known categories below.

Known categories:
{categories_list}

Examples:
{examples}

Now classify this preset:
Name: {name}
Description: {description[:300] if description else "(no description)"}
Frequency code preview: {code_preview}

Category (respond with exactly one category name):"""

        return prompt

    def _extract_context_keywords(self, name: str, description: str) -> List[str]:
        """Extract likely keywords from name and description before LLM call."""
        text = (name + " " + (description or "")).lower()
        keywords = []
        for hint, cat in NAME_CATEGORY_HINTS.items():
            if hint in text:
                keywords.append(hint)
        return keywords

    def _check_name_category(self, name: str, description: str) -> Optional[str]:
        """Fast path: check if keywords in name/description clearly match a category."""
        text = (name + " " + (description or "")).lower()

        # Check for exact-ish matches
        for hint, cat in NAME_CATEGORY_HINTS.items():
            if hint in text:
                # Verify it's a real match, not a substring false positive
                # (e.g., "cancer" in "dancer" should not match)
                if (text.find(hint) == 0 or
                    not text[text.find(hint) - 1].isalpha() or
                    text.find(hint) + len(hint) >= len(text) or
                    not text[text.find(hint) + len(hint)].isalpha()):
                    return cat

        return None

    def categorize(
        self,
        name: str,
        description: str,
        code: str = "",
        use_llm: bool = True,
    ) -> Dict:
        """
        Categorize a preset. Returns:
        {
            "category": str,
            "confidence": "high" | "medium" | "low",
            "method": "keyword" | "llm" | "heuristic" | "unknown",
            "llm_reasoning": str (optional),
        }
        """
        name = name or ""
        description = description or ""
        code = code or ""

        # Step 1: Try keyword matching on name/description
        keyword_cat = self._check_name_category(name, description)
        if keyword_cat:
            return {
                "category": keyword_cat,
                "confidence": "high",
                "method": "keyword",
            }

        # Step 2: Try matching on frequency code content
        code_cat = self._check_code_heuristics(code)
        if code_cat:
            return {
                "category": code_cat,
                "confidence": "medium",
                "method": "heuristic",
            }

        # Step 3: LLM classification
        if use_llm:
            return self._categorize_via_llm(name, description, code)

        return {
            "category": None,
            "confidence": None,
            "method": "unknown",
        }

    def _check_code_heuristics(self, code: str) -> Optional[str]:
        """Check frequency code for category hints."""
        if not code:
            return None

        code_lower = code.lower()

        # Common frequency ranges and patterns
        # Cancer-related often have specific frequency patterns
        if any(freq in code_lower for freq in ["mhz", "ghz"]):
            pass  # Not enough to classify

        return None

    def _categorize_via_llm(self, name: str, description: str, code: str) -> Dict:
        """Query an LLM for categorization."""
        prompt = self._build_prompt(name, description, code, KNOWN_CATEGORIES)

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert categorizer for Spooky2 frequency presets. "
                        "Classify each preset into exactly one category from the provided list. "
                        "Respond with ONLY the category name, nothing else."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        try:
            import httpx

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.api_base}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                )

            if response.status_code != 200:
                logging.getLogger("categorize_presets").warning(
                    f"LLM API error {response.status_code}: {response.text[:200]}"
                )
                return {
                    "category": None,
                    "confidence": None,
                    "method": "llm_error",
                    "error": f"API returned {response.status_code}",
                }

            data = response.json()
            choice = data.get("choices", [{}])
            message = choice[0].get("message", {})
            content = message.get("content", "").strip()

            # Validate against known categories
            matched_category = None
            for cat in KNOWN_CATEGORIES:
                if cat.lower() in content.lower():
                    matched_category = cat
                    break

            if not matched_category:
                # Use as-is, might be a reasonable response
                matched_category = content.split("\n")[0].strip()

            return {
                "category": matched_category,
                "confidence": "medium",
                "method": "llm",
                "llm_reasoning": content,
            }

        except Exception as e:
            logging.getLogger("categorize_presets").warning(
                f"LLM categorization failed: {e}"
            )
            return {
                "category": None,
                "confidence": None,
                "method": "llm_error",
                "error": str(e),
            }

    def categorize_batch(
        self,
        items: List[Dict],
        use_llm: bool = True,
    ) -> List[Dict]:
        """Categorize a batch of presets. Each item should have 'name', 'description', 'code'."""
        results = []
        for i, item in enumerate(items):
            result = self.categorize(
                name=item.get("name", ""),
                description=item.get("description", ""),
                code=item.get("code", ""),
                use_llm=use_llm,
            )
            result["input"] = item
            results.append(result)

            # Rate limiting
            if use_llm and i < len(items) - 1:
                time.sleep(0.5)

        return results

    def categorize_file(
        self,
        filepath: Path,
        use_llm: bool = True,
    ) -> Dict:
        """Read a .txt preset file and categorize it."""
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            name = filepath.stem
            description = ""
            code = content

            # Try to extract name and description from common patterns
            if "PresetName=" in content or "PresetName = " in content:
                match = __import__("re").search(
                    r'PresetName"?\s*=\s*"?([^"\n]+)"?', content
                )
                if match:
                    name = match.group(1).strip()

            if "Preset_Notes=" in content or "Preset_Notes = " in content:
                match = __import__("re").search(
                    r'Preset_Notes"?\s*=\s*"?([^"\n]+)"?', content
                )
                if match:
                    description = match.group(1).strip()

            return self.categorize(name, description, code, use_llm=use_llm)

        except Exception as e:
            return {
                "category": None,
                "confidence": None,
                "method": "error",
                "error": str(e),
            }


def process_directory(
    input_dir: Path,
    output_dir: Path,
    categorizer: LLMCategorizer,
    logger: logging.Logger,
    use_llm: bool = True,
    resume: bool = True,
) -> Dict:
    """Process all .txt files in a directory, categorize, and organize."""
    results_path = output_dir / "categorization_results.json"
    stats_path = output_dir / "categorization_stats.json"

    # Resume: load existing results
    existing_results = {}
    if resume and results_path.exists():
        try:
            with open(results_path, "r", encoding="utf-8") as f:
                existing_results = json.load(f)
            logger.info(f"Resumed from {len(existing_results)} existing results")
        except Exception:
            existing_results = {}

    # Find all .txt files
    txt_files = list(input_dir.rglob("*.txt"))
    logger.info(f"Found {len(txt_files)} .txt files to categorize")

    results = {}
    stats = {
        "total_files": len(txt_files),
        "categorized": 0,
        "by_category": {},
        "by_method": {},
        "by_confidence": {},
        "errors": 0,
    }

    for filepath in txt_files:
        rel_path = str(filepath.relative_to(input_dir))

        # Skip if already processed
        if rel_path in existing_results:
            results[rel_path] = existing_results[rel_path]
            continue

        # Get the program name from the result if already extracted
        name = filepath.stem
        description = ""
        code = filepath.read_text(encoding="utf-8", errors="replace")[:5000]

        # Try to extract from content
        if "PresetName=" in code:
            match = __import__("re").search(
                r'PresetName"?\s*=\s*"?([^"\n]+)"?', code
            )
            if match:
                name = match.group(1).strip()
        if "Preset_Notes=" in code:
            match = __import__("re").search(
                r'Preset_Notes"?\s*=\s*"?([^"\n]+)"?', code
            )
            if match:
                description = match.group(1).strip()

        result = categorizer.categorize(name, description, code, use_llm=use_llm)
        result["file"] = rel_path
        results[rel_path] = result

        # Update stats
        category = result.get("category") or "Unclassified"
        method = result.get("method", "unknown")
        confidence = result.get("confidence", "unknown")

        stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
        stats["by_method"][method] = stats["by_method"].get(method, 0) + 1
        stats["by_confidence"][confidence] = stats["by_confidence"].get(confidence, 0) + 1

        if method == "llm_error":
            stats["errors"] += 1
        else:
            stats["categorized"] += 1

        # Save progress every 50 files
        if len(results) % 50 == 0:
            with open(results_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            logger.info(f"Progress: {len(results)}/{len(txt_files)} files categorized")

    # Final save
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    logger.info(f"\nCategorization complete:")
    logger.info(f"  Total files:    {stats['total_files']}")
    logger.info(f"  Categorized:    {stats['categorized']}")
    logger.info(f"  Errors:         {stats['errors']}")
    logger.info(f"  By category:    {json.dumps(stats['by_category'], indent=2)}")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Auto-categorize Spooky2 preset files using LLM",
        epilog="""
Examples:
  # Categorize with LLM (default: OpenAI GPT-4o-mini)
  python3 categorize_presets.py --input data/presets/telegram_raw

  # Use local LM Studio
  python3 categorize_presets.py --input data/presets/telegram_raw --api-base http://localhost:1234/v1

  # Dry run (keyword matching only, no LLM)
  python3 categorize_presets.py --input data/presets/telegram_raw --dry-run

  # Custom model
  python3 categorize_presets.py --input data/presets/telegram_raw --model llama-3.1-8b --api-key lm-studio
        """,
    )

    parser.add_argument(
        "--input", "-i",
        default="data/presets/telegram_raw",
        help="Input directory with preset files (default: data/presets/telegram_raw)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output directory (default: same as input)",
    )
    parser.add_argument(
        "--api-base",
        default=os.environ.get("LLM_API_BASE", "https://api.openai.com/v1"),
        help="API base URL (default: $LLM_API_BASE or OpenAI)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("LLM_API_KEY", ""),
        help="API key (default: $LLM_API_KEY or empty for local)",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        help="Model name (default: $LLM_MODEL or gpt-4o-mini)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="LLM temperature (default: 0.1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use keyword matching only, no LLM calls",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Start fresh without resuming previous results",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    logger = setup_logging("DEBUG" if args.verbose else "INFO")

    input_dir = Path(args.input)
    output_dir = Path(args.output) if args.output else input_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        sys.exit(1)

    use_llm = not args.dry_run

    categorizer = LLMCategorizer(
        api_base=args.api_base,
        api_key=args.api_key,
        model=args.model,
        temperature=args.temperature,
    )

    logger.info(f"Input: {input_dir}")
    logger.info(f"Output: {output_dir}")
    logger.info(f"Model: {args.model}")
    logger.info(f"API base: {args.api_base}")
    logger.info(f"LLM enabled: {use_llm}")

    stats = process_directory(
        input_dir,
        output_dir,
        categorizer,
        logger,
        use_llm=use_llm,
        resume=not args.no_resume,
    )

    if use_llm:
        print("\nTip: Set LLM_API_KEY and/or LLM_API_BASE environment variables to avoid passing flags.")
        print("  export LLM_API_KEY='sk-...'")
        print("  export LLM_API_BASE='http://localhost:1234/v1'  # for LM Studio")

    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())