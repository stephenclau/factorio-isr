from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("factorio-isr")
except PackageNotFoundError:
    # Package not installed, fallback for development
    __version__ = "dev"
