"""Behavioral contract tests; this does not execute an ECU or C166 firmware."""
from pathlib import Path
import hashlib,json,unittest
from pops_event_ticks_reference_20261102 import ReleaseBudget,Phase,MASK32,HALF32

class ContractTests(unittest.TestCase):
    def arm_release(self,start=100,budget=93750):
        e=ReleaseBudget(budget=budget)
        self.assertFalse(e.step((start-1)&MASK32,165,True,True,False))
        self.assertTrue(e.step(start,165,False,True,False))
        return e

    def test_boot_released_and_other_modes_never_enable(self):
        for mode in range(256):
            e=ReleaseBudget()
            self.assertFalse(e.step(1,mode,False,True,False))
            self.assertFalse(e.step(2,mode,True,True,False))
            self.assertEqual(e.step(3,mode,False,True,False),mode==165)

    def test_positive_pedal_in_another_mode_does_not_arm_pops(self):
        for mode in (90,69,105,0,255):
            e=ReleaseBudget()
            e.step(1,mode,True,True,False)
            self.assertFalse(e.step(2,165,False,True,False))

    def test_budget_boundary(self):
        e=self.arm_release()
        self.assertTrue(e.step(93849,165,False,True,False))
        self.assertFalse(e.step(93850,165,False,True,False))
        self.assertEqual(e.remaining,0)
        self.assertFalse(e.step(93851,165,False,True,False))

    def test_legacy_resets_and_permission_oscillations_do_not_extend(self):
        e=self.arm_release(start=0,budget=1000)
        for t in range(1,1101):
            eligible=t%7!=0
            self.assertEqual(e.step(t,165,False,eligible,False,
                                    legacy_counter=0 if t%3==0 else t%80),
                             t<1000 and eligible)

    def test_real_32bit_rollover(self):
        start=MASK32-99
        e=self.arm_release(start=start,budget=1000)
        self.assertTrue(e.step(49,165,False,True,False))
        self.assertEqual(e.remaining,851)
        self.assertTrue(e.step((start+999)&MASK32,165,False,True,False))
        self.assertFalse(e.step((start+1000)&MASK32,165,False,True,False))

    def test_backward_clock_or_very_long_gap_closes(self):
        for now in (99,100+HALF32):
            e=self.arm_release()
            self.assertFalse(e.step(now,165,False,True,False))
            self.assertEqual(e.phase,Phase.SPENT)

    def test_notified_clock_reset_closes_and_requires_positive_pedal(self):
        e=self.arm_release()
        self.assertFalse(e.step(200,165,False,True,False,clock_reinitialized=True))
        self.assertFalse(e.step(201,165,False,True,False))
        self.assertFalse(e.step(202,165,True,True,False))
        self.assertTrue(e.step(203,165,False,True,False))

    def test_duplicate_helper_calls_do_not_restart_or_double_charge(self):
        e=self.arm_release(budget=1000)
        for _ in range(10):
            self.assertTrue(e.step(200,165,False,True,False))
            self.assertEqual(e.remaining,900)
        self.assertFalse(e.step(1100,165,False,True,False))

    def test_fuel_cut_and_mode_return_do_not_rearm(self):
        e=self.arm_release()
        self.assertFalse(e.step(101,165,False,True,True))
        self.assertFalse(e.step(102,165,False,True,False))
        e=self.arm_release()
        self.assertFalse(e.step(101,90,False,True,False))
        self.assertFalse(e.step(102,165,False,True,False))

    def test_expiration_during_inhibition(self):
        e=self.arm_release(budget=1000)
        self.assertFalse(e.step(500,165,False,False,False))
        self.assertFalse(e.step(1200,165,False,False,False))
        self.assertFalse(e.step(1201,165,False,True,False))

    def test_eight_byte_layout_and_serialized_continuation(self):
        e=self.arm_release(budget=1000)
        encoded=e.pack()
        self.assertEqual(len(encoded),8)
        self.assertEqual(encoded,bytes.fromhex('64000000e8030002'))
        restored=ReleaseBudget.unpack(encoded,budget=1000)
        self.assertTrue(restored.step(1099,165,False,True,False))
        self.assertEqual(restored.remaining,1)
        self.assertFalse(restored.step(1100,165,False,True,False))

    def test_invalid_serialized_state_is_closed(self):
        for data in (b'\xff'*8,bytes.fromhex('0000000001000000'),
                     bytes.fromhex('0000000000000002')):
            e=ReleaseBudget.unpack(data,budget=1000)
            self.assertFalse(e.step(5,165,False,True,False))

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ContractTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    root=Path(__file__).resolve().parent.parent
    record={'tests':result.testsRun,'failures':len(result.failures),
            'errors':len(result.errors),'success':result.wasSuccessful(),
            'status':'REFERENCE_MODEL_ONLY','state_bytes':8,
            'example_budget_ticks':93750,'seconds_calibrated':False,
            'C166_generated':False,'firmware_modified':False,
            'base_sha256':hashlib.sha256((root/'work/r4_pops_dev/base_ddli_readonly.FLS').read_bytes()).hexdigest()}
    (root/'work/ram_owner_audit/event_ticks_model_20261102.json').write_text(json.dumps(record,indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
