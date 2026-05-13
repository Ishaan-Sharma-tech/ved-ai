import logging

logger = logging.getLogger("aether.blackboard")

class GlobalBlackboard:
    """
    Shared memory restricted to the CEO and Department Heads.
    Worker agents do not have access to this.
    """
    def __init__(self):
        self.state = {}
        
    def write(self, dept_name: str, summary: str):
        logger.info(f"Blackboard updated by {dept_name}")
        self.state[dept_name] = summary
        
    def get_current_state(self) -> str:
        if not self.state:
            return "The Blackboard is currently empty."
        return "\n\n".join(f"[{k.upper()} DEPARTMENT]\n{v}" for k, v in self.state.items())
