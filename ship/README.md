# Ship Instructions — apple-a-day

> How to safely get code from working directory to PyPI.

## Status

### Steps
1. `git status` — show modified/untracked files
2. `git diff --stat` — summary of changes
3. `git log --oneline -5` — recent commits
4. `git fetch && git status` — check if behind remote
5. Report: files changed, uncommitted work, behind/ahead

## Build

### Steps
1. `cd /Users/dshanklinbv/repos-eidos-agi/apple-a-day`
2. `pip install -e ".[report,dev]"` — install with all optional deps
3. `python -c "from apple_a_day.checks import ALL_CHECKS; print(f'{len(ALL_CHECKS)} checks loaded')"` — verify imports
4. `python -c "from apple_a_day.report_html import generate_html_report; print('report_html OK')"` — verify Jinja2 templates
5. `python -c "from apple_a_day.vitals import sample; s = sample(); print(f'vitals OK: load={s[\"load\"][0]:.1f}')"` — verify vitals
6. Report: pass/fail for each

## Preflight

### Steps
1. `pytest tests/ -x -q` — run all tests, stop on first failure
2. Secrets scan: grep staged files for `api_key|secret|password|token|credential` patterns. HARD FAIL if found.
3. Version check: ensure `__init__.py` version matches `pyproject.toml` version
4. Template check: `ls apple_a_day/templates/components/ | wc -l` — should be 14+ component files
5. Report: pass/fail

## Commit

### Steps
1. Run **Status**
2. Run **Preflight** — stop if any hard failures
3. Stage files: `git add` specific files (never `git add .`)
4. Commit message style: match existing (`feat:`, `fix:`, `refactor:`)
5. Footer: `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>`
6. Show `git log --oneline -N` after committing

## Push

### Steps
1. `git push origin main`
2. Verify: `gh run list --limit 2` — check CI status
3. If CI fails, check: `gh run view <id> --log-failed | tail -20`

## Deploy

apple-a-day is a PyPI package. Deployment = tag + publish.

### Steps
1. Verify version in `pyproject.toml` and `__init__.py` match
2. Verify version in `templates/report.html` footer matches
3. `git tag -a v<VERSION> -m "v<VERSION> — <summary>"` — create annotated tag
4. `git push origin v<VERSION>` — triggers publish.yml workflow
5. Watch: `gh run list --limit 2` — verify publish workflow starts
6. If publish fails (trusted publisher not configured):
   - Go to https://pypi.org/manage/project/apple-a-day/settings/publishing/
   - Add trusted publisher: owner=eidos-agi, repo=apple-a-day, workflow=publish.yml, environment=pypi
   - Delete the tag: `git tag -d v<VERSION> && git push origin :refs/tags/v<VERSION>`
   - Re-tag and push

## Smoke Test

### Steps
1. `pip install apple-a-day` (in a clean venv or after publish)
2. `aad --version` — verify version matches
3. `aad checkup --json -c cpu_load | python -m json.tool | head -10` — verify checks work
4. `aad monitor --once --json | python -m json.tool | head -5` — verify vitals
5. `aad report --html` — verify report generates and opens

## Verify

### Steps
1. All 13 checks produce valid output: `aad checkup --json | python -c "import json,sys; d=json.load(sys.stdin); print(f'{len(d[\"findings\"])} findings')" `
2. HTML report renders without errors: `aad report --html`
3. Vitals daemon installs: `aad install && aad status`
4. Score command works: `aad score --json`
5. Profile command works: `aad profile --json | head -5`

## Rollback

### Steps
1. If a bad version is published to PyPI, you can yank it:
   - `pip install twine && twine yank apple-a-day <VERSION>`
2. For git: `git revert HEAD` + new tag with bumped patch version
3. Never force-push main

## Ship All

Full pipeline: Status -> Build -> Preflight -> Commit -> Push -> Deploy -> Smoke Test.

### Steps
Run each section in order. Stop on any failure.

1. **Status** — what's changing?
2. **Build** — is the environment ready?
3. **Preflight** — is the code safe to ship?
4. **Commit** — create clean commits
5. **Push** — send to remote
6. **Deploy** — tag and publish to PyPI
7. **Smoke Test** — does `aad` work after install?
