#!/usr/bin/python3

import os
import subprocess
import sys
import time

import click
import fasteners
from utils import helpers, output
from utils.rebase import rebase


@click.group("cli")
def cli():
    """Manage system operations."""


def main():
    cli(prog_name="system")


@cli.command("update-check", hidden=True)
def update_check_daemon():
    if os.environ.get("USER") == "gdm-greeter":
        exit()

    check_interval = 3600

    if isinstance(helpers.get_system_config().get("auto-update"), bool):
        if not helpers.get_system_config().get("auto-update"):
            exit()

    if isinstance(helpers.get_system_config().get("auto-update-interval"), int):
        check_interval = helpers.get_system_config()["auto-update-interval"]

    while True:
        try:
            if not os.path.isdir("/.update_rootfs"):
                system_config = helpers.get_system_config()

                if not helpers.is_already_latest(system_config["image"]):
                    if helpers.notify_prompt(
                        title="Update available",
                        body="A system update is available",
                        actions={"update": "Update in the background"},
                    ):
                        if (
                            subprocess.run(["pkexec", "system", "update"]).returncode
                            == 0
                        ):
                            if (
                                helpers.notify_prompt(
                                    title="System updated",
                                    body="Reboot to apply update?",
                                    actions={"reboot": "Reboot now", "later": "Later"},
                                )
                                == "reboot"
                            ):
                                subprocess.run(["reboot"])
        except Exception:
            pass

        time.sleep(check_interval)


@cli.command("update")
@click.option("-f", "--force", is_flag=True)
def upgrade_cmd(force):
    """
    Update your system to the latest available image.
    """

    if os.geteuid() != 0:
        output.error("must be run as root")
        exit(1)

    system_lock = fasteners.InterProcessLock("/var/lib/commonarch/.system-lock")
    output.info("attempting to acquire system lock")
    output.info("if stuck for long, an update may be progressing in the background")

    if not os.path.isdir("/.update_rootfs") and not force:
        system_config = helpers.get_system_config()

        if helpers.is_already_latest(system_config["image"]):
            output.error("your system is already up-to-date")
            sys.exit(1)
    else:
        output.error(
            "an update has already been downloaded and is waiting to be applied"
        )
        output.error("you must reboot before running this command")
        sys.exit(1)

    with system_lock:
        rebase(system_config["image"])
        output.info("update complete; you may now reboot.")


@cli.command("rebase")
@click.argument("image_name", nargs=1, required=True)
@click.option("-f", "--force", is_flag=True)
def rebase_cmd(image_name, force):
    """
    Switch to a different OS image.
    """

    if os.geteuid() != 0:
        output.error("must be run as root")
        exit(1)

    system_lock = fasteners.InterProcessLock("/var/lib/commonarch/.system-lock")
    output.info("attempting to acquire system lock")
    output.info("if stuck for long, an update may be progressing in the background")

    if not os.path.isdir("/.update_rootfs") and not force:
        if helpers.is_already_latest(image_name):
            output.error(
                "your system is already on the latest revision of the specified image"
            )
            sys.exit(1)
    else:
        output.error(
            "an update has already been downloaded and is waiting to be applied"
        )
        output.error("you must reboot before running this command")
        sys.exit(1)

    with system_lock:
        rebase(image_name)
        output.info("update complete; you may now reboot.")


if __name__ == "__main__":
    main()
