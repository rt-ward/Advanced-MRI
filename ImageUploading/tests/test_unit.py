import json
import os
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)
import fwImageUpload  # noqa: E402
from fwImageUpload import FlywheelConnector  # noqa: E402

# --------------------------------------------------
# Helpers
# --------------------------------------------------


class MockMeta:
    """Mock pydicom metadata."""

    def __init__(self):
        self.data = {
            (0x0020, 0x000E): MagicMock(value="SERIES123"),
            (0x0008, 0x0020): MagicMock(value="20240101"),
            (0x0020, 0x0011): MagicMock(value=5),
        }

    def get(self, key):
        return self.data[key]


def make_mock_project():
    """Create nested Flywheel mock structure."""
    acquisition = MagicMock()
    acquisition.files = []

    session = MagicMock()
    session.acquisitions.iter.return_value = [acquisition]

    subject = MagicMock()
    subject.sessions.iter.return_value = [session]

    project = MagicMock()
    project.subjects.iter.return_value = [subject]

    return project


# --------------------------------------------------
# FlywheelConnector
# --------------------------------------------------


@patch("fwImageUpload.FWClient")
@patch("fwImageUpload.flywheel.Client")
def test_flywheelconnector_init(mock_sdk, mock_rest):
    fc = FlywheelConnector("abc123")

    assert fc.APIKey == "abc123"
    mock_rest.assert_called_once()
    mock_sdk.assert_called_once()
    assert fc.imageList == []
    assert fc.sessionList == []


@patch("fwImageUpload.FWClient")
@patch("fwImageUpload.flywheel.Client")
def test_set_project_success(mock_sdk, mock_rest):
    mock_project = MagicMock()
    mock_project.label = "TEST_PROJECT"

    rest = mock_rest.return_value
    rest.get.return_value = [MagicMock(label="TEST_PROJECT", _id="123")]

    sdk = mock_sdk.return_value
    sdk.get_project.return_value = mock_project

    fc = fwImageUpload.FlywheelConnector("key")
    fc.setProject("TEST")

    assert fc.project == mock_project


@patch("fwImageUpload.FWClient")
@patch("fwImageUpload.flywheel.Client")
def test_set_project_not_found(mock_sdk, mock_rest):
    rest = mock_rest.return_value
    rest.get.return_value = []

    fc = fwImageUpload.FlywheelConnector("key")

    with pytest.raises(ValueError):
        fc.setProject("MISSING")


def test_collect_image_information_no_project():
    fc = fwImageUpload.FlywheelConnector.__new__(fwImageUpload.FlywheelConnector)
    fc.project = None

    with pytest.raises(RuntimeError):
        fc.CollectImageInformation()


def test_collect_session_information_no_project():
    fc = fwImageUpload.FlywheelConnector.__new__(fwImageUpload.FlywheelConnector)
    fc.project = None

    with pytest.raises(RuntimeError):
        fc.CollectSessionInformation()


# --------------------------------------------------
# Config
# --------------------------------------------------


def test_config_load_success(tmp_path):
    config_data = {"APIKey": "123", "project": "TEST"}

    file = tmp_path / "conf.json"
    file.write_text(json.dumps(config_data))

    cfg = fwImageUpload.Config(str(file))

    assert cfg.get("APIKey") == "123"
    assert cfg.get("project") == "TEST"


def test_config_load_failure():
    with pytest.raises(FileNotFoundError):
        fwImageUpload.Config("missing.json")


# --------------------------------------------------
# UploadImageData
# --------------------------------------------------


@patch("fwImageUpload.zipfile.ZipFile")
def test_upload_init_success(mock_zip):
    fc = MagicMock()

    uploader = fwImageUpload.UploadImageData(fc, "test.zip")

    mock_zip.assert_called_once_with("test.zip")
    assert uploader.baseName == "test"


@patch("fwImageUpload.zipfile.ZipFile")
def test_upload_init_failure(mock_zip):
    mock_zip.side_effect = zipfile.BadZipFile("bad zip")

    with pytest.raises(zipfile.BadZipFile):
        fwImageUpload.UploadImageData(MagicMock(), "bad.zip")


@patch("fwImageUpload.pydicom.dcmread")
@patch("fwImageUpload.zipfile.ZipFile")
def test_upload_images_basic(mock_zip, mock_dcmread, tmp_path):
    """End-to-end uploadImages test with mocks."""
    # ---- Setup ZIP ----
    zip_inst = mock_zip.return_value
    zip_inst.namelist.return_value = [
        "root/NACC001/acq1/file1.dcm",
        "root/NACC001/acq1/file2.dcm",
    ]

    def extract_mock(src, path):
        full = Path(path) / src
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text("fake")

    zip_inst.extract.side_effect = extract_mock

    # ---- DICOM ----
    mock_dcmread.return_value = MockMeta()

    # ---- Flywheel hierarchy ----
    acquisition = MagicMock()
    acquisition.upload_file = MagicMock()

    session = MagicMock()
    session.acquisitions.find_first.return_value = acquisition

    subject = MagicMock()
    subject.sessions.find_first.return_value = session

    project = MagicMock()
    project.subjects.find_first.return_value = subject

    fc = MagicMock()
    fc.project = project

    # ---- Run ----
    uploader = fwImageUpload.UploadImageData(fc, "fake.zip")

    with patch("tempfile.TemporaryDirectory") as tmpdir:
        tmpdir.return_value.__enter__.return_value = tmp_path

        uploader.uploadImages(segIndex=1)

    # ---- Assert upload called ----
    assert acquisition.upload_file.called


@patch("fwImageUpload.pydicom.dcmread")
@patch("fwImageUpload.zipfile.ZipFile")
def test_upload_images_no_nacc(mock_zip, mock_dcmread, tmp_path):
    zip_inst = mock_zip.return_value
    zip_inst.namelist.return_value = ["root/NOID/file.dcm"]

    fc = MagicMock()
    fc.project = MagicMock()

    uploader = fwImageUpload.UploadImageData(fc, "fake.zip")

    with patch("tempfile.TemporaryDirectory") as tmpdir:
        tmpdir.return_value.__enter__.return_value = tmp_path

        uploader.uploadImages(segIndex=1)

    # Should silently skip
    assert True


# --------------------------------------------------
# main()
# --------------------------------------------------


@patch("fwImageUpload.UploadImageData")
@patch("fwImageUpload.FlywheelConnector")
@patch("fwImageUpload.Config")
def test_main_success(
    mock_config,
    mock_connector,
    mock_uploader,
    monkeypatch,
):
    # ---- Config ----
    cfg = MagicMock()
    cfg.get.side_effect = lambda k: {
        "APIKey": "123",
        "project": "TEST",
    }.get(k)

    mock_config.return_value = cfg

    # ---- Args ----
    monkeypatch.setattr(
        sys,
        "argv",
        ["prog", "-f", "file.zip"],
    )

    monkeypatch.setenv("FLYWHEEL_API_KEY", "123")

    instance = mock_connector.return_value
    uploader = mock_uploader.return_value

    fwImageUpload.main()

    instance.setProject.assert_called_once()
    uploader.uploadImages.assert_called_once()


@patch("fwImageUpload.Config")
def test_main_missing_api_key(mock_config, monkeypatch):
    cfg = MagicMock()
    cfg.get.return_value = None
    mock_config.return_value = cfg

    monkeypatch.setattr(
        sys,
        "argv",
        ["prog", "-f", "file.zip"],
    )

    monkeypatch.delenv("FLYWHEEL_API_KEY", raising=False)

    with pytest.raises(ValueError):
        fwImageUpload.main()


@patch("fwImageUpload.Config")
@patch("fwImageUpload.FlywheelConnector")
def test_main_fatal_error(
    mock_connector,
    mock_config,
    monkeypatch,
):
    cfg = MagicMock()
    cfg.get.side_effect = lambda k: {
        "APIKey": "123",
        "project": "TEST",
    }.get(k)

    mock_config.return_value = cfg

    monkeypatch.setenv("FLYWHEEL_API_KEY", "123")
    monkeypatch.setattr(
        sys,
        "argv",
        ["prog", "-f", "file.zip"],
    )

    mock_connector.side_effect = ValueError("boom")

    with pytest.raises(SystemExit):
        fwImageUpload.main()
