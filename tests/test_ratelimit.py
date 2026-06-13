"""Tests for the dashboard auth-failure throttle."""
import unittest

from dashboard.ratelimit import AuthThrottle


class TestAuthThrottle(unittest.TestCase):
    def test_locks_out_after_max_fails(self):
        t = AuthThrottle(window=60.0, max_fails=3)
        now = 1000.0
        for i in range(3):
            self.assertFalse(t.record_failure("1.2.3.4", now=now + i))
        # 4th failure crosses the threshold
        self.assertTrue(t.record_failure("1.2.3.4", now=now + 3))
        self.assertTrue(t.is_locked("1.2.3.4", now=now + 3))

    def test_window_expiry_clears_lock(self):
        t = AuthThrottle(window=60.0, max_fails=2)
        now = 1000.0
        for i in range(3):
            t.record_failure("ip", now=now + i)
        self.assertTrue(t.is_locked("ip", now=now + 3))
        # After the window, old failures age out
        self.assertFalse(t.is_locked("ip", now=now + 61))

    def test_per_ip_isolation(self):
        t = AuthThrottle(window=60.0, max_fails=1)
        now = 1000.0
        t.record_failure("a", now=now)
        t.record_failure("a", now=now)
        self.assertTrue(t.is_locked("a", now=now))
        self.assertFalse(t.is_locked("b", now=now))

    def test_reset(self):
        t = AuthThrottle(window=60.0, max_fails=1)
        now = 1000.0
        t.record_failure("a", now=now)
        t.record_failure("a", now=now)
        self.assertTrue(t.is_locked("a", now=now))
        t.reset("a")
        self.assertFalse(t.is_locked("a", now=now))

    def test_good_auth_never_locks(self):
        # A throttle that's never told about failures stays open.
        t = AuthThrottle()
        self.assertFalse(t.is_locked("anyone"))


if __name__ == "__main__":
    unittest.main()
