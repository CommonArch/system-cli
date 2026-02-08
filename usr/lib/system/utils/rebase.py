import filecmp
import json
import os
import subprocess
import sys

from classes import exceptions
from classes.rootfs import PackageManager, RootFS
from utils import output, users

from . import helpers


def update_cleanup() -> None:
    """Clean-up from previous rebase/update."""
    subprocess.run(
        [
            "rm",
            "-rf",
            "/var/lib/commonarch/bundle",
            "/var/lib/commonarch/system-image",
            "/.update",
            "/.update_rootfs",
            "/.new.etc",
            "/.new.var.lib",
        ]
    )


def merge_etc(new_rootfs) -> None:
    """Merge host and rootfs /etc/ trees into /.new.etc/.

    Args:
        new_rootfs: Path to rootfs.
    """
    subprocess.run(["cp", "-ax", f"{new_rootfs}/etc", "/.new.etc"])

    if not os.path.isdir("/usr/etc"):
        subprocess.run(["rm", "-rf", "/usr/etc"])
        subprocess.run(["cp", "-ax", "/etc", "/usr/etc"])

    etc_diff = filecmp.dircmp("/etc/", "/usr/etc/")

    def handle_diff_etc_files(dcmp):
        dir_name = dcmp.left.replace("/etc/", "/.new.etc/", 1)
        for name in dcmp.left_only:
            subprocess.run(["mkdir", "-p", dir_name])
            subprocess.run(["cp", "-ax", "--", os.path.join(dcmp.left, name), dir_name])
        for name in dcmp.diff_files:
            subprocess.run(["cp", "-ax", "--", os.path.join(dcmp.left, name), dir_name])
        for sub_dcmp in dcmp.subdirs.values():
            handle_diff_etc_files(sub_dcmp)

    handle_diff_etc_files(etc_diff)


def merge_var_lib(new_rootfs) -> None:
    """Merge host and rootfs /var/lib/ trees into /.new.var.lib/.

    Args:
        new_rootfs: Path to rootfs.
    """
    subprocess.run(["cp", "-ax", "/var/lib", "/.new.var.lib"])

    var_lib_diff = filecmp.dircmp(f"{new_rootfs}/var/lib/", "/.new.var.lib/")

    dir_name = "/.new.var.lib/"
    for name in var_lib_diff.left_only:
        if os.path.isdir(os.path.join(var_lib_diff.left, name)):
            subprocess.run(
                ["cp", "-ax", os.path.join(var_lib_diff.left, name), dir_name]
            )


def replace_boot_files() -> None:
    """Replace files in /boot with those from new rootfs."""
    new_boot_files = []

    for f in os.listdir("/.update_rootfs/boot"):
        if not os.path.isdir(f"/.update_rootfs/boot/{f}"):
            subprocess.run(["mv", f"/.update_rootfs/boot/{f}", "/boot"])
            new_boot_files.append(f)

    for f in os.listdir("/boot"):
        if not os.path.isdir(f"/boot/{f}"):
            if f not in new_boot_files:
                subprocess.run(["rm", "-f", f"/boot/{f}"])

    subprocess.run(["grub-mkconfig", "-o", "/boot/grub/grub.cfg"])


def rebase(image_name) -> None:
    """Rebase system to an OS image.

    Args:
        image_name: Name of image to rebase to.
    """

    update_cleanup()

    try:
        system_config = helpers.get_system_config()
    except exceptions.SystemFileException:
        system_config = {"image": image_name}

    try:
        new_revision = helpers.fetch_image_metadata(image_name)["Labels"][
            "org.opencontainers.image.revision"
        ]
    except exceptions.ImageMetadataException:
        output.error(f"failed to read remote metadata for image {image_name}")
        output.warn("does the image exist, and are you connected to the internet?")
        sys.exit(1)
    except KeyError:
        output.error("missing revision from remote image metadata")
        sys.exit(1)

    output.info("pulling image")
    helpers.pull_image(image_name)

    output.info("generating new rootfs")

    # Load image config from pulled bundle
    with open("/var/lib/commonarch/bundle/config.json") as f:
        image_config = json.load(f)

    new_rootfs = RootFS(f"/var/lib/commonarch/bundle/{image_config['root']['path']}")
    new_rootfs.copy_kernels_to_boot()
    new_rootfs.generate_initramfs()

    subprocess.run(["cp", "/etc/locale.gen", f"{new_rootfs}/etc/locale.gen"])
    new_rootfs.exec("locale-gen")

    merge_etc(new_rootfs)

    try:
        # Store new_passwd_entries for users.merge_group() call
        new_passwd_entries = users.merge_passwd(new_rootfs)
    except Exception:
        output.error("malformed /etc/passwd")
        sys.exit(1)

    try:
        users.merge_shadow(new_rootfs)
    except Exception:
        output.error("malformed /etc/shadow")
        sys.exit(1)

    try:
        users.merge_group(new_rootfs, new_passwd_entries)
    except Exception:
        output.error("malformed /etc/group")
        sys.exit(1)

    try:
        users.merge_gshadow(new_rootfs, new_passwd_entries)
    except Exception:
        output.error("malformed /etc/shadow")
        sys.exit(1)

    merge_var_lib(new_rootfs)

    if isinstance((packages := system_config.get("packages")), list):
        PackageManager(new_rootfs).install(*packages)

    if isinstance((services := system_config.get("services")), list):
        for service in services:
            new_rootfs.exec("systemctl", "enable", service)

    if isinstance((user_services := system_config.get("user-services")), list):
        for user_service in user_services:
            new_rootfs.exec("systemctl", "enable", "--global", user_service)

    subprocess.run(["mkdir", "-p", "/.new.var.lib/commonarch"])
    with open("/.new.var.lib/commonarch/revision", "w") as new_revision_file:
        try:
            new_revision_file.write(new_revision)
        except Exception:
            pass

    if (
        len(
            [
                kernel
                for kernel in os.listdir(f"{new_rootfs}/boot")
                if kernel.startswith("vmlinuz")
            ]
        )
        == 0
    ):
        output.error("new rootfs contains no kernel")
        output.error("refusing to proceed with applying update")
        exit(1)

    new_rootfs.exec("cp", "-ax", "/etc", "/usr/etc")
    subprocess.run(["cp", "-ax", str(new_rootfs), "/.update_rootfs"])

    replace_boot_files()

    print()
