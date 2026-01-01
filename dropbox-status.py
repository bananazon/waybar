#!/usr/bin/env python3

import json
import re
from dataclasses import dataclass

import click

from waybar import glyphs
from waybar.util import system


@dataclass
class DropboxStatus:
    success: bool = False
    error: str | None = None
    icon: str = glyphs.fa_dropbox
    message: str | None = None
    tooltip: str | None = None


context_settings = dict(help_option_names=["-h", "--help"])


def generate_tooltip(dropbox_status: DropboxStatus) -> str:
    tooltip: list[str] = []

    return "\n".join(tooltip)


def get_dropbox_status() -> DropboxStatus:
    dropbox_status: DropboxStatus = DropboxStatus()
    command = "dropbox status"
    rc, stdout_raw, stderr_raw = system.run_piped_command(command)

    stdout = stdout_raw if isinstance(stdout_raw, str) else ""
    stderr = stderr_raw if isinstance(stderr_raw, str) else ""

    if rc == 0:
        if stdout != "":
            lines = [line.strip() for line in stdout.split("\n")]
            if lines[0] == "Up to date":
                dropbox_status = DropboxStatus(
                    success=True,
                    message=stdout,
                )
            elif lines[0] == "Dropbox isn't running!":
                dropbox_status = DropboxStatus(
                    success=True,
                    message=stdout,
                )
            elif lines[0] == "Syncing paused":
                dropbox_status = DropboxStatus(
                    success=True,
                    message=stdout,
                )
            elif lines[0].startswith("Syncing"):
                message: str = "Syncing"
                tooltip: str = "Syncing..."

                match = re.search(r"(Syncing\s+(\d[\d,]*)+\s+files)", lines[0])
                if match:
                    message = match.group(1)

                tooltip = "\n".join(lines[1:])

                dropbox_status = DropboxStatus(
                    success=True,
                    message=message,
                    tooltip=tooltip,
                )

        else:
            dropbox_status = DropboxStatus(
                error="No output from dropbox",
                tooltip="Dropbox error",
            )
    else:
        dropbox_status = DropboxStatus(
            error=stderr or f"{command}",
            tooltip="Dropbox error",
        )

    return dropbox_status


@click.command(
    help="Get Dropbox sync status",
    context_settings=context_settings,
)
def main():
    output: dict[str, object] = {}
    dropbox_status = get_dropbox_status()
    if dropbox_status.success:
        output = {
            "text": f"{dropbox_status.icon}{glyphs.icon_spacer}{dropbox_status.message}",
            "class": "success",
            "tooltip": dropbox_status.tooltip or None,
        }
    else:
        output = {
            "text": f"{dropbox_status.icon}{glyphs.icon_spacer}{dropbox_status.error}",
            "class": "weeoe",
            "tooltip": dropbox_status.tooltip or None,
        }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
