import unittest
from pops_indicator_state_reference_20261109 import JointState


class Contract(unittest.TestCase):
    def test_four_modes_display_for_two_seconds_then_real_rpm(self):
        for mode, rpm in ((69, 2000), (105, 3000), (165, 4000), (90, 1000)):
            s = JointState(pops_ticks=50, indicator_ticks=200)
            s.step(0, 90 if mode != 90 else 69, False, True, False, True)
            self.assertEqual(s.step(10, mode, False, True, False, True), (False, rpm))
            self.assertEqual(s.step(209, mode, False, True, False, True), (False, rpm))
            self.assertEqual(s.step(210, mode, False, True, False, True), (False, None))
            self.assertEqual(s.step(211, mode, False, True, False, True), (False, None))

    def test_movement_unknown_speed_and_pedal_cancel(self):
        for speed in (False, None):
            s = JointState(indicator_ticks=200)
            s.step(0, 90, False, True, False, True)
            self.assertEqual(s.step(1, 69, False, True, False, speed), (False, None))
        s = JointState(indicator_ticks=200)
        s.step(0, 90, False, True, False, True)
        s.step(1, 165, False, True, False, True)
        self.assertEqual(s.step(2, 165, True, True, False, True), (False, None))
        self.assertEqual(s.step(3, 165, False, True, False, True), (True, None))

    def test_sixteen_bit_mode_and_state_round_trip(self):
        s = JointState(indicator_ticks=200)
        s.step(0, 90, False, True, False, True)
        s.step(1, 69, False, True, False, True)
        raw = s.pack()
        self.assertEqual(len(raw), 8)
        loaded = JointState.unpack(raw, indicator_ticks=200)
        self.assertEqual(loaded.step(2, 69, False, True, False, True), (False, 2000))
        self.assertFalse(JointState.unpack(b'\xff' * 8).indicating)
        malformed = (0).to_bytes(4, 'little') + (50).to_bytes(3, 'little') + bytes([2])
        self.assertEqual(JointState.unpack(malformed).remaining, 0)

    def test_clock_reset_and_wrap(self):
        s = JointState(indicator_ticks=20)
        s.step(0xfffffffa, 90, False, True, False, True)
        self.assertEqual(s.step(0xfffffffc, 69, False, True, False, True), (False, 2000))
        self.assertEqual(s.step(3, 69, False, True, False, True), (False, 2000))
        self.assertEqual(s.step(16, 69, False, True, False, True), (False, None))
        self.assertEqual(s.step(17, 165, False, True, False, True, clock_reinitialized=True), (False, None))


if __name__ == '__main__':
    unittest.main()
