# Viewer Protocol Configuration & Form Check

This document defines the Viewer Protocol and validates that the Viewer
Configuration and Viewer Form are aligned for use in automated review,
segmentation, and radiology-oriented workflows.

---

## Purpose

- Establish a canonical viewer configuration for imaging review
- Ensure viewer config and viewer form remain identical
- Support reproducibility across sites, readers, and deployments
- Provide a reference for GitHub review and change tracking

---

## Scope

This protocol applies to:

- DICOM and NIfTI visualization  
- MR imaging  

---

## Overall Purpose

The form documents a human QC assessment of image reconstruction quality,
focused on completeness, motion, coverage, and common artifacts. The results
are stored with the task and can be queried, audited, or used to gate
downstream processing.

---

## QC Dimensions Captured

### 1. Series Completeness

**Binary Status:** Complete vs. Incomplete  

**Optional Comment:**  
Free-text explanation of missing frames, slices, timepoints, or reconstruction
failures.

**QC Value:**  
Enables identification of datasets that are unusable or require re-upload or
reprocessing before analysis.

---

### 2. Motion Assessment

**Severity Scale:** Pass / Mild / Moderate / Severe  

**Optional Comment:**  
Description of type or impact of motion.

**QC Value:**  
Allows analysts to:

- Flag scans that may bias quantitative results  
- Stratify datasets by motion severity  
- Exclude or down-weight affected series in analysis pipelines  

---

### 3. Field-of-View (FOV) Coverage

**Severity Scale:** Pass / Mild / Moderate / Severe  

**Optional Comment:**  
Description of anatomy cut off.

**QC Value:**

- Identifies incomplete anatomical coverage  
- Prevents downstream failures in registration, segmentation, or atlas-based
quantification  

---

### 4. Image Artifact Characterization

This section captures specific artifact classes, each with standardized
severity scoring and optional narrative detail.

#### a. Field Inhomogeneity

- Detects B0/B1 nonuniformity effects  
- Important for intensity-based analysis and segmentation  

#### b. Ghosting or Wrapping

- Identifies phase-encoding or aliasing artifacts  
- Relevant for both visual QC and automated failure detection  

#### c. Banding

- Captures reconstruction or hardware-related striping artifacts
- Helps distinguish scanner or protocol issues from subject-related problems

#### For Each Artifact

- **Severity Scale:** Pass / Mild / Moderate / Severe
- **Optional Comment:** Contextual explanation

**QC Value:**  
Enables artifact-specific filtering, reporting, and longitudinal site/scanner
performance monitoring.

---

## Structured and Narrative QC Data

### Structured Fields

Dropdown fields enable:

- Querying across projects  
- Dashboarding and summary statistics  
- Rule-based acceptance/rejection logic in workflows  

### Conditional Comments

Enable:

- Reviewer justification  
- Documentation for audit trails and site feedback  

---

## Change Control

- Any changes to this protocol must update both sections.
