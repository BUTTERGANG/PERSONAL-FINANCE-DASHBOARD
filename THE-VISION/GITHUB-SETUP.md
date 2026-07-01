# GitHub Setup — Private Repo with Granular Access

## Should You Use GitHub?

**Yes.** Even for a personal project, GitHub gives you:
- Version history (undo bad changes)
- Easy deployment to Replit via Git integration
- Backup of all your code (separate from Replit)
- Ability to grant read-only access to collaborators (e.g., a developer friend helping you)

**The code in this repo contains no secrets.** All credentials live in Replit Secrets.
A private repo is best practice (defense in depth), but the code itself is not sensitive.

---

## Step 1: Create the Private Repo

```bash
# In your project directory:
git init
git add .
git commit -m "Initial commit: Personal Finance Dashboard"
```

Then on GitHub:
1. Go to https://github.com/new
2. Repository name: `finance-dashboard` (or your preferred name)
3. **Visibility: Private** ← critical
4. Do NOT initialize with README (you already have one)
5. Click **Create repository**

Push:
```bash
git remote add origin git@github.com:YOUR_USERNAME/finance-dashboard.git
git branch -M main
git push -u origin main
```

---

## Step 2: Enable Branch Protection

This prevents accidentally force-pushing over your history.

1. GitHub repo → Settings → Branches
2. Add branch protection rule for `main`
3. Enable:
   - ✅ Require a pull request before merging (optional for personal)
   - ✅ Do not allow bypassing the above settings
4. Save

---

## Step 3: Enable Secret Scanning

Prevents accidentally committed secrets from going unnoticed.

1. GitHub repo → Settings → Code security and analysis
2. Enable:
   - ✅ Secret scanning
   - ✅ Push protection (blocks commits containing known secret patterns)

This is free on private repos.

---

## Step 4: Granular Collaborator Access

For each person you want to give access:

1. GitHub repo → Settings → Collaborators and teams
2. Click **Add people**
3. Enter their GitHub username or email
4. Choose permission level:

| Level | What They Can Do | Use Case |
|-------|-----------------|---------|
| **Read** | View code, clone, no write | Share code for review |
| **Triage** | Read + manage issues/PRs | Project manager |
| **Write** | Read + push branches | Active co-developer |
| **Maintain** | Write + manage settings (limited) | Senior collaborator |
| **Admin** | Full control | Only you |

**Recommendation:** For now, only you as Admin. If you ever need a developer to help:
- Give them **Write** access to a feature branch
- Never give Admin access to anyone you don't fully trust

---

## Step 5: Connect Replit to GitHub

1. In Replit, open your project
2. Click **Version control** (Git icon in sidebar)
3. Connect to your GitHub repo
4. Future updates: push to GitHub → pull in Replit

---

## What NEVER Goes in This Repo

The .gitignore blocks these, but verify manually before every push:

```bash
git status  # nothing sensitive should appear as staged
git diff --staged  # review every line before committing
```

Files to NEVER commit:
- `.env` (your real credentials)
- `finance.db` (your transaction history)
- Any file with account numbers, API keys, or tokens

---

## Rotating Access

If you ever need to revoke someone's access:
1. GitHub repo → Settings → Collaborators and teams
2. Find their name → Click the gear → Remove

Their local clone still exists, but they can no longer pull updates or push.
If they had write access and you're concerned about what they might have seen,
consider rotating your Replit Secrets (ENCRYPTION_KEY, PLAID_SECRET, etc.).

---

## Keeping the Repo Clean

Recommended `.git/hooks/pre-commit` to catch accidental secret commits:

```bash
# Auto-installed by running: cp scripts/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
#!/bin/bash
if git diff --staged --name-only | grep -E '\.env$|finance\.db$|\.key$'; then
  echo "ERROR: Attempting to commit a secrets file. Aborting."
  exit 1
fi
```

---

## Summary Checklist

- [ ] Private repo created
- [ ] Branch protection on main
- [ ] Secret scanning enabled
- [ ] Push protection enabled
- [ ] Replit connected to GitHub
- [ ] .gitignore verified (run `git status` — no .env or .db files)
- [ ] Collaborators added only as needed (default: just you)
