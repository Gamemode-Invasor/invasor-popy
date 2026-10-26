"""Popy: show Steam notifications (as Steam shows an achievement) from a local web service.

Programs on this machine POST JSON to http://127.0.0.1:<port>/notify (see endpoints.py), and
Invasor's core shows it (ctx.notify). If Steam can't show notifications, the request gets a 503
and nothing else is affected; if the port is taken, the tab says so. "Do not disturb" silences
it, read live, without restarting the service.
"""
import threading

from . import endpoints as endpoints_mod
from . import service

ctx = None
server = None
error = None
eps = {}  # name -> Endpoint
_lock = threading.Lock()


def _stop_service():
    """Stop the web service (with _lock held)."""
    global server
    if server:
        server.stop()
        server = None


def _start():
    """(Re)start the service with the current settings. Never raises."""
    global server, error
    with _lock:
        _stop_service()
        error = None
        if not ctx.settings.get("enabled"):
            return
        port = ctx.settings.get("port")
        s = service.PopyServer(port, ctx.notify, ctx.log, endpoints=eps.values(), unavailable=(ctx.Unavailable,),
                               quiet=lambda: ctx.settings.get("dnd"), default_icon=lambda name: endpoints_mod.default_icon())
        try:
            s.start()
        except OSError as e:
            error = f"can't listen on 127.0.0.1:{port} ({e.strerror or e})"
            ctx.log.warning("%s", error)
            return
        server = s
        ctx.log.info("listening on http://127.0.0.1:%s/notify", port)


def _changed(key, value):
    # Only these need a new server: "do not disturb" is read live.
    if key in ("enabled", "port"):
        _start()


def setup(context):
    global ctx, eps
    ctx = context
    eps = endpoints_mod.build()
    context.settings.on_change(_changed)
    _start()


def teardown():
    with _lock:
        _stop_service()


def status():
    port = ctx.settings.get("port")
    return {"enabled": ctx.settings.get("enabled"), "running": server is not None, "port": port,
            "url": f"http://127.0.0.1:{port}/notify", "error": error, "dnd": ctx.settings.get("dnd")}


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
