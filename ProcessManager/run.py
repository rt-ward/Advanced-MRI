#!/usr/bin/env python3
"""Pipeline Manager Tool.

Scans a Flywheel project and launches the QSMxT and QSM-MEDI gears on
acquisitions that contain QSM input files.
"""

import datetime
import logging
import sys
from dataclasses import dataclass, field

import flywheel
from fw_client import FWClient
from fw_gear.context import GearContext

###############################################################################
# Logging Setup
###############################################################################

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_handler)

###############################################################################
# Flywheel Connector
###############################################################################


class FlywheelConnector:
    """Holds the REST and SDK clients plus the project being processed.

    The SDK client is provided by the gear context (``fw-gear`` builds it from
    the ``api-key`` input). The raw REST client is created here from the same
    API key, since ``fw-gear`` does not expose one.
    """

    def __init__(self, sdk_client: flywheel.Client, api_key: str):
        self.api_key = api_key
        self.project = None
        self.rest_client = FWClient(api_key=api_key)
        self.sdk_client = sdk_client

    def set_project_by_id(self, project_id: str) -> None:
        try:
            self.project = self.sdk_client.get_project(project_id)
        except flywheel.rest.ApiException:
            logger.exception("Cannot fetch project '%s' via SDK", project_id)
            raise
        logger.info("Project set: %s", self.project.label)


###############################################################################
# Analysis Results
###############################################################################

AcqKey = tuple  # (subject label, session label, acquisition label)


#: Canonical Flywheel job states. Source of truth is
#: ``flywheel.models.job_state.JobState`` (flywheel-sdk 22.4.0: a ``str``-enum
#: with exactly five values ``pending, running, failed, complete, cancelled``;
#: no ``held`` and no ``retried`` state). "retried" is derived at runtime from a
#: ``failed`` job whose ``retried`` timestamp is set and whose successor is found
#: via ``previous_job_id``. Kept as validated string literals (not the enum
#: import) to match the raw-REST job dicts read here and the in-house JobPoll
#: pattern this logic is ported from.
_STATE_COMPLETE = "complete"
_IN_PROGRESS_STATES = ("pending", "running")

#: Maximum number of retries Flywheel performs for a job, bounding how far the
#: retry chain is followed (mirrors ``JobPoll.is_job_complete``).
_MAX_JOB_RETRIES = 3


class AnalysisResults:
    """Existing analyses that are completed or in progress, per gear/acquisition.

    ``results[gear_name][(subject, session, acquisition)]`` is a non-``None``
    marker when an analysis of that gear is already **completed** (job state is
    ``complete``) or **in progress** (its ``pending``/``running`` state),
    following any retry chain so a failed-and-retried job is judged by its
    successor's state. It is ``None`` when no such analysis exists (this
    includes analyses whose final job failed or was cancelled with no live
    retry, which may be relaunched).
    """

    def __init__(self, fc: FlywheelConnector):
        self._fc = fc
        self._label_cache: dict = {}
        self.results: dict = {}

        analyses = fc.rest_client.get(f"/api/projects/{fc.project.id}/all/analyses")

        for analysis in analyses:
            gear_info = analysis.get("gear_info")
            job_id = analysis.get("job")
            if not gear_info or not job_id:
                # e.g. uploaded analyses that were not produced by a gear job
                continue

            parents = analysis.get("parents") or {}
            key = (
                self._label("subjects", parents.get("subject")),
                self._label("sessions", parents.get("session")),
                self._label("acquisitions", parents.get("acquisition")),
            )

            marker = self._dedup_marker(job_id)

            per_gear = self.results.setdefault(gear_info.get("name"), {})
            if per_gear.get(key) is None:
                per_gear[key] = marker

    def _dedup_marker(self, job_id: str):
        """Return a non-``None`` marker if the analysis is done or in flight.

        The decision is keyed on the job **state** (``complete`` or
        ``pending``/``running``), not on the presence of a
        ``transitions.complete`` timestamp. A ``failed`` job that Flywheel has
        retried is followed to its successor via ``previous_job_id`` (ported
        from ``JobPoll.is_job_complete``), so a retried-and-still-running or
        retried-and-complete analysis is treated as already processed and is
        not relaunched as a duplicate. A final state of ``failed`` or
        ``cancelled`` with no live retry returns ``None`` (relaunchable).
        """
        state = self._final_job_state(job_id)
        if state == _STATE_COMPLETE or state in _IN_PROGRESS_STATES:
            return state
        return None

    def _final_job_state(self, job_id: str):
        """Resolve a job's effective state, following any retry chain.

        While the current job is ``failed`` and has been retried
        (``retried`` timestamp set), hop forward to the successor job
        (``previous_job_id="<id>"``), bounded to the Flywheel retry maximum.
        Returns the state string of the final job in the chain, or ``None`` if
        the original job cannot be read.
        """
        job = self._get_job(job_id)
        if job is None:
            return None

        hops = 0
        while (
            self._job_state(job) == "failed"
            and self._job_retried(job) is not None
            and hops < _MAX_JOB_RETRIES
        ):
            successor = self._find_successor(self._job_id(job))
            if successor is None:
                # Marked retried but successor not found; stop and use this state.
                break
            job = successor
            hops += 1

        return self._job_state(job)

    def _get_job(self, job_id: str):
        """Fetch a job by id via the SDK ``jobs`` finder (typed ``Job``)."""
        try:
            return self._fc.sdk_client.jobs.find_first(f"_id={job_id}")
        except flywheel.rest.ApiException:
            logger.exception("Cannot fetch job '%s'", job_id)
            return None

    def _find_successor(self, job_id: str):
        """Find the job that superseded ``job_id`` when it was retried."""
        try:
            return self._fc.sdk_client.jobs.find_first(f'previous_job_id="{job_id}"')
        except flywheel.rest.ApiException:
            logger.exception("Cannot look up retry successor of job '%s'", job_id)
            return None

    @staticmethod
    def _job_state(job):
        return getattr(job, "state", None)

    @staticmethod
    def _job_retried(job):
        return getattr(job, "retried", None)

    @staticmethod
    def _job_id(job):
        return getattr(job, "id", None)

    def _label(self, kind: str, obj_id) -> str:
        """Return the label of a subject/session/acquisition, with caching."""
        if obj_id is None:
            return "None"
        cache_key = (kind, obj_id)
        if cache_key not in self._label_cache:
            obj = self._fc.rest_client.get(f"/api/{kind}/{obj_id}")
            self._label_cache[cache_key] = obj.label
        return self._label_cache[cache_key]

    def for_gear(self, gear_name: str) -> dict:
        return self.results.get(gear_name, {})


###############################################################################
# Gear tools
###############################################################################


class GearTool:
    """Base wrapper for launching a gear as an analysis on an acquisition."""

    gear_name: str = ""
    qsm_inputs: list = []

    def __init__(self, fc: FlywheelConnector, label: str):
        self.fc = fc
        self.label = label
        self.inputs: dict = {}
        self.inputs_names: list = []
        self.config: dict = {}
        self.destination = None
        self.destination_name = ""
        self.job_id = ""
        self._qsm_input_index = 0

    @classmethod
    def max_qsm_inputs(cls) -> int:
        return len(cls.qsm_inputs)

    def add_qsm_input(self, file_info: "FileInfo") -> None:
        slot = self.qsm_inputs[self._qsm_input_index]
        self.inputs[slot] = file_info.file
        self.inputs_names.append(file_info.file_name)
        self._qsm_input_index += 1
        self.destination = self.fc.sdk_client.get(file_info.acquisition_id)
        self.destination_name = file_info.acquisition

    def set_structural(self, file_info: "FileInfo") -> None:
        """Hook for gears that accept a structural image (default: ignore)."""

    def add_config(self, tag: str, value) -> None:
        self.config[tag] = value

    def run(self) -> None:
        gear = self.fc.sdk_client.lookup(f"gears/{self.gear_name}")
        stamp = datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
        analysis_label = f"{self.gear_name} {stamp}"
        logger.info(
            "%s, %s, %s, %s, %s, %s",
            self.label,
            analysis_label,
            self.gear_name,
            self.inputs_names,
            self.config,
            self.destination_name,
        )
        self.job_id = gear.run(
            analysis_label=analysis_label,
            inputs=self.inputs,
            config=self.config,
            destination=self.destination,
        )
        logger.info("job_id: %s", self.job_id)


class QSMxTGearTool(GearTool):
    gear_name = "qsmxt"
    qsm_inputs = ["input_file", "input_file_opt", "input_file_opt2"]

    def set_structural(self, file_info: "FileInfo") -> None:
        self.inputs["anatomical"] = file_info.file
        self.inputs_names.append(file_info.file_name)
        self.add_config("premade", "bet")


class QSMMediGearTool(GearTool):
    gear_name = "qsm-medi"
    qsm_inputs = ["input_file", "input_file_opt"]


###############################################################################
# Acquisition Classification and Launch
###############################################################################


@dataclass
class FileInfo:
    subject: str
    session: str
    acquisition: str
    acquisition_id: str
    file: object = field(repr=False)
    file_name: str
    intent: str | None


def _first_intent(classification) -> str | None:
    intent = (classification or {}).get("Intent")
    return intent[0] if intent else None


class AcquisitionClassification:
    """Indexes project files by acquisition and launches the enabled gears."""

    def __init__(self, fc: FlywheelConnector, config: dict):
        self.fc = fc
        self.process_all = config.get("process_all")
        self.do_qsmxt = config.get("do_qsmxt")
        self.do_qsm_medi = config.get("do_qsm_medi")

        # (subject, session, acquisition) -> [FileInfo, ...]
        self.acquisitions: dict[AcqKey, list[FileInfo]] = {}

        for subject in fc.project.subjects.iter():
            for session in subject.sessions.iter():
                for acquisition in session.acquisitions.iter():
                    key = (subject.label, session.label, acquisition.label)
                    self.acquisitions[key] = [
                        FileInfo(
                            subject=subject.label,
                            session=session.label,
                            acquisition=acquisition.label,
                            acquisition_id=acquisition.id,
                            file=file,
                            file_name=file.name,
                            intent=_first_intent(file.classification),
                        )
                        for file in acquisition.files
                    ]

    def launch_gears(self, analyses: AnalysisResults) -> None:
        for key, files in self.acquisitions.items():
            qsm_files = [f for f in files if f.intent == "QSM"]
            if not qsm_files:
                continue
            structural = next((f for f in files if f.intent == "Structural"), None)
            label = "/".join(key)

            self._launch(QSMxTGearTool, self.do_qsmxt, key, label, qsm_files,
                         structural, analyses)
            self._launch(QSMMediGearTool, self.do_qsm_medi, key, label, qsm_files,
                         structural, analyses)

    def _should_run(self, tool_cls, enabled, key, analyses: AnalysisResults) -> bool:
        if not enabled:
            return False
        if self.process_all:
            return True
        # Not analyzed yet, or no completed/in-progress analysis exists
        # (in-progress now including a failed job whose retry is still running).
        return analyses.for_gear(tool_cls.gear_name).get(key) is None

    def _launch(self, tool_cls, enabled, key, label, qsm_files, structural, analyses):
        if not self._should_run(tool_cls, enabled, key, analyses):
            return
        if len(qsm_files) > tool_cls.max_qsm_inputs():
            logger.warning(
                "Skipping %s for %s: %d QSM files, gear accepts at most %d",
                tool_cls.gear_name, label, len(qsm_files), tool_cls.max_qsm_inputs(),
            )
            return

        # Guard this single gear-launch attempt (SDK get/lookup/run for one
        # gear on one acquisition) so a transient Flywheel API failure is
        # logged and skipped rather than aborting the whole project scan. The
        # loop in launch_gears then proceeds to the next gear/acquisition.
        try:
            tool = tool_cls(self.fc, label)
            if structural:
                tool.set_structural(structural)
            for file_info in qsm_files:
                tool.add_qsm_input(file_info)
            tool.run()
        except flywheel.rest.ApiException:
            logger.exception(
                "Skipping %s launch for %s: Flywheel API error",
                tool_cls.gear_name, label,
            )


###############################################################################
# Main
###############################################################################


def _get_api_key(context: GearContext) -> str:
    """Return the API key supplied via the gear's ``api-key`` input."""
    for inp in context.config.inputs.values():
        if inp.get("base") == "api-key" and inp.get("key"):
            return inp["key"]
    raise ValueError("The 'api-key' gear input is required")


def main(context: GearContext) -> None:
    config_opts = context.config.opts

    sdk_client = context.client
    analysis = sdk_client.get_analysis(context.config.destination["id"])
    project_id = analysis.parent["id"]

    api_key = _get_api_key(context)

    fc = FlywheelConnector(sdk_client, api_key)
    fc.set_project_by_id(project_id)

    analyses = AnalysisResults(fc)
    classification = AcquisitionClassification(fc, config_opts)
    classification.launch_gears(analyses)


if __name__ == "__main__":
    with GearContext() as gear_context:
        main(gear_context)
