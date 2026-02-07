import sys


def info(msg):
    """Print an informative message to stdout.

    Args:
        msg: String containing the message.
    """
    print(f"i: {msg}")


def warn(msg):
    """Print a warning message to stderr.

    Args:
        msg: String containing the message."""
    print(f"w: {msg}", file=sys.stderr)


def error(msg):
    """Print an error message to stderr.

    Args:
        msg: String containing the message.
    """
    print(f"E: {msg}", file=sys.stderr)
