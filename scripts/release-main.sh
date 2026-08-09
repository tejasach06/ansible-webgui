#!/usr/bin/env bash
# Regenerate the runtime-only `main` branch from `dev`.
# Usage: ./scripts/release-main.sh   (run from repo root, clean tree, on any branch)
set -euo pipefail

RUNTIME_PATHS=(
  backend/app backend/alembic backend/alembic.ini backend/pyproject.toml backend/README.md
  frontend/src frontend/index.html frontend/package.json frontend/package-lock.json
  frontend/tsconfig.json frontend/vite.config.ts frontend/tailwind.config.js frontend/postcss.config.js
  Containerfile.backend Containerfile.web compose.yaml nginx.conf
  .dockerignore .gitignore .env.example LICENSE SECURITY.md
)

[ -z "$(git status --porcelain)" ] || { echo "working tree not clean"; exit 1; }
git rev-parse --verify dev >/dev/null

git checkout main
git rm -r --quiet --ignore-unmatch . >/dev/null
git checkout dev -- "${RUNTIME_PATHS[@]}"
git checkout dev -- README.main.md && git mv -f README.main.md README.md
git add -A
git commit -m "release: sync runtime tree from dev ($(git rev-parse --short dev))"
echo "main updated. push with: git push origin main"
