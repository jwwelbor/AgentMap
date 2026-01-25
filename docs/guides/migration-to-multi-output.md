# Migration Guide: Converting to Multi-Output Agents

This guide helps you migrate existing single-output agents to use the multi-output feature.

## When to Migrate

Consider migrating to multi-output when:

- Agent produces related pieces of information (data + status, result + count, etc.)
- Downstream agents need different combinations of outputs
- You're duplicating state management across multiple downstream agents
- You want clearer workflow contracts
- You need better error reporting alongside results

## Do NOT migrate if:

- Agent truly produces single piece of data (no status, metadata, etc.)
- Agent is used in many workflows (wait for better tooling)
- Multi-output would significantly complicate the agent logic

## Migration Process

### Step 1: Analyze Current Workflow

Examine what your agent currently produces and how it's used:

**Before:**
```python
class ProcessAgent(BaseAgent):
    def process(self, inputs):
        result = process_data(inputs)
        return result  # Returns single value
```

**CSV:**
```csv
Node,AgentType,Input_Fields,Output_Field,Edge
Process,ProcessAgent,raw_data,result,Save
Save,SaveAgent,result,save_result,
```

**Questions to ask:**
- What information does the agent compute?
- Does it compute status separately elsewhere?
- Do downstream agents need to extract multiple pieces of information?
- Would a status field help with error handling?

### Step 2: Identify Additional Outputs

List what the agent should produce:

```
Current output: result (the processed data)

Additional outputs to add:
1. status (success/failure/partial)
2. count (number of items processed)
3. duration (how long it took)
```

### Step 3: Update CSV Declaration

Add pipe-delimited output fields:

**Before:**
```csv
Node,AgentType,Input_Fields,Output_Field,Edge
Process,ProcessAgent,raw_data,result,Save
```

**After:**
```csv
Node,AgentType,Input_Fields,Output_Field,Edge
Process,ProcessAgent,raw_data,result|status|count|duration,Save
```

### Step 4: Update Agent Implementation

Return a dictionary with all declared fields:

**Before:**
```python
class ProcessAgent(BaseAgent):
    def process(self, inputs):
        raw_data = inputs.get("raw_data", [])
        result = []

        for item in raw_data:
            result.append(self._transform(item))

        return result
```

**After:**
```python
import time

class ProcessAgent(BaseAgent):
    def process(self, inputs):
        raw_data = inputs.get("raw_data", [])
        result = []
        start_time = time.time()

        try:
            for item in raw_data:
                result.append(self._transform(item))

            duration = time.time() - start_time

            return {
                "result": result,
                "status": "success",
                "count": len(result),
                "duration": duration
            }

        except Exception as e:
            duration = time.time() - start_time
            self.log_error(f"Processing failed: {str(e)}")

            return {
                "result": [],
                "status": f"error: {str(e)}",
                "count": 0,
                "duration": duration
            }
```

### Step 5: Update Downstream Agents

Update agents that use the output to request specific fields:

**Before:**
```csv
Node,Input_Fields,Output_Field,Edge
Process,raw_data,result,Save
Save,result,save_result,
```

**After:**
```csv
Node,Input_Fields,Output_Field,Edge
Process,raw_data,result|status|count|duration,Save
Save,result|status,save_result,
```

If downstream agent needs multiple fields:

```python
# Before
class SaveAgent(BaseAgent):
    def process(self, inputs):
        result = inputs.get("result")
        # Had to add status separately
        saved = save_to_db(result)
        return f"Saved {len(saved)} items"

# After - Can now access status from upstream
class SaveAgent(BaseAgent):
    def process(self, inputs):
        result = inputs.get("result")
        status = inputs.get("status")  # Now available!

        if status != "success":
            self.log_warning(f"Upstream returned: {status}")

        saved = save_to_db(result)
        return f"Saved {len(saved)} items"
```

### Step 6: Test

Write tests to verify the new behavior:

```python
import unittest
from unittest.mock import MagicMock

class TestProcessAgentMigration(unittest.TestCase):

    def setUp(self):
        self.agent = ProcessAgent(
            name="TestProcess",
            prompt="Test",
            logger=MagicMock()
        )

    def test_returns_all_fields(self):
        """Verify all declared fields are returned."""
        inputs = {"raw_data": [1, 2, 3]}
        result = self.agent.process(inputs)

        # Check all fields present
        self.assertIn("result", result)
        self.assertIn("status", result)
        self.assertIn("count", result)
        self.assertIn("duration", result)

    def test_success_case(self):
        """Test happy path."""
        inputs = {"raw_data": [1, 2, 3]}
        result = self.agent.process(inputs)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["count"], 3)
        self.assertGreater(result["duration"], 0)
        self.assertEqual(len(result["result"]), 3)

    def test_empty_input(self):
        """Test edge case."""
        inputs = {"raw_data": []}
        result = self.agent.process(inputs)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["result"], [])

    def test_error_case(self):
        """Test error handling."""
        inputs = {"raw_data": [{"invalid": "data"}]}
        result = self.agent.process(inputs)

        self.assertIn("error", result["status"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["result"], [])
```

### Step 7: Deploy and Monitor

1. **Test in staging** with real workflows
2. **Monitor logs** for validation warnings
3. **Check state** to verify all fields present
4. **Verify downstream** agents still work correctly
5. **Performance test** for any regression

## Migration Patterns

### Pattern 1: Simple Result + Status

**Before:**
```python
def process(self, inputs):
    try:
        result = compute(inputs)
        return result
    except Exception as e:
        return None
```

Downstream couldn't tell if None meant empty or error.

**After:**
```python
def process(self, inputs):
    try:
        result = compute(inputs)
        return {
            "result": result,
            "status": "success"
        }
    except Exception as e:
        return {
            "result": None,
            "status": f"error: {str(e)}"
        }
```

Now downstream can handle errors appropriately.

### Pattern 2: Data + Count

**Before:**
```python
def process(self, inputs):
    items = filter_items(inputs)
    return items  # Downstream had to len() it again
```

**After:**
```python
def process(self, inputs):
    items = filter_items(inputs)
    return {
        "items": items,
        "count": len(items)
    }
```

Now count is available without recomputation.

### Pattern 3: Multiple Categories

**Before (split across two agents):**
```python
# Agent1: Filter valid
class FilterValidAgent(BaseAgent):
    def process(self, inputs):
        items = inputs.get("items", [])
        valid = [i for i in items if is_valid(i)]
        return valid

# Agent2: Filter invalid
class FilterInvalidAgent(BaseAgent):
    def process(self, inputs):
        items = inputs.get("items", [])
        invalid = [i for i in items if not is_valid(i)]
        return invalid
```

**After (single agent):**
```python
class ClassifyItemsAgent(BaseAgent):
    def process(self, inputs):
        items = inputs.get("items", [])
        valid = [i for i in items if is_valid(i)]
        invalid = [i for i in items if not is_valid(i)]

        return {
            "valid_items": valid,
            "invalid_items": invalid,
            "valid_count": len(valid),
            "invalid_count": len(invalid)
        }
```

### Pattern 4: Result + Metadata

**Before (computed separately):**
```python
class ProcessAgent(BaseAgent):
    def process(self, inputs):
        result = expensive_process(inputs)
        return result

class MetadataAgent(BaseAgent):
    def process(self, inputs):
        # Had to recompute to get metadata
        result = expensive_process(inputs)
        metadata = extract_metadata(result)
        return metadata
```

**After (single agent):**
```python
class ProcessAgentWithMetadata(BaseAgent):
    def process(self, inputs):
        result = expensive_process(inputs)

        return {
            "result": result,
            "metadata": extract_metadata(result),
            "processed_at": datetime.now().isoformat(),
            "version": "2.0"
        }
```

## Validation Mode Selection

When migrating, choose validation mode based on use case:

### Development: Use `warn` (default)

```csv
output_validation: warn
```

See warnings about mismatches, workflow continues.

### Testing: Use `error`

```csv
output_validation: error
```

Catch mismatches immediately, fail tests fast.

### Production: Use Based on Criticality

- **Critical path**: Use `error` for strict validation
- **Best effort**: Use `warn` with monitoring
- **Resilient**: Use `ignore` for graceful degradation

## Rollback Strategy

If migration causes issues:

### Option 1: Quick Rollback

Revert CSV and agent code to original versions:

```bash
git revert <commit>
```

### Option 2: Gradual Rollback

Use feature flags in agent:

```python
class ProcessAgent(BaseAgent):
    def __init__(self, name, prompt, context=None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        self.use_multi_output = self.context.get("use_multi_output", True)

    def process(self, inputs):
        result = compute(inputs)

        if self.use_multi_output:
            return {
                "result": result,
                "status": "success"
            }
        else:
            return result  # Old format
```

Then update CSV:
```csv
Extra: {"use_multi_output": false}
```

### Option 3: Parallel Workflows

Run both old and new agents in parallel during transition:

```csv
Node1,NewProcessAgent,raw_data,result|status,Split
Node2,OldProcessAgent,raw_data,result_old,Compare
Compare,CompareAgent,result|result_old,comparison,
```

Monitor comparison and remove old agent once confident.

## Validation Mode Troubleshooting

### Getting Too Many Warnings

**Symptom:**
```
WARNING - Agent ParseData missing declared output fields: ['row_count']
```

**Solution:**
1. Update agent to always return all declared fields
2. Switch to `error` mode for stricter checking
3. Update CSV to match actual agent returns

### Errors Causing Workflow Failures

**Symptom:**
```
ValueError: Agent ValidateData missing declared output fields
```

**Solution:**
1. Verify agent is returning all fields
2. Check field names match exactly (case-sensitive)
3. Switch to `warn` mode temporarily while debugging
4. Add logging to see what agent actually returns

```python
# Temporary debug logging
def process(self, inputs):
    result = do_work(inputs)
    self.log_info(f"Returning: {result.keys()}")
    return result
```

## Compatibility Notes

### State Changes

State will grow as you add multi-output agents:

**Before:**
```python
state = {
    "raw_data": "...",
    "result": [1, 2, 3]
}
```

**After:**
```python
state = {
    "raw_data": "...",
    "result": [1, 2, 3],
    "status": "success",
    "count": 3,
    "duration": 0.042
}
```

Old fields remain, new fields are added. No state is lost.

### Downstream Compatibility

Downstream agents can request any combination of fields:

```csv
# Old agent still works - requests only "result"
Node2,Agent2,result,output,

# New agent uses new fields
Node2,Agent2,result|status|count,output,
```

### Performance Impact

Migration has minimal performance impact:

- **Parsing**: O(n) where n = number of fields (negligible)
- **Validation**: O(n) field checks (< 1ms typical)
- **State merge**: Native Python dict merge (no overhead)

## Checklist Before Deploying

- [ ] All declared output fields returned by agent
- [ ] Tests pass (unit and integration)
- [ ] Downstream agents request needed fields
- [ ] Validation mode chosen (warn for dev, error for test)
- [ ] Migration tested in staging
- [ ] Rollback plan documented
- [ ] Team notified of changes
- [ ] Monitoring alerts set up
- [ ] Documentation updated
- [ ] Performance baseline compared

## Examples

### Real-world Example: Data Pipeline

**Before (Separate agents):**
```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,Edge
etl,Extract,ExtractAgent,source,raw_data,Parse
etl,Parse,ParseAgent,raw_data,parsed,Validate
etl,Validate,ValidateAgent,parsed,valid_rows,Transform
etl,Transform,TransformAgent,valid_rows,transformed,Load
etl,Load,LoadAgent,transformed,load_result,
```

Multiple downstream agents to handle statuses, counts, errors.

**After (Multi-output):**
```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,Edge
etl,Extract,ExtractAgent,source,raw_data|extract_status,Parse
etl,Parse,ParseAgent,raw_data,parsed|row_count|parse_status,Validate
etl,Validate,ValidateAgent,parsed|row_count,valid_rows|errors|validation_status,Transform
etl,Transform,TransformAgent,valid_rows,transformed|transform_count,Load
etl,Load,LoadAgent,transformed|transform_count|validation_status,load_result,
```

Single workflow with more information flowing through, clearer contracts.

## See Also

- [Multi-Output Feature Guide](../features/multi-output-agents.md)
- [Agent Development Guide](./agent-development-multi-output.md)
- [CSV Reference](../reference/csv-multi-output-reference.md)
