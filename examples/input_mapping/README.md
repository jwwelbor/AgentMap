# Add Two Numbers — AgentMap Example

A minimal example showing all three input binding modes:
 **positional**, **direct**, and **mapped**.

Demonstrates input

## Files

```
add_two_numbers/
├── agentmap_config.yaml          # Points to custom_agents/ and workflows/
├── agentmap_config_storage.yaml  # Storage config (required by agentmap)
├── custom_agents/
│   ├── adder_agent.py            # AdderAgent — adds two numbers
│   └── custom_agents.yaml        # Declares the "adder" agent type
├── workflows/
│   ├── AddTwice.csv              # Workflow 1 — positional binding
│   └── AddBindingModes.csv       # Workflow 2 — direct & mapped binding
├── run_example.py                # Runs both workflows
└── README.md
```

## The Custom Agent

```python
class AdderAgent(BaseAgent):
    expected_params = ["addend_a", "addend_b"]

    def process(self, inputs):
        a = inputs.get("addend_a", 0)
        b = inputs.get("addend_b", 0)
        return a + b
```

The agent always reads `addend_a` and `addend_b` from its inputs. The three
binding modes control how CSV field names get mapped to those parameter names.

## Workflow 1 — Positional Binding (`AddTwice.csv`)

```
GraphName  Node       AgentType  Input_Fields        Output_Field  Edge
AddTwice   FirstAdd   adder      first_a|first_b     first_sum     SecondAdd
AddTwice   SecondAdd  adder      first_sum|second_b  final_sum     Done
AddTwice   Done       echo       final_sum           result
```

Because `AdderAgent` declares `expected_params = ["addend_a", "addend_b"]`,
the CSV fields are mapped **by position**:

- Position 0: `first_a` → `addend_a`
- Position 1: `first_b` → `addend_b`

The agent sees `{"addend_a": 3, "addend_b": 4}` even though the state keys
are `first_a` and `first_b`. This lets you reuse the same agent with
different state key names without changing the agent code.

**Result:** `3 + 4 = 7`, then `7 + 5 = 12`

## Workflow 2 — Direct & Mapped Binding (`AddBindingModes.csv`)

```
GraphName       Node       AgentType  Input_Fields                    Output_Field  Edge
AddBindingModes DirectAdd  adder      addend_a|addend_b               direct_sum    MappedAdd
AddBindingModes MappedAdd  adder      direct_sum:addend_a|extra:addend_b  mapped_sum    MixedAdd
AddBindingModes MixedAdd   adder      mapped_sum:addend_a|addend_b    mixed_sum     Done
AddBindingModes Done       echo       direct_sum|mapped_sum|mixed_sum result
```

Three nodes, three binding styles:

### DirectAdd — Direct mode
`Input_Fields = addend_a|addend_b`

No colons, and the field names already match the agent's parameter names.
No remapping needed — the values pass through as-is.

### MappedAdd — Fully mapped mode
`Input_Fields = direct_sum:addend_a|extra:addend_b`

Colon syntax `state_key:param_name` remaps state values to agent parameters.
`direct_sum` (30) becomes `addend_a`, `extra` (5) becomes `addend_b`.

### MixedAdd — Mixed mode
`Input_Fields = mapped_sum:addend_a|addend_b`

One field is mapped (`mapped_sum` → `addend_a`), the other passes through
directly as `addend_b`. When any field uses `:` syntax, positional binding
is disabled for the entire node — unmapped fields use direct mode instead.

**Result:** `10 + 20 = 30`, then `30 + 5 = 35`, then `35 + 20 = 55`

## Running

```bash
cd examples/add_two_numbers
python run_example.py
```
