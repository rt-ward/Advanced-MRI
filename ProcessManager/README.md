# Pipeline Manager (QSM)

A Flywheel gear that scans a project and launches the **QSMxT** and **QSM-MEDI** gears on every acquisition that contains QSM input files. It is meant to be run as a project-level analysis, and it can be re-run safely to pick up acquisitions that have not been processed yet.

## How it works

1. The gear finds the project it was launched from and connects with the supplied API key.
2. It reads all existing analyses in the project and records, for each gear and acquisition, whether a completed (job state `complete`) or in-progress (running/pending) analysis exists. If an analysis's job failed and Flywheel retried it, the retry chain is followed so the decision reflects the successor job's state.
3. It walks every subject, session and acquisition and reads each file's classification.
4. For each acquisition that contains at least one file with **Intent = QSM**, it decides whether to launch each enabled gear (see [Rerun behavior](#rerun-behavior)) and starts a new analysis on that acquisition.

The gear only launches jobs. It does not wait for them or collect their results. If a single gear launch fails with a Flywheel API error, that one launch is logged (with the gear name and acquisition) and skipped; the scan continues with the remaining acquisitions rather than aborting the whole run.

## Inputs

| Name | Type | Description |
|---|---|---|
| `api-key` | API key | Flywheel API key used to query the project and launch gears. The key's user needs read access to the project and permission to run the target gears. |

## Configuration

| Option | Type | Description |
|---|---|---|
| `do_qsmxt` | boolean | Launch the `qsmxt` gear on eligible acquisitions. |
| `do_qsm_medi` | boolean | Launch the `qsm-medi` gear on eligible acquisitions. |
| `process_all` | boolean | Launch every enabled gear on every eligible acquisition, even if a completed analysis already exists. |

## Required file classification

Files must be classified in Flywheel before running. Only the first value of the **Intent** classification is used:

| Intent | Used as |
|---|---|
| `QSM` | QSM input file for the gears |
| `Structural` | Anatomical image (QSMxT only) |

Files with any other intent, or no classification, are ignored.

## Gears launched

| Gear | Max QSM inputs | Input slots (in order) | Extra behavior |
|---|---|---|---|
| `qsmxt` | 3 | `input_file`, `input_file_opt`, `input_file_opt2` | If a Structural file exists, it is passed as `anatomical` and `premade` is set to `bet`. |
| `qsm-medi` | 2 | `input_file`, `input_file_opt` | Structural files are not used. |

QSM files are assigned to input slots in the order they are found in the acquisition. If an acquisition has more QSM files than a gear has slots, that gear is skipped for the acquisition and a warning is logged. If an acquisition has more than one Structural file, the first is used.

Each analysis is created on the acquisition containing the QSM files and labeled `<gear name> MM/DD/YYYY, HH:MM:SS`.

## Rerun behavior

For each enabled gear and eligible acquisition:

- With `process_all` enabled, the gear always runs.
- Otherwise, the gear runs only if no **completed** (job state `complete`) and no **in-progress** (running or pending) analysis of that gear exists for the acquisition. Acquisitions that were never analyzed, or whose final job failed or was cancelled with no live retry, are launched.

Because running and pending jobs count as "already processed", rerunning the manager while jobs are in progress does not launch duplicates for those acquisitions. A failed job that Flywheel has retried is followed to its successor, so a failed-then-retried analysis that is still running (or has since completed) is also treated as already processed and is not relaunched.

## Logging

Progress is written to stdout: the project name, and for each launch the acquisition, analysis label, gear, input file names, config and resulting job ID. Skipped acquisitions and unreadable data are reported as warnings.

## Limitations

- Requires all target gears (`qsmxt`, `qsm-medi`) to be installed and visible to the API key's user.
- Acquisitions are matched to existing analyses by subject, session and acquisition label, so labels should be unique within a session.
- Analyses that were uploaded rather than produced by a gear job are ignored when checking for previous results.
- Depends on the `flywheel-sdk`, `fw-client`, and `fw-gear` packages.

## Development

This Flywheel gear is containerized and designed to run within the Flywheel platform. Unlike the processing gears it launches, this is a lightweight pip-based gear that only makes Flywheel API calls — it has no file inputs (only an `api-key` input) and spawns no subprocesses.

### Prerequisites

- Docker
- [uv](https://docs.astral.sh/uv/) (Python package manager) for local linting
- Flywheel CLI (`flyw`) for deployment

### Building the Container

The image is based on `python:3.12-slim`, pinned by SHA256 digest in the `Dockerfile` for reproducible builds. It runs as a non-root `flywheel` user and is launched via the manifest `command` (`python3 /flywheel/v0/run.py`).

```bash
cd ProcessManager
docker build -t process-manager-qsm:local .
```

### Testing Locally

The gear reads its configuration, `api-key` input, and run destination from the Flywheel gear context (via `fw-gear`), so it is normally exercised as a project-level analysis on `naccdata.flywheel.io` with the three config booleans (`process_all`, `do_qsmxt`, `do_qsm_medi`). See the [Flywheel Gear Development Guide](https://docs.flywheel.io/hc/en-us/articles/360008162214) for running a gear against a live project.

For a quick import/compile check outside the container:

```bash
python3 -m py_compile run.py
```

### Development with uv

For Python development outside the container:

```bash
# From repository root
uv sync --group dev

# Run linting
uv run ruff check ProcessManager/

# Format code
uv run ruff format ProcessManager/
```

## Pre-deploy Checks

Before deploying, run these checks from the repository root:

```bash
# Lint
uv run ruff check ProcessManager/

# Verify formatting
uv run ruff format --check ProcessManager/

# Lint the Dockerfile
hadolint ProcessManager/Dockerfile

# Build the Docker image (tags using manifest's custom.gear-builder.image)
flyw gear build ProcessManager
```

## Deploying to Flywheel

The gear is deployed to `naccdata.flywheel.io` using the Flywheel CLI (`flyw`).

```bash
# Log in (prompts for your API key)
flyw login

# Validate the gear manifest
flyw gear --validate ProcessManager/manifest.json

# Upload the gear (tags and pushes the locally built image)
flyw gear upload ProcessManager/
```

The `flyw gear upload` command tags the local image (from `custom.gear-builder.image`
in `manifest.json`) for the Flywheel registry and pushes it. Keep the manifest
`version` and `custom.gear-builder.image` in sync when cutting a release.

## Maintaining the Base Image

This gear builds on the official `python:3.12-slim` image, pinned by SHA256
digest in the `Dockerfile`. To move to a newer base:

1. Pull the desired tag and resolve its digest:

   ```bash
   docker pull python:3.12-slim
   docker inspect --format '{{index .RepoDigests 0}}' python:3.12-slim
   ```

2. Update the `FROM` line in `Dockerfile` with the new tag and digest.
3. Rebuild and re-run the pre-deploy checks above.
4. Bump the `version` field in `manifest.json` and `custom.gear-builder.image`.