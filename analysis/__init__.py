"""
Analysis package for the DuckDB Query Agent.
"""

from .database import DuckDBAnalyzer
from .prompts import (
    ANALYSIS_SYSTEM_PROMPT,
    BATCH_SYSTEM_PROMPT,
    TEAM_ANALYSIS_PROMPT
)
from .agent import (
    run_agent,
    run_agent_with_memory
)
from .datasets import (
    create_team_dataset,
    create_compact_dataset
)

__all__ = [
    'DuckDBAnalyzer',
    'ANALYSIS_SYSTEM_PROMPT',
    'BATCH_SYSTEM_PROMPT',
    'TEAM_ANALYSIS_PROMPT',
    'run_agent',
    'run_agent_with_memory',
    'create_team_dataset',
    'create_compact_dataset'
]
