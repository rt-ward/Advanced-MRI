#!/usr/bin/env python3

import argparse
import json
import logging
import sys
import zipfile
import tempfile
from typing import Dict, List, Optional

import pydicom
import flywheel

from os import path
from fw_client import FWClient


###############################################################################
# Logging Setup
###############################################################################

logger = logging.getLogger("fw_uploader")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(handler)


###############################################################################
# Flywheel Connector
###############################################################################

class FlywheelConnector:
    """
    FlywheelConnector
    ------------------
    Provides a combined wrapper around the Flywheel REST API (via FWClient)
    and the official Flywheel Python SDK. This class simplifies the process of:

      Authenticating using an API key  
      Locating and selecting a Flywheel project  
      Iterating subjects, sessions, acquisitions, and files  
      Storing lists of retrieved image or session objects  
      
    The intent is to centralize and abstract Flywheel interactions so higher-level
    classes such as UploadImageData do not need to manage API calls directly.
    """

    def __init__(self, api_key: str):
        self.APIKey: str = api_key
        self.project = None

        self.RestClient: FWClient = FWClient(api_key=self.APIKey)
        self.SDKClient: flywheel.Client = flywheel.Client(self.APIKey)

        self.imageList: List = []
        self.sessionList: List = []

    def setProject(self, project_name: str) -> None:
        """Locate Flywheel project by prefix match."""
        try:
            project_list = self.RestClient.get("/api/projects")
        except Exception as e:
            logger.error(f"Error retrieving project list: {e}")
            raise

        for p in project_list:
            if p.label.startswith(project_name):
                try:
                    self.project = self.SDKClient.get_project(p._id)
                except Exception as e:
                    logger.error(f"Cannot fetch project '{project_name}' via SDK: {e}")
                    raise
                logger.info(f"Project set: {self.project.label}")
                return

        raise ValueError(f"No project found starting with '{project_name}'")

    def CollectImageInformation(self) -> None:
        """Collect file objects from all acquisitions in the selected project."""
        if not self.project:
            raise RuntimeError("Project not initialized before image collection.")

        self.imageList = []
        try:
            for subject in self.project.subjects.iter():
                for session in subject.sessions.iter():
                    for acq in session.acquisitions.iter():
                        for f in acq.files:
                            self.imageList.append(f)
        except Exception as e:
            logger.error(f"Error collecting image information: {e}")
            raise

    def CollectSessionInformation(self) -> None:
        """Collect a list of session objects from every subject."""
        if not self.project:
            raise RuntimeError("Project not initialized before session collection.")

        self.sessionList = []
        try:
            for subject in self.project.subjects.iter():
                for session in subject.sessions.iter():
                    self.sessionList.append(session)
        except Exception as e:
            logger.error(f"Error collecting session information: {e}")
            raise


###############################################################################
# Upload Image Data
###############################################################################

class UploadImageData:
    """
    UploadImageData
    ----------------
    Handles ingestion and upload of DICOM files stored in a structured ZIP archive.

    Responsibilities:
       Open and read archive files (ZIP format)  
       Extract and parse DICOM metadata necessary to group files correctly  
       Group DICOMs into Flywheel acquisitions based on SeriesInstanceUID  
       Re-compress files into per-series ZIP archives for upload  
       Create missing subjects, sessions, and acquisitions in Flywheel  
       Upload ZIP bundles with metadata to Flywheel  

    This class abstracts all logic related to reading and organizing DICOMs
    so the FlywheelConnector only handles connectivity and project lookup.
    """

    def __init__(self, fc: FlywheelConnector, fileSpec: str):
        self.fc = fc
        self.fileSpec = fileSpec

        try:
            self.zip = zipfile.ZipFile(fileSpec)
        except Exception as e:
            logger.error(f"Could not open zip file '{fileSpec}': {e}")
            raise

        self.baseName, _ = path.splitext(path.basename(fileSpec))

    def uploadImages(self, segIndex: int) -> None:
        """Extract DICOMs, group by subject/SUID, zip files, and upload to Flywheel."""

        acqList: Dict[str, List[str]] = {}

        logger.info("Scanning archive for DICOM files…")

        # Group files by subject NACC ID
        try:
            for f in self.zip.namelist():
                _, ext = path.splitext(f)
                if ext.lower() != ".dcm":
                    continue

                segments = f.split("/")
                subject_label = next((s for s in segments if "NACC" in s), None)

                if subject_label is None:
                    logger.warning(f"No NACC ID in file path: {f}")
                    continue

                acqList.setdefault(subject_label, []).append(f)
        except Exception as e:
            logger.error(f"Error scanning DICOM files: {e}")
            raise

        logger.info(f"Found {len(acqList)} subjects in archive.")

        # Process each subject block
        for subject_label, file_list in acqList.items():
            logger.info(f"Processing subject {subject_label} with {len(file_list)} files…")

            with tempfile.TemporaryDirectory() as tmpDir:
                zipFiles: Dict[str, List[str]] = {}
                zipNumbers: Dict[str, List[int]] = {}
                zipDates: Dict[str, List[str]] = {}

                try:
                    for f in file_list:
                        self.zip.extract(f, path=tmpDir)
                        meta = pydicom.dcmread(path.join(tmpDir, f), stop_before_pixels=True)

                        suid = meta.get((0x0020, 0x000E)).value
                        studyDate = meta.get((0x0008, 0x0020)).value
                        seriesNumber = meta.get((0x0020, 0x0011)).value

                        zipFiles.setdefault(suid, []).append(f)
                        zipNumbers.setdefault(suid, []).append(seriesNumber)
                        zipDates.setdefault(suid, []).append(studyDate)

                except Exception as e:
                    logger.error(f"Metadata extraction failure for subject {subject_label}: {e}")
                    continue

                # Upload each series as a zip
                for suid, file_group in zipFiles.items():
                    try:
                        first_file = file_group[0]
                        fileName = path.basename(first_file)
                        series_no = zipNumbers[suid][0]
                        date_str = zipDates[suid][0]

                        base_name = fileName.split("_br")[0]
                        zipFileName = f"{series_no}-{base_name}.zip"
                        zipPath = path.join(tmpDir, zipFileName)

                        logger.info(f"Packaging series {series_no} -> {zipPath}")

                        # Create compressed archive
                        with zipfile.ZipFile(zipPath, "w") as zf:
                            for f in file_group:
                                zf.write(path.join(tmpDir, f), path.basename(f))

                        segments = first_file.split("/")
                        subject_label = segments[segIndex]
                        session_label = f"{date_str}_MRI"
                        acquisition_label = segments[segIndex + 1]

                        # Ensure Flywheel objects exist
                        subject = self.fc.project.subjects.find_first(f"label={subject_label}")
                        if not subject:
                            logger.info(f"Creating new subject: {subject_label}")
                            subject = self.fc.project.add_subject(label=subject_label)

                        session = subject.sessions.find_first(f"label={session_label}")
                        if not session:
                            logger.info(f"Creating session: {session_label}")
                            session = subject.add_session(label=session_label)

                        acquisition = session.acquisitions.find_first(f"label={acquisition_label}")
                        if not acquisition:
                            logger.info(f"Creating acquisition: {acquisition_label}")
                            acquisition = session.add_acquisition(label=acquisition_label)

                        # Upload
                        logger.info(f"Uploading {zipFileName}…")
                        acquisition.upload_file(zipPath, metadata={"type": "dicom"})

                    except Exception as e:
                        logger.error(f"Failed to upload series {suid}: {e}")
                        continue

        logger.info("Upload processing complete.")


###############################################################################
# Configuration
###############################################################################

class Config:
    """
    Config
    ------
    Simple utility class for loading JSON configuration files.
    Used primarily to retrieve:
       APIKey - Flywheel API authorization token  
       project - project label prefix for automatic project selection  
    """

    def __init__(self, fileSpec: str):
        try:
            with open(fileSpec) as f:
                self.config = json.load(f)
        except Exception as e:
            logger.error(f"Error reading config file '{fileSpec}': {e}")
            raise

    def get(self, target: str) -> Optional[str]:
        """Retrieve a config field by name."""
        return self.config.get(target)


###############################################################################
# Main
###############################################################################

def main() -> None:
    parser = argparse.ArgumentParser(description="LONI to Flywheel upload tool")
    parser.add_argument("-f", "--file", required=True, help="Archive file name (zip)")
    parser.add_argument("-s", "--segIndex", help="Path segment containing NACC ID")
    args = parser.parse_args()

    segIndex = int(args.segIndex) if args.segIndex else 1

    config = Config(path.join(".", "fwImageUpload.conf"))
    api_key = config.get("APIKey")
    project_name = config.get("project")

    if not api_key or not project_name:
        logger.error("Missing APIKey or project in config file.")
        sys.exit(1)

    logger.info(f"Connecting to Flywheel with project prefix: {project_name}")

    try:
        fc = FlywheelConnector(api_key)
        fc.setProject(project_name)
        uploader = UploadImageData(fc, args.file)
        uploader.uploadImages(segIndex)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
