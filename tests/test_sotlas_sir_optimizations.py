import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.sir.instructions import (
    SIRModule, SIRFunction, SIRBasicBlock, SIRValue,
    AllocStackInst, StoreInst, LoadInst, CallInst, ReturnInst,
    BranchInst, CondBranchInst, PhiInst, BoundsCheckInst,
    RetainInst, ReleaseInst
)
from sotlas.sir.passes import (
    BoundsCheckEliminationPass,
    ArcOptimizationPass,
    Mem2RegPass,
    SIRPassManager
)


class TestSotlasSIROptimizations(unittest.TestCase):
    def test_bounds_check_elimination(self):
        mod = SIRModule(name="test_bce")
        fn = SIRFunction(name="test_fn", parameters=[], return_type="void")
        bb = fn.add_block("entry")

        idx = SIRValue("i", "u64")
        length = SIRValue("len", "u64")

        # First check
        bb.add(BoundsCheckInst(index=idx, length=length))
        # Second redundant check
        bb.add(BoundsCheckInst(index=idx, length=length))
        bb.add(ReturnInst())
        mod.add_function(fn)

        pass_bce = BoundsCheckEliminationPass()
        res = pass_bce.run(mod)

        self.assertTrue(res.success)
        self.assertTrue(res.changed)
        # Verify first is not eliminated, second is eliminated
        checks = [inst for inst in bb.instructions if isinstance(inst, BoundsCheckInst)]
        self.assertEqual(len(checks), 2)
        self.assertFalse(checks[0].can_eliminate)
        self.assertTrue(checks[1].can_eliminate)

    def test_arc_retain_release_elimination(self):
        mod = SIRModule(name="test_arc")
        fn = SIRFunction(name="process_packet", parameters=[], return_type="void")
        bb = fn.add_block("entry")

        pkt = SIRValue("pkt", "Arc<Packet>")
        bb.add(RetainInst(value=pkt))
        # No call or return escaping pkt
        bb.add(ReleaseInst(value=pkt))
        bb.add(ReturnInst())
        mod.add_function(fn)

        pass_arc = ArcOptimizationPass()
        res = pass_arc.run(mod)

        self.assertTrue(res.success)
        self.assertTrue(res.changed)
        retains = [inst for inst in bb.instructions if isinstance(inst, RetainInst)]
        releases = [inst for inst in bb.instructions if isinstance(inst, ReleaseInst)]
        self.assertEqual(len(retains), 0)
        self.assertEqual(len(releases), 0)

    def test_arc_does_not_eliminate_when_escapes(self):
        mod = SIRModule(name="test_arc_escape")
        fn = SIRFunction(name="forward_packet", parameters=[], return_type="void")
        bb = fn.add_block("entry")

        pkt = SIRValue("pkt", "Arc<Packet>")
        bb.add(RetainInst(value=pkt))
        # pkt escapes via call
        bb.add(CallInst(callee="net_send", arguments=[pkt]))
        bb.add(ReleaseInst(value=pkt))
        bb.add(ReturnInst())
        mod.add_function(fn)

        pass_arc = ArcOptimizationPass()
        res = pass_arc.run(mod)

        self.assertTrue(res.success)
        self.assertFalse(res.changed)
        retains = [inst for inst in bb.instructions if isinstance(inst, RetainInst)]
        releases = [inst for inst in bb.instructions if isinstance(inst, ReleaseInst)]
        self.assertEqual(len(retains), 1)
        self.assertEqual(len(releases), 1)

    def test_mem2reg_single_block(self):
        mod = SIRModule(name="test_mem2reg_single")
        fn = SIRFunction(name="compute", parameters=[], return_type="u32")
        bb = fn.add_block("entry")

        slot = SIRValue("slot_x", "*u32")
        val42 = SIRValue("val_42", "u32")
        load_res = SIRValue("r0", "u32")

        bb.add(AllocStackInst(var_name="x", type_name="u32", result=slot))
        bb.add(StoreInst(destination=slot, source=val42))
        bb.add(LoadInst(source=slot, result=load_res))
        bb.add(ReturnInst(value=load_res))
        mod.add_function(fn)

        pass_m2r = Mem2RegPass()
        res = pass_m2r.run(mod)

        self.assertTrue(res.success)
        self.assertTrue(res.changed)
        allocs = [inst for inst in bb.instructions if isinstance(inst, AllocStackInst)]
        self.assertEqual(len(allocs), 0)
        ret = [inst for inst in bb.instructions if isinstance(inst, ReturnInst)][0]
        self.assertEqual(ret.value.name, "val_42")

    def test_mem2reg_phi_insertion(self):
        mod = SIRModule(name="test_mem2reg_phi")
        fn = SIRFunction(name="select_val", parameters=[], return_type="u32")
        
        bb_entry = fn.add_block("entry")
        bb_then = fn.add_block("then")
        bb_else = fn.add_block("else")
        bb_merge = fn.add_block("merge")

        cond = SIRValue("c", "bool")
        slot = SIRValue("slot_y", "*u32")
        v_then = SIRValue("val_10", "u32")
        v_else = SIRValue("val_20", "u32")

        bb_entry.add(AllocStackInst(var_name="y", type_name="u32", result=slot))
        bb_entry.add(CondBranchInst(condition=cond, true_block="then", false_block="else"))

        bb_then.add(StoreInst(destination=slot, source=v_then))
        bb_then.add(BranchInst(target_block="merge"))

        bb_else.add(StoreInst(destination=slot, source=v_else))
        bb_else.add(BranchInst(target_block="merge"))

        bb_merge.add(ReturnInst())
        mod.add_function(fn)

        pass_m2r = Mem2RegPass()
        res = pass_m2r.run(mod)

        self.assertTrue(res.success)
        self.assertTrue(res.changed)
        phis = [inst for inst in bb_merge.instructions if isinstance(inst, PhiInst)]
        self.assertEqual(len(phis), 1)
        self.assertEqual(phis[0].result.name, "phi_slot_y_merge")
        self.assertEqual(len(phis[0].incoming), 2)

    def test_pass_manager_runs_all(self):
        mod = SIRModule(name="test_pm")
        fn = SIRFunction(name="main_kernel", parameters=[], return_type="void")
        bb = fn.add_block("entry")
        bb.add(ReturnInst())
        bb.add(BranchInst(target_block="entry")) # Dead code
        mod.add_function(fn)

        pm = SIRPassManager()
        res = pm.run_all(mod)
        self.assertTrue(res.success)
        self.assertTrue(res.changed)


if __name__ == "__main__":
    unittest.main()
