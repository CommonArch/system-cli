import os
import subprocess

from classes.exceptions import UnsupportedPkgManagerException


class RootFS:
    """Handles root filesystem operations.

    Attributes:
        rootfs_path: A string containing the path to the root filesystem
    """

    def __init__(self, rootfs_path: str) -> None:
        """Initialises the instance based on a rootfs path.

        Args:
            rootfs: Path to root filesystem.
        """
        self.rootfs_path = rootfs_path

    def exists(self, path):
        """Check if path exists within rootfs.

        Args:
            path: Path to check for.
        """
        return os.path.exists(os.path.join(self.rootfs_path, path))

    def exec(self, *cmd, **kwargs):
        """Run command within rootfs.

        Args:
            *cmd: Variable length command.
            **kwargs: Keyword arguments list for subprocess.run().
        """
        return subprocess.run(
            ["systemd-nspawn", "-D", self.rootfs_path] + list(cmd),
            **kwargs,
        )

    def copy_kernels_to_boot(self) -> None:
        """Copy any found kernels to /boot within rootfs."""
        for boot_file in os.listdir(f"{self.rootfs_path}/boot"):
            if not os.path.isdir(boot_file):
                self.exec("rm", "-f", f"/boot/{boot_file}")

        for kernel in os.listdir(f"{self.rootfs_path}/usr/lib/modules"):
            self.exec(
                "cp",
                f"/usr/lib/modules/{kernel}/vmlinuz",
                f"/boot/vmlinuz-{kernel}",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def generate_initramfs(self) -> None:
        """Generate initramfs within rootfs."""
        self.exec("dracut", "--force", "--regenerate-all")

    def __repr__(self) -> str:
        return self.rootfs_path


class PackageManager:
    """Handle package manager operations.

    Attributes:
        rootfs: An instance of RootFS.
        pkg_manager: A string containing the type of package manager ('apt' or 'pacman').
    """

    def __init__(self, rootfs: RootFS, pkg_manager: str = "detect") -> None:
        """Initialises the instance based on package manager and rootfs.

        Args:
            rootfs: An instance of rootfs
            pkg_manager: Type of package manager ('apt' or 'pacman').
        """
        self.rootfs = rootfs

        # Detect package manager if not already known
        self.pkg_manager = (
            self.detect_pkg_manager(rootfs) if pkg_manager == "detect" else pkg_manager
        )

        if self.pkg_manager == "none":
            raise UnsupportedPkgManagerException()

    def init(self) -> None:
        """Initialises the package manager for use."""
        if self.pkg_manager == "pacman":
            self.rootfs.exec("pacman-key", "--init")
            self.rootfs.exec("pacman-key", "--populate")
        elif self.pkg_manager == "apt":
            self.rootfs.exec("apt-get", "update")

    def install(self, *pkgs) -> None:
        """Installs packages within rootfs.

        Args:
            *pkgs: Variable length list of packages to install.
        """
        if self.pkg_manager == "pacman":
            self.rootfs.exec("pacman", "-Sy", "--ask=4", *pkgs)
        elif self.pkg_manager == "apt":
            return self.rootfs.exec(
                [
                    "env",
                    "DEBIAN_FRONTEND=noninteractive",
                    "apt-get",
                    "install",
                    "-yq",
                    *pkgs,
                ]
            )

    @staticmethod
    def detect_pkg_manager(rootfs) -> str:
        """Detect package manager from rootfs.

        Args:
            rootfs: Path to root filesystem.

        Returns:
            The type of package manager found.
        """

        if os.path.isfile(os.path.join(str(rootfs), "usr/bin/pacman")):
            return "pacman"
        elif os.path.isfile(os.path.join(str(rootfs), "usr/bin/apt-get")):
            return "apt"
        else:
            return "none"
