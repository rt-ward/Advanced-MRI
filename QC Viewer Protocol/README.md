Viewer Protocol - Configuration & Form Check

This document defines the Viewer Protocol and validates that the Viewer Configuration and Viewer Form are aligned for use in automated review, segmentation, and radiology-oriented workflows.

Purpose

Establish a canonical viewer configuration for imaging review

Ensure viewer config and viewer form remain identical

Support reproducibility across sites, readers, and deployments

Provide a reference for GitHub review and change tracking

Scope

This protocol applies to:

DICOM and NIfTI visualization

MR imaging

Overall purpose

The form documents a human QC assessment of image reconstruction quality, focused on completeness, motion, coverage, and common artifacts. The results are stored with the task and can be queried, audited, or used to gate downstream processing.

QC dimensions captured
1. Series completeness

Binary status: Complete vs Incomplete

Optional free-text comment explaining missing frames, slices, timepoints, or reconstruction failures

QC value: Enables identification of datasets that are unusable or require re-upload or reprocessing before analysis

2. Motion assessment

Graded severity: Pass / Mild / Moderate / Severe

Optional comment describing type or impact of motion

QC value: Allows analysts to:

Flag scans that may bias quantitative results

Stratify datasets by motion severity

Exclude or down-weight affected series in analysis pipelines

3. Field-of-view (FOV) coverage

Graded severity: Pass / Mild / Moderate / Severe

Optional comment describing anatomy cut off

QC value:

Identifies incomplete anatomical coverage

Prevents downstream failures in registration, segmentation, or atlas-based quantification

4. Image artifact characterization

This section captures specific artifact classes, each with standardized severity scoring and optional narrative detail:

a. Field inhomogeneity

Detects B0/B1 nonuniformity effects

Important for intensity-based analysis and segmentation

b. Ghosting or wrapping

Identifies phase-encoding or aliasing artifacts

Relevant for both visual QC and automated failure detection

c. Banding

Captures reconstruction or hardware-related striping artifacts

Helps distinguish scanner or protocol issues from subject-related problems

For each artifact:

Severity scale: Pass / Mild / Moderate / Severe

Optional comment for contextual explanation

QC value: Enables artifact-specific filtering, reporting, and longitudinal site/scanner performance monitoring

Structured + narrative QC data

Structured fields (dropdowns) enable:

Querying across projects

Dashboarding and summary statistics

Rule-based acceptance/rejection logic in workflows

Conditional comments allow:

Reviewer justification

Documentation for audit trails and site feedback



Change Control

Any changes to this protocol must update both sections