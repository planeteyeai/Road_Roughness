#!/bin/bash
# Check for sensitive files before committing

echo "🔍 Checking for sensitive files before commit..."
echo ""

FOUND_ISSUES=0

# Check for .env files
echo "1. Checking for .env files..."
if git status --porcelain | grep -E "\.env$" | grep -v "\.env\.example\|\.env\.docker\.example"; then
    echo "   ❌ FOUND .env files! These should NOT be committed."
    FOUND_ISSUES=1
else
    echo "   ✅ No .env files found"
fi

# Check for service account JSON
echo ""
echo "2. Checking for service account JSON files..."
if git status --porcelain | grep -iE "service.*account.*\.json|credentials.*\.json"; then
    echo "   ❌ FOUND service account JSON! This should NOT be committed."
    FOUND_ISSUES=1
else
    echo "   ✅ No service account JSON found"
fi

# Check for storage data
echo ""
echo "3. Checking for storage data..."
if git status --porcelain | grep "backend/storage/projects/" | grep -v ".gitkeep"; then
    echo "   ⚠️  WARNING: Found storage data files"
    echo "   These usually shouldn't be committed (images, reports, etc.)"
    FOUND_ISSUES=1
else
    echo "   ✅ No storage data found"
fi

# Check for virtual environment
echo ""
echo "4. Checking for virtual environment..."
if git status --porcelain | grep -E "\.venv/|venv/|env/"; then
    echo "   ❌ FOUND virtual environment! This should NOT be committed."
    FOUND_ISSUES=1
else
    echo "   ✅ No virtual environment found"
fi

# Check for __pycache__
echo ""
echo "5. Checking for Python cache..."
if git status --porcelain | grep "__pycache__"; then
    echo "   ❌ FOUND __pycache__! This should NOT be committed."
    FOUND_ISSUES=1
else
    echo "   ✅ No Python cache found"
fi

# Summary
echo ""
echo "═══════════════════════════════════════════════════════════"
if [ $FOUND_ISSUES -eq 0 ]; then
    echo "✅ ALL CHECKS PASSED - Safe to commit!"
    echo ""
    echo "You can now run:"
    echo "  git add ."
    echo "  git commit -m 'Add Railway deployment'"
    echo "  git push origin main"
else
    echo "❌ ISSUES FOUND - DO NOT COMMIT YET!"
    echo ""
    echo "Fix the issues above before committing."
    echo ""
    echo "To remove files from staging:"
    echo "  git reset HEAD <file>"
    echo ""
    echo "Or to remove from Git tracking:"
    echo "  git rm --cached <file>"
fi
echo "═══════════════════════════════════════════════════════════"

exit $FOUND_ISSUES
