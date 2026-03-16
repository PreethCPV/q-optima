"""
Conversation Memory for Q-Optima
Tracks errors, fixes attempted, and outcomes across iterations
so the optimizer doesn't repeat failed strategies.
"""

class ConversationMemory:
    def __init__(self):
        self.history = []          # List of all iteration records
        self.failed_fixes = []     # Fixes that were tried and failed
        self.error_types_seen = set()  # Unique error categories encountered

    def record_iteration(self, iteration: int, code: str, error: str, fix_applied: str = None):
        """
        Record what happened in each iteration.
        
        Args:
            iteration: Which iteration number (1, 2, 3...)
            code: The circuit code that was tested
            error: The error/failure message from verifier
            fix_applied: Description of what the optimizer tried to fix (if any)
        """
        entry = {
            "iteration": iteration,
            "code_snapshot": code,
            "error": error,
            "fix_applied": fix_applied
        }
        self.history.append(entry)

        # Track failed fixes to avoid repeating them

        # Categorize the error type
        if "Code Validation Error" in error:
            self.error_types_seen.add("code_validation")
        elif "Hardware Mapping" in error:
            self.error_types_seen.add("hardware_mapping")
        elif "Low Fidelity" in error:
            self.error_types_seen.add("low_fidelity")
        elif "Runtime Error" in error:
            self.error_types_seen.add("runtime_error")
        elif "Import Error" in error:
            self.error_types_seen.add("import_error")
        elif "Malformed" in error or "crashed" in error:
            self.error_types_seen.add("verifier_error")
        elif "injection" in error.lower():
            self.error_types_seen.add("code_injection")
        else:
            self.error_types_seen.add("unknown")
    
    def record_fix(self, fix_description: str):
        """Call this after optimizer runs to log the fix attempt."""
        if self.history:
            self.history[-1]["fix_applied"] = fix_description
            self.failed_fixes.append(fix_description)

    def get_optimizer_context(self) -> str:
        """
        Returns a formatted string to inject into the optimizer's task description.
        Tells the optimizer what has already been tried so it doesn't repeat itself.
        """
        if not self.history:
            return "No previous attempts. This is the first fix."

        context_lines = ["PREVIOUS ATTEMPTS (Do NOT repeat these fixes):"]
        context_lines.append("=" * 50)

        for record in self.history:
            context_lines.append(f"\nIteration {record['iteration']}:")
            context_lines.append(f"  Error: {record['error'][:200]}...")  # Truncate long errors
            if record["fix_applied"]:
                context_lines.append(f"  Fix Tried: {record['fix_applied']}")
                context_lines.append(f"  Result: FAILED (do not try this again)")

        context_lines.append("\n" + "=" * 50)
        context_lines.append("Based on the above failed attempts, try a DIFFERENT approach.")

        return "\n".join(context_lines)

    def get_summary(self) -> dict:
        """Returns a summary of the session for logging."""
        return {
            "total_iterations": len(self.history),
            "error_types_encountered": list(self.error_types_seen),
            "failed_fixes_count": len(self.failed_fixes)
        }