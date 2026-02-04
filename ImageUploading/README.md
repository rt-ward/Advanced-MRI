# DICOM ZIP Archiving & Flywheel Uploader

A lightweight Python utility for ingesting ZIP-compressed DICOM archives,
restructuring them into series-level bundles, and uploading them into a Flywheel
project with consistent subject/session/acquisition organization.

What It Does

+ Reads raw DICOM .zip archives
+ Extracts subject IDs and key DICOM metadata
+ Groups images into per-series ZIP bundles
+ Creates subjects, sessions, and acquisitions in Flywheel
+ Uploads each packaged series with metadata ({"type": "dicom"})
+ Designed for large-scale, multi-site imaging workflows where automated and
reproducible handling of incoming DICOM is required.

How It Works

+ Load configuration (fwImageUpload.conf) containing Flywheel API key
+ project prefix
+ Connect to Flywheel via a wrapper class (FlywheelConnector)
+ Parse the input ZIP and identify subjects
+ Extract DICOM metadata (SeriesInstanceUID, SeriesNumber, StudyDate)
+ Build new ZIP archives per unique series
+ Ensure required Flywheel objects exist
+ Upload the bundles and log progress

Example Usage

+ python uploader.py --input archive.zip --config fwImageUpload.conf

Example config:
  {
    "APIKey": "YOUR_API_KEY",
    "project": "PROJECT_PREFIX"
  }

Requirements

+ Python 3.8+
+ Flywheel SDK  
+ pydicom
+ fw-client

Install:

+ pip install flywheel-sdk pydicom

Intended Use

+ Ideal for:
  + Multi-site imaging studies
  + Centralized ingestion pipelines (e.g., LONI -> Flywheel)
  + Large DICOM uploads requiring standardized Flywheel organization

Output ZIPs are generated in a temporary directory and cleaned up post-run.

Script is safe for batch execution.

Testing

+ Download a collection of know image send as a zipfile
+ Execute script to execute the upload
+ This should include adding to existing session
