
## Project Overview

A Python pipeline that **analyzes**, **grades**, and **discovers** basketball photos using heuristic image processing. The system:

1. Analyzes a local reference set of basketball photos using a 10-parameter rubric
2. Builds a benchmark profile from those scores
3. Searches public photo APIs (Openverse, Wikimedia Commons) for new candidates
4. Downloads candidates that meet or exceed the benchmark quality threshold

**Current state:** 9 reference photos analyzed (average score 5.75/10), 2 photos discovered so far.

---

## Directory Structure

```
basketball-photos/
├── src/                        # All application source code
│   ├── analyzer/               # Photo scoring pipeline
│   │   ├── grading_rubric.py   # 10-parameter heuristic scoring (core logic)
│   │   ├── image_analyzer.py   # Orchestrates metadata → score → categorize → persist
│   │   └── metadata_extractor.py
│   ├── categorizer/
│   │   ├── classifier.py       # Rule-based primary category assignment
│   │   └── tagger.py           # Secondary tag generation
│   ├── grader/
│   │   ├── comparator.py       # Builds BenchmarkProfile; accepts/rejects candidates
│   │   └── threshold_manager.py
│   ├── scraper/
│   │   ├── photo_discovery.py  # Top-level discovery workflow
│   │   ├── downloader.py       # File download with dedup
│   │   └── sources.py          # Openverse & Wikimedia Commons API clients
│   ├── storage/
│   │   ├── database.py         # SQLite persistence (3 tables)
│   │   └── json_store.py       # JSON export/import
│   ├── config/
│   │   └── loader.py           # YAML config parser with validation
│   ├── types/                  # Dataclasses (data models)
│   │   ├── photo.py            # PhotoMetadata
│   │   ├── scores.py           # PhotoScore (10 params + overall)
│   │   ├── analysis.py         # AnalysisResult
│   │   ├── config.py           # Config dataclasses
│   │   └── errors.py           # Custom exceptions
│   └── cli.py                  # Click CLI (analyze / discover / pipeline)
├── tests/                      # pytest test suite (9 modules)
├── config/
│   └── settings.yaml           # Primary configuration file
├── images/                     # Reference photos (IMG_1409–1417.jpeg)
│   └── discovered/             # Auto-downloaded photos land here
├── reports/                    # JSON outputs (analysis_results, discovery_results)
├── data/                       # .gitignored — SQLite DB lives here at runtime
├── main.py                     # Entry point (6 lines, delegates to cli.py)
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```

---

## Tech Stack

| Layer | Library |
|---|---|
| Image processing | `pillow`, `opencv-python`, `scikit-image` |
| Numerical / signal | `numpy`, `scipy` |
| Data | `pandas`, `sqlite3` (stdlib) |
| HTTP / scraping | `requests`, `beautifulsoup4`, `selenium` |
| Config | `pyyaml` |
| CLI | `click` |
| Player ID | `ultralytics` (YOLO), `easyocr`, `nba_api` |
| Optional AI | `torch`, `torchvision`, `transformers`, CLIP (not required) |
| Dev | `pytest`, `pytest-cov`, `ruff` |
| Package Mgmt | `uv` (recommended) or `pip` |

**Python 3.12+** is required (set in `pyproject.toml` as `target-version = "py312"`).

---

## Development Workflow

### Setup

**Using UV (recommended):**
```bash
# Install dependencies (includes dev tools)
uv sync

# With AI extras for player identification
uv sync --extra ai
```

**Using pip:**
```bash
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\Activate.ps1      # Windows

pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Run the CLI

```bash
# Analyze reference photos
python main.py analyze --directory ./images

# Discover & download new photos matching the benchmark
python main.py discover --directory ./images --count 10 --strategy all --target-dir ./images/discovered

# Full pipeline (analyze then discover)
python main.py pipeline --directory ./images --count 10 --strategy all --target-dir ./images/discovered

# Verbose output
python main.py --verbose analyze --directory ./images
```

### Test

```bash
python -m pytest              # Run all tests (quiet mode by default)
python -m pytest -v           # Verbose
python -m pytest --cov=src    # With coverage
```

### Lint

```bash
python -m ruff check .        # Lint
python -m ruff check . --fix  # Auto-fix
```

**Line length:** 88 characters (configured in `pyproject.toml` and `.editorconfig`).

---

## Core Architecture & Pipeline

```
images/ (reference set)
    │
    ▼
metadata_extractor.py  →  PhotoMetadata
    │
    ▼
grading_rubric.py      →  PhotoScore (10 params, weighted overall)
    │
    ▼
classifier.py + tagger.py  →  category + tags
    │
    ▼
database.py + json_store.py  (persist to SQLite + JSON)
    │
    ▼
comparator.py          →  BenchmarkProfile (avg, median, max, quartiles)
    │
    ▼
photo_discovery.py     →  query Openverse / Wikimedia Commons
    │                      filter by license, resolution, benchmark threshold
    ▼
downloader.py          →  images/discovered/
```

---

## Data Models (`src/types/`)

### `PhotoMetadata` (`photo.py`)
Fields: `path`, `filename`, `width`, `height`, `format`, `file_size`, `color_mode`, `aspect_ratio`, `exif_data`, `created_at`

Key properties: `megapixels`, `is_square`, `is_landscape`, `resolution_tier`

### `PhotoScore` (`scores.py`)
10 heuristic parameters (each scored 1.0–10.0):
- `resolution_clarity`, `composition`, `action_moment`, `lighting`, `color_quality`
- `subject_isolation`, `emotional_impact`, `technical_quality`, `relevance`, `instagram_suitability`

Plus: `overall_score` (weighted average per `config/settings.yaml` weights)

Key properties: `grade` (A+ → F), `quality_tier`, `top_three_params`, `bottom_three_params`

### `AnalysisResult` (`analysis.py`)
Combines `PhotoMetadata` + `PhotoScore` + `category` + `tags` + `analyzed_at` + `errors`

Key properties: `is_high_quality` (≥7.0), `is_instagram_ready` (≥6.0 + square), `needs_review` (5–7)

### `BenchmarkProfile` (`grader/comparator.py`)
Built from a list of `AnalysisResult`. Contains: `average_overall`, `median_overall`, `max_overall`, `min_overall`, `top_quartile_overall`, `category_distribution`, `top_tags`

---

## Configuration (`config/settings.yaml`)

```yaml
analysis:
  min_width: 1080
  min_height: 1080
  formats: [.jpg, .jpeg, .png, .webp]

weights:                    # Must sum to ~1.0
  resolution_clarity: 0.12
  composition: 0.12
  action_moment: 0.15
  lighting: 0.10
  color_quality: 0.08
  subject_isolation: 0.10
  emotional_impact: 0.13
  technical_quality: 0.10
  relevance: 0.05
  instagram_suitability: 0.05

thresholds:
  excellent: 9.0
  good: 7.5
  acceptable: 6.0
  poor: 4.0

discovery:
  min_overall_grade: 7.0
  target_count: 50
  download_dir: ./images/discovered
  rate_limit: 2             # seconds between API requests

output:
  database: ./data/photo_grades.db
  reports_dir: ./reports
```

`config/loader.py` validates that weights sum to ~1.0 and logs warnings on misconfiguration.

---

## Database Schema

SQLite at `data/photo_grades.db` (auto-created at runtime; path is `.gitignored`).

```sql
photos (id, path UNIQUE, filename, width, height, format, file_size,
        color_mode, aspect_ratio, megapixels, analyzed_at)

scores (photo_id FK, resolution_clarity, composition, action_moment,
        lighting, color_quality, subject_isolation, emotional_impact,
        technical_quality, relevance, instagram_suitability,
        overall_score, grade, quality_tier)

categories (photo_id FK, primary_category, tags)

player_identities (id, photo_id FK, player_id, name, jersey_number, team,
                   confidence, detection_confidence, ocr_confidence, bbox,
                   review_status, method)
```

Indexes: `photos.path`, `scores.overall_score DESC`, `player_identities.photo_id`

---

## Player Identification (Optional)

The system can identify NBA players in photos using a multi-stage pipeline:

1. **Detection**: YOLOv8 person detection (`src/analyzer/player_detector.py`)
2. **OCR**: EasyOCR jersey number recognition (`src/analyzer/jersey_ocr.py`)
3. **Roster Matching**: NBA API + local database (`src/analyzer/roster_matcher.py`)

### Components

- `PlayerIdentity` (dataclass): Stores identified player info with confidence scores
- `PlayerIdentifier` (orchestrator): Coordinates the full pipeline
- `DatabasePlayerStore`: Local NBA database queries for roster matching
- `ReviewQueueExporter`: Export uncertain identifications for manual review

### Configuration

```yaml
player_identification:
  enabled: false              # Master switch
  confidence_threshold: 0.6
  review_threshold: 0.6       # Below this = rejected
  auto_approve_threshold: 0.85 # Above this = auto-approved
```

### CLI Usage

```bash
# Enable player identification
python main.py analyze --directory ./images --identify-players --team LAL

# Export review queue for manual verification
python main.py analyze --directory ./images --identify-players --export-review-queue ./reviews
```

---

## External APIs

### Openverse (`src/scraper/sources.py`)
- Endpoint: `https://api.openverse.org/v1/images/`
- Filters: `license_type=commercial`, `category=photograph`
- Returns: image metadata, URL, license, creator

### Wikimedia Commons (`src/scraper/sources.py`)
- MediaWiki API: `action=query`, `list=allimages`
- Returns: image metadata with file URLs

**Rate limiting:** 2-second delay between requests (configured via `discovery.rate_limit`).

**Accepted licenses:** CC0, BY, BY-SA, PDM only.

---

## Discovery Threshold Strategies

Passed as `--strategy` to the CLI:

| Strategy | Threshold used |
|---|---|
| `all` | All reference photo scores individually |
| `average` | Average overall score of reference set |
| `median` | Median overall score |
| `blend` | Blend of average + median |

---

## Key Conventions

### Error handling
- Custom exceptions are defined in `src/types/errors.py` (`ImageReadError`, `DatabaseError`, `ConfigError`, etc.)
- Use these; don't raise generic `Exception`

### Graceful degradation
- `grading_rubric.py` falls back to numpy-only analysis when scipy is unavailable — maintain this pattern for any new optional dependencies

### Metadata extraction
- Uses PIL (not OpenCV) for metadata and basic analysis
- Supports: `.jpg`, `.jpeg`, `.png`, `.webp`, `.tiff`, `.bmp`

### Categorization
- 10 valid categories: `action_shot`, `portrait`, `celebration`, `dunk`, `three_pointer`, `defense`, `team_photo`, `court_side`, `fan_moment`, `iconic_moment`

### Serialization
- All dataclasses implement `to_dict()` / `from_dict()` for JSON serialization
- Reports are written to `reports/` as JSON

---

## Important Constraints

**Do NOT scrape or fetch images from:**
- NBA.com
- Getty Images
- ESPN
- Any source requiring paid licensing

Only use **Openverse** and **Wikimedia Commons**, and only accept CC0, BY, BY-SA, or PDM licensed content.

---

## Reports / Outputs

| File | Contents |
|---|---|
| `reports/analysis_results.json` | Per-photo analysis with all 10 parameters |
| `reports/analysis_summary.json` | Aggregate stats (total, avg, best/worst, categories) |
| `reports/discovery_results.json` | Discovery manifest with source metadata and acceptance reasoning |

---

## No CI/CD

There is no CI/CD pipeline. All testing and linting is run locally. Consider adding GitHub Actions if automating in the future.
