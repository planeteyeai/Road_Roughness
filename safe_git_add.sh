#!/bin/bash
# Safely add files to git, excluding sensitive data

echo "🔒 Adding files safely to Git..."
echo ""

# Add .gitignore first
echo "1. Adding .gitignore..."
git add .gitignore

# Add documentation
echo "2. Adding documentation files..."
git add *.md *.txt 2>/dev/null

# Add deployment configs
echo "3. Adding deployment configurations..."
git add Dockerfile docker-compose.yml .dockerignore 2>/dev/null
git add .env.docker.example 2>/dev/null
git add railway.toml nixpacks.toml Procfile runtime.txt 2>/dev/null

# Add scripts (but check they're safe)
echo "4. Adding scripts..."
git add *.sh 2>/dev/null

# Add code updates
echo "5. Adding code updates..."
git add road_roughness/backend/app/config.py 2>/dev/null
git add road_roughness/backend/app/gee_auth.py 2>/dev/null
git add road_roughness/backend/app/ndwi.py 2>/dev/null

# Add existing project files (that are safe)
echo "6. Adding existing project files..."
git add road_roughness/frontend/ 2>/dev/null
git add road_roughness/backend/app/*.py 2>/dev/null
git add road_roughness/backend/main.py 2>/dev/null
git add road_roughness/backend/requirements.txt 2>/dev/null
git add road_roughness/backend/*.sh 2>/dev/null
git add road_roughness/backend/*.bat 2>/dev/null
git add road_roughness/backend/.env.example 2>/dev/null
git add road_roughness/.gitignore 2>/dev/null
git add road_roughness/README.md 2>/dev/null

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "✅ Files added safely!"
echo ""
echo "Now checking for sensitive files..."
echo "═══════════════════════════════════════════════════════════"
echo ""

# Run safety check
if [ -f "./check_before_commit.sh" ]; then
    ./check_before_commit.sh
else
    echo "⚠️  check_before_commit.sh not found, manual check:"
    echo ""
    git status
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "If everything looks good, run:"
echo ""
echo "  git commit -m 'Add Railway deployment configuration'"
echo "  git push origin main"
echo "═══════════════════════════════════════════════════════════"
