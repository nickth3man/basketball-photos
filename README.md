# NBA Photo Analyzer & Discovery System

A runnable Python system for categorizing, heuristically grading, benchmarking, and legally discovering basketball photos for Instagram-style content workflows.

## System Overview

The system analyzes the current reference photos in `images/` with a 10-parameter heuristic rubric, builds a benchmark profile from those scores, then searches legal/public image sources for basketball photos that match or exceed that benchmark. Accepted discoveries are downloaded into `images/discovered/` so the original benchmark set stays stable.

## 10-Parameter Grading Rubric

Each photo is graded on a scale of 1-10 for:

1. **Resolution & Clarity** - Image sharpness, pixel density, absence of blur
2. **Composition** - Rule of thirds, framing, visual balance
3. **Action/Moment Quality** - Peak action capture, decisive moments
4. **Lighting** - Exposure, contrast, dynamic range
5. **Color Quality** - Saturation, color accuracy, vibrancy
6. **Subject Isolation** - Player prominence, background separation
7. **Emotional Impact** - Drama, intensity, storytelling
8. **Technical Quality** - Noise, artifacts, compression quality
9. **Relevance** - Current players, trending teams, iconic moments
10. **Instagram Suitability** - Square format friendly, mobile viewport optimized

## Project Structure

```
basketball-photos/
├── src/
│   ├── analyzer/                  # Metadata extraction + rubric scoring
│   ├── categorizer/               # Primary categories + secondary tags
│   ├── grader/                    # Benchmark profile + threshold comparison
│   ├── scraper/                   # Openverse/Wikimedia discovery + download
│   ├── storage/                   # SQLite + JSON exports
│   ├── config/                    # Config loader
│   ├── types/                     # Dataclasses and typed models
│   └── cli.py                     # Click CLI
├── images/                        # Reference images
│   └── discovered/                # Accepted discoveries
├── data/                          # SQLite database outputs
├── reports/                       # JSON reports/manifests
├── config/settings.yaml
├── tests/
└── main.py
```

## Installation

### Option 1: Using UV (Recommended)

[UV](https://docs.astral.sh/uv/) is a fast Python package manager and resolver.

```bash
# Install uv (if not already installed)
pip install uv

# Create virtual environment and install dependencies
uv sync

# Install with AI extras (torch, transformers, CLIP)
uv sync --extra ai
```

### Option 2: Using pip

```bash
# Create and activate a virtual environment
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Install runtime dependencies
pip install -r requirements.txt

# Install developer tooling
pip install -r requirements-dev.txt

# Optional: Install AI extras
pip install -e ".[ai]"
```

## Development Workflow

```bash
# Run the test suite
python -m pytest

# Run linting and import sorting checks
python -m ruff check .
```

Tooling defaults are configured in `pyproject.toml`, and local editor settings are standardized in `.editorconfig`.

## Usage

### Analyze existing photos
```bash
python main.py analyze --directory ./images
```

### Discover benchmark-matching photos into the images tree
```bash
python main.py discover --directory ./images --count 5 --strategy all --target-dir ./images/discovered
```

### Full pipeline
```bash
python main.py pipeline --directory ./images --count 5 --strategy all --target-dir ./images/discovered
```

### Player Identification (Optional)

Identify NBA players in photos using YOLO person detection, EasyOCR jersey recognition, and NBA roster matching:

```bash
# Enable player identification
python main.py analyze --directory ./images --identify-players --team LAL

# Export review queue for manual verification
python main.py analyze --directory ./images --identify-players --export-review-queue ./reviews
```

**Requirements:** Install AI extras for player identification:
```bash
uv sync --extra ai  # or: pip install -e ".[ai]"
```

## Data Storage

- SQLite database stores all grades and metadata
- JSON exports for analysis summaries and discovery manifests
- Player identities stored with confidence scores and review status
- Accepted discoveries are saved with source/license metadata in `reports/discovery_results.json`

## Discovery Sources

The implemented discovery flow uses legal/public sources that can be accessed programmatically without scraping copyrighted NBA sites:

- Openverse image search API
- Wikimedia Commons API

The system intentionally does **not** scrape Getty Images, NBA.com, ESPN, or Sports Illustrated because those sources have licensing and terms-of-use constraints that are unsafe for automated downloading.

## Current Outputs

After running on the repo's current photo set, the analyzer generated:

- `reports/analysis_results.json`
- `reports/analysis_summary.json`
- `reports/discovery_results.json`
- accepted basketball photos in `images/discovered/`

## Important Notes

- The 10-parameter rubric is **heuristic**, not a trained aesthetic model.
- Discovery currently uses **Openverse** and **Wikimedia Commons** only.
- Accepted downloads should still get a human editorial pass before posting to Instagram.

## License

MIT License
