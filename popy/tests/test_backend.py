import http.client
import json
import logging
import socket
import unittest

from tests.loader import HERE, free_port, load_backend, submodule
MODULE = json.loads((HERE / "module.json").read_text())


def defaults():
    """Every setting's default, as the core would give them (sections flattened)."""
    fields = []
    for item in MODULE["settings"]:
        fields += item.get("items", [item])
    return {f["key"]: f["default"] for f in fields}


class InvalidArgument(ValueError):
    pass


class Unavailable(RuntimeError):
    pass


class FakeSettings:
    def __init__(self, values):
        self.values, self.cbs = values, []

    def get(self, key=None):
        return self.values if key is None else self.values[key]

    def on_change(self, cb):
        self.cbs.append(cb)

    def change(self, key, value):
        self.values[key] = value
        for cb in self.cbs:
            cb(key, value)


class FakeCtx:
    InvalidArgument = InvalidArgument
    Unavailable = Unavailable

    def __init__(self, port):
        self.settings = FakeSettings({**defaults(), "enabled": True, "port": port})
        self.log = logging.getLogger("test.popy")
        self.shown, self.bodies, self.icons, self.sounds = [], [], [], []

    def notify(self, title, body="", icon="", sound=""):
        self.shown.append(title)
        self.bodies.append(body)
        self.icons.append(icon)
        self.sounds.append(sound)


class Backend(unittest.TestCase):
    def setUp(self):
        self.b = load_backend()
        self.ctx = FakeCtx(free_port())
        self.b.setup(self.ctx)
        self.addCleanup(self.b.teardown)

    def post(self, body, path="/notify"):
        c = http.client.HTTPConnection("127.0.0.1", self.b.status()["port"], timeout=5)
        c.request("POST", path, json.dumps(body), {"Content-Type": "application/json"})
        r = c.getresponse()
        r.read()
        c.close()
        return r.status

    def test_lifecycle(self):
        b, ctx = self.b, self.ctx
        self.assertTrue(b.status()["running"])
        self.assertTrue(b.test())
        self.assertEqual(ctx.shown, ["Popy"])
        self.assertEqual(b.recent()[0]["title"], "Popy")
        ctx.settings.change("enabled", False)
        self.assertEqual((b.status()["running"], b.status()["error"]), (False, None))
        self.assertTrue(b.test())  # the test button works with the service off too

    def test_do_not_disturb_is_read_live(self):
        b, ctx = self.b, self.ctx
        server = b.server
        ctx.settings.change("dnd", True)
        self.assertIs(b.server, server)  # no restart
        st = b.status()
        self.assertTrue(st["dnd"])
        self.assertEqual([(e["path"], e["on"]) for e in st["endpoints"]], [("/notify", True)])
        self.assertEqual(st["endpoints"][0]["url"], f"http://127.0.0.1:{st['port']}/notify")
        self.assertEqual(server.receive("popy", "x", "", ""), "do_not_disturb")
        self.assertTrue(b.test())  # the test button ignores it
        self.assertEqual(ctx.shown, ["Popy"])
        ctx.settings.change("dnd", False)
        self.assertIsNone(server.receive("popy", "x", "", ""))
        self.assertEqual(ctx.shown, ["Popy", "x"])
        ctx.settings.change("port", free_port())
        self.assertIsNot(b.server, server)  # the port does restart it

    def test_a_notification_without_an_image_gets_popy_s(self):
        endpoints = submodule(self.b, "endpoints")
        self.assertEqual(self.post({"title": "Hi"}), 200)
        self.assertEqual(self.post({"title": "Hi", "icon": "https://x.example/a.png"}), 200)
        default = endpoints.default_icon()
        self.assertTrue(default.startswith("data:image/png;base64,"))
        self.assertEqual(self.ctx.icons, [default, "https://x.example/a.png"])
        self.assertTrue(self.b.test())
        self.assertEqual(self.ctx.icons[-1], default)

    def test_a_sound_reaches_the_core(self):
        for body in ({"title": "a"}, {"title": "b", "sound": "online"}):
            self.assertEqual(self.post(body), 200)
        self.assertEqual(self.ctx.sounds, ["", "online"])  # no sound: Steam decides

    def test_starting_the_service_says_nothing(self):
        self.assertEqual(self.ctx.shown, [])


class Port(unittest.TestCase):
    def test_port_taken_is_reported_not_raised(self):
        with socket.socket() as busy:
            busy.bind(("127.0.0.1", 0))
            busy.listen()
            b = load_backend()
            b.setup(FakeCtx(busy.getsockname()[1]))
            self.addCleanup(b.teardown)
            st = b.status()
            self.assertFalse(st["running"])
            self.assertIn("can't listen", st["error"])


if __name__ == "__main__":
    unittest.main()
