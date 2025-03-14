#!/bin/bash
# Release script for NC Soccer Hudson
# Usage: ./scripts/release.sh v0.2.0

set -e

# Check if a version argument was provided
if [ -z "$1" ]; then
  echo "Error: No version tag provided"
  echo "Usage: ./scripts/release.sh v0.2.0"
  exit 1
fi

VERSION=$1

# Verify version format
if [[ ! $VERSION =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Error: Version must be in format v0.0.0"
  exit 1
fi

# Check if we're on the main branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "main" ]; then
  echo "Error: You must be on the main branch to create a release"
  exit 1
fi

# Check if working directory is clean
if [ -n "$(git status --porcelain)" ]; then
  echo "Error: Working directory is not clean. Please commit all changes before creating a release."
  exit 1
fi

# Pull latest changes
echo "Pulling latest changes from main..."
git pull origin main

# Check if version exists in CHANGELOG.md
if ! grep -q "\[$VERSION\]" CHANGELOG.md; then
  echo "Error: Version $VERSION not found in CHANGELOG.md"
  echo "Please update the CHANGELOG.md file with the new version before creating a release."
  exit 1
fi

# Check if tag already exists
if git tag | grep -q "^$VERSION$"; then
  echo "Error: Tag $VERSION already exists"
  echo "Use a different version number or delete the existing tag with 'git tag -d $VERSION'"
  exit 1
fi

# Create and push tag
echo "Creating tag $VERSION..."
git tag $VERSION

echo "Pushing tag to origin..."
git push origin $VERSION

echo "Release $VERSION created successfully!"
echo "GitHub Actions will now start the deployment process."
echo "You can monitor the progress at https://github.com/your-org/ncsoccer-agent/actions"