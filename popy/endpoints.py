"""What an endpoint is, and the ones Popy has (one file each: endpoint_<name>.py).

An endpoint is a way to send notifications to Popy: a path to POST to, how to turn its payload
into a notification, and what to do when it starts and stops. Subclass Endpoint, put it in
endpoint_<name>.py, and add it to build().
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
    name = ""     # the "source" of its notifications
    path = ""     # POST here
    label = ""    # how its messages call it
    icon = None   # file in assets/ with its image: used by its own messages

    def adapt(self, data):
        """The payload (a dict) as (title, body, icon[, sound]), or None to ignore it. Rejected(400, …)
        if it's wrong."""
        raise NotImplementedError

    def start(self, host):
        """The service is running."""

    def stop(self):
        """The service is stopping."""

    def details(self):
        """Lines for the tab, under the endpoint, while the service runs."""
        return []

    def icon_data(self):
        """Its image as a data: URI, or "" if it has none."""
        if not hasattr(self, "_icon_data"):
            try:
                self._icon_data = service.icon_from_file(ASSETS / self.icon) if self.icon else ""
            except service.Rejected:
                self._icon_data = ""
        return self._icon_data

    def icon_or_default(self):
        """Its image, or Popy's own if it has none."""
        return self.icon_data() or default_icon()


def build():
    """Every endpoint, by name, in the order they are listed."""
    from . import endpoint_popy
    endpoints = [endpoint_popy.Popy()]
    return {ep.name: ep for ep in endpoints}
