#!/usr/bin/env python3

#
#  Pipeline Manager Tool
#

import argparse
import ast
import json
import logging
import os
import re
import sys
from os import path
from typing import Dict, List, Optional
import flywheel
from fw_client import FWClient
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


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

    def __init__(self, api_key: str):
        self.APIKey: str = api_key
        self.project = None

        self.RestClient: FWClient = FWClient(api_key=self.APIKey)
        self.SDKClient = flywheel.Client(self.APIKey)

    def setProject(self, project_name: str) -> None:
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

    def setProjectFromDestination(self, destination_id: str) -> None:
        """Gear mode: the gear runs as an analysis, so its parent project is
        the project the user launched it from."""
        analysis = self.SDKClient.get_analysis(destination_id)
        self.project = self.SDKClient.get_project(analysis.parents.project)
        logger.info(f"Project set from gear destination: {self.project.label}")


###############################################################################
# Status Report
###############################################################################

class StatusReport:

    def __init__(self, flywheelConnector):
        self.connector = flywheelConnector

###############################################################################
# Configuration
###############################################################################

class Config:

    def __init__(self, fileSpec: str):
        try:
            with open(fileSpec) as f:
                self.config = json.load(f)
        except Exception as e:
            logger.error(f"Error reading config file '{fileSpec}': {e}")
            raise

    def get(self, target: str) -> Optional[str]:
        return self.config.get(target)

###############################################################################
# Images
###############################################################################


class ImageInformation:
    def __init__(self, fc):
        rows = []
        for subject in fc.project.subjects.iter():
            for session in subject.sessions.iter():
                logger.info(f"{subject.label}, {session.label}")
                for acquisition in session.acquisitions.iter():

                    for file in acquisition.files:

                        features = self.getClassification(file.classification, 'Features')
                        intent =  self.getClassification(file.classification, 'Intent')
                        measurement = self.getClassification(file.classification, 'Measurement')
                        scanOrientation = self.getClassification(file.classification, 'Scan Orientation')

                        row = {
                            "group": fc.project.group,
                            "project": fc.project.label,
                            "subject": subject.label,
                            "session": session.label,
                            "session_id": session._id,
                            "acquisition": acquisition.label,
                            "acquisition_id": acquisition._id,
                            "file": file.name,
                            "file_id": file.id,
                            "modality": file.modality,
                            "file_type": file.type,
                            "features": features,
                            "Intent": intent,
                            "Measurement": measurement,
                            "Scan Orientation": scanOrientation,
                        }
                        rows.append(row)

        self.df = pd.DataFrame(rows)
        self.df.to_csv(fc.project.label + "_images.csv", index=False)

    def getClassification(self, classification, target):

        try:
            value = classification[target]
        except (KeyError, TypeError):
            value = None

        return value

###############################################################################
# Summary Statistics
###############################################################################

# Sequential blue ramp, light -> dark, for heatmap cells.
HEATMAP_CMAP = matplotlib.colors.LinearSegmentedColormap.from_list(
    "fw_sequential_blue",
    ["#cde2fb", "#6da7ec", "#256abf", "#0d366b"],
)


class ScanTypeClassifier:
    """Assigns each image file a single human-readable scan-type label.

    Classification is driven by two things, both already present in every
    row with zero extra API calls:

    1. Keyword matching on the `acquisition` and `file` labels (their names
       as they appear in Flywheel) — these carry rich, human-assigned
       naming like "MPRAGE", "vNav", "QSM_GRAPPA3", "pCASL", "PASL" that
       reliably identifies scan type. This is the primary signal.
    2. Flywheel's own DICOM classification fields (Intent/Measurement/
       Features) as a fallback / backstop for anything the keywords miss.

    An earlier version of this pulled the DICOM SeriesDescription tag via a
    dedicated per-file Flywheel API call and matched it against
    ImageClassificationGroups.csv (a lookup table from the NACC team). That
    added a slow API round-trip per file and turned out to be unnecessary:
    the acquisition/file label already carries the same information (NAV,
    MPRAGE, QSM, pCASL, etc.) for free. ImageClassificationGroups.csv is
    kept as a manual reference (see ImageClassificationGroups.xlsx) but is
    no longer wired into this pipeline.

    RULES is a simple ordered list on purpose: each rule is checked in order
    and the first match wins, so you can read top-to-bottom exactly which
    combination of fields produces which label. To tweak or add a scan type,
    add/edit an entry below — no other code needs to change.

    Each rule is (label, predicate) where predicate(features, intent,
    measurement, label_text) -> bool. features/intent/measurement are the
    parsed list values for one file (e.g. features=['pCASL', '3D'],
    intent=['Functional']); label_text is the lowercased acquisition label
    + file name, concatenated, for keyword search. "Unclassified" is used
    when nothing matches.

    Your boss's four priority categories — Multi-Echo, ASL, T1-Structural,
    and vNAV — are called out explicitly below (search "PRIORITY").
    """

    UNCLASSIFIED = "Unclassified"

    # Substrings (checked against the lowercased acquisition label + file
    # name) that mark a vNAV (real-time motion-navigator) acquisition. Any
    # match is labeled vNAV regardless of Intent/Measurement, so T2 vNAVs
    # count too, not just T1. "_rms" is deliberately NOT a marker: in
    # MEMPRAGE protocols the _RMS image is the main T1, not a navigator.
    NAV_MARKERS = ["nav"]

    # Substrings that mark a T1 acquisition by name. Catches MPRAGE (and
    # MEMPRAGE) files that have no Flywheel Intent/Measurement
    # classification, e.g. NIfTI conversions and derived "c_" images.
    T1_MARKERS = ["mprage"]

    # Substrings that mark a Multi-Echo / QSM (GRE) acquisition by name,
    # independent of the Intent/Measurement classification fields.
    MULTI_ECHO_MARKERS = ["me_t2", "me t2", "multi-echo", "multiecho", "_me_", "megre", "swi", "swan", "grappa"]

    # Substrings that mark an ASL/perfusion acquisition by name. pCASL and
    # PASL are reported separately; "pasl" is not a substring of "pcasl", so
    # the two never overlap. Anything else matching "asl" lands in the
    # "type not specified" bucket.
    ASL_MARKERS = ["asl", "pcasl", "pasl"]
    PCASL_MARKERS = ["pcasl"]
    PASL_MARKERS = ["pasl"]

    # ASL-related scans that are kept OUT of the ASL counts: MeanPerf
    # (scanner-derived mean perfusion map) and M0 calibration scans are
    # always excluded; fieldmaps are excluded when they look ASL-related.
    MEANPERF_MARKERS = ["meanperf", "mean_perf"]
    FIELDMAP_MARKERS = ["fieldmap", "field_map", "field map"]

    # "m0" at the start of a word (e.g. "ASL_M0", "M0scan", "pcasl-m0"),
    # so it doesn't fire on an "m0" buried inside some other token.
    M0_PATTERN = re.compile(r"(?<![a-z0-9])m0")

    @classmethod
    def _label_text(cls, acquisition: str, file_name: str) -> str:
        return f"{acquisition or ''} {file_name or ''}".lower()

    @classmethod
    def _has_any(cls, text: str, markers: List[str]) -> bool:
        return any(marker in text for marker in markers)

    @classmethod
    def _is_asl_excluded(cls, intent: List[str], measurement: List[str], text: str) -> bool:
        if cls._has_any(text, cls.MEANPERF_MARKERS) or cls.M0_PATTERN.search(text):
            return True
        is_fieldmap = "Fieldmap" in intent or cls._has_any(text, cls.FIELDMAP_MARKERS)
        looks_asl = "Perfusion" in measurement or cls._has_any(text, cls.ASL_MARKERS)
        return is_fieldmap and looks_asl

    RULES = [
        # PRIORITY: vNAV — any scan with "nav" in its name, checked first so
        # it wins over every Intent/Measurement-based rule below
        (
            "vNAV",
            lambda f, i, m, t: ScanTypeClassifier._has_any(t, ScanTypeClassifier.NAV_MARKERS),
        ),
        # PRIORITY: T1-Structural
        (
            "T1 Structural",
            lambda f, i, m, t: ("Structural" in i and "T1" in m)
            or ScanTypeClassifier._has_any(t, ScanTypeClassifier.T1_MARKERS),
        ),
        ("T2 Structural", lambda f, i, m, t: "Structural" in i and "T2" in m),
        ("PD Structural", lambda f, i, m, t: "Structural" in i and "PD" in m),
        # PRIORITY: ASL — Fieldmap/MeanPerf/M0 scans are pulled out before
        # Multi-Echo and ASL so they never land in either count
        (
            "ASL Fieldmap / MeanPerf / M0 (excluded from ASL)",
            lambda f, i, m, t: ScanTypeClassifier._is_asl_excluded(i, m, t),
        ),
        # PRIORITY: Multi-Echo / QSM (GRE) — label keywords first, Intent as backstop
        (
            "Multi-Echo / QSM (GRE, susceptibility)",
            lambda f, i, m, t: "QSM" in i or ScanTypeClassifier._has_any(t, ScanTypeClassifier.MULTI_ECHO_MARKERS),
        ),
        (
            "ASL Perfusion (pCASL)",
            lambda f, i, m, t: ScanTypeClassifier._has_any(t, ScanTypeClassifier.PCASL_MARKERS)
            or ("Functional" in i and "Perfusion" in m and "pCASL" in f),
        ),
        (
            "ASL Perfusion (PASL)",
            lambda f, i, m, t: ScanTypeClassifier._has_any(t, ScanTypeClassifier.PASL_MARKERS)
            or ("Functional" in i and "Perfusion" in m and "PASL" in f),
        ),
        (
            "ASL Perfusion (type not specified)",
            lambda f, i, m, t: ScanTypeClassifier._has_any(t, ScanTypeClassifier.ASL_MARKERS),
        ),
        (
            "Perfusion (untagged, possible ASL)",
            lambda f, i, m, t: "Functional" in i and "Perfusion" in m,
        ),
    ]

    @classmethod
    def classify(
        cls,
        features: List[str],
        intent: List[str],
        measurement: List[str],
        acquisition: str = "",
        file_name: str = "",
    ) -> str:
        label_text = cls._label_text(acquisition, file_name)
        for label, predicate in cls.RULES:
            if predicate(features, intent, measurement, label_text):
                return label
        return cls.UNCLASSIFIED

    @classmethod
    def classify_row(cls, row) -> str:
        """Reads columns off a pandas row. Every field is sanitized with
        pd.notna rather than plain truthiness because pandas represents a
        missing value as float NaN, and NaN is truthy in Python (`nan or x`
        evaluates to `nan`, not `x`) -- a naive `row.get(...) or default`
        lets a NaN slip through as-is and break downstream string/list ops.
        """
        def clean(key, default):
            value = row.get(key)
            # isinstance guard first: pd.notna() on a list returns an
            # elementwise array, not a bool, so it can't gate a list value.
            if isinstance(value, (list, dict)):
                return value
            return value if pd.notna(value) else default

        return cls.classify(
            clean("features", []),
            clean("Intent", []),
            clean("Measurement", []),
            clean("acquisition", ""),
            clean("file", ""),
        )


def scan_type_acquisition_counts(images_df: pd.DataFrame, scan_types: pd.Series) -> pd.DataFrame:
    """Counts acquisitions (not files) per scan type, split by file type.

    An acquisition usually holds the same scan as both a DICOM archive and
    one or more NIfTI conversions, so counting files double counts. Here
    each acquisition counts at most once per column: "DICOM" / "NIfTI" are
    acquisitions with at least one file of that type, and "acquisitions" is
    acquisitions with any file of that scan type.
    """
    if "acquisition_id" in images_df.columns:
        acq_key = images_df["acquisition_id"]
    else:
        acq_key = images_df["session"].astype(str) + "/" + images_df["acquisition"].astype(str)
    file_type = images_df.get("file_type", pd.Series("", index=images_df.index))
    frame = pd.DataFrame(
        {
            "scan_type": scan_types,
            "acq": acq_key,
            "file_type": file_type.fillna("").astype(str).str.lower(),
        }
    )

    def unique_acqs(subset: pd.DataFrame) -> pd.Series:
        return subset.groupby("scan_type")["acq"].nunique()

    counts = pd.DataFrame(
        {
            "DICOM": unique_acqs(frame[frame["file_type"] == "dicom"]),
            "NIfTI": unique_acqs(frame[frame["file_type"] == "nifti"]),
            "acquisitions": unique_acqs(frame),
        }
    )
    return (
        counts.fillna(0)
        .astype(int)
        .rename_axis("scan_type")
        .reset_index()
        .sort_values(["acquisitions", "scan_type"], ascending=[False, True])
        .reset_index(drop=True)
    )


class SummaryStats:
    """Builds count breakdowns of classification columns from an images CSV."""

    CLASSIFICATION_COLUMNS = ["features", "Intent", "Measurement", "Scan Orientation"]

    def __init__(self, images_csv: str, output_prefix: str):
        self.images_csv = images_csv
        self.output_prefix = output_prefix
        self.df = pd.read_csv(images_csv)

        for col in self.CLASSIFICATION_COLUMNS:
            if col in self.df.columns:
                self.df[col] = self.df[col].apply(self._parse_list_cell)

        self.column_counts: Dict[str, pd.DataFrame] = {}
        self.intent_orientation: Optional[pd.DataFrame] = None
        self.qsm_orientation: Optional[pd.DataFrame] = None
        self.scan_type_counts: Optional[pd.DataFrame] = None
        self.scan_types: Optional[pd.Series] = None

    @staticmethod
    def _parse_list_cell(value) -> List[str]:
        """Classification cells are written as stringified lists, e.g. "['QSM']".

        Handles missing values, plain scalars, and genuinely multi-valued
        cells (e.g. features) uniformly by always returning a list of str.
        """
        if isinstance(value, list):
            return [str(v) for v in value]
        if pd.isna(value):
            return []
        try:
            parsed = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return [str(value)]
        if isinstance(parsed, list):
            return [str(v) for v in parsed]
        if isinstance(parsed, (set, tuple)):
            return [str(v) for v in parsed]
        return [str(parsed)]

    def _value_counts(self, column: str) -> pd.DataFrame:
        exploded = self.df[column].explode().dropna()
        counts = exploded.value_counts().rename_axis(column).reset_index(name="count")
        return counts.sort_values("count", ascending=False).reset_index(drop=True)

    def _pair_counts(self, col_a: str, col_b: str) -> pd.DataFrame:
        exploded = self.df[[col_a, col_b]].explode(col_a).explode(col_b)
        exploded = exploded.dropna(subset=[col_a, col_b])
        counts = (
            exploded.groupby([col_a, col_b])
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
            .reset_index(drop=True)
        )
        return counts

    def compute(self) -> None:
        for col in self.CLASSIFICATION_COLUMNS:
            if col in self.df.columns:
                self.column_counts[col] = self._value_counts(col)
                logger.info(f"Counts for '{col}':\n{self.column_counts[col].to_string(index=False)}")

        if "Intent" in self.df.columns and "Scan Orientation" in self.df.columns:
            self.intent_orientation = self._pair_counts("Intent", "Scan Orientation")
            logger.info(
                "Counts for Intent x Scan Orientation:\n"
                f"{self.intent_orientation.to_string(index=False)}"
            )

            qsm_rows = self.intent_orientation[self.intent_orientation["Intent"] == "QSM"]
            self.qsm_orientation = qsm_rows[
                qsm_rows["Scan Orientation"].isin(["Axial", "Sagittal"])
            ].reset_index(drop=True)
            logger.info(
                "QSM counts by Axial/Sagittal orientation:\n"
                f"{self.qsm_orientation.to_string(index=False)}"
            )

        if all(c in self.df.columns for c in ("features", "Intent", "Measurement")):
            self.scan_types = self.df.apply(ScanTypeClassifier.classify_row, axis=1)
            self.scan_type_counts = scan_type_acquisition_counts(self.df, self.scan_types)
            logger.info(
                "Acquisitions by scan type:\n" f"{self.scan_type_counts.to_string(index=False)}"
            )

    ROW_HEIGHT_IN = 0.22
    TITLE_HEIGHT_IN = 0.35
    SECTION_GAP_IN = 0.35

    @classmethod
    def _table_height_in(cls, table: pd.DataFrame) -> float:
        """Inches of vertical space a table needs: title + header row + one
        row per entry."""
        return cls.TITLE_HEIGHT_IN + (len(table) + 1) * cls.ROW_HEIGHT_IN

    def _draw_table(self, ax, title: str, table: pd.DataFrame) -> None:
        ax.axis("off")
        ax.set_title(title, fontsize=11, fontweight="bold", loc="left", pad=8)

        # Two-column (label, count) tables fit in half the page; wider tables
        # like the per-file-type scan type counts need the full width.
        width = 0.5 if len(table.columns) <= 2 else 1.0
        mpl_table = ax.table(
            cellText=table.values,
            colLabels=table.columns,
            cellLoc="left",
            loc="upper left",
            bbox=[0, 0, width, 1],
        )
        mpl_table.auto_set_font_size(False)
        mpl_table.set_fontsize(8)
        mpl_table.auto_set_column_width(col=list(range(len(table.columns))))

        for (row, _col), cell in mpl_table.get_celld().items():
            cell.set_edgecolor("#d9dde3")
            if row == 0:
                cell.set_facecolor("#0d366b")
                cell.set_text_props(color="white", fontweight="bold")
            else:
                cell.set_facecolor("#f7f8fa" if row % 2 == 0 else "white")

    def _draw_table_pages(self, pdf: PdfPages, sections: List[tuple]) -> None:
        """Packs (title, table) sections onto as few 8.5x11in pages as fit,
        stacking tables top-to-bottom (tightly sized to row count) instead of
        one table per page."""
        PAGE_HEIGHT_IN = 11
        MARGIN_IN = 0.6
        usable_height = PAGE_HEIGHT_IN - 2 * MARGIN_IN

        page_sections: List[tuple] = []
        used_in = 0.0

        def flush():
            nonlocal page_sections, used_in
            if not page_sections:
                return
            fig = plt.figure(figsize=(8.5, 11))
            y_top_in = PAGE_HEIGHT_IN - MARGIN_IN
            for title, table, h_in in page_sections:
                ax_height_frac = h_in / PAGE_HEIGHT_IN
                y_bottom_in = y_top_in - h_in
                ax = fig.add_axes(
                    [0.08, y_bottom_in / PAGE_HEIGHT_IN, 0.84, ax_height_frac]
                )
                self._draw_table(ax, title, table)
                y_top_in = y_bottom_in - self.SECTION_GAP_IN
            pdf.savefig(fig)
            plt.close(fig)
            page_sections = []
            used_in = 0.0

        for title, table in sections:
            if table is None or table.empty:
                continue
            h_in = self._table_height_in(table)
            projected = used_in + h_in + (self.SECTION_GAP_IN if page_sections else 0)
            if projected > usable_height and page_sections:
                flush()
                projected = h_in
            page_sections.append((title, table, h_in))
            used_in = projected

        flush()

    def _draw_heatmap_page(self, pdf: PdfPages) -> None:
        pivot = self.intent_orientation.pivot(
            index="Intent", columns="Scan Orientation", values="count"
        ).fillna(0)

        fig, ax = plt.subplots(figsize=(8.5, max(3, 0.6 * len(pivot) + 2)))
        im = ax.imshow(pivot.values, cmap=HEATMAP_CMAP, aspect="auto")

        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels(pivot.columns)
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels(pivot.index)
        ax.set_title("Intent x Scan Orientation", fontsize=13, fontweight="bold", loc="left", pad=12)

        vmax = pivot.values.max() if pivot.values.size else 0
        for i in range(pivot.shape[0]):
            for j in range(pivot.shape[1]):
                val = pivot.values[i, j]
                text_color = "white" if vmax and val > vmax * 0.6 else "#1a1a1a"
                ax.text(j, i, int(val), ha="center", va="center", color=text_color, fontsize=10)

        fig.colorbar(im, ax=ax, label="count", fraction=0.046, pad=0.04)
        fig.tight_layout()

        pdf.savefig(fig)
        plt.close(fig)

    def write_pdf(self) -> None:
        pdf_path = f"{self.output_prefix}_summary_report.pdf"
        with PdfPages(pdf_path) as pdf:
            sections = []
            if self.scan_type_counts is not None:
                sections.append(("Acquisitions by Scan Type", self.scan_type_counts))
            sections += [(f"Counts by {col}", counts) for col, counts in self.column_counts.items()]
            if self.intent_orientation is not None:
                sections.append(("Counts by Intent x Scan Orientation", self.intent_orientation))
            if self.qsm_orientation is not None and not self.qsm_orientation.empty:
                sections.append(
                    ("QSM Intent by Scan Orientation (Axial / Sagittal)", self.qsm_orientation)
                )
            self._draw_table_pages(pdf, sections)

            if self.intent_orientation is not None:
                self._draw_heatmap_page(pdf)

        logger.info(f"Wrote summary PDF report: {pdf_path}")

    def write_unclassified_csv(self) -> Optional[str]:
        """Writes the full image rows that no ScanTypeClassifier rule matched,
        so they can be reviewed and turned into new rules."""
        if self.scan_types is None:
            return None
        unclassified = self.df[self.scan_types == ScanTypeClassifier.UNCLASSIFIED]
        unclassified = unclassified.sort_values(["acquisition", "file"])
        out_path = f"{self.output_prefix}_unclassified.csv"
        unclassified.to_csv(out_path, index=False)
        logger.info(f"Wrote {len(unclassified)} unclassified image rows: {out_path}")
        return out_path

    def run(self) -> None:
        self.compute()
        self.write_pdf()


###############################################################################
# Analysis Results
###############################################################################

# Cancelled runs were stopped on purpose, so they get their own status
# rather than counting as failures.
FAILURE_STATES = {"failed"}
CANCELLED_STATES = {"cancelled"}
SUCCESS_STATES = {"complete"}
STATUS_LABELS = {"pass": "Pass", "fail": "Fail", "cancelled": "Cancelled", "other": "Other"}


class AnalysisResults:
    def __init__(self, fc):

        rows = []

        #analyses = fc.SDKClient.get_analyses(project_id=fc.project.id)

        analyses_list = fc.RestClient.get(f"/api/projects/{fc.project._id}/all/analyses")
        # Project-level analyses
        for analysis in  analyses_list:
            if analysis.parents.subject is not None:
                subject = fc.RestClient.get(f"/api/subjects/{analysis.parents.subject}")
                subject_label = subject.label
            else:
                subject_label = "None"
            if analysis.parents.session is not None:
                session = fc.RestClient.get(f"/api/sessions/{analysis.parents.session}")
                session_label = session.label
            else:
                session_label = "None"
            if analysis.parents.acquisition is not None:
                acquisition = fc.RestClient.get(f"/api/acquisitions/{analysis.parents.acquisition}")
                acquisition_label = acquisition.label
            else:
                acquisition_label = "None"
            job = fc.RestClient.get(f"/api/jobs/{analysis.job}")
            logger.info(f"Analysis: {analysis.label}")

            try:
                finished = job['transitions']['complete']
            except (KeyError, TypeError):
                finished = None

            state = job.state
            if state in SUCCESS_STATES:
                status = "pass"
            elif state in FAILURE_STATES:
                status = "fail"
            elif state in CANCELLED_STATES:
                status = "cancelled"
            else:
                status = "other"

            rows.append(
                {
                    "subject": subject_label,
                    "subject_id": analysis.parents.subject,
                    "session": session_label,
                    "session_id": analysis.parents.session,
                    "acquisition": acquisition_label,
                    "acquisition_id": analysis.parents.acquisition,
                    "analysis_label": analysis.label,
                    "gear_name": analysis.gear_info.name,
                    "gear_version": analysis.gear_info.version,
                    "state": state,
                    "status": status,
                    "created": analysis.created,
                    "finished": finished
                }
            )

        self.df = pd.DataFrame(rows)

        self.df.to_csv(fc.project.label + "_analyses.csv", index=False)


###############################################################################
# Project Summary (human-readable, label-only, no Flywheel IDs)
###############################################################################

class ProjectSummary:
    """Builds a single human-readable summary CSV covering image and analysis
    counts, intended for viewing directly in Flywheel Attachments."""

    def __init__(
        self,
        images_df: pd.DataFrame,
        analyses_df: pd.DataFrame,
        output_prefix: str,
    ):
        self.images_df = images_df
        self.analyses_df = analyses_df
        self.output_prefix = output_prefix

    @staticmethod
    def _parse_list_cell(value) -> List[str]:
        if isinstance(value, list):
            return [str(v) for v in value]
        if pd.isna(value):
            return []
        try:
            parsed = ast.literal_eval(value)
        except (ValueError, SyntaxError, TypeError):
            return [str(value)]
        if isinstance(parsed, (list, set, tuple)):
            return [str(v) for v in parsed]
        return [str(parsed)]

    def _section_rows(self, section: str, df: pd.DataFrame) -> List[Dict[str, str]]:
        rows = [{"section": section, "label": "", "count": ""}]
        for _, r in df.iterrows():
            rows.append({"section": "", "label": r["label"], "count": r["count"]})
        rows.append({"section": "", "label": "", "count": ""})
        return rows

    def build(self) -> pd.DataFrame:
        rows: List[Dict[str, str]] = []

        # --- Image counts ---
        total_images = len(self.images_df)
        total_sessions = self.images_df["session"].nunique() if "session" in self.images_df else 0
        total_subjects = self.images_df["subject"].nunique() if "subject" in self.images_df else 0
        total_acquisitions = (
            self.images_df["acquisition"].nunique() if "acquisition" in self.images_df else 0
        )

        overview = pd.DataFrame(
            [
                {"label": "Total subjects", "count": total_subjects},
                {"label": "Total sessions", "count": total_sessions},
                {"label": "Total acquisitions", "count": total_acquisitions},
                {"label": "Total image files", "count": total_images},
            ]
        )
        rows += self._section_rows("Image Counts", overview)

        # --- Acquisitions by Intent (image type) ---
        if "Intent" in self.images_df.columns:
            intents = self.images_df["Intent"].apply(self._parse_list_cell)
            intent_by_acq = (
                self.images_df.assign(Intent=intents)[["acquisition", "Intent"]]
                .explode("Intent")
                .dropna(subset=["Intent"])
                .drop_duplicates(subset=["acquisition", "Intent"])
            )
            intent_counts = (
                intent_by_acq["Intent"].value_counts().rename_axis("label").reset_index(name="count")
            )
            rows += self._section_rows("Acquisitions by Image Type (Intent)", intent_counts)

        # --- Acquisitions by scan type (see ScanTypeClassifier for the rules) ---
        if all(c in self.images_df.columns for c in ("features", "Intent", "Measurement")):
            classify_df = pd.DataFrame(
                {
                    "features": self.images_df["features"].apply(self._parse_list_cell),
                    "Intent": self.images_df["Intent"].apply(self._parse_list_cell),
                    "Measurement": self.images_df["Measurement"].apply(self._parse_list_cell),
                    "acquisition": self.images_df.get("acquisition", ""),
                    "file": self.images_df.get("file", ""),
                }
            )
            scan_types = classify_df.apply(ScanTypeClassifier.classify_row, axis=1)
            per_acq = scan_type_acquisition_counts(self.images_df, scan_types)
            column_labels = {"DICOM": "DICOM", "NIfTI": "NIfTI", "acquisitions": "all acquisitions"}
            scan_type_counts = pd.DataFrame(
                [
                    {"label": f"{r['scan_type']} - {text}", "count": r[col]}
                    for _, r in per_acq.iterrows()
                    for col, text in column_labels.items()
                ]
            )
            rows += self._section_rows("Acquisitions by Scan Type", scan_type_counts)

        # --- Analysis counts by gear ---
        if not self.analyses_df.empty:
            gear_counts = (
                self.analyses_df["gear_name"]
                .value_counts()
                .rename_axis("label")
                .reset_index(name="count")
            )
            rows += self._section_rows("Analyses by Gear", gear_counts)

            status_counts = (
                self.analyses_df["status"]
                .map(STATUS_LABELS)
                .value_counts()
                .rename_axis("label")
                .reset_index(name="count")
            )
            rows += self._section_rows("Analysis Pass/Fail Counts", status_counts)

            gear_status = (
                self.analyses_df.groupby(["gear_name", "status"])
                .size()
                .reset_index(name="count")
            )
            gear_status["label"] = (
                gear_status["gear_name"]
                + " - "
                + gear_status["status"].map(STATUS_LABELS)
            )
            rows += self._section_rows(
                "Pass/Fail Counts by Gear", gear_status[["label", "count"]]
            )

        return pd.DataFrame(rows, columns=["section", "label", "count"])

    def write_csv(self) -> str:
        out_path = f"{self.output_prefix}_summary.csv"
        self.build().to_csv(out_path, index=False)
        logger.info(f"Wrote project summary: {out_path}")
        return out_path


###############################################################################
# Failed Analyses (per-gear, latest-run-wins)
###############################################################################

class FailedAnalyses:
    """Lists failed analysis runs that do NOT have a later successful run of
    the same gear on the same container (subject + session + acquisition).
    Evaluated independently per gear, so a passing run of one gear never
    clears a failure from a different gear. Cancelled runs are left out
    entirely: someone stopped them on purpose, so they aren't failures.

    Containers are matched by Flywheel ID rather than label, so two
    acquisitions that share a label (e.g. a repeated MPRAGE) stay separate.
    """

    OUTPUT_COLUMNS = [
        "subject",
        "session",
        "acquisition",
        "gear_name",
        "gear_version",
        "analysis_label",
        "state",
        "created",
    ]
    GROUP_COLUMNS = ["subject_id", "session_id", "acquisition_id", "gear_name"]

    def __init__(self, analyses_df: pd.DataFrame, output_prefix: str):
        self.analyses_df = analyses_df
        self.output_prefix = output_prefix

    def build(self) -> pd.DataFrame:
        df = self.analyses_df.copy()
        if df.empty:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        df["created"] = pd.to_datetime(df["created"], errors="coerce", utc=True)
        out_rows = []

        for _, group in df.groupby(self.GROUP_COLUMNS, dropna=False):
            success_times = group.loc[group["status"] == "pass", "created"]
            last_success_time = success_times.max() if not success_times.empty else pd.NaT

            for _, run in group[group["state"] == "failed"].iterrows():
                if pd.notna(last_success_time) and pd.notna(run["created"]) and run["created"] < last_success_time:
                    continue  # cleared by a later successful run of the same gear
                out_rows.append(run)

        if not out_rows:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        return (
            pd.DataFrame(out_rows)[self.OUTPUT_COLUMNS]
            .sort_values(["subject", "session", "gear_name", "created"])
            .reset_index(drop=True)
        )

    def write_csv(self) -> str:
        out_path = f"{self.output_prefix}_failed_analyses.csv"
        self.build().to_csv(out_path, index=False)
        logger.info(f"Wrote failed analyses report: {out_path}")
        return out_path


###############################################################################
# Flywheel Attachments
###############################################################################

class AttachmentUploader:
    """Uploads local report files to the project's Attachments area so users
    can open them directly in Flywheel."""

    def __init__(self, fc):
        self.fc = fc

    def upload(self, file_path: str) -> None:
        try:
            self.fc.project.upload_file(file_path)
            logger.info(f"Uploaded attachment to Flywheel project: {path.basename(file_path)}")
        except Exception as e:
            logger.error(f"Failed to upload attachment '{file_path}': {e}")


###############################################################################
# Main
###############################################################################


# When Flywheel runs this as a gear it writes the job's settings (including
# the launching user's API key) to config.json, and saves anything left in
# the output folder to the analysis.
GEAR_DIR = "/flywheel/v0"
GEAR_CONFIG = path.join(GEAR_DIR, "config.json")
GEAR_OUTPUT_DIR = path.join(GEAR_DIR, "output")


def connect_as_gear() -> FlywheelConnector:
    with open(GEAR_CONFIG) as f:
        gear_config = json.load(f)
    api_key_input = gear_config.get("inputs", {}).get("api-key")
    if not api_key_input:
        logger.error(
            "No API key was passed to this gear. Check that the uploaded "
            "manifest.json has an 'api-key' input (base: api-key). Inputs "
            f"received: {list(gear_config.get('inputs', {}))}"
        )
        sys.exit(1)
    api_key = api_key_input["key"]
    fc = FlywheelConnector(api_key)
    fc.setProjectFromDestination(gear_config["destination"]["id"])
    # Every report below is written with a relative path, so working from the
    # output folder lands them all in the analysis outputs.
    os.makedirs(GEAR_OUTPUT_DIR, exist_ok=True)
    os.chdir(GEAR_OUTPUT_DIR)
    return fc


def connect_from_manager_conf() -> FlywheelConnector:
    config = Config(path.join(".", "Manager.conf"))
    api_key = os.getenv("FLYWHEEL_API_KEY") or config.get("APIKey")
    project_name = config.get("project")

    if not api_key or not project_name:
        logger.error("Missing APIKey (or FLYWHEEL_API_KEY) or project in Manager.conf.")
        sys.exit(1)

    logger.info(f"Connecting to Flywheel with project prefix: {project_name}")
    fc = FlywheelConnector(api_key)
    fc.setProject(project_name)
    return fc


def main() -> None:
    parser = argparse.ArgumentParser(description="PipelineStatusTool")
    parser.parse_args()

    if path.exists(GEAR_CONFIG):
        logger.info("Running as a Flywheel gear")
        fc = connect_as_gear()
    else:
        fc = connect_from_manager_conf()

    #try:
    II = ImageInformation(fc)
    SS = SummaryStats(fc.project.label + "_images.csv", fc.project.label)
    SS.run()
    AR = AnalysisResults(fc)

    summary_path = ProjectSummary(II.df, AR.df, fc.project.label).write_csv()
    failed_path = FailedAnalyses(AR.df, fc.project.label).write_csv()
    unclassified_path = SS.write_unclassified_csv()

    # In gear mode these files are also saved to the analysis outputs; they
    # go to project Attachments as well so they're easy to find.
    report_paths = [
        fc.project.label + "_images.csv",
        fc.project.label + "_analyses.csv",
        f"{fc.project.label}_summary_report.pdf",
        summary_path,
        failed_path,
        unclassified_path,
    ]
    uploader = AttachmentUploader(fc)
    for report_path in report_paths:
        if report_path and path.exists(report_path):
            uploader.upload(report_path)
    #except Exception as e:
    #    logger.error(f"Fatal error: {e}")
    #    sys.exit(1)


if __name__ == "__main__":
    main()
