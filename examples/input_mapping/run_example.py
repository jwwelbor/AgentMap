#!/usr/bin/env python3
"""
Add Two Numbers — AgentMap Example

Demonstrates three input binding modes with a custom AdderAgent.

Workflow 1 — Positional Binding (AddTwice):
  FirstAdd:  3 + 4 = 7      (first_a + first_b → positionally bound to addend_a, addend_b)
  SecondAdd: 7 + 5 = 12     (first_sum + second_b → same positional binding)
  Done:      echoes 12

Workflow 2 — Direct & Mapped Binding (AddBindingModes):
  DirectAdd: 10 + 20 = 30   (addend_a + addend_b → direct mode, names already match)
  MappedAdd: 30 + 5 = 35    (direct_sum:addend_a | extra:addend_b → mapped via colon syntax)
  MixedAdd:  35 + 20 = 55   (mapped_sum:addend_a | addend_b → mixed: one mapped, one direct passthrough)
  Done:      echoes all sums
"""

import os

# Run from the example directory so config paths resolve
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from agentmap.runtime_api import run_workflow

# ── Workflow 1: Positional binding ──────────────────────────────────────────
# AdderAgent.expected_params = ["addend_a", "addend_b"]
# CSV fields first_a|first_b are mapped to addend_a|addend_b by position.

print("=" * 60)
print("Workflow 1: Positional Binding (AddTwice)")
print("=" * 60)

result1 = run_workflow(
    "AddTwice",
    {"first_a": 3, "first_b": 4, "second_b": 5},
)

out1 = result1.get("outputs", {})
print(f"  FirstAdd:  3 + 4 = {out1.get('first_sum')}")
print(f"  SecondAdd: 7 + 5 = {out1.get('final_sum')}")

# ── Workflow 2: Direct + Mapped binding ─────────────────────────────────────
# DirectAdd:  Input_Fields = addend_a|addend_b         → direct (names match agent params)
# MappedAdd:  Input_Fields = direct_sum:addend_a|extra:addend_b → mapped via colon
# MixedAdd:   Input_Fields = mapped_sum:addend_a|bonus  → mixed (one mapped, one direct)

print()
print("=" * 60)
print("Workflow 2: Direct & Mapped Binding (AddBindingModes)")
print("=" * 60)

result2 = run_workflow(
    "AddBindingModes",
    {"addend_a": 10, "addend_b": 20, "extra": 5},
)

out2 = result2.get("outputs", {})
print(f"  DirectAdd: 10 + 20 = {out2.get('direct_sum')}   (direct: addend_a, addend_b match agent params)")
print(f"  MappedAdd: 30 + 5  = {out2.get('mapped_sum')}   (mapped: direct_sum:addend_a, extra:addend_b)")
print(f"  MixedAdd:  35 + 20 = {out2.get('mixed_sum')}   (mixed: mapped_sum:addend_a + direct addend_b)")
