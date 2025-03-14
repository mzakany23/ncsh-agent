# NC Soccer Hudson Deployment Guide

## Overview

This document outlines the process for deploying the NC Soccer Hudson application using the tag-based deployment strategy.

The key benefits of this approach:

1. **Controlled Deployments**: Deployments only occur when explicitly triggered by a new tag, not automatically on every push to `main`.
2. **Versioned Releases**: Each deployment is tied to a specific version in the CHANGELOG.md.
3. **Minimal Disruption**: The deployment process avoids rebuilding Docker containers unnecessarily, using SSH to pull new code and restart services.

## Deployment Process

### 1. Update CHANGELOG.md

Before creating a new release, update the CHANGELOG.md with your new version and changes:

```markdown
## [v0.2.0] - 2023-06-15

### Added
- New dataset visualization feature
- Support for multiple data sources

### Fixed
- Issue with dataset loading
- UI rendering bug in analysis view
```

The format should follow semantic versioning (vX.Y.Z):
- **X**: Major version (breaking changes)
- **Y**: Minor version (new features, non-breaking)
- **Z**: Patch version (bug fixes)

### 2. Create and Push a Tag

You can use the provided release script to create and push a tag:

```bash
# Make the script executable (first time only)
chmod +x scripts/release.sh

# Create and push a new tag
./scripts/release.sh v0.2.0
```

The script will:
1. Verify you're on the main branch
2. Ensure your working directory is clean
3. Pull the latest changes
4. Check that the version exists in CHANGELOG.md
5. Create and push the tag

Alternatively, you can do this manually:

```bash
# Create a tag
git tag v0.2.0

# Push the tag to remote
git push origin v0.2.0
```

### 3. Monitor Deployment

Once the tag is pushed, the GitHub Actions workflow will automatically start:

1. Go to the GitHub repository → Actions tab
2. You'll see a workflow run with the name of your tag
3. The workflow will:
   - Verify the tag exists in CHANGELOG.md
   - Deploy the code via SSH to the production server
   - Restart the necessary services

The deployment typically takes 3-5 minutes to complete.

### 4. Manual Deployment (if needed)

If you need to deploy manually:

1. Go to the GitHub repository → Actions tab
2. Select the "NC Soccer Hudson Tag-Based Deployment" workflow
3. Click "Run workflow"
4. Enter the tag version to deploy (must match a version in CHANGELOG.md)
5. Click "Run workflow"

## Troubleshooting

### Deployment Failed: Version Not Found in CHANGELOG.md

If the workflow fails with "Version not found in CHANGELOG.md":

1. Verify the tag name matches exactly what's in CHANGELOG.md (case-sensitive)
2. Update CHANGELOG.md with the correct version
3. Push the changes to main
4. Try again with the same tag

### EC2 Instance Not Responding

If the deployment succeeds but the application is not accessible:

1. SSH into the instance: `ssh user@instance-ip`
2. Check service status: `sudo systemctl status ncsoccer-agent`
3. Check application logs: `sudo journalctl -u ncsoccer-agent -f`
4. Restart the service if needed: `sudo systemctl restart ncsoccer-agent`

### Docker Container Issues

If there are issues with the Docker container:

1. SSH into the instance
2. Check container status: `sudo docker ps -a`
3. View container logs: `sudo docker logs ncsoccer-ui`
4. Restart the container: `sudo docker restart ncsoccer-ui`

## Best Practices

1. **Always test locally** before creating a release
2. **Keep releases small and focused** to simplify troubleshooting
3. **Document all changes** in CHANGELOG.md
4. **Monitor deployments** to catch issues early
5. **Roll back** to a previous tag if needed: `git checkout v0.1.9`