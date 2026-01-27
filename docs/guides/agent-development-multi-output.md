# Agent Development Guide: Multi-Output Implementation

## Writing Multi-Output Agents

This guide covers implementing agents that produce multiple output fields.

## Basic Structure

### Required Methods

Every agent must implement the `process()` method:

```python
from agentmap.agents.base_agent import BaseAgent
from typing import Any, Dict

class MyAgent(BaseAgent):
    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process inputs and return multi-output dictionary.

        Args:
            inputs: Dictionary with keys matching Input_Fields

        Returns:
            Dictionary with keys matching Output_Field declaration
        """
        # Your implementation here
        pass
```

## Single vs Multi-Output Process Methods

### Single Output Agent

Agent declares one field:

```csv
Output_Field: result
```

Can return scalar or dict:

```python
def process(self, inputs):
    # Option 1: Return scalar
    return "processed"

    # Option 2: Return dict
    return {"result": "processed"}
```

### Multi-Output Agent

Agent declares multiple fields:

```csv
Output_Field: result|count|status
```

**Must return dict** with all declared fields:

```python
def process(self, inputs):
    result = do_work(inputs)
    return {
        "result": result,
        "count": len(result) if iterable else 1,
        "status": "success"
    }
```

## Implementation Patterns

### Pattern 1: Processing with Metrics

Compute main result and include processing metrics:

```python
class DataProcessorAgent(BaseAgent):
    def process(self, inputs):
        data = inputs.get("raw_data", [])

        # Process
        processed = self._process_items(data)

        # Return with metrics
        return {
            "processed": processed,
            "item_count": len(processed),
            "processing_time_ms": self._calculate_time(),
            "status": "success"
        }

    def _process_items(self, items):
        return [self._transform(item) for item in items]

    def _calculate_time(self):
        # Implement timing logic
        return 0

    def _transform(self, item):
        # Implement transformation
        return item
```

**CSV:**
```csv
Output_Field: processed|item_count|processing_time_ms|status
```

### Pattern 2: Error Handling with Status

Return result, status, and error information:

```python
class RiskyOperationAgent(BaseAgent):
    def process(self, inputs):
        try:
            result = self._risky_operation(inputs)
            return {
                "result": result,
                "status": "success",
                "error_code": None,
                "error_message": None,
                "recovery_possible": False
            }
        except RecoverableError as e:
            return {
                "result": None,
                "status": "recoverable_error",
                "error_code": e.code,
                "error_message": str(e),
                "recovery_possible": True
            }
        except FatalError as e:
            return {
                "result": None,
                "status": "fatal_error",
                "error_code": e.code,
                "error_message": str(e),
                "recovery_possible": False
            }
        except Exception as e:
            self.log_error(f"Unexpected error: {str(e)}")
            return {
                "result": None,
                "status": "unexpected_error",
                "error_code": "UNKNOWN",
                "error_message": str(e),
                "recovery_possible": False
            }

    def _risky_operation(self, inputs):
        # Implementation
        pass
```

**CSV:**
```csv
Output_Field: result|status|error_code|error_message|recovery_possible
```

**Downstream Routing:**
```csv
Node,Edge,Condition
RiskyOp,Recover,recovery_possible == true
RiskyOp,Report,status == 'fatal_error'
```

### Pattern 3: Data Splitting/Classification

Return different categories of data:

```python
class DataClassifierAgent(BaseAgent):
    def process(self, inputs):
        items = inputs.get("items", [])

        valid = []
        invalid = []
        suspicious = []

        for item in items:
            if self._is_valid(item):
                valid.append(item)
            elif self._is_suspicious(item):
                suspicious.append(item)
            else:
                invalid.append(item)

        return {
            "valid_items": valid,
            "invalid_items": invalid,
            "suspicious_items": suspicious,
            "classification_report": {
                "total": len(items),
                "valid": len(valid),
                "invalid": len(invalid),
                "suspicious": len(suspicious)
            }
        }

    def _is_valid(self, item):
        # Implement validation
        return True

    def _is_suspicious(self, item):
        # Implement suspicious detection
        return False
```

**CSV:**
```csv
Output_Field: valid_items|invalid_items|suspicious_items|classification_report
```

### Pattern 4: Aggregation with Details

Produce summary and detailed breakdown:

```python
class AggregationAgent(BaseAgent):
    def process(self, inputs):
        records = inputs.get("records", [])

        # Aggregate
        totals = self._calculate_totals(records)
        by_category = self._group_by_category(records)
        by_date = self._group_by_date(records)

        return {
            "summary": totals,
            "by_category": by_category,
            "by_date": by_date,
            "record_count": len(records),
            "aggregation_successful": True
        }

    def _calculate_totals(self, records):
        # Implementation
        return {}

    def _group_by_category(self, records):
        # Implementation
        return {}

    def _group_by_date(self, records):
        # Implementation
        return {}
```

**CSV:**
```csv
Output_Field: summary|by_category|by_date|record_count|aggregation_successful
```

### Pattern 5: Conditional Output Routing

Use status field to control downstream execution:

```python
class SmartRouterAgent(BaseAgent):
    def process(self, inputs):
        result = self._analyze(inputs)

        # Determine routing based on analysis
        if result.get("score") > 0.8:
            next_action = "fast_track"
        elif result.get("score") > 0.5:
            next_action = "standard"
        else:
            next_action = "review"

        return {
            "result": result,
            "score": result.get("score"),
            "next_action": next_action,
            "requires_approval": next_action == "review"
        }

    def _analyze(self, inputs):
        # Implementation
        return {"score": 0.7}
```

**CSV:**
```csv
Output_Field: result|score|next_action|requires_approval
...
Node,Edge,Condition
SmartRouter,FastTrack,next_action == 'fast_track'
SmartRouter,Standard,next_action == 'standard'
SmartRouter,Review,next_action == 'review'
```

## Accessing Input Fields

### Single Input

```python
def process(self, inputs):
    value = inputs.get("field_name")
    # ...
```

### Multiple Inputs

```csv
Input_Fields: field1|field2|field3
```

```python
def process(self, inputs):
    field1 = inputs.get("field1")
    field2 = inputs.get("field2")
    field3 = inputs.get("field3")

    # Or unpack all at once
    field1, field2, field3 = inputs.values()
```

### Safe Access Pattern

```python
def process(self, inputs):
    # Use .get() with defaults
    data = inputs.get("data", [])
    config = inputs.get("config", {})
    limit = inputs.get("limit", 100)

    # Prevents KeyError if field not provided
```

## Error Handling

### Try-Except Pattern

```python
def process(self, inputs):
    try:
        result = expensive_operation(inputs)
        return {
            "result": result,
            "status": "success"
        }
    except ValueError as e:
        self.log_warning(f"Validation failed: {e}")
        return {
            "result": None,
            "status": f"validation_error: {str(e)}"
        }
    except Exception as e:
        self.log_error(f"Unexpected error: {e}")
        return {
            "result": None,
            "status": f"unexpected_error: {str(e)}"
        }
```

### Logging Errors

Use built-in logging methods:

```python
def process(self, inputs):
    try:
        result = risky_work(inputs)
        self.log_info(f"Processing complete: {len(result)} items")
        return {"result": result, "count": len(result)}
    except Exception as e:
        self.log_error(f"Processing failed: {str(e)}")
        return {"result": None, "count": 0}
```

**Available logging methods:**
- `self.log_debug(msg)` - Debug level
- `self.log_info(msg)` - Info level
- `self.log_warning(msg)` - Warning level
- `self.log_error(msg)` - Error level

### Handling Missing Fields

```python
def process(self, inputs):
    # Wrong - will crash if field missing
    required = inputs["required_field"]

    # Right - handles missing gracefully
    required = inputs.get("required_field")
    if required is None:
        self.log_warning("Required field missing, using default")
        required = "default_value"
```

## Testing Multi-Output Agents

### Unit Test Example

```python
import unittest
from unittest.mock import MagicMock
from myagents import DataProcessorAgent

class TestDataProcessorAgent(unittest.TestCase):

    def setUp(self):
        self.agent = DataProcessorAgent(
            name="TestProcessor",
            prompt="Test",
            logger=MagicMock()
        )

    def test_process_returns_all_declared_fields(self):
        inputs = {"raw_data": [1, 2, 3]}
        result = self.agent.process(inputs)

        # All declared fields present
        self.assertIn("processed", result)
        self.assertIn("item_count", result)
        self.assertIn("status", result)

    def test_process_correct_counts(self):
        inputs = {"raw_data": [1, 2, 3, 4, 5]}
        result = self.agent.process(inputs)

        self.assertEqual(result["item_count"], 5)
        self.assertEqual(result["status"], "success")

    def test_process_handles_empty_input(self):
        inputs = {"raw_data": []}
        result = self.agent.process(inputs)

        self.assertEqual(result["item_count"], 0)
        self.assertEqual(result["status"], "success")

    def test_process_handles_missing_input(self):
        inputs = {}  # Missing required "raw_data"
        result = self.agent.process(inputs)

        # Should still return all fields (with defaults)
        self.assertIn("processed", result)
        self.assertIn("item_count", result)
        self.assertIn("status", result)
```

### Integration Test Example

```python
import unittest
from agentmap.services.graph_runner_service import GraphRunnerService

class TestDataProcessorIntegration(unittest.TestCase):

    def test_agent_produces_correct_state_fields(self):
        # Create a workflow with multi-output agent
        csv_content = """GraphName,Node,AgentType,Input_Fields,Output_Field,Edge
test,Process,DataProcessorAgent,raw_data,processed|item_count|status,"""

        runner = GraphRunnerService()
        result = runner.execute_from_csv(
            csv_content,
            initial_state={"raw_data": [1, 2, 3]}
        )

        # All output fields in final state
        self.assertIn("processed", result.state)
        self.assertIn("item_count", result.state)
        self.assertIn("status", result.state)
        self.assertEqual(result.state["item_count"], 3)
```

## Working with Context

### Accessing Agent Context

```python
class ConfigurableAgent(BaseAgent):
    def __init__(self, name, prompt, context=None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)

        # Extract custom config from context
        self.batch_size = self.context.get("batch_size", 100)
        self.timeout = self.context.get("timeout", 30)
        self.retry_count = self.context.get("retry_count", 3)

    def process(self, inputs):
        # Use context-provided configuration
        for batch in self._batch_items(inputs["data"], self.batch_size):
            result = self._process_batch(batch)
```

### From CSV Extra Column

```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,Extra
pipeline,MyNode,MyAgent,input,output1|output2,"{""batch_size"": 50, ""timeout"": 60}"
```

## Performance Optimization

### Avoid Unnecessary Computation

```python
# Wrong - computing extra fields not needed
def process(self, inputs):
    return {
        "result": heavy_computation(),
        "status": "ok",
        "debug_data": very_expensive_debug_info(),  # Not needed
        "timing_data": complex_profiling()          # Not needed
    }

# Right - only compute declared fields
def process(self, inputs):
    return {
        "result": heavy_computation(),
        "status": "ok"
    }
```

### Lazy Computation

```python
# Wrong - compute everything
def process(self, inputs):
    fields = {
        "field1": compute_field1(inputs),
        "field2": compute_field2(inputs),
        "field3": compute_field3(inputs),
    }
    return fields

# Right - compute on demand
def process(self, inputs):
    return {
        "field1": compute_field1(inputs),
        "field2": compute_field2(inputs),  # Only if needed
        "field3": compute_field3(inputs),  # Only if needed
    }
```

### Early Returns

```python
def process(self, inputs):
    # Fail fast
    if not self._validate_inputs(inputs):
        return {
            "result": None,
            "status": "invalid_input",
            "error": "Input validation failed"
        }

    # Only do expensive work if inputs valid
    result = expensive_computation(inputs)

    return {
        "result": result,
        "status": "success",
        "error": None
    }
```

## Complete Working Example

Here's a complete, production-ready multi-output agent:

```python
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from agentmap.agents.base_agent import BaseAgent


class DataValidationAgent(BaseAgent):
    """
    Validate data and return comprehensive validation report.

    Declared outputs: valid_records|invalid_records|validation_report|validation_status
    """

    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        self.strict_mode = self.context.get("strict_validation", False)
        self.max_errors_reported = self.context.get("max_errors_reported", 100)

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate records and return split valid/invalid with report.

        Args:
            inputs: Dictionary with 'records' key

        Returns:
            Dictionary with validation results and report
        """
        try:
            records = inputs.get("records", [])

            if not records:
                self.log_warning("No records provided for validation")
                return self._empty_result()

            # Validate records
            valid_records = []
            invalid_records = []
            errors = []

            for idx, record in enumerate(records):
                error = self._validate_record(record, idx)
                if error:
                    invalid_records.append(record)
                    errors.append(error)
                else:
                    valid_records.append(record)

            # Prepare report
            report = self._build_report(
                valid_records,
                invalid_records,
                errors
            )

            self.log_info(
                f"Validation complete: {len(valid_records)} valid, "
                f"{len(invalid_records)} invalid"
            )

            return {
                "valid_records": valid_records,
                "invalid_records": invalid_records,
                "validation_report": report,
                "validation_status": "success"
            }

        except Exception as e:
            self.log_error(f"Validation failed: {str(e)}")
            return {
                "valid_records": [],
                "invalid_records": [],
                "validation_report": {"error": str(e)},
                "validation_status": f"error: {str(e)}"
            }

    def _validate_record(self, record: Dict, idx: int) -> Optional[Dict]:
        """
        Validate single record.

        Returns:
            None if valid, error dict if invalid
        """
        try:
            if not isinstance(record, dict):
                return {"record_index": idx, "error": "Not a dictionary"}

            # Check required fields
            required = ["id", "name", "email"]
            missing = [f for f in required if f not in record]
            if missing:
                return {
                    "record_index": idx,
                    "error": f"Missing required fields: {missing}"
                }

            # Validate email format
            if not self._is_valid_email(record.get("email", "")):
                return {
                    "record_index": idx,
                    "error": f"Invalid email: {record.get('email')}"
                }

            return None

        except Exception as e:
            return {
                "record_index": idx,
                "error": f"Validation error: {str(e)}"
            }

    def _is_valid_email(self, email: str) -> bool:
        """Simple email validation."""
        return "@" in email and "." in email

    def _build_report(
        self,
        valid: List[Dict],
        invalid: List[Dict],
        errors: List[Dict]
    ) -> Dict[str, Any]:
        """Build validation report."""
        return {
            "timestamp": datetime.now().isoformat(),
            "total_records": len(valid) + len(invalid),
            "valid_count": len(valid),
            "invalid_count": len(invalid),
            "error_count": len(errors),
            "error_details": errors[:self.max_errors_reported],
            "truncated": len(errors) > self.max_errors_reported
        }

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty valid result."""
        return {
            "valid_records": [],
            "invalid_records": [],
            "validation_report": {
                "timestamp": datetime.now().isoformat(),
                "total_records": 0,
                "valid_count": 0,
                "invalid_count": 0,
                "error_count": 0
            },
            "validation_status": "success"
        }
```

**CSV Definition:**
```csv
GraphName,Node,AgentType,Input_Fields,Output_Field,Edge,output_validation
etl,Validate,DataValidationAgent,records,valid_records|invalid_records|validation_report|validation_status,Split,error
```

## Best Practices Checklist

- [ ] All declared output fields present in return dict
- [ ] Meaningful field names that clearly describe content
- [ ] Consistent field types (don't vary by execution)
- [ ] Error information included for failure cases
- [ ] Logging at appropriate levels (debug, info, warning, error)
- [ ] Input validation and safe defaults
- [ ] Tests covering happy path and error cases
- [ ] Documentation on context parameters used
- [ ] Performance optimization (no unnecessary computation)
- [ ] Clear error messages for downstream agents

## See Also

- [Multi-Output Feature Guide](../features/multi-output-agents.md)
- [CSV Reference](../reference/csv-multi-output-reference.md)
- [BaseAgent API](../api/base-agent.md)
