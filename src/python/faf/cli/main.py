"""FAF Map AI command-line interface.

This module provides CLI commands for downloading and parsing Supreme Commander maps.
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click
import numpy as np

from faf.downloader import BulkDownloader, DownloadProgress, MapDownloader, MapDownloadError
from faf.parser import SCMapParser
from faf.parser.scmap import SCMapParseError

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
def bulk_download(
    limit: Optional[int],
    output_dir: Path,
    from_file: Optional[Path],
    concurrency: int,
    resume: bool,
) -> None:
    """Download multiple maps in bulk.

    Downloads maps from the FAF content server with parallel downloads,
    checkpointing for resume capability, and error logging.

    By default, uses a built-in seed list of map URLs. Use --from-file
    to specify a custom list of URLs.

    Examples:

        # Download 100 maps from seed list
        faf bulk-download --limit 100 --output-dir /data/maps

        # Download from custom URL file
        faf bulk-download --from-file my_urls.txt --output-dir /data/maps

        # Resume interrupted download
        faf bulk-download --resume --output-dir /data/maps
    """
    try:

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


if __name__ == "__main__":
    cli()
