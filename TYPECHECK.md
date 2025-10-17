# Type Checking Guide

## Full Run (recommended)
```bash
mypy backend/
```
Runs against application code and tests for highest confidence.

## Fast Mode (skip tests)
```bash
mypy backend/ --exclude '/tests/'
```
Use sparingly for emergency hotfixes when time is critical.

## CI Integration
The main CI pipeline honours the environment variable `SKIP_TEST_TYPECHECK`:

- Omit or set to anything other than `true` → full type check (default).
- Set to `true` → fast mode, test directory excluded.

Example (GitHub Actions):
```yaml
env:
  SKIP_TEST_TYPECHECK: true
```

## Why Both?
- **Full check** keeps overall quality high, catches regressions in tests and fixtures, and helps new contributors trust the suite.
- **Fast mode** trims minutes off urgent fixes when confidence in tests already exists.

## New Team Member Tips
1. Install dev type stubs: `pip install -r backend/requirements.txt`.
2. Run the full type check locally (`mypy backend/`) before pushing.
3. For large refactors, run both modes: fast first for quick feedback, then the full pass.
4. If mypy flags missing stubs, prefer adding the types (see requirements.txt "Type checking" section) before ignoring.
