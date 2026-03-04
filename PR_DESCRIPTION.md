# Improve Code Quality and Documentation

This PR adds code quality tooling and expands developer documentation on top of the existing development environment setup. It also incorporates the latest changes from upstream, including the new qsm-medi gear.

## What's New in This PR

### Code Quality Enhancements

- **Docstring linting**: Added numpy-style docstring convention checking with ruff (test files excluded)
- **Module docstrings**: Added missing module-level documentation to `ImageUploading/fwImageUpload.py`
- **Exception handling**: Replaced broad `except Exception` with specific exception types (`OSError`, `ValueError`, `flywheel.ApiException`, `KeyError`, `AttributeError`, `zipfile.BadZipFile`) for better error diagnosis and debugging
- **Blind exception checking**: Enabled `BLE` rule to prevent overly broad exception handlers

### Configuration Improvements

- **Dependency groups**: Updated to modern `[dependency-groups]` syntax (replacing deprecated `[tool.uv]`)
- **Test paths**: Fixed pytest configuration to correctly discover tests in `ImageUploading/tests` and `QSMxT/tests`
- **Coverage paths**: Corrected coverage reporting to use actual directory names
- **Missing dependency**: Added `fw-client>=0.1.0` as explicit dependency

### Documentation

- **Developer guides**: Added comprehensive setup, testing, and code quality instructions to all component READMEs
- **Markdown consistency**: Standardized list markers (`-` instead of `+`) and arrows (`→` instead of `=>`)
- **Development workflow**: Added clear instructions for using `uv` for dependency management, testing, and linting

### Repository Cleanup

- Removed unused root-level placeholder files (`main.py`, empty `__init__.py`)

### Upstream Integration

- **Merged latest upstream changes**: This branch includes all changes from upstream/main, including the new qsm-medi gear
- **Conflict resolution**: All merge conflicts resolved in favor of improved versions while preserving new upstream content

## Testing

- Updated test to work with specific exception types
- All 14 tests passing with 71% coverage
- All ruff checks passing

## Benefits

These changes provide:

- Automated docstring quality checks
- More precise error handling for easier debugging
- Consistent documentation formatting
- Correct test and coverage configuration
- Clear developer onboarding documentation
- Full compatibility with latest upstream changes

All changes are backward compatible with existing functionality.

## ⚠️ Security Notice: Exposed API Key in Git History

**Critical:** This repository still contains an exposed Flywheel API key in its git history (commit `1849112` from December 2025). While the key was replaced with a placeholder in commit `0cba685`, it remains accessible in the repository's history.

### Immediate Actions Required

1. **Revoke the exposed API key** in Flywheel and generate a new one
2. **Clean the git history** to permanently remove the secret

### Cleaning Git History

Install git-filter-repo (recommended method):

```bash
# macOS with Homebrew
brew install git-filter-repo

# Linux with pip
pip3 install git-filter-repo

# Or download directly
curl -O https://raw.githubusercontent.com/newren/git-filter-repo/main/git-filter-repo
chmod +x git-filter-repo
sudo mv git-filter-repo /usr/local/bin/
```

Then clean the repository:

```bash
# Clone a fresh copy
git clone https://github.com/rt-ward/Advanced-MRI.git
cd Advanced-MRI

# Remove the file from all history
git filter-repo --path ImageUploading/fwImageUpload.conf --invert-paths

# Force push to update remote (WARNING: This rewrites history)
git push --force --all
git push --force --tags
```

**Note:** After force-pushing, all collaborators will need to re-clone the repository or reset their local copies.

### Alternative: Using BFG Repo-Cleaner

```bash
# Install BFG
brew install bfg  # macOS
# Or download from: https://rtyley.github.io/bfg-repo-cleaner/

# Clone a mirror
git clone --mirror https://github.com/rt-ward/Advanced-MRI.git

# Remove the file
bfg --delete-files fwImageUpload.conf Advanced-MRI.git

# Clean up and push
cd Advanced-MRI.git
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push --force
```
