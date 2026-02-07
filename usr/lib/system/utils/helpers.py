import json
import os
import subprocess

import yaml
from classes import exceptions


def get_system_config() -> dict:
    """Retrieve system config.

    Returns:
        Dict containing system config.
    """

    try:
        with open("/system.yaml") as system_yaml_file:
            return yaml.safe_load(system_yaml_file)
    except Exception:
        raise exceptions.SystemFileException()


def fetch_image_metadata(image_name: str) -> dict:
    """Fetch image metadata.

    Args:
        image_name: Image to check metadata for.

    Returns:
        Dict containing image metadata.
    """
    try:
        return json.loads(
            subprocess.run(
                ["skopeo", "inspect", image_name], stdout=subprocess.PIPE
            ).stdout.decode()
        )
    except json.decoder.JSONDecodeError:
        raise exceptions.ImageMetadataException()


def pull_image(image_name) -> None:
    """Pull the provided image locally."""
    if not (
        (
            subprocess.run(
                [
                    "skopeo",
                    "copy",
                    image_name,
                    "--dest-shared-blob-dir=/var/lib/commonarch/blobs",
                    "oci:/var/lib/commonarch/system-image:main",
                ]
            ).returncode
            == 0
        )
        and (
            subprocess.run(
                ["rm", "-rf", "/var/lib/commonarch/system-image/blobs"]
            ).returncode
            == 0
        )
        and (
            subprocess.run(
                [
                    "ln",
                    "-s",
                    "/var/lib/commonarch/blobs",
                    "/var/lib/commonarch/system-image/blobs",
                ]
            ).returncode
            == 0
        )
        and (
            subprocess.run(
                [
                    "umoci",
                    "unpack",
                    "--image",
                    "/var/lib/commonarch/system-image:main",
                    "/var/lib/commonarch/bundle",
                ]
            ).returncode
            == 0
        )
    ):
        raise exceptions.ImageMetadataException()


def is_already_latest(image_name: str) -> bool:
    """Check if already on the latest revision.

    Args:
        image_name: Image to check against.

    Returns:
        True if there is no update available; otherwise False.
    """

    if os.path.isfile("/var/lib/commonarch/revision"):
        with open("/var/lib/commonarch/revision") as current_revision_file:
            current_revision = current_revision_file.read().strip()
    else:
        return False

    return (
        fetch_image_metadata(image_name)["Labels"].get(
            "org.opencontainers.image.revision"
        )
        == current_revision
    )


def notify_prompt(title: str, body: str, actions: dict):
    """Display a notification prompting the user.

    Args:
        title: Title of the notification.
        body: Body of the notification.
        actions: Dict containing action key-value pairs.

    Returns:
        String containing selected action.
    """
    return (
        subprocess.run(
            [
                "notify-send",
                "--app-name=System",
                "--urgency=critical",
                title,
                body,
                *[f"--action={action}={actions[action]}" for action in actions.keys()],
            ],
            stdout=subprocess.PIPE,
        )
        .stdout.decode()
        .strip()
    )
