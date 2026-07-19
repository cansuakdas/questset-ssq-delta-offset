# GitHub Upload Guide

This guide updates the existing GitHub repository with the fully English version of the project.

## Recommended method: GitHub CLI

1. Open Terminal and move to the extracted project directory:

```bash
cd ~/Desktop/questset-ssq-delta-offset
```

2. Confirm that the correct files are present:

```bash
pwd
ls
```

3. Replace the contents of the existing repository with this English version, then run:

```bash
git status
git add .
git commit -m "Convert repository documentation and code comments to English"
git push origin main
```

The repository will be updated at:

```text
https://github.com/cansuakdas/questset-ssq-delta-offset
```

## Recreate the repository from scratch

Only use this section when starting from a new local folder without a `.git` directory.

```bash
cd ~/Desktop/questset-ssq-delta-offset
git init
git add .
git commit -m "Initial English release"
git branch -M main
gh repo create questset-ssq-delta-offset \
  --public \
  --source=. \
  --remote=origin \
  --push
```

## Final checks

Before pushing, verify that no dataset files or large generated outputs are staged:

```bash
git status
```

Real participant CSV files under `data/` and generated files under `outputs/` should not appear. The included `.gitignore` prevents these files from being committed.
