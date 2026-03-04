#!/usr/bin/env python3
"""DICOM ZIP archiving and Flywheel uploader utility.

This module provides functionality for ingesting ZIP-compressed DICOM archives,
restructuring them into series-level bundles, and uploading them to Flywheel
with consistent subject/session/acquisition organization.
"""

import argparse
import json
import logging
import os
import sys
import tempfile
import zipfile
from os import path
from typing import Dict, List, Optional

import flywheel
import pydicom
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
    FlywheelConnector.

    Provides a convenience wrapper around:

      • The Flywheel REST API client (FWClient)
      • The official Flywheel Python SDK (flywheel.Client)

    It centralizes retrieval and iteration over projects, subjects, sessions,
    acquisitions, and file objects.

    Parameters
    ----------
    api_key : str
        A valid Flywheel API key used for authentication.

    Attributes
    ----------
    APIKey : str
        Stored Flywheel API token.
    RestClient : FWClient
        Wrapper around Flywheel REST API.
    SDKClient : flywheel.Client
        Official Flywheel SDK client.
    project : flywheel.Project or None
        Selected project object after calling `setProject`.
    imageList : List
        Collected list of file objects from acquisitions.
    sessionList : List
        Collected list of session objects.
    """

    def __init__(self, api_key: str):
        self.APIKey: str = api_key
        self.project = None

        self.RestClient: FWClient = FWClient(api_key=self.APIKey)
        self.SDKClient = flywheel.Client(self.APIKey)

        self.imageList: List = []
        self.sessionList: List = []

    def setProject(self, project_name: str) -> None:
        """
        Locate and set the Flywheel project matching a prefix string.

        Parameters
        ----------
        project_name : str
            Prefix of the Flywheel project label. The first matching project
            returned by the REST API list will be selected.

        Returns
        -------
        None

        Raises
        ------
        Exception
            If project listing or retrieval fails.
        ValueError
            If no project label begins with the provided prefix.
        """
        try:
            project_list = self.RestClient.get("/api/projects")
        except Exception as e:
            logger.error(f"Error retrieving project list: {e}")
            raise

        for p in project_list:
            if p.label.startswith(project_name):
                try:
                    self.project = self.SDKClient.get_project(p._id)  # noqa: SLF001
                except Exception as e:
                    logger.error(f"Cannot fetch project '{project_name}' via SDK: {e}")
                    raise
                logger.info(f"Project set: {self.project.label}")
                return

        raise ValueError(f"No project found starting with '{project_name}'")

    def CollectImageInformation(self) -> None:
        """
        Collect all Flywheel file objects from every acquisition in the project.

        Returns
        -------
        None

        Raises
        ------
        RuntimeError
            If no project has been initialized.
        Exception
            If any SDK iteration fails.
        """
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
        """
        Collect all session objects from every subject in the selected project.

        Returns
        -------
        None

        Raises
        ------
        RuntimeError
            If project is not set.
        Exception
            If SDK traversal fails.
        """
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
    UploadImageData.

    Responsible for uploading DICOMs from an input ZIP file to Flywheel.
    Files are grouped by SeriesInstanceUID and uploaded as per-series ZIPs.

    Parameters
    ----------
    fc : FlywheelConnector
        Initialized FlywheelConnector instance with project selected.
    fileSpec : str
        Path to the ZIP archive containing DICOM files.

    Attributes
    ----------
    fc : FlywheelConnector
        Connector used for Flywheel operations.
    fileSpec : str
        Provided ZIP file path.
    zip : zipfile.ZipFile
        Opened ZIP archive.
    baseName : str
        Base name of the input archive (without extension).

    Raises
    ------
    Exception
        If the ZIP archive cannot be opened.
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

    def uploadImages(self, segIndex: int) -> None:  # noqa: C901
        """
        Extract, group, package, and upload DICOMs to Flywheel.

        Workflow:
        1. Identify subject folders containing NACC IDs.
        2. Group DICOMs by SeriesInstanceUID.
        3. Extract grouped files to temporary directory.
        4. Create ZIP archives per series.
        5. Ensure subject/session/acquisition exist in Flywheel.
        6. Upload each ZIP to Flywheel with metadata.

        Parameters
        ----------
        segIndex : int
            Index of the path segment containing the subject label.

        Returns
        -------
        None

        Raises
        ------
        Exception
            On DICOM metadata read failure or Flywheel upload issues.
        """
        acqList: Dict[str, List[str]] = {}

        logger.info("Scanning archive for DICOM files…")

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

        for subject_label, file_list in acqList.items():
            logger.info(
                f"Processing subject {subject_label} with {len(file_list)} files…"
            )

            with tempfile.TemporaryDirectory() as tmpDir:
                zipFiles: Dict[str, List[str]] = {}
                zipNumbers: Dict[str, List[int]] = {}
                zipDates: Dict[str, List[str]] = {}

                try:
                    for f in file_list:
                        self.zip.extract(f, path=tmpDir)
                        meta = pydicom.dcmread(
                            path.join(tmpDir, f), stop_before_pixels=True
                        )

                        suid = meta.get((0x0020, 0x000E)).value
                        studyDate = meta.get((0x0008, 0x0020)).value
                        seriesNumber = meta.get((0x0020, 0x0011)).value

                        zipFiles.setdefault(suid, []).append(f)
                        zipNumbers.setdefault(suid, []).append(seriesNumber)
                        zipDates.setdefault(suid, []).append(studyDate)

                except (OSError, KeyError, AttributeError) as e:
                    logger.error(
                        f"Metadata extraction failure for subject {subject_label}: {e}"
                    )
                    continue

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

                        with zipfile.ZipFile(zipPath, "w") as zf:
                            for f in file_group:
                                zf.write(path.join(tmpDir, f), path.basename(f))

                        segments = first_file.split("/")
                        subject_label = segments[segIndex]
                        session_label = f"{date_str}_MRI"
                        acquisition_label = segments[segIndex + 1]

                        subject = self.fc.project.subjects.find_first(
                            f"label={subject_label}"
                        )
                        if not subject:
                            logger.info(f"Creating new subject: {subject_label}")
                            subject = self.fc.project.add_subject(label=subject_label)

                        session = subject.sessions.find_first(f"label={session_label}")
                        if not session:
                            logger.info(f"Creating session: {session_label}")
                            session = subject.add_session(label=session_label)

                        acquisition = session.acquisitions.find_first(
                            f"label={acquisition_label}"
                        )
                        if not acquisition:
                            logger.info(f"Creating acquisition: {acquisition_label}")
                            acquisition = session.add_acquisition(
                                label=acquisition_label
                            )

                        logger.info(f"Uploading {zipFileName}…")
                        acquisition.upload_file(zipPath, metadata={"type": "dicom"})

                    except (OSError, flywheel.ApiException) as e:
                        logger.error(f"Failed to upload series {suid}: {e}")
                        continue

        logger.info("Upload processing complete.")


###############################################################################
# Configuration
###############################################################################


class Config:
    """
    Config.

    Wrapper for reading JSON configuration that supplies Flywheel credentials.

    Parameters
    ----------
    fileSpec : str
        Path to the JSON config file.

    Attributes
    ----------
    config : dict
        Parsed JSON configuration.

    Raises
    ------
    Exception
        If file cannot be read or parsed.
    """

    def __init__(self, fileSpec: str):
        try:
            with open(fileSpec) as f:
                self.config = json.load(f)
        except Exception as e:
            logger.error(f"Error reading config file '{fileSpec}': {e}")
            raise

    def get(self, target: str) -> Optional[str]:
        """
        Return a configuration value by key.

        Parameters
        ----------
        target : str
            Key to retrieve from configuration.

        Returns
        -------
        Optional[str]
            The retrieved value, or None if the key is missing.
        """
        return self.config.get(target)


###############################################################################
# Main
###############################################################################


def main() -> None:
    """
    Entry point for the LONI → Flywheel upload tool.

    Parses command-line arguments, loads configuration,
    initializes FlywheelConnector, and uploads DICOMs.

    Command-Line Arguments
    ----------------------
    -f / --file : str (required)
        Path to ZIP archive of DICOMs.
    -s / --segIndex : int (optional)
        Index of path segment containing subject label in filenames.

    Returns
    -------
    None

    Exit Codes
    ----------
    1 : Missing configuration, project not found, upload failure.
    """
    parser = argparse.ArgumentParser(description="LONI to Flywheel upload tool")
    parser.add_argument("-f", "--file", required=True, help="Archive file name (zip)")
    parser.add_argument("-s", "--segIndex", help="Path segment containing NACC ID")
    args = parser.parse_args()

    segIndex = int(args.segIndex) if args.segIndex else 1

    config = Config(path.join(".", "fwImageUpload.conf"))
    api_key = os.getenv("FLYWHEEL_API_KEY") or config.get("APIKey")
    if not api_key:
        raise ValueError(
            "FLYWHEEL_API_KEY environment variable or config APIKey required"
        )
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
    except (ValueError, OSError, zipfile.BadZipFile, flywheel.ApiException) as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
