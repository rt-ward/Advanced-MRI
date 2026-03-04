# DICOM ZIP Archiving & Flywheel Uploader

A lightweight Python utility for ingesting ZIP-compressed DICOM archives,
restructuring them into series-level bundles, and uploading them into a Flywheel
project with consistent subject/session/acquisition organization.

## What It Does

- Reads raw DICOM .zip archives
- Extracts subject IDs and key DICOM metadata
- Groups images into per-series ZIP bundles
- Creates subjects, sessions, and acquisitions in Flywheel
- Uploads each packaged series with metadata ({"type": "dicom"})
- Designed for large-scale, multi-site imaging workflows where automated and
reproducible handling of incoming DICOM is required.

## How It Works

- Load configuration (fwImageUpload.conf) containing Flywheel API key
- project prefix
- Connect to Flywheel via a wrapper class (FlywheelConnector)
- Parse the input ZIP and identify subjects
- Extract DICOM metadata (SeriesInstanceUID, SeriesNumber, StudyDate)
- Build new ZIP archives per unique series
- Ensure required Flywheel objects exist
- Upload the bundles and log progress

## Example Usage

- python uploader.py --input archive.zip --config fwImageUpload.conf

Example config:

```json
{
  "APIKey": "YOUR_API_KEY",
  "project": "PROJECT_PREFIX"
}
```

## Requirements

- Python 3.12+
- Flywheel SDK  
- pydicom
- fw-client

Install:

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install flywheel-sdk pydicom fw-client
```

## Intended Use

- Ideal for:
  - Multi-site imaging studies
  - Centralized ingestion pipelines (e.g., LONI → Flywheel)
  - Large DICOM uploads requiring standardized Flywheel organization

Output ZIPs are generated in a temporary directory and cleaned up post-run.

Script is safe for batch execution.

## Testing

- Download a collection of know image send as a zipfile
- Execute script to execute the upload
- This should include adding to existing session

## Development Setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

### Prerequisites

- Python 3.12+
- uv package manager

### Installation

1. Install uv (if not already installed):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

1. Install dependencies:

```bash
# Install production dependencies
uv sync

# Install with development dependencies
uv sync --group dev
```

1. Configure Flywheel credentials:

```bash
# Option 1: Use environment variable (recommended)
export FLYWHEEL_API_KEY="your-api-key-here"

# Option 2: Create config file
cp fwImageUpload.conf.example fwImageUpload.conf
# Edit fwImageUpload.conf with your API key
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_unit.py
```

### Code Quality

```bash
# Check code style
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# Format code
uv run ruff format .
```

### Running the Script

```bash
# Using uv
uv run python fwImageUpload.py -f archive.zip

# Or activate the virtual environment
source .venv/bin/activate  # On Unix/macOS
python fwImageUpload.py -f archive.zip
```
