#!/bin/bash
# Script to systematically merge Dependabot PRs
# Usage: ./scripts/merge_dependabot_prs.sh

set -e

echo "🤖 Dependabot PR Merge Assistant"
echo "================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}Error: GitHub CLI (gh) is not installed${NC}"
    echo "Install from: https://cli.github.com/"
    exit 1
fi

# Function to merge a PR
merge_pr() {
    local pr_number=$1
    local pr_title=$2
    
    echo -e "${YELLOW}Processing PR #${pr_number}: ${pr_title}${NC}"
    
    # Checkout PR
    gh pr checkout $pr_number
    
    # Run tests
    echo "Running tests..."
    if pytest -v --tb=short; then
        echo -e "${GREEN}✓ Tests passed for PR #${pr_number}${NC}"
        
        # Ask for confirmation
        read -p "Merge this PR? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            gh pr merge $pr_number --squash --delete-branch
            echo -e "${GREEN}✓ Merged PR #${pr_number}${NC}"
        else
            echo -e "${YELLOW}⊘ Skipped PR #${pr_number}${NC}"
        fi
    else
        echo -e "${RED}✗ Tests failed for PR #${pr_number}${NC}"
        echo "Skipping merge. Fix issues manually."
    fi
    
    echo ""
}

# Phase 1: GitHub Actions updates (safest)
echo -e "${GREEN}Phase 1: GitHub Actions Updates${NC}"
echo "These are the safest to merge"
echo ""

gh pr list --label "github-actions" --json number,title --jq '.[] | "\(.number)|\(.title)"' | while IFS='|' read -r number title; do
    merge_pr "$number" "$title"
done

# Phase 2: Patch updates
echo -e "${GREEN}Phase 2: Patch Version Updates${NC}"
echo "Minor updates with low risk"
echo ""

# List all Dependabot PRs and filter patch updates
gh pr list --label "dependencies" --json number,title --jq '.[] | select(.title | contains("patch")) | "\(.number)|\(.title)"' | while IFS='|' read -r number title; do
    merge_pr "$number" "$title"
done

# Phase 3: Review remaining PRs
echo -e "${YELLOW}Phase 3: Review Remaining PRs${NC}"
echo "These require manual review:"
echo ""

gh pr list --label "dependencies" --search "is:open" --json number,title,labels
echo ""
echo -e "${YELLOW}Hint: Review these PRs individually and merge with caution${NC}"
echo "For major version bumps, check the changelog carefully!"

echo ""
echo "✓ Merge process complete!"
echo "Run 'pytest --cov=app' to verify all changes work together"