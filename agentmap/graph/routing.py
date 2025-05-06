def dynamic_branch(success_targets, failure_targets):
    def route(state):
        if state.get('last_action_success', True):
            return success_targets if len(success_targets) > 1 else success_targets[0]
        else:
            return failure_targets if len(failure_targets) > 1 else failure_targets[0]
    return route

def parallel_branch(targets):
    def route(state):
        return targets
    return route

def choose_next(state: dict, success: list, failure: list):
    """
    Choose next node based on success or failure in state.
    
    Args:
        state: The current state dictionary  
        success: List of success target nodes
        failure: List of failure target nodes
        
    Returns:
        A single node name or list of node names for parallel execution
    """
    if state.get("last_action_success", True):
        return success if len(success) > 1 else success[0]
    else:
        return failure if len(failure) > 1 else failure[0]

def always_success(state: dict, targets: list):
    """
    Always return the target nodes regardless of state.
    
    Args:
        state: The current state dictionary
        targets: List of target nodes
        
    Returns:
        The target nodes
    """  
    return targets

def success_only(state: dict, target: str):
    """
    Return the target only on success, otherwise None.
    
    Args:
        state: The current state dictionary
        target: Target node name
        
    Returns:
        Target node name or None
    """
    return target if state.get("last_action_success", True) else None

def failure_only(state: dict, target: str):
    """
    Return the target only on failure, otherwise None.
    
    Args:
        state: The current state dictionary
        target: Target node name
        
    Returns:
        Target node name or None
    """
    return target if not state.get("last_action_success", True) else None