"""Tests for the device registry and active-device push routing."""
import os
import tempfile
import time
import unittest

import config
from agent import longterm


def _fresh_db():
    d = tempfile.mkdtemp()
    longterm.DB_PATH = os.path.join(d, "dev.db")
    longterm.init_db()
    from agent import notify, devices
    notify.init_push_table()
    devices.init_db()


class TestRegistry(unittest.TestCase):
    def setUp(self):
        self._orig = longterm.DB_PATH
        _fresh_db()

    def tearDown(self):
        longterm.DB_PATH = self._orig

    def test_touch_upserts_and_heartbeats(self):
        from agent import devices
        devices.touch("dev-1", label="phone", kind="pwa")
        rows = devices.list_devices()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["label"], "phone")
        first_seen = rows[0]["last_seen"]
        time.sleep(0.01)
        devices.touch("dev-1")  # heartbeat keeps label
        rows = devices.list_devices()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["label"], "phone")
        self.assertGreaterEqual(rows[0]["last_seen"], first_seen)

    def test_online_flag(self):
        from agent import devices
        devices.touch("dev-1", label="laptop")
        self.assertTrue(devices.list_devices(fresh_seconds=300)[0]["online"])
        self.assertFalse(devices.list_devices(fresh_seconds=0)[0]["online"])

    def test_active_device_is_most_recent(self):
        from agent import devices
        devices.touch("old")
        time.sleep(0.01)
        devices.touch("new")
        self.assertEqual(devices.active_device_id(), "new")

    def test_active_device_none_when_stale(self):
        from agent import devices
        devices.touch("dev-1")
        self.assertIsNone(devices.active_device_id(fresh_seconds=0))

    def test_forget(self):
        from agent import devices
        devices.touch("dev-1")
        devices.forget("dev-1")
        self.assertEqual(devices.list_devices(), [])


class TestRouting(unittest.TestCase):
    def setUp(self):
        self._orig = longterm.DB_PATH
        _fresh_db()

    def tearDown(self):
        longterm.DB_PATH = self._orig

    def _sub(self, endpoint, device_id):
        from agent import notify
        notify.add_subscription(
            {"endpoint": endpoint, "keys": {"p256dh": "a", "auth": "b"}},
            device_label=device_id, device_id=device_id,
        )

    def test_high_priority_fans_to_all(self):
        from agent import notify, devices
        self._sub("https://e/1", "dev-1")
        self._sub("https://e/2", "dev-2")
        devices.touch("dev-1")  # active
        n = notify.Notifier()
        targets = n._target_subscriptions("high")
        self.assertEqual(len(targets), 2)

    def test_normal_routes_to_active_device(self):
        from agent import notify, devices
        self._sub("https://e/1", "dev-1")
        self._sub("https://e/2", "dev-2")
        devices.touch("dev-1")
        time.sleep(0.01)
        devices.touch("dev-2")  # dev-2 is the active device now
        n = notify.Notifier()
        targets = n._target_subscriptions("normal")
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]["device_id"], "dev-2")

    def test_normal_fans_to_all_when_active_has_no_sub(self):
        from agent import notify, devices
        self._sub("https://e/1", "dev-1")
        self._sub("https://e/2", "dev-2")
        devices.touch("dev-3")  # active device has no push subscription
        n = notify.Notifier()
        targets = n._target_subscriptions("normal")
        self.assertEqual(len(targets), 2)

    def test_single_subscription_always_returned(self):
        from agent import notify
        self._sub("https://e/1", "dev-1")
        n = notify.Notifier()
        self.assertEqual(len(n._target_subscriptions("normal")), 1)


if __name__ == "__main__":
    unittest.main()
