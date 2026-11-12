"""Extract Flywheel run metadata and write it to the pipeline work directory.

Called by pipeline_singlePLD.sh as:
    python3 flywheel_context.py -dir <work_dir>

Uses the fw-gear GearContext (rather than the raw flywheel SDK GearContext) to
obtain the SDK client and the destination container, then walks the
subject/session/project hierarchy to record run metadata as metadata.json.
"""

import argparse
import json
import logging
import os
from datetime import datetime

import flywheel
from fw_gear.context import GearContext

# get directory of metadata file
parser = argparse.ArgumentParser(description='get location of metadata file')
parser.add_argument('-dir', type=str, help='The directory where the metadata file is.')
args = parser.parse_args()

# logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('aslscp')
logger.info("=======: ASL gear :=======")

with GearContext() as context:
    # Setup basic logging
    context.init_logging()

    # Use the working directory passed in by the pipeline. Fall back to the
    # gear output dir if -dir was not supplied.
    if args.dir:
        workdir = args.dir
    else:
        workdir = str(context.output_dir)

    # SDK client (built from the api-key input) and destination container.
    fw = context.client
    analysis_container = context.config.get_destination_container()
    analysis_id = analysis_container.id

    # Walk the container hierarchy for labels.
    project_container = fw.get(analysis_container.parents['project'])
    session_container = fw.get(analysis_container.parent['id'])
    subject_container = fw.get(session_container.parents['subject'])

    # Get subject, session, and project labels
    session_label = session_container.label
    subject_label = subject_container.label
    project_label = project_container.label

    # Get current runtime timestamp
    gear_run_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Extract scan date from session label
    # Expected format: ${subject label}x${scan date}x3Tx${studyname}
    scan_date = "Unknown"
    try:
        session_parts = session_label.split('x')
        if len(session_parts) >= 3:
            # Second element should be the scan date
            scan_date = session_parts[1]
            logger.info(f"Extracted scan date: {scan_date} from session label: {session_label}")
        else:
            logger.warning(f"Session label format unexpected: {session_label}")
            logger.warning("Expected format: subjectxScanDatex3TxStudyName")
    except (AttributeError, IndexError) as e:
        logger.warning(f"Could not parse scan date from session label '{session_label}': {e}")
        scan_date = "Unknown"

    # Get acquisition label - need to determine which acquisition this analysis belongs to
    acquisition_label = "Unknown"
    try:
        # If this is an acquisition-level analysis, get the acquisition
        if 'acquisition' in analysis_container.parent:
            acquisition_container = fw.get(analysis_container.parent['id'])
            acquisition_label = acquisition_container.label
        else:
            # If session-level analysis, you might want to get a specific acquisition
            # or list all acquisitions in the session
            acquisitions = session_container.acquisitions()
            if acquisitions:
                # Take the first acquisition or implement logic to select the right one
                acquisition_label = acquisitions[0].label
                logger.info(f"Multiple acquisitions found, using: {acquisition_label}")
    except (KeyError, AttributeError, flywheel.rest.ApiException) as e:
        logger.warning(f"Could not determine acquisition label: {e}")
        acquisition_label = "Unknown"

    subjects = [subject_container.label]
    sessions = [session_container.label]

    # Define the output file path
    INFO_OUT = os.path.join(workdir, "metadata.json")

    # Create metadata dictionary
    metadata = {
        "project_label": project_label,
        "subject_label": subject_label,
        "session_label": session_label,
        "acquisition_label": acquisition_label,
        "analysis_id": analysis_id,
        "scan_date": scan_date,
        "gear_run_datetime": gear_run_datetime
    }

    # Write metadata to text file
    try:
        with open(INFO_OUT, 'w') as f:
            f.write("=== Flywheel Metadata ===\n")
            f.write(f"Project: {project_label}\n")
            f.write(f"Subject: {subject_label}\n")
            f.write(f"Session: {session_label}\n")
            f.write(f"Acquisition: {acquisition_label}\n")
            f.write(f"Analysis ID: {analysis_id}\n")
            f.write(f"Scan Date: {scan_date}\n")
            f.write(f"Gear Run Date/Time: {gear_run_datetime}\n")
            f.write("========================\n")

            # Also write as JSON for machine readability
            f.write("\nJSON Format:\n")
            json.dump(metadata, f, indent=2)
            f.write("\n")

        logger.info(f"Metadata written to: {INFO_OUT}")
        logger.info(f"Metadata content: {metadata}")

    except OSError as e:
        logger.error(f"Failed to write metadata file: {e}")
        raise
