# Build & Deployment Instructions

## Development Workflow

1. Create Pull Request:
   ```
   gh pr create --title "Fix team name matching and date filtering" --body "Improves the team name matching in fuzzy_match_teams function and fixes date/timezone handling"
   ```

2. Merge Pull Request to main:
   ```
   gh pr merge --delete --squash
   ```

## Deployment Process

Deployment is triggered ONLY by creating a version tag. Merging to main does NOT automatically deploy.

1. Ensure CHANGELOG.md is updated with the correct version (e.g., [v0.3.0])

2. Create and push a tag AFTER merging your changes to main:
   ```
   git checkout main
   git pull
   git tag v0.3.0
   git push origin v0.3.0
   ```

3. The GitHub Actions workflow (.github/workflows/deploy.yml) will:
   - Verify the tag exists in CHANGELOG.md
   - Deploy to the EC2 server by:
     - Checking out the specific tagged version
     - Restarting the ncsoccer-agent service
     - Verifying the deployment

4. You can monitor the deployment status on the GitHub Actions tab in the repository

## Manual Deployment (if needed)

If you need to deploy manually:

1. SSH into the EC2 instance:
   ```
   ssh ec2-user@<ec2-instance-ip>
   ```

2. Navigate to the application directory:
   ```
   cd /path/to/ncsoccer-agent
   ```

3. Pull the latest changes for the specific tag:
   ```
   git fetch --all --tags
   git checkout v0.3.0
   ```

4. Restart the service:
   ```
   sudo systemctl restart ncsoccer-agent
   ```

## Verifying the Update

To verify the date filtering and team matching are working correctly:

1. Access the UI and search for "Key West games in March 2025"
2. Confirm that the results show proper date formatting and include the AFC Richmond vs Key West FC game on March 22, 2025
3. Try variations like "Key West I" and "Key West FC" to ensure the fuzzy matcher is working

Note: The Docker container mounts the entire analysis directory, so code changes are reflected without rebuilding the container. However, a rebuild is recommended to ensure all dependencies are up to date.