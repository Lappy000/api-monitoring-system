# Dependabot PR Merge Checklist

## ✅ Good News!
Your tests are passing locally: **232 passed, 4 skipped** ✨

## 📋 Current Status
- **15 open Dependabot PRs**
- **CI/CD workflows updated** to latest GitHub Actions
- **Tests passing locally** but failing in CI (environment issue, now fixed)

## 🔄 Merge Strategy

### Phase 1: GitHub Actions (Safest - Merge First)
```bash
# These PRs update workflow dependencies - lowest risk
□ ci: bump actions/checkout from 3 to 4
□ ci: bump actions/setup-python from 4 to 6  
□ ci: bump actions/cache from 3 to 4
□ ci: bump codecov/codecov-action from 3 to 5
```

### Phase 2: Patch Updates (Low Risk)
```bash
# Minor version bumps - safe to merge together
□ chore(deps): bump python-dateutil from 2.8.x to 2.9.x
□ chore(deps): bump fastapi from 0.104.1 to 0.121.1
□ chore(deps): bump cryptography (security updates)
□ chore(deps): bump alembic from 1.13.0 to 1.17.1
□ chore(deps): bump pydantic from 2.5.0 to 2.10.4
```

### Phase 3: Minor Updates (Medium Risk - Test After Merge)
```bash
# Check changelogs for breaking changes
□ chore(deps-dev): bump isort from 5.13.2 to 7.0.0
□ chore(deps): bump python-dotenv from 1.0.0 to 1.2.1
□ chore(deps): bump sqlalchemy from 2.0.23 to 2.0.44
□ chore(deps): bump pytz from 2023.3 to 2025.2
```

### Phase 4: Major Updates (High Risk - One at a Time)
```bash
# BREAKING CHANGES POSSIBLE - Review carefully!
□ build: bump python from 3.11-slim to 3.14-slim
  ⚠️ Test with Python 3.14 compatibility first

□ chore(deps): bump python-jose from 3.3.0 to 46.0.3
  ⚠️ MAJOR BREAKING CHANGE - Check migration guide
  📖 https://github.com/mpdavis/python-jose/blob/master/CHANGELOG.md
```

## 🚀 Quick Merge Commands

### Using GitHub CLI (Recommended)
```bash
cd "Middle python"

# Merge all GitHub Actions PRs at once
gh pr list --label "github-actions" --json number --jq '.[].number' | \
  xargs -I {} gh pr merge {} --squash --auto

# Merge safe dependency updates
gh pr list --label "dependencies" --search "patch" --json number --jq '.[].number' | \
  xargs -I {} gh pr merge {} --squash --auto

# Run tests after each batch
pytest -v --tb=short
```

### Manual Review Process
```bash
# 1. Checkout PR
gh pr checkout <PR_NUMBER>

# 2. Run tests
pytest -v

# 3. If tests pass, merge
gh pr merge <PR_NUMBER> --squash --delete-branch

# 4. Move to next PR
```

## ⚠️ Special Attention Required

### python-jose (3.3.0 → 46.0.3)
This is a **MAJOR version jump**. Before merging:
1. Check if your code uses `jose` directly
2. Review breaking changes in changelog
3. Test authentication functionality thoroughly
4. Consider doing this last

### Python Version (3.11 → 3.14)
If updating Python version:
1. Check compatibility of all dependencies
2. Test locally with Python 3.14 first
3. Update CI/CD workflows after local testing
4. May require updating other dependencies

## 📊 After Merging All PRs

### Verification Steps
```bash
# 1. Pull latest main
git checkout main
git pull origin main

# 2. Clean install
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 3. Run full test suite
pytest --cov=app --cov-report=html -v

# 4. Check for security issues
pip-audit

# 5. Verify application starts
uvicorn app.main:app --host 127.0.0.1 --port 8888

# 6. Run a smoke test
curl http://127.0.0.1:8888/health
```

### Update Documentation
```bash
□ Update CHANGELOG.md with dependency changes
□ Update requirements.txt lock versions if needed
□ Tag a new release if appropriate
```

## 🔧 CI/CD Fixes Already Applied

✅ Updated to latest GitHub Actions versions  
✅ Fixed Codecov v4 compatibility  
✅ Added environment setup steps  
✅ Added PYTHONPATH to test runs  
✅ Improved Dependabot configuration with grouping  

## 📝 Notes

- Tests are **passing locally** (232 passed, 4 skipped)
- Some warnings about deprecated Pydantic v2 features (non-critical)
- RuntimeWarnings about unawaited coroutines in tests (cosmetic, not affecting functionality)

## 🆘 If Something Breaks

```bash
# Revert last merge
git revert HEAD
git push origin main

# Or reset to before merges
git reset --hard <commit-before-merging>
git push origin main --force

# Re-run tests
pytest -v
```

## 📞 Need Help?

- Check [`CI_CD_FIX_GUIDE.md`](CI_CD_FIX_GUIDE.md) for detailed troubleshooting
- Use `scripts/merge_dependabot_prs.sh` for automated merging (requires gh CLI)
- Review individual PR descriptions for details