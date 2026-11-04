# Pipeline Status Report

A Flywheel gear that reports on a project's imaging data and processing status: how many acquisitions of each scan type exist, which gears have run, and which analyses failed without a later successful rerun. It is meant to be run as a project-level analysis, and it changes no data. It only reads the project and writes reports.

## How it works

1. The gear finds the project it was launched from and connects with the supplied API key.
2. It walks every subject, session and acquisition and records each file's name, type and Flywheel classification (Features, Intent, Measurement, Scan Orientation).
3. Each file is assigned a scan type (see [Scan types](#scan-types)), and counts are built per acquisition, split by DICOM and NIfTI.
4. It reads every analysis in the project, looks up its job state, and marks it as pass (`complete`), fail (`failed`), cancelled (`cancelled`) or other.
5. It writes the reports below to the analysis outputs and also uploads them to the project's **Attachments**, so they are easy to find.

## Inputs

| Name | Type | Description |
|---|---|---|
| `api-key` | API key | Flywheel API key used to read the project and upload attachments. The key's user needs read access to the project and permission to upload project files. |

The gear has no configuration options.

## Outputs

Every file name starts with the project label.

| File | Contents |
|---|---|
| `<project>_summary_report.pdf` | Acquisitions by scan type (first page), counts by each classification field, Intent × Scan Orientation counts and heatmap, and QSM counts by Axial/Sagittal orientation. |
| `<project>_summary.csv` | Human-readable summary: subject/session/acquisition/file totals, acquisitions by Intent and by scan type, analyses by gear, and pass/fail/cancelled counts overall and per gear. |
| `<project>_failed_analyses.csv` | Failed analyses that have no later successful run (see [Failed analyses](#failed-analyses)). |
| `<project>_unclassified.csv` | Every file that no scan-type rule matched, for review and for writing new rules. |
| `<project>_images.csv` | One row per file with its container labels and IDs, file type and classification. |
| `<project>_analyses.csv` | One row per analysis with its container labels and IDs, gear name and version, job state, status, and created/finished times. |

## Scan types

Rules are checked in order and the first match wins. A rule matches on the file's Flywheel classification or on keywords in the acquisition label plus file name (case-insensitive).

| Scan type | Matches |
|---|---|
| vNAV | Name contains `nav`. Checked first, so T1 and T2 navigators both land here. |
| T1 Structural | Intent `Structural` and Measurement `T1`, or name contains `mprage` (this includes MEMPRAGE). |
| T2 Structural | Intent `Structural` and Measurement `T2`. |
| PD Structural | Intent `Structural` and Measurement `PD`. |
| ASL Fieldmap / MeanPerf / M0 (excluded from ASL) | MeanPerf or M0 scans, or fieldmaps that look ASL-related. Kept out of the ASL counts. |
| Multi-Echo / QSM (GRE, susceptibility) | Intent `QSM`, or a multi-echo/GRE keyword (`me_t2`, `multiecho`, `megre`, `swi`, `swan`, `grappa`, …). |
| ASL Perfusion (pCASL) | Name contains `pcasl`, or Features `pCASL` with Functional/Perfusion classification. |
| ASL Perfusion (PASL) | Name contains `pasl`, or Features `PASL` with Functional/Perfusion classification. |
| ASL Perfusion (type not specified) | Name contains `asl` but neither of the above. |
| Perfusion (untagged, possible ASL) | Intent `Functional` and Measurement `Perfusion`, with no ASL keyword. |
| Unclassified | Nothing above matched. These files are listed in `<project>_unclassified.csv`. |

To add or change a scan type, edit `ScanTypeClassifier.RULES` (and its marker lists) in `PipeLineStatus.py`. No other code needs to change.

### How acquisitions are counted

An acquisition usually holds the same scan more than once, for example a DICOM archive plus one or more NIfTI conversions, so counting files would double count. The scan-type table therefore counts **acquisitions**, at most once per column:

| Column | Meaning |
|---|---|
| DICOM | Acquisitions with at least one DICOM file of that scan type. |
| NIfTI | Acquisitions with at least one NIfTI file of that scan type. |
| acquisitions | Acquisitions with any file of that scan type. |

The file type comes from Flywheel's file `type` field. A DICOM archive that Flywheel did not type as `dicom` (for example some `.zip.gz` uploads) counts toward `acquisitions` but not toward `DICOM`.

## Failed analyses

`<project>_failed_analyses.csv` lists analyses whose job state is `failed` and that have **no later successful run** of the same gear on the same container. Specifically:

- Runs are grouped by subject, session and acquisition **ID** plus gear name, so a success on one acquisition never clears a failure on another, even if the two share a label.
- Each gear is evaluated independently, so a passing run of one gear never clears a failure of a different gear.
- A failure is cleared only by a `complete` run created after it. A failure that comes after the most recent success stays on the list.
- Cancelled runs are left out entirely. They are reported as their own "Cancelled" count in the summary CSV, not as failures.

## Limitations

- Classification relies on Flywheel's file classification and on naming conventions. Files with neither (PET, registration outputs, templates, results CSVs) are reported as Unclassified.
- Only files attached to acquisitions are counted. Analysis output files are not.
- Analysis status reflects the job's final state only. Running and pending jobs are counted as "other".
- The gear makes one API call per analysis (plus parent-container lookups), so large projects take longer to report on.

## Running locally

Outside Flywheel, the script reads a `Manager.conf` from the current folder:

```json
{
  "APIKey": "your-api-key-here",
  "project": "project-label-prefix"
}
```

The `FLYWHEEL_API_KEY` environment variable takes precedence over `APIKey` if set. The first project whose label starts with `project` is used. Reports are written to the current folder and uploaded to the project's Attachments.

`*.conf` files are ignored by this repository's `.gitignore`. Never commit a `Manager.conf` containing a real API key.

```bash
pip install -r requirements.txt
python PipeLineStatus.py
```

## Development

### Building the container

The image is based on `python:3.11-slim` and launched via the manifest `command` (`python /flywheel/v0/PipeLineStatus.py`).

```bash
cd PipelineStatus
docker build -t pipeline-status:0.1.2 .
```

### Deploying to Flywheel

```bash
# Log in (prompts for your API key)
flyw login

# Validate the gear manifest
flyw gear --validate PipelineStatus/manifest.json

# Upload the gear
flyw gear upload PipelineStatus/
```

Keep the manifest `version` and `custom.gear-builder.image` in sync, and bump both for every release.

## Changelog

- **0.1.2:** pCASL and PASL counted separately. The scan-type table moved to the start of the PDF and now counts acquisitions (DICOM / NIfTI / total) instead of files. MPRAGE files are classified as T1 by name. Failed-analysis matching uses container IDs including the acquisition, and cancelled runs are no longer counted as failures.
- **0.1.1:** Version in use before this gear was added to the repository.
