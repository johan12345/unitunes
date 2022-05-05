from tqdm import tqdm
import typer
from universal_playlists.cli.utils import get_playlist_manager
from universal_playlists.main import (
    Config,
    FileManager,
    augment_track,
    get_predicted_tracks,
    get_prediction_track,
)
from typing import List, Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table
from universal_playlists.cli.playlist_cli import playlist_app
from universal_playlists.cli.service_cli import service_app
from universal_playlists.eval.eval import eval_app
from universal_playlists.track import Track

from universal_playlists.types import ServiceType


console = Console()
app = typer.Typer(no_args_is_help=True)
app.add_typer(service_app, name="service")
app.add_typer(playlist_app, name="playlist")
app.add_typer(eval_app, name="eval")


def print_tracks(tracks: List[Track]) -> None:
    for track in tracks:
        console.print(track)
        console.print("")


@app.command()
def init(
    directory: Optional[Path] = typer.Argument(
        Path("."),
        help="Directory to store playlist files in",
    )
) -> None:
    """Initialize a new playlist manager"""
    if not directory:
        directory = Path(".")
    fm = FileManager(directory)

    try:
        fm.save_config(Config())
    except FileExistsError:
        console.print(
            f"A playlist manager is already initialized in {directory}",
            style="red",
        )
        raise typer.Exit()

    fm.make_playlist_dir()


@app.command()
def view(playlist: str) -> None:
    """View a playlist"""
    pm = get_playlist_manager()
    if playlist not in pm.playlists:
        console.print(f"{playlist} is not a playlist", style="red")
        raise typer.Exit()
    pl = pm.playlists[playlist]

    console.print(pl)


@app.command()
def pull(
    playlists: Optional[List[str]] = typer.Argument(None),
    services: Optional[List[str]] = typer.Option(
        None,
        "--service",
        "-s",
        help="Service to pull from",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
    ),
):
    """Pull a playlist from a service"""
    pm = get_playlist_manager()

    if not playlists:
        playlists = list(pm.config.playlists.keys())

    if not services:
        services = list(pm.config.services.keys())

    for playlist_name in playlists:
        if playlist_name not in pm.playlists:
            console.print(f"{playlist_name} is not a playlist", style="red")
            raise typer.Exit()
        pl = pm.playlists[playlist_name]

        new_tracks: List[Track] = []
        removed_tracks: List[Track] = []

        for service_name in services:
            if service_name not in pm.services:
                console.print(f"{service_name} is not a service", style="red")
                raise typer.Exit()
            service = pm.services[service_name]

            uri = pl.find_uri(service.type)
            if not uri:
                continue

            remote_tracks = service.pull_tracks(uri)
            new_tracks.extend(pl.get_new_tracks(remote_tracks))
            removed_tracks.extend(pl.get_removed_tracks(service.type, remote_tracks))

        console.print(f"{len(new_tracks)} new tracks")
        if verbose:
            print_tracks(new_tracks)
        console.print(f"{len(removed_tracks)} removed tracks")
        if verbose:
            print_tracks(removed_tracks)

        console.print("Augmenting new tracks...")
        for track in tqdm(new_tracks):
            augment_track(track)

        pl.merge_new_tracks(new_tracks)
        pl.remove_tracks(removed_tracks)

        pm.save_playlist(pl.name)


@app.command()
def search(
    service: ServiceType,
    playlist: str,
    showall: bool = False,
    debug: bool = False,
    onlyfailed: bool = False,
) -> None:
    """Search for every track in the playlist on the service"""
    typer.echo(f"Searching {service.value} for {playlist}")

    pm = get_playlist_manager()
    pl = pm.playlists[playlist]
    original_tracks = pl.tracks
    streaming_service = [s for s in pm.services.values() if s.type == service][0]
    predicted_tracks = [
        get_prediction_track(streaming_service, track, threshold=0.5)
        for track in tqdm(original_tracks)
    ]
    all_predicted_tracks = [
        get_predicted_tracks(streaming_service, track) for track in original_tracks
    ]

    table = Table(title=f"Uncertain {service.value} search results for {playlist}")
    table.add_column("Original Track")
    table.add_column("Predicted Track")
    table.add_column("Confidence")
    table.show_lines = True

    for i, (original, predicted) in enumerate(zip(original_tracks, predicted_tracks)):
        if predicted is None:
            if showall or onlyfailed:
                table.add_row(original, "", "")
                for track in all_predicted_tracks[i]:
                    table.add_row("", track, f"{original.similarity(track):.2f}")
            continue
        elif onlyfailed:
            continue

        similarity = original.similarity(predicted)
        if not showall and similarity >= 0.7:
            continue

        table.add_row(original, predicted, f"{original.similarity(predicted):.2f}")
        if debug:
            for track in all_predicted_tracks[i][1:]:
                table.add_row("", track, f"{original.similarity(track):.2f}")

    console.print(table)
    num_not_found = len([t for t in predicted_tracks if t is None])
    console.print(f"{len(predicted_tracks) - num_not_found} tracks found")
    console.print(f"{num_not_found} tracks not found")
