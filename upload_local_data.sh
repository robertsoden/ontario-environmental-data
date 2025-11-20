#!/bin/bash
#
# Upload local data directly to GitHub repository
#
# This script commits and pushes your local data directory to a special
# branch that the workflows can use as a data source.
#

set -e

echo "==========================================="
echo "Upload Local Data to GitHub"
echo "==========================================="
echo ""

# Check if data directory exists
if [ ! -d "data" ]; then
    echo "❌ Error: data directory not found"
    exit 1
fi

# Check current git status
if [ -n "$(git status --porcelain)" ]; then
    echo "⚠️  You have uncommitted changes. Stashing them..."
    git stash
    STASHED=1
fi

# Create a data branch
BRANCH_NAME="data-upload-$(date +%Y%m%d-%H%M%S)"
echo "📦 Creating branch: $BRANCH_NAME"

# Create and switch to new branch
git checkout -b "$BRANCH_NAME"

# Add data directory (overriding .gitignore)
echo "📁 Adding data directory..."
git add -f data/

# Commit
echo "💾 Committing data..."
git commit -m "Upload local data snapshot

This is a temporary data upload branch.
Can be deleted after the data is extracted by workflows.

Created: $(date)"

# Push to GitHub
echo "⬆️  Pushing to GitHub..."
git push -u origin "$BRANCH_NAME"

echo ""
echo "✅ Data uploaded successfully!"
echo ""
echo "Branch: $BRANCH_NAME"
echo ""
echo "Next steps:"
echo "1. The data is now in GitHub on branch '$BRANCH_NAME'"
echo "2. You can merge this into main if you want to commit the data"
echo "3. Or workflows can checkout this branch to access the data"
echo "4. After extracting, you can delete this branch"
echo ""
echo "To delete the branch later:"
echo "  git push origin --delete $BRANCH_NAME"
echo ""

# Switch back to original branch
git checkout -

# Restore stashed changes if any
if [ -n "$STASHED" ]; then
    echo "📦 Restoring stashed changes..."
    git stash pop
fi
