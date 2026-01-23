"""FAF Map AI command-line interface.

This module provides CLI commands for downloading and parsing Supreme Commander maps.
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click
import numpy as np

from faf.api.auth import (
    FAFAuthClient,
    FAFAuthError,
    has_credentials_in_environment,
)
from faf.downloader import BulkDownloader, DownloadProgress, MapDownloader, MapDownloadError
from faf.parser import SCMapParser
from faf.parser.scmap import SCMapParseError
from faf.preprocessing import DatasetBuilder, DatasetStats, DatasetValidator
from faf.preprocessing.dataset import BuildProgress

# Exit codes
EXIT_SUCCESS = 0
EXIT_USER_ERROR = 1
EXIT_SYSTEM_ERROR = 2

# Map size constants (width in game units to km)
SIZE_TO_KM = {
    128: "2.5km",
    256: "5km",
    512: "10km",
    1024: "20km",
    2048: "40km",
    4096: "80km",
}


def get_map_size_label(width: float) -> str:
    """Get human-readable map size label.

    Args:
        width: Map width in game units.

    Returns:
        Human-readable size string like "256x256 (5km)".
    """
    size = int(width)
    km_label = SIZE_TO_KM.get(size, "unknown")
    return f"{size}x{size} ({km_label})"


def print_error(message: str) -> None:
    """Print error message to stderr.

    Args:
        message: Error message to print.
    """
    click.echo(click.style(f"Error: {message}", fg="red"), err=True)


def print_success(message: str) -> None:
    """Print success message.

    Args:
        message: Success message to print.
    """
    click.echo(click.style(message, fg="green"))


@click.group()
@click.version_option(version="0.1.0", prog_name="faf")
def cli() -> None:
    """FAF Map AI - Tools for Supreme Commander map processing.

    Download maps from FAF content server and extract terrain data.
    """
    pass


@cli.command()
@click.argument("url")
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    default=Path("./maps"),
    help="Directory to extract map to (default: ./maps)",
)
def download(url: str, output_dir: Path) -> None:
    """Download a map from the FAF content server.

    URL should be a direct link to a map zip file, e.g.:
    https://content.faforever.com/maps/theta_passage_5.v0001.zip
    """
    try:
        if not output_dir.exists():
            output_dir.mkdir(parents=True)

        downloader = MapDownloader()
        info = downloader.download(url, output_dir=output_dir)

        print_success(f"Downloaded to {info.root_dir}/")
        click.echo(f"  SCMAP: {info.scmap_path.name}")
        click.echo(f"  Scenario: {info.scenario_path.name}")

    except MapDownloadError as e:
        print_error(str(e))
        sys.exit(EXIT_USER_ERROR)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(EXIT_SYSTEM_ERROR)


@cli.command()
@click.argument("scmap_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-f",
    "output_format",
    type=click.Choice(["json", "numpy"]),
    default="json",
    help="Output format (default: json)",
)
@click.option(
    "--output-file",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path (default: stdout for json, required for numpy)",
)
def parse(scmap_path: Path, output_format: str, output_file: Optional[Path]) -> None:
    """Parse a local .scmap file and output terrain data.

    SCMAP_PATH is the path to a .scmap file to parse.
    """
    try:
        map_data = SCMapParser.parse(scmap_path)

        if output_format == "json":
            result = {
                "version": map_data.version,
                "width": map_data.width,
                "height": map_data.height,
                "heightmap_scale": map_data.heightmap_scale,
                "water_elevation": map_data.water_elevation,
                "heightmap_shape": list(map_data.heightmap.shape),
                "texture_paths": map_data.texture_paths,
            }
            json_output = json.dumps(result, indent=2)

            if output_file:
                output_file.write_text(json_output)
                print_success(f"Wrote JSON to {output_file}")
            else:
                click.echo(json_output)

        elif output_format == "numpy":
            if not output_file:
                print_error("--output-file is required for numpy format")
                sys.exit(EXIT_USER_ERROR)

            np.save(output_file, map_data.heightmap)
            print_success(f"Wrote heightmap to {output_file}")
            click.echo(f"  Shape: {map_data.heightmap.shape}")
            click.echo(f"  Dtype: {map_data.heightmap.dtype}")

    except FileNotFoundError:
        print_error(f"File not found: {scmap_path}")
        sys.exit(EXIT_USER_ERROR)
    except SCMapParseError as e:
        print_error(f"Failed to parse SCMAP: {e}")
        sys.exit(EXIT_USER_ERROR)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(EXIT_SYSTEM_ERROR)


@cli.command()
@click.argument("scmap_path", type=click.Path(exists=True, path_type=Path))
def info(scmap_path: Path) -> None:
    """Display information about a .scmap file.

    SCMAP_PATH is the path to a .scmap file to inspect.
    """
    try:
        map_data = SCMapParser.parse(scmap_path)

        map_name = scmap_path.stem
        size_label = get_map_size_label(map_data.width)
        heightmap_shape = f"{map_data.heightmap.shape[0]}x{map_data.heightmap.shape[1]}"
        num_textures = len([t for t in map_data.texture_paths if t])

        click.echo(f"Map: {map_name}")
        click.echo(f"Version: {map_data.version}")
        click.echo(f"Size: {size_label}")
        click.echo(f"Heightmap: {heightmap_shape}")
        click.echo(f"Heightmap Scale: {map_data.heightmap_scale}")
        click.echo(f"Water Elevation: {map_data.water_elevation}")
        click.echo(f"Textures: {num_textures} stratum layers")

    except FileNotFoundError:
        print_error(f"File not found: {scmap_path}")
        sys.exit(EXIT_USER_ERROR)
    except SCMapParseError as e:
        print_error(f"Failed to parse SCMAP: {e}")
        sys.exit(EXIT_USER_ERROR)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(EXIT_SYSTEM_ERROR)


@cli.command()
@click.argument("url")
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    default=Path("./maps"),
    help="Directory to extract map to (default: ./maps)",
)
def fetch(url: str, output_dir: Path) -> None:
    """Download a map and display its information.

    This is a convenience command that combines 'download' and 'info'.

    URL should be a direct link to a map zip file, e.g.:
    https://content.faforever.com/maps/theta_passage_5.v0001.zip
    """
    try:
        if not output_dir.exists():
            output_dir.mkdir(parents=True)

        downloader = MapDownloader()
        map_info = downloader.download(url, output_dir=output_dir)

        print_success(f"Downloaded to {map_info.root_dir}/")
        click.echo()

        map_data = SCMapParser.parse(map_info.scmap_path)

        size_label = get_map_size_label(map_data.width)
        heightmap_shape = f"{map_data.heightmap.shape[0]}x{map_data.heightmap.shape[1]}"
        num_textures = len([t for t in map_data.texture_paths if t])

        click.echo(f"Map: {map_info.name}")
        click.echo(f"Version: {map_info.version}")
        click.echo(f"Size: {size_label}")
        click.echo(f"Heightmap: {heightmap_shape}")
        click.echo(f"Heightmap Scale: {map_data.heightmap_scale}")
        click.echo(f"Water Elevation: {map_data.water_elevation}")
        click.echo(f"Textures: {num_textures} stratum layers")

    except MapDownloadError as e:
        print_error(str(e))
        sys.exit(EXIT_USER_ERROR)
    except SCMapParseError as e:
        print_error(f"Failed to parse downloaded map: {e}")
        sys.exit(EXIT_USER_ERROR)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(EXIT_SYSTEM_ERROR)


@cli.command("bulk-download")
@click.option(
    "--limit",
    "-n",
    type=int,
    default=None,
    help="Maximum number of maps to download",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    default=Path("./maps"),
    help="Directory to download maps to (default: ./maps)",
)
@click.option(
    "--from-file",
    "-f",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="File containing map URLs (one per line)",
)
@click.option(
    "--concurrency",
    "-c",
    type=int,
    default=4,
    help="Number of parallel downloads (default: 4)",
)
@click.option(
    "--resume/--no-resume",
    default=True,
    help="Resume from checkpoint if available (default: resume)",
)
@click.option(
    "--auth-config",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to YAML file with OAuth credentials (client_id, client_secret)",
)
@click.option(
    "--no-auth",
    is_flag=True,
    default=False,
    help="Disable authentication (use seed file fallback)",
)
def bulk_download(
    limit: Optional[int],
    output_dir: Path,
    from_file: Optional[Path],
    concurrency: int,
    resume: bool,
    auth_config: Optional[Path],
    no_auth: bool,
) -> None:
    """Download multiple maps in bulk.

    Downloads maps from the FAF content server with parallel downloads,
    checkpointing for resume capability, and error logging.

    By default, uses a built-in seed list of map URLs. Use --from-file
    to specify a custom list of URLs.

    Authentication: The command checks for OAuth credentials in this order:
    1. --auth-config flag (path to YAML credentials file)
    2. Environment variables: FAF_CLIENT_ID, FAF_CLIENT_SECRET
    3. Falls back to seed file (with warning)

    Examples:

        # Download 100 maps from seed list
        faf bulk-download --limit 100 --output-dir /data/maps

        # Download from custom URL file
        faf bulk-download --from-file my_urls.txt --output-dir /data/maps

        # Resume interrupted download
        faf bulk-download --resume --output-dir /data/maps

        # Use credentials from config file
        faf bulk-download --auth-config ~/.faf/credentials.yaml --output-dir /data/maps

        # Use environment variables for auth
        export FAF_CLIENT_ID="your_client_id"
        export FAF_CLIENT_SECRET="your_client_secret"
        faf bulk-download --output-dir /data/maps

        # Explicitly disable authentication
        faf bulk-download --no-auth --output-dir /data/maps
    """
    try:
        # Set up authentication if available and not disabled
        # _auth_client is unused until TODO-012 is resolved (switch to API from seed file)
        _auth_client: Optional[FAFAuthClient] = None
        if not no_auth and not from_file:
            # Try to get auth credentials
            if auth_config:
                try:
                    _auth_client = FAFAuthClient.from_config_file(auth_config)
                    click.echo(f"Using credentials from: {auth_config}")
                except FAFAuthError as e:
                    print_error(f"Failed to load auth config: {e}")
                    sys.exit(EXIT_USER_ERROR)
            elif has_credentials_in_environment():
                try:
                    _auth_client = FAFAuthClient.from_environment()
                    click.echo("Using credentials from environment variables")
                except FAFAuthError as e:
                    print_error(f"Failed to load credentials from environment: {e}")
                    sys.exit(EXIT_USER_ERROR)
            else:
                click.echo(
                    click.style(
                        "Warning: No OAuth credentials found. " "Using seed file fallback.",
                        fg="yellow",
                    )
                )
                click.echo("  Set FAF_CLIENT_ID and FAF_CLIENT_SECRET environment variables,")
                click.echo("  or use --auth-config to specify a credentials file.")
                click.echo()

        def progress_callback(progress: DownloadProgress) -> None:
            """Update progress display."""
            total = progress.total
            done = progress.completed + progress.failed + progress.skipped
            click.echo(
                f"\rProgress: {done}/{total} "
                f"(completed: {progress.completed}, "
                f"failed: {progress.failed}, "
                f"skipped: {progress.skipped})",
                nl=False,
            )

        downloader = BulkDownloader(
            output_dir=output_dir,
            concurrency=concurrency,
            progress_callback=progress_callback,
        )

        click.echo(f"Output directory: {output_dir}")
        click.echo(f"Concurrency: {concurrency}")
        if limit:
            click.echo(f"Limit: {limit}")
        click.echo()

        if from_file:
            click.echo(f"Reading URLs from: {from_file}")
            progress = downloader.download_from_file(from_file, limit=limit, resume=resume)
        else:
            # TODO-012: Use API with auth_client when credentials are verified
            # For now, continue using seed file fallback
            click.echo("Using built-in seed URL list")
            click.echo("(Use --from-file to specify custom URLs)")
            try:
                progress = downloader.download_from_seed_file(limit=limit, resume=resume)
            except FileNotFoundError:
                print_error("Seed URL file not found. Use --from-file to specify URLs.")
                sys.exit(EXIT_USER_ERROR)

        click.echo()
        click.echo()
        print_success("Download complete!")
        click.echo(f"  Total: {progress.total}")
        click.echo(f"  Completed: {progress.completed}")
        click.echo(f"  Failed: {progress.failed}")
        click.echo(f"  Skipped: {progress.skipped}")

        if progress.failed > 0:
            click.echo(f"\nSee {output_dir}/failures.json for details on failed downloads.")

    except FileNotFoundError as e:
        print_error(str(e))
        sys.exit(EXIT_USER_ERROR)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(EXIT_SYSTEM_ERROR)


@cli.command()
@click.argument("input_dir", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    "output_dir",
    type=click.Path(path_type=Path),
    required=True,
    help="Output directory for the dataset",
)
@click.option(
    "--min-size",
    type=int,
    default=None,
    help="Minimum map size in game units (e.g., 256 for 5km)",
)
@click.option(
    "--max-size",
    type=int,
    default=None,
    help="Maximum map size in game units (e.g., 1024 for 20km)",
)
@click.option(
    "--split",
    "split_str",
    type=str,
    default="0.8,0.1,0.1",
    help="Train/val/test split ratios (default: 0.8,0.1,0.1)",
)
@click.option(
    "--seed",
    type=int,
    default=42,
    help="Random seed for reproducible splits (default: 42)",
)
def preprocess(
    input_dir: Path,
    output_dir: Path,
    min_size: Optional[int],
    max_size: Optional[int],
    split_str: str,
    seed: int,
) -> None:
    """Preprocess downloaded maps into an ML-ready dataset.

    Extracts heightmaps from .scmap files, normalizes them to float32 [0,1],
    and creates train/val/test splits.

    INPUT_DIR is the directory containing downloaded map folders
    (e.g., from 'faf bulk-download').

    Examples:

        # Basic preprocessing
        faf preprocess /data/maps --output /data/dataset

        # Filter by size (10km and larger maps only)
        faf preprocess /data/maps --output /data/dataset --min-size 512

        # Custom split ratios (70% train, 15% val, 15% test)
        faf preprocess /data/maps --output /data/dataset --split 0.7,0.15,0.15

        # Reproducible splits with specific seed
        faf preprocess /data/maps --output /data/dataset --seed 123
    """
    try:
        # Parse split ratios
        try:
            split_parts = [float(x.strip()) for x in split_str.split(",")]
            if len(split_parts) != 3:
                raise ValueError("Expected 3 values")
            split_ratios = {
                "train": split_parts[0],
                "val": split_parts[1],
                "test": split_parts[2],
            }
        except (ValueError, IndexError) as e:
            print_error(f"Invalid split format '{split_str}': {e}")
            print_error("Expected format: TRAIN,VAL,TEST (e.g., 0.8,0.1,0.1)")
            sys.exit(EXIT_USER_ERROR)

        def progress_callback(progress: BuildProgress) -> None:
            """Update progress display."""
            total = progress.total
            done = progress.processed + progress.failed + progress.skipped
            click.echo(
                f"\rProgress: {done}/{total} "
                f"(processed: {progress.processed}, "
                f"failed: {progress.failed}, "
                f"skipped: {progress.skipped}) "
                f"- {progress.current_map}",
                nl=False,
            )

        click.echo(f"Input directory: {input_dir}")
        click.echo(f"Output directory: {output_dir}")
        click.echo(
            f"Split ratios: train={split_ratios['train']}, "
            f"val={split_ratios['val']}, test={split_ratios['test']}"
        )
        click.echo(f"Random seed: {seed}")
        if min_size:
            click.echo(f"Min size filter: {min_size}")
        if max_size:
            click.echo(f"Max size filter: {max_size}")
        click.echo()

        builder = DatasetBuilder(
            output_dir=output_dir,
            min_size=min_size,
            max_size=max_size,
            split_ratios=split_ratios,
            seed=seed,
            progress_callback=progress_callback,
        )

        result = builder.build(input_dir)

        click.echo()
        click.echo()
        print_success("Preprocessing complete!")
        click.echo(f"  Output: {result.output_dir}")
        click.echo(f"  Total samples: {result.total_samples}")
        click.echo(f"  Processed: {result.processed}")
        click.echo(f"  Failed: {result.failed}")
        click.echo(f"  Skipped: {result.skipped}")
        click.echo()
        click.echo("Splits:")
        click.echo(f"  Train: {result.split_counts.get('train', 0)}")
        click.echo(f"  Val: {result.split_counts.get('val', 0)}")
        click.echo(f"  Test: {result.split_counts.get('test', 0)}")

        if result.failed > 0:
            click.echo(f"\nSee {output_dir}/errors.json for details on failed maps.")

    except FileNotFoundError as e:
        print_error(str(e))
        sys.exit(EXIT_USER_ERROR)
    except ValueError as e:
        print_error(str(e))
        sys.exit(EXIT_USER_ERROR)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(EXIT_SYSTEM_ERROR)


@cli.command("dataset-validate")
@click.argument("dataset_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    default=False,
    help="Output results as JSON",
)
def dataset_validate(dataset_path: Path, output_json: bool) -> None:
    """Validate a preprocessed dataset.

    Checks that all heightmaps are valid, values are in range,
    and train/val/test splits are properly constructed.

    DATASET_PATH is the path to a dataset created by 'faf preprocess'.

    Exit code is 0 if valid, 1 if errors found.

    Examples:

        # Validate and show human-readable output
        faf dataset-validate /data/dataset

        # Output validation report as JSON
        faf dataset-validate /data/dataset --json > report.json
    """
    try:
        validator = DatasetValidator(dataset_path)
        report = validator.validate()

        if output_json:
            click.echo(report.to_json())
        else:
            if report.valid:
                print_success(f"Dataset is valid: {dataset_path}")
                click.echo(f"  Total samples: {report.total_samples}")
                click.echo(f"  Valid samples: {report.valid_samples}")
            else:
                print_error(f"Dataset has errors: {dataset_path}")
                click.echo(f"  Total samples: {report.total_samples}")
                click.echo(f"  Valid samples: {report.valid_samples}")
                click.echo(f"  Invalid samples: {report.invalid_samples}")

                if report.metadata_errors:
                    click.echo("\nMetadata errors:")
                    for err in report.metadata_errors:
                        click.echo(f"  - {err}")

                if report.split_errors:
                    click.echo("\nSplit errors:")
                    for err in report.split_errors:
                        click.echo(f"  - {err}")

                if report.sample_errors:
                    click.echo(f"\nSample errors ({len(report.sample_errors)} samples):")
                    for sample_err in report.sample_errors[:10]:  # Show first 10
                        click.echo(f"  {sample_err.sample_id}:")
                        for err in sample_err.errors:
                            click.echo(f"    - {err}")
                    if len(report.sample_errors) > 10:
                        click.echo(f"  ... and {len(report.sample_errors) - 10} more")

        sys.exit(EXIT_SUCCESS if report.valid else EXIT_USER_ERROR)

    except FileNotFoundError as e:
        print_error(str(e))
        sys.exit(EXIT_USER_ERROR)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(EXIT_SYSTEM_ERROR)


@cli.command("dataset-info")
@click.argument("dataset_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    default=False,
    help="Output results as JSON",
)
@click.option(
    "--no-heightmap-stats",
    is_flag=True,
    default=False,
    help="Skip heightmap statistics (faster for large datasets)",
)
def dataset_info(dataset_path: Path, output_json: bool, no_heightmap_stats: bool) -> None:
    """Show statistics for a preprocessed dataset.

    Displays information about map sizes, terrain types, water coverage,
    and heightmap value distributions.

    DATASET_PATH is the path to a dataset created by 'faf preprocess'.

    Examples:

        # Show human-readable statistics
        faf dataset-info /data/dataset

        # Output statistics as JSON
        faf dataset-info /data/dataset --json > stats.json

        # Skip heightmap stats for faster output
        faf dataset-info /data/dataset --no-heightmap-stats
    """
    try:
        stats = DatasetStats(dataset_path, compute_heightmap_stats=not no_heightmap_stats)
        result = stats.compute()

        if output_json:
            click.echo(result.to_json())
        else:
            click.echo(result.format_human_readable())

    except FileNotFoundError as e:
        print_error(str(e))
        sys.exit(EXIT_USER_ERROR)
    except ValueError as e:
        print_error(str(e))
        sys.exit(EXIT_USER_ERROR)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(EXIT_SYSTEM_ERROR)


if __name__ == "__main__":
    cli()
