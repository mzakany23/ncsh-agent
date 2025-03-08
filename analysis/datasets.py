"""
Dataset operations for the soccer data analysis system.

This module contains functionality for creating and manipulating datasets,
including filtering team-specific datasets and creating compact representations.
"""

import os
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from analysis.database import build_dataset, compact_dataset

# Initialize console for rich output
console = Console()

def create_team_dataset(team: str, parquet_file: str, output_file: str = None):
    """
    Create a filtered dataset for a specific team and save it as a new parquet file.

    Args:
        team: The team name to filter the dataset by
        parquet_file: Path to the source parquet file
        output_file: Path to save the filtered dataset as a parquet file (optional)

    Returns:
        A dictionary with the result information
    """
    if not output_file:
        # Generate output filename based on team name if not provided
        output_dir = os.path.dirname(parquet_file)
        team_slug = team.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_')
        output_file = os.path.join(output_dir, f"{team_slug}_dataset.parquet")

    # Build the dataset
    console.print(f"[yellow]Building dataset for team '{team}'...[/yellow]")
    result = build_dataset(team, parquet_file, output_file)

    if "error" in result:
        console.print(f"[red]Error building dataset: {result['error']}[/red]")
        return None

    console.print(f"[green]Dataset built successfully![/green]")
    console.print(f"[green]Found {result['row_count']} matches involving {team}[/green]")
    console.print(f"[green]Dataset saved to: {result['output_file']}[/green]")

    return result

def create_compact_dataset(parquet_file: str, output_format: str = "compact"):
    """
    Create a compact representation of match data optimized for Claude's context window.

    Args:
        parquet_file: Path to the parquet file containing match data
        output_format: Format style ('compact', 'table', or 'csv')

    Returns:
        A dictionary with the result information
    """
    # Create compact representation
    console.print(f"[yellow]Creating compact dataset representation in '{output_format}' format...[/yellow]")
    result = compact_dataset(parquet_file, output_format)

    if "error" in result:
        console.print(f"[red]Error creating compact dataset: {result['error']}[/red]")
        return None

    console.print(f"[green]Compact dataset created successfully![/green]")
    console.print(f"[green]Processed {result['row_count']} matches[/green]")
    console.print(f"[green]Original size: {result['original_size_bytes']} bytes[/green]")
    console.print(f"[green]Compact size: {result['compact_size_bytes']} bytes[/green]")
    console.print(f"[green]Compression ratio: {result['compression_ratio']}[/green]")

    # Print the compact dataset
    syntax = Syntax(result['result'], "text", theme="monokai", line_numbers=True, word_wrap=True)
    console.print(
        Panel(
            syntax,
            title=f"[bold]Compact Dataset ({output_format} format)[/bold]",
            border_style="green",
        )
    )

    return result