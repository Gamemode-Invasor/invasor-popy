"""What an endpoint is, and the ones Popy has (one file each: endpoint_<name>.py).

An endpoint is a way to send notifications to Popy: a path to POST to and how to turn its
payload into a notification. Subclass Endpoint, put it in endpoint_<name>.py, and add it to
build().
"""
from functools import lru_cache
from pathlib import Path

from . import service

ASSETS = Path(__file__).resolve().parent / "assets"


@lru_cache(maxsize=None)
def default_icon():
    """Popy's own image (assets/default.png) as a data: URI, or "" if it can't be read."""
    try:
        return service.icon_from_file(ASSETS / "default.png")
    except service.Rejected:
        return ""


class Endpoint:
    name = ""  # the "source" of its notifications
    path = ""  # POST here

    def adapt(self, data):
        """The payload (a dict) as (title, body, icon[, sound]), or None to ignore it. Rejected(400, …)
        if it's wrong."""
        raise NotImplementedError


def build():
    """Every endpoint, by name, in the order they are listed."""
    from . import endpoint_popy
    endpoints = [endpoint_popy.Popy()]
    return {ep.name: ep for ep in endpoints}
