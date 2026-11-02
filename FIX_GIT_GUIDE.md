# 🔧 Fix Git Before Pushing - Step by Step

## ✅ Current Status

Good news! I checked your repository and:
- ✅ `.env` file is NOT tracked (safe!)
- ✅ No service account JSON files tracked (safe!)
- ✅ Only `.env.example` is tracked (correct!)

## 📋 What You Need to Do Now

### Step 1: Add the New Files (Safety Files)

Add the .gitignore and safety tools:

```bash
git add .gitignore
git add check_before_commit.sh
git add GITIGNORE_GUIDE.txt
git add FIX_GIT_GUIDE.md
```

### Step 2: Add All Deployment Files

Add all the deployment documentation and configuration:

```bash
# Documentation
git add *.md *.txt

# Deployment configs
git add Dockerfile
git add docker-compose.yml
git add .dockerignore
git add .env.docker.example
git add railway.toml
git add nixpacks.toml
git add Procfile
git add runtime.txt

# Scripts
git add *.sh

# Code updates
git add road_roughness/backend/app/config.py
git add road_roughness/backend/app/gee_auth.py
git add road_roughness/backend/app/ndwi.py
```

### Step 3: Verify Before Committing

Check what will be committed:

```bash
./check_before_commit.sh
```

Or manually:

```bash
git status
```

**Look for these RED FLAGS (should NOT see):**
- ❌ `road_roughness/backend/.env` (without .example)
- ❌ Any `*service-account*.json` files
- ❌ `__pycache__/` folders
- ❌ `.venv/` folders
- ❌ `storage/projects/` data

**Should see (OK to commit):**
- ✅ `*.md` files (documentation)
- ✅ `Dockerfile`
- ✅ `*.sh` scripts
- ✅ `.gitignore`
- ✅ Python code files (`*.py`)

### Step 4: Commit

```bash
git commit -m "Add Railway deployment configuration with security"
```

### Step 5: Push to GitHub

```bash
git push origin main
```

Or if you're using `master`:

```bash
git push origin master
```

---

## 🔥 If You Find Sensitive Files Are Staged

If you see `.env` or service account JSON in `git status`:

### Unstage them:

```bash
# Unstage specific file
git reset HEAD road_roughness/backend/.env

# Or unstage everything and start over
git reset HEAD .
```

### If already committed (but not pushed):

```bash
# Undo last commit but keep changes
git reset --soft HEAD~1

# Then follow Steps 1-5 above
```

---

## ⚠️ If You Already Pushed Sensitive Files

If you already pushed to GitHub with `.env` or credentials:

### Method 1: Remove and recommit (if recent)

```bash
# Remove from tracking
git rm --cached road_roughness/backend/.env
git rm --cached *service-account*.json

# Commit the removal
git commit -m "Remove sensitive files"

# Push
git push origin main --force
```

### Method 2: Complete history cleanup (if in history)

Use GitHub's guide:
https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository

**IMPORTANT:** After removing from Git, immediately:
1. Regenerate your service account key (old one is compromised)
2. Change any exposed credentials
3. Update Railway environment variables with new credentials

---

## 🎯 Quick Commands (Copy-Paste)

### Add everything safely:

```bash
git add .gitignore check_before_commit.sh
git add *.md *.txt *.toml Dockerfile docker-compose.yml .dockerignore Procfile runtime.txt
git add *.sh
git add road_roughness/backend/app/*.py
```

### Check safety:

```bash
./check_before_commit.sh
```

### Commit and push:

```bash
git commit -m "Add Railway deployment configuration"
git push origin main
```

---

## ✅ Checklist

Before pushing, verify:

- [ ] `.gitignore` is added
- [ ] `check_before_commit.sh` passes
- [ ] No `.env` in git status (except .env.example)
- [ ] No service account JSON in git status
- [ ] All deployment docs added (*.md files)
- [ ] Dockerfile and configs added
- [ ] Code changes added (app/*.py)

---

## 🚀 Ready to Deploy?

After pushing, follow:
- **Quick Start:** `DEPLOY_STEP_BY_STEP.md`
- **Variables:** `RAILWAY_VARIABLES.txt`
- **Full Guide:** `README_RAILWAY.md`

---

**You're all set! The .gitignore will protect you going forward.** 🔒
