
# Flywheel gear implementation for QSMxT v8.2.0

- Implements full MEGRE pipeline: DICOM unzip → BIDS conversion → QSMxT execution
- Produces QSM maps, SWI images, segmentation outputs, and tabular metrics
- Adds workflow archive creation, crash file capture, and container version recording
- Designed for integration into CLARiTI/MEGRE neuroimaging workflows
- Validated with test MEGRE data and QSMxT reference outputs

QSMxT source: <https://github.com/QSMxT/QSMxT>


## Development

This Flywheel gear is containerized and designed to run within the Flywheel platform. For local development and testing:

### Prerequisites

- Docker
- Flywheel SDK (for testing gear context)

### Building the Container

```bash
cd QSMxT
docker build -t qsmxt-gear .
```

### Testing Locally

The gear can be tested locally using Flywheel's gear testing tools. See the [Flywheel Gear Development Guide](https://docs.flywheel.io/hc/en-us/articles/360008162214) for details.

### Development with uv

For Python development outside the container:

```bash
# From repository root
uv sync --group dev

# Run linting
uv run ruff check QSMxT/

# Format code
uv run ruff format QSMxT/
```
