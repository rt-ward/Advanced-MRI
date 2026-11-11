# mri-reface Flywheel gear

Wraps **mri_reface 0.3.5** (Christopher G. Schwarz, Mayo Clinic;
https://www.nitrc.org/projects/mri_reface) as a Flywheel gear. The face in a
head scan is replaced with a population-average face, which protects against
face recognition while changing brain measurements less than defacing.

> mri_reface is free for **non-commercial research use only**. Keep that in
> mind before uploading to a shared or commercial Flywheel site.

## What the gear does

| Input | What happens | Outputs |
|---|---|---|
| `.nii` / `.nii.gz` | gunzipped (mri_reface can't read `.gz`), refaced | `<name>_deFaced.nii.gz`, before/after render(s) |
| `.dicom.zip` / `.zip` (one series) | flattened into one folder of DICOMs, refaced, converted back to DICOM by mri_reface | `<name>_deFaced.dicom.zip`, `<name>_deFaced.nii.gz`, render(s) |

File names are simplified (periods and spaces become dashes), as recommended
on the mri_reface forum. Registration by-products (`*_to_MCALT_*Affine.txt`,
`*Warp.nii`) are dropped unless `save_transforms` is on.

### Config options

| Option | Default | Meaning |
|---|---|---|
| `imType` | `T1` | Passed to `-imType`. MRI/CT: T1, T2, FLAIR, T2st, ASL, CT. Empty = let mri_reface decide. |
| `gzip_nifti` | `true` | Save the refaced NIfTI as `.nii.gz` |
| `save_transforms` | `false` | Keep registration files |
| `extra_args` | `""` | Extra mri_reface flags, passed as-is |
| `debug` | `false` | Verbose logging |

## 1. Load and tag the base image

Download `mri_reface_0.3.5_docker.zip` from NITRC, unzip it, and load or
build the image as its instructions say. It's named `mri_reface`. Then pin it:

```bash
docker images | grep mri_reface                # confirm it's there
docker tag mri_reface:latest mri_reface:0.3.5
```

## 2. Check two things (one-time, ~1 minute)

```bash
# a) the container user (Dockerfile assumes reface-user)
docker inspect --format '{{.Config.User}}' mri_reface:0.3.5

# b) how NITRC's wrapper launches the tool inside the container
grep -n "docker run" run_mri_reface_docker.sh
```

* If (a) isn't `reface-user`, build with `--build-arg REFACE_USER=<that user>`.
* `run.py` auto-detects the launcher (`run_mri_reface`, `run_mri_reface.sh` or
  `mri_reface`, adding the MATLAB Runtime path if needed). If the job log
  shows the wrong command, copy the command from (b) into `REFACE_COMMAND` at
  the top of `run.py`.

## 3. Build, test locally, upload (Flywheel CLI `flyw`, alias `fw-beta`)

```bash
flyw login <API_KEY>
cd mri-reface-gear

flyw gear build .     # docker build + copies the image's ENV (MATLAB Runtime
                      # paths, PATH, LD_LIBRARY_PATH) into manifest.json. Don't skip.

flyw gear config --new .
flyw gear config -i input_file=/path/to/T1.nii.gz -c imType=T1 .
flyw gear run --prepare .          # prints a staging dir
flyw gear run <staging dir>

flyw gear upload .
```

For a new upload, bump `version` and the matching image tag in
`custom.gear-builder.image`, e.g. `0.1.1_0.3.5`.

## Quick test with plain Docker

```bash
docker build -t mri-reface:0.1.0_0.3.5 .
mkdir -p test/input/input_file test/output
cp /path/to/T1.nii.gz test/input/input_file/
cat > test/config.json <<'EOF'
{"config": {"imType": "T1", "gzip_nifti": true, "save_transforms": false,
            "extra_args": "", "debug": true},
 "inputs": {"input_file": {"base": "file",
   "location": {"path": "/flywheel/v0/input/input_file/T1.nii.gz", "name": "T1.nii.gz"}}}}
EOF
chmod -R a+rwX test
docker run --rm \
  -v "$PWD/test/input:/flywheel/v0/input" \
  -v "$PWD/test/output:/flywheel/v0/output" \
  -v "$PWD/test/config.json:/flywheel/v0/config.json" \
  mri-reface:0.1.0_0.3.5 python3 /flywheel/v0/run.py
```

## Notes

* **Resources:** mri_reface runs ANTs nonlinear registration. Expect several
  minutes to tens of minutes per scan. Ask your site admin for at least 4 GB RAM
  for the gear.
* **DICOM input:** the zip must hold **one series only**. The author does not
  recommend the direct-DICOM workflow for PET, because it doesn't correct for
  motion between frames. Convert PET to NIfTI first.
* **Citation:** Schwarz et al., NeuroImage 2021 and 2023
  (doi:10.1016/j.neuroimage.2023.120199).
