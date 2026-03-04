# Advanced-MRI

This repository contains scripts, Flywheel gears, and viewer protocols that
support the processing, quality control, and visualization of Advanced MRI
data, including MEGRE, ASL, and vNAV sequences. It provides a centralized,
version-controlled workspace for developing, testing, and deploying tools used
across CLARiTI, SCAN, and related imaging workflows.

## Contents

- Scripts
  - Utilities for data preparation, DICOM metadata extraction, automated
  classification, reprocessing, and workflow orchestration.
- Flywheel Gears
  - Containerized analysis tools ready for execution within the Flywheel
  platform, including:
    - Sequence-specific QC pipelines
    - MEGRE → QSM workflows
    - ASL quantification and derived metrics
    - Reprocessing utilities for updated analysis methods
- Viewer Protocols
  - Standardized configurations for image inspection and QC in popular viewers
  (e.g., Flywheel’s built-in viewer, ITK-SNAP, 3D Slicer).

## Purpose

Advanced MRI techniques evolve rapidly, and this repository provides a shared
home for:

- Reproducible analysis workflows
- Standardized QC tools
- Rapid prototyping of new methods
- Seamless integration with Flywheel for multisite studies
- Reprocessing capabilities when new algorithms or updates become available

## Usage

Each component includes its own documentation in subdirectories. Typical uses
include:

- Running automated QC on new uploads
- Deploying or updating Flywheel gears
- Testing new analysis approaches prior to production release
- Organizing viewer presets for consistent manual review across sites
  
## Development

This project uses [uv](https://docs.astral.sh/uv/) for dependency management and development workflows.

### Quick Start for Developers

```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/naccdata/clariti-advanced-mri.git
cd clariti-advanced-mri

# Install dependencies (including dev dependencies)
uv sync --group dev

# Run tests
uv run pytest

# Check code quality
uv run ruff check .
```

### Development Workflow

1. Install dependencies:

```bash
uv sync --group dev
```

1. Make your changes

2. Run tests and linting:

```bash
uv run pytest
uv run ruff check --fix .
uv run ruff format .
```

1. Commit and push your changes

### Configuration

Set your Flywheel API key using an environment variable:

```bash
export FLYWHEEL_API_KEY="your-api-key-here"
```

See individual component READMEs for component-specific setup and usage instructions.
