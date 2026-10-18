"""Popy: show Steam notifications (as Steam shows an achievement) from a local web service.

Programs on this machine POST JSON to http://127.0.0.1:<port>/notify (see endpoints.py), and
Invasor's core shows it (ctx.notify). If Steam can't show notifications, the request gets a 503
and nothing else is affected; if the port is taken, the tab says so. "Do not disturb" silences
it, read live, without restarting the service. Each endpoint is told when it starts and stops
(endpoints.Endpoint), and can announce itself.
"""
import threading

from . import endpoints as endpoints_mod
from . import service

ctx = None
server = None
error = None
eps = {}  # name -> Endpoint
host = None
_lock = threading.Lock()


class Host:
    """What an endpoint can use of Popy."""

    def __init__(self, context):
        self.ctx, self.log = context, context.log

    @property
    def port(self):
        return server.port if server else None

    def announce(self, endpoint, title, body="", icon="", sound=""):
        """A message of the endpoint itself, with its image unless there's a better icon (or
        Popy's default one, if the endpoint has none). It follows "do not disturb" and the
        rate limit."""
        s = server
        if not s:
            return
        try:
            s.receive(endpoint.name, title[:64], body[:256], icon or endpoint.icon_or_default(), announce=True, sound=sound)
        except service.Rejected as e:
            self.log.warning("%s: message not shown: %s", endpoint.name, e)


def _icon_for(name):
    """The icon of a notification of the endpoint that has none: its image, or Popy's."""
    return eps[name].icon_or_default() if name in eps else endpoints_mod.default_icon()


def _stop_endpoints():
    for ep in eps.values():
        try:
            ep.stop()
        except Exception:
            ctx.log.exception("%s: stopping failed", ep.name)


def _start():
    """(Re)start the service with the current settings. Never raises."""
    global server, error
    with _lock:
        _stop_endpoints()
        if server:
            server.stop()
            server = None
        error = None
        if not ctx.settings.get("enabled"):
            return
        port = ctx.settings.get("port")
        s = service.PopyServer(port, ctx.notify, ctx.log, endpoints=eps.values(), unavailable=(ctx.Unavailable,),
                               quiet=lambda: ctx.settings.get("dnd"), default_icon=_icon_for)
        try:
            s.start()
        except OSError as e:
            error = f"can't listen on 127.0.0.1:{port} ({e.strerror or e})"
            ctx.log.warning("%s", error)
            return
        server = s
        ctx.log.info("listening on http://127.0.0.1:%s/notify", port)
        for ep in eps.values():
            _safely(ep.start, host)


def _safely(call, *args):
    try:
        call(*args)
    except Exception:
        ctx.log.exception("endpoint hook failed")


def _changed(key, value):
    # Only these need a new server: "do not disturb" is read live.
    if key in ("enabled", "port"):
        _start()


def setup(context):
    global ctx, host, eps
    ctx = context
    host = Host(context)
    eps = endpoints_mod.build()
    context.settings.on_change(_changed)
    _start()


def teardown():
    global server
    with _lock:
        _stop_endpoints()
        if server:
            server.stop()
            server = None


def status():
    port = ctx.settings.get("port")
    base = f"http://127.0.0.1:{port}"
    running = server is not None
    listed = [{"name": ep.name, "path": ep.path, "url": base + ep.path, "on": True,
               "details": ep.details() if running else []} for ep in eps.values()]
    return {"enabled": ctx.settings.get("enabled"), "running": running, "port": port,
            "url": base + "/notify", "error": error, "dnd": ctx.settings.get("dnd"), "endpoints": listed}


def recent():
    return list(server.recent) if server else []


def test():
    """Show a test notification (through the service's rate limit, as a POST would). It
    ignores "do not disturb": the user asked for it."""
    s = server or service.PopyServer(0, ctx.notify, ctx.log, unavailable=(ctx.Unavailable,))
    try:
        s.notify("Popy", "This is a test notification from Invasor.", endpoints_mod.default_icon())
    except service.Rejected as e:
        raise (ctx.Unavailable if e.status == 503 else ctx.InvalidArgument)(str(e)) from None
    return True


METHODS = {"status": status, "recent": recent, "test": test}
