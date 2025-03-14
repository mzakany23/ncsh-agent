# Changelog

All notable changes to this project will be documented in this file.

## [v0.2.0] - 2023-06-15

### Added
- Tag-based deployment process for more controlled releases
- New release.sh script to automate version tagging
- Comprehensive deployment documentation

### Changed
- Simplified dataset creation UI by removing format selection
- Standardized dataset format to use "compact" format for better performance
- Updated CI/CD workflow to trigger deployments only on tags

### Fixed
- Issue with "table" format not working properly in dataset creation
- Inconsistent behavior when creating and selecting datasets

## [0.1.0] - 2023-08-04

### Added
- Initial release of the DuckDB Soccer Analysis Agent with Claude 3.7
- Natural Language to SQL translation capabilities
- Team Name Fuzzy Matching system for automatic team name resolution
- Schema understanding for automatic database schema extraction
- SQL validation to prevent execution errors
- Recursive Tool Calling framework for complex analysis pipelines
- Interactive Streamlit UI for easy interaction
- Command-line interface for agent queries and dataset management
- Team comparison pipeline with comprehensive analysis
- Data visualization and statistical analysis tools
- Conversation memory to maintain context across queries
- Comprehensive summary tool for synthesizing analysis results
- Analysis pipeline orchestration with intelligent tool selection
- Documentation including README and code comments

### Changed
- Enhanced agent architecture with DAG-like workflow for better analysis
- Improved error handling for team existence verification
- Refined prompt engineering for better Claude 3.7 performance

### Fixed
- Pipeline data flow issues ensuring data passes correctly between tools
- Team name matching for teams not in the dataset
- CLI compatibility with updated agent interface