#!/usr/bin/env python3
"""Flywheel gear entrypoint for mri_reface 0.3.5.

Flow:
  1. Read /flywheel/v0/config.json.
  2. Stage the input in a scratch dir, in the form mri_reface wants:
       NIfTI -> uncompressed .nii (mri_reface does not read .nii.gz)
       DICOM zip -> a directory holding only that series' DICOM files
     File names are simplified (extra periods -> dashes), per the author's
     advice that periods can confuse mri_reface's name parsing.
  3. Run:  <mri_reface> <input> <outdir> -imType <type> [extra args]
  4. Copy results to /flywheel/v0/output (gzip NIfTI, zip DICOM, keep renders,
     drop registration files unless asked).

Standard library only.
"""

import glob
import gzip
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

FLYWHEEL = Path(os.environ.get("FLYWHEEL", "/flywheel/v0"))
CONFIG_PATH = FLYWHEEL / "config.json"
OUTPUT_DIR = FLYWHEEL / "output"
WORK_DIR = FLYWHEEL / "work"

# ---------------------------------------------------------------------------
# How mri_reface is launched inside the image.
# None = auto-detect from the candidates below. If auto-detection picks the
# wrong thing, set this to the exact command, e.g. "/opt/mri_reface/run_mri_reface.sh /opt/mcr/v912"
# (the docker run line in NITRC's run_mri_reface_docker.sh shows it).
# ---------------------------------------------------------------------------
REFACE_COMMAND = None
CANDIDATE_EXES = ["run_mri_reface", "run_mri_reface.sh", "mri_reface"]
CANDIDATE_DIRS = ["/opt", "/usr/local", "/home", "/app", "/mri_reface"]

# Registration by-products that mri_reface writes next to the refaced image.
TRANSFORM_PATTERN = re.compile(r"_to_MCALT_.*(Affine|Warp)", re.IGNORECASE)

log = logging.getLogger("mri-reface")


# --------------------------------------------------------------------------- helpers
def load_config() -> dict:
    if not CONFIG_PATH.exists():
        log.error("No config.json at %s; is this running inside a Flywheel job?", CONFIG_PATH)
        sys.exit(1)
    with CONFIG_PATH.open() as f:
        return json.load(f)


def split_name(filename: str):
    """Return (stem, kind) where kind is 'nifti', 'nifti_gz', 'zip', 'dcm' or None."""
    low = filename.lower()
    for ext, kind in ((".nii.gz", "nifti_gz"), (".nii", "nifti"),
                      (".dicom.zip", "zip"), (".dcm.zip", "zip"), (".zip", "zip"),
                      (".dcm", "dcm"), (".dicom", "dcm")):
        if low.endswith(ext):
            return filename[: -len(ext)], kind
    return Path(filename).stem, None


def safe_stem(stem: str) -> str:
    """Periods and odd characters -> dashes (mri_reface parses names on '.')."""
    s = re.sub(r"[^A-Za-z0-9_-]+", "-", stem).strip("-")
    return s or "input"


def find_mcr_root():
    for var in ("MCRROOT", "MCR_ROOT", "MATLAB_RUNTIME", "MCR_PATH"):
        val = os.environ.get(var)
        if val and Path(val).is_dir():
            return val
    for pattern in ("/opt/mcr/*", "/opt/matlab-runtime/*", "/opt/MATLAB/MATLAB_Runtime/*",
                    "/usr/local/MATLAB/MATLAB_Runtime/*", "/opt/matlabruntime/*", "/opt/mcr"):
        for d in sorted(glob.glob(pattern)):
            if Path(d, "runtime", "glnxa64").is_dir():
                return d
    return None


def find_reface_command() -> list:
    if REFACE_COMMAND:
        return shlex.split(REFACE_COMMAND)

    exe = None
    for name in CANDIDATE_EXES:
        exe = shutil.which(name)
        if exe:
            break
    if not exe:
        for base in CANDIDATE_DIRS:
            for name in CANDIDATE_EXES:
                hits = glob.glob(f"{base}/**/{name}", recursive=True)
                hits = [h for h in hits if os.access(h, os.X_OK) and Path(h).is_file()]
                if hits:
                    exe = sorted(hits, key=len)[0]
                    break
            if exe:
                break
    if not exe:
        log.error("Could not find mri_reface in the image (looked for %s). "
                  "Set REFACE_COMMAND in run.py.", ", ".join(CANDIDATE_EXES))
        sys.exit(1)

    cmd = [exe]
    # MATLAB-compiled launchers (run_<app>.sh) take the Runtime root as arg 1.
    name = Path(exe).name
    if name.startswith("run_") and name.endswith(".sh"):
        try:
            text = Path(exe).read_text(errors="ignore")
        except OSError:
            text = ""
        if "MCRROOT=\"$1\"" in text or "MCRROOT=$1" in text or "<deployedMCRroot>" in text:
            mcr = find_mcr_root()
            if not mcr:
                log.error("%s needs the MATLAB Runtime path, but none was found. "
                          "Set REFACE_COMMAND in run.py.", exe)
                sys.exit(1)
            cmd.append(mcr)
    return cmd


# --------------------------------------------------------------------------- staging
def stage_input(src: Path) -> tuple:
    """Return (path_to_pass_to_mri_reface, safe_stem, kind)."""
    stem, kind = split_name(src.name)
    stem = safe_stem(stem)
    stage = WORK_DIR / "in"
    stage.mkdir(parents=True, exist_ok=True)

    if kind == "nifti":
        dst = stage / f"{stem}.nii"
        shutil.copyfile(src, dst)
        return dst, stem, "nifti"

    if kind == "nifti_gz":
        dst = stage / f"{stem}.nii"
        with gzip.open(src, "rb") as fin, dst.open("wb") as fout:
            shutil.copyfileobj(fin, fout)
        log.info("Decompressed .nii.gz (mri_reface needs uncompressed .nii)")
        return dst, stem, "nifti"

    if kind in ("zip", "dcm"):
        dcm_dir = stage / stem
        dcm_dir.mkdir(parents=True, exist_ok=True)
        if kind == "dcm":
            shutil.copyfile(src, dcm_dir / src.name)
        else:
            with zipfile.ZipFile(src) as zf:
                n = 0
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    base = Path(info.filename).name
                    # skip OS junk and non-DICOM side files
                    if (not base or base.startswith(".") or "__MACOSX" in info.filename
                            or base.lower() in ("dicomdir",) or base.lower().endswith((".txt", ".json", ".xml"))):
                        continue
                    n += 1
                    target = dcm_dir / f"{n:05d}_{safe_stem(base)}.dcm"
                    with zf.open(info) as fin, target.open("wb") as fout:
                        shutil.copyfileobj(fin, fout)
            log.info("Extracted %d DICOM files into a flat series directory", n)
            if n == 0:
                log.error("The zip contained no DICOM files.")
                sys.exit(1)
        return dcm_dir, stem, "dicom"

    log.error("Unsupported input '%s'. Use .nii, .nii.gz, or a zip of one DICOM series.", src.name)
    sys.exit(1)


# --------------------------------------------------------------------------- outputs
def is_dicom(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            f.seek(128)
            return f.read(4) == b"DICM"
    except OSError:
        return False


def collect_outputs(tool_out: Path, stem: str, cfg: dict) -> list:
    gz = cfg.get("gzip_nifti", True)
    keep_xfm = cfg.get("save_transforms", False)
    saved = []

    # Any directory full of DICOMs -> one zip per directory.
    dicom_dirs = set()
    for p in tool_out.rglob("*"):
        if p.is_file() and is_dicom(p):
            dicom_dirs.add(p.parent)
    for i, d in enumerate(sorted(dicom_dirs)):
        suffix = "" if len(dicom_dirs) == 1 else f"_{i + 1}"
        name = f"{stem}_deFaced{suffix}.dicom.zip"
        with zipfile.ZipFile(OUTPUT_DIR / name, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(d.iterdir()):
                if f.is_file():
                    zf.write(f, arcname=f"{stem}_deFaced/{f.name}")
        saved.append(name)

    for p in sorted(tool_out.rglob("*")):
        if not p.is_file() or p.parent in dicom_dirs:
            continue
        if TRANSFORM_PATTERN.search(p.name) and not keep_xfm:
            log.debug("Skipping registration file %s", p.name)
            continue
        if p.name.lower().endswith(".nii") and gz:
            name = p.name + ".gz"
            with p.open("rb") as fin, gzip.open(OUTPUT_DIR / name, "wb", compresslevel=6) as fout:
                shutil.copyfileobj(fin, fout)
        else:
            name = p.name
            shutil.copyfile(p, OUTPUT_DIR / name)
        saved.append(name)
    return saved


# --------------------------------------------------------------------------- main
def main() -> int:
    cfg_all = load_config()
    cfg = cfg_all.get("config", {})
    debug = bool(cfg.get("debug", False))
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    try:
        src = Path(cfg_all["inputs"]["input_file"]["location"]["path"])
    except KeyError:
        log.error("Required input 'input_file' was not provided.")
        return 1
    log.info("Input: %s", src.name)

    staged, stem, kind = stage_input(src)
    tool_out = WORK_DIR / "out"
    tool_out.mkdir(parents=True, exist_ok=True)

    cmd = find_reface_command() + [str(staged), str(tool_out)]
    im_type = str(cfg.get("imType", "") or "").strip()
    if im_type:
        cmd += ["-imType", im_type]
    elif kind == "dicom":
        log.warning("No imType given; the author strongly recommends setting it for DICOM input.")
    if cfg.get("extra_args"):
        cmd += shlex.split(cfg["extra_args"])

    log.info("Running: %s", shlex.join(cmd))
    if debug:
        log.debug("Environment:\n%s", json.dumps(dict(os.environ), indent=2))

    # mri_reface writes temp files to $TMPDIR; keep them in the job's work dir.
    env = dict(os.environ, TMPDIR=str(WORK_DIR / "tmp"))
    Path(env["TMPDIR"]).mkdir(exist_ok=True)

    proc = subprocess.run(cmd, cwd=WORK_DIR, env=env)
    if proc.returncode != 0:
        log.error("mri_reface exited with code %d", proc.returncode)
        return proc.returncode

    produced = sorted(str(p.relative_to(tool_out)) for p in tool_out.rglob("*") if p.is_file())
    log.debug("mri_reface produced: %s", produced)
    if not any("deFaced" in p or "refaced" in p.lower() for p in produced):
        log.error("mri_reface finished but no refaced image was found in its output: %s", produced)
        return 1

    saved = collect_outputs(tool_out, stem, cfg)
    log.info("Saved %d output file(s): %s", len(saved), ", ".join(saved))
    return 0


if __name__ == "__main__":
    sys.exit(main())
