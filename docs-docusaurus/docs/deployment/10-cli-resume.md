---
sidebar_position: 8
title: Workflow Resume Commands
description: How to resume interrupted workflows and handle workflow state persistence
keywords: [CLI commands, resume workflow, state persistence, interrupted workflows]
---

# Workflow Resume Commands

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/deployment">Deployment</a> → <strong>Workflow Resume Commands</strong></span>
</div>

AgentMap provides functionality to resume interrupted workflows using the **runtime facade pattern**, allowing you to handle user interventions, approvals, or recovery from errors. This is particularly useful for workflows that require human oversight or complex decision points.

## Resume Architecture

### Facade Pattern Implementation

The resume command follows AgentMap's consistent facade pattern, using `runtime_api.py` for workflow management:

```python
# Resume command pattern
from agentmap.runtime_api import ensure_initialized, resume_workflow
from agentmap.deployment.cli.utils.cli_presenter import print_json, print_err, map_exception_to_exit_code

def resume_command(thread_id, response, args):
    try:
        # Ensure runtime is initialized
        ensure_initialized(config_file=args.config)
        
        # Use runtime facade for resume logic
        result = resume_workflow(
            thread_id=thread_id,
            response=response,
            data=args.data,
            config_file=args.config
        )
        
        # Use CLI presenter for consistent output
        print_json(result)
        
    except Exception as e:
        print_err(str(e))
        exit_code = map_exception_to_exit_code(e)
        raise typer.Exit(code=exit_code)
```

### Runtime API Integration

The resume command uses these runtime facade functions:

| Function | Purpose | Usage |
|----------|---------|--------|
| `resume_workflow()` | Resume interrupted workflow execution | Primary resume functionality |
| `ensure_initialized()` | Verify runtime system is ready | Called before resume operations |

### CLI Presenter Integration

Resume commands benefit from standardized CLI presenter utilities:

- **State Serialization**: Handles complex workflow state objects and thread data
- **Error Mapping**: Maps resume-specific exceptions to appropriate exit codes
- **JSON Output**: Structured results for automation and script integration

### State Management Through Facade

The resume functionality leverages the runtime facade for sophisticated state management:

```python
# Resume command implementation
def resume_command(thread_id, response, data, config_file):
    try:
        # Ensure runtime system is ready
        ensure_initialized(config_file=config_file)
        
        # Parse response data using CLI utilities
        parsed_data = parse_json_state(data) if data else {}
        
        # Use runtime facade for workflow resumption
        result = resume_workflow(
            thread_id=thread_id,
            response=response,
            data=parsed_data,
            config_file=config_file
        )
        
        # Runtime facade handles:
        # - Thread ID validation
        # - State deserialization 
        # - Response data integration
        # - Workflow continuation
        # - Result serialization
        
        print_json(result)
        
    except Exception as e:
        print_err(str(e))
        exit_code = map_exception_to_exit_code(e)
        raise typer.Exit(code=exit_code)
```

### Facade Benefits for Resume Operations

**State Persistence:**
- **Thread Management**: Runtime facade handles thread ID validation and lookup
- **State Serialization**: Complex workflow state handled by the service layer  
- **Response Integration**: User responses seamlessly integrated into workflow context

**Error Handling:**
- **Invalid Threads**: Clear error messages for non-existent or expired threads
- **Data Validation**: Response data validated before workflow continuation
- **Exception Mapping**: Resume-specific exceptions mapped to appropriate exit codes

**CLI Integration:**
- **Data File Support**: JSON file input handled by CLI utilities
- **Output Formatting**: Complex workflow results formatted by CLI presenter
- **Script Compatibility**: Structured JSON output for automation systems

## Resume Command

The `resume` command allows you to continue an interrupted workflow by providing a thread ID and response data.

```bash
agentmap resume <thread_id> <response> [OPTIONS]
```

Arguments:
- `thread_id`: Thread ID to resume (required)
- `response`: Response action (approve, reject, choose, respond, edit) (required)

Options:
- `--data`, `-d`: Additional data as JSON string
- `--data-file`, `-f`: Path to JSON file containing additional data
- `--config`, `-c`: Path to custom config file

### Example Usage

```bash
# Resume a workflow with approval
agentmap resume thread_12345 approve

# Resume with additional data
agentmap resume thread_12345 respond --data '{"user_response": "Yes, proceed with the order"}'

# Resume with data from a file
agentmap resume thread_12345 choose --data-file response_data.json

# Resume with custom configuration
agentmap resume thread_12345 edit --data '{"edited_content": "Updated text"}' --config custom_config.yaml
```

## Response Types

The `resume` command supports several response types:

### 1. Approve/Reject

Used for simple approval workflows:

```bash
# Approve the pending action
agentmap resume thread_12345 approve

# Reject the pending action
agentmap resume thread_12345 reject --data '{"reason": "Budget exceeded"}'
```

### 2. Choose

Used when the workflow presents multiple options:

```bash
# Choose an option by ID
agentmap resume thread_12345 choose --data '{"choice": "option_2"}'

# Choose with additional context
agentmap resume thread_12345 choose --data '{"choice": "option_3", "notes": "Preferred due to cost"}'
```

### 3. Respond

Used for providing free-form responses:

```bash
# Provide a text response
agentmap resume thread_12345 respond --data '{"response": "The proposed solution looks good"}'

# Respond with structured data
agentmap resume thread_12345 respond --data '{"response": "Approved", "additional_requirements": ["Feature A", "Feature B"]}'
```

### 4. Edit

Used for editing content generated by the workflow:

```bash
# Edit generated content
agentmap resume thread_12345 edit --data '{"edited_content": "This is the revised version of the text."}'

# Edit with formatting options
agentmap resume thread_12345 edit --data '{"edited_content": "New content", "format": "markdown"}'
```

## Using Data Files

For complex responses, it's often easier to use a JSON file:

```bash
# Create a data file
cat > response_data.json << EOF
{
  "choice": "option_2",
  "feedback": "This option aligns better with our requirements",
  "additional_parameters": {
    "priority": "high",
    "deadline": "2023-05-15",
    "assigned_to": "engineering_team"
  }
}
EOF

# Resume with the data file
agentmap resume thread_12345 choose --data-file response_data.json
```

## How Workflow Resumption Works

1. **Interruption Point**: Workflows can be designed with interruption points using the `HumanInTheLoop` agent or similar mechanisms.

2. **Thread ID Generation**: When a workflow reaches an interruption point, it generates a unique thread ID and waits for a response.

3. **State Persistence**: The current state of the workflow is saved, including all variables and context.

4. **Resume Command**: When you run the `resume` command with the thread ID and response, the workflow loads the saved state and continues execution with the provided response data.

5. **Response Integration**: The response data is integrated into the workflow state and available to subsequent nodes.

## Example: Approval Workflow

Here's a simple example of how to create a workflow with an approval step:

```csv
ApprovalFlow,start,,Start the approval workflow,Input,validate_request,,request,request_data,Process request: {request}
ApprovalFlow,validate_request,request_approval|reject_invalid,Validate the request data,Function,,,request_data,is_valid,
ApprovalFlow,reject_invalid,,Handle invalid requests,Output,,,is_valid,rejection_message,Request rejected: Invalid format
ApprovalFlow,request_approval,,Request approval from human,HumanInTheLoop,end,,request_data,approval_result,Please review this request: {request_data}
ApprovalFlow,end,,Complete the workflow,Output,,,approval_result,final_message,Request processed with result: {approval_result}
```

In this workflow:
1. The `request_approval` node uses the `HumanInTheLoop` agent to pause execution
2. The workflow will provide a thread ID when it reaches this node
3. You can resume the workflow using:

```bash
# Approve the request
agentmap resume thread_12345 approve

# Or reject with a reason
agentmap resume thread_12345 reject --data '{"reason": "Budget limit exceeded"}'
```

## Best Practices for Resumable Workflows

1. **Design for Interruptions**: Identify natural points in your workflow where human input might be valuable.

2. **Clear Thread ID Communication**: Ensure thread IDs are communicated clearly to the people who need to respond.

3. **Timeout Handling**: Consider implementing timeout handling for workflows that don't receive responses within a certain timeframe.

4. **Response Validation**: Validate response data to ensure it meets the expected format and requirements.

5. **Audit Trail**: Keep a log of all resume actions for audit and troubleshooting purposes.

## Security Considerations

1. **Thread ID Protection**: Treat thread IDs as sensitive information, as they provide access to resume workflows.

2. **Authentication**: Consider implementing additional authentication for resume operations in production environments.

3. **Data Validation**: Always validate response data to prevent injection attacks or other security issues.

4. **Access Control**: Implement appropriate access controls to determine who can resume specific workflows.

## Related Documentation

- **[CLI Commands Reference](./04-cli-commands)**: Complete list of all CLI commands
- **[Human-in-the-Loop Agents](/docs/reference/agent-types#humanintheloop)**: Documentation for the HumanInTheLoop agent
- **[State Persistence](/docs/guides/operations/state-persistence)**: How workflow state is saved and restored
- **[Approval Workflow Example](/docs/examples/approval-workflow)**: Complete example of an approval workflow
