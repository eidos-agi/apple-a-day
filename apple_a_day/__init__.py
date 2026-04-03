"""apple-a-day: Mac health toolkit — keeps the doctor away."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("apple-a-day")
except PackageNotFoundError:
    __version__ = "dev"
