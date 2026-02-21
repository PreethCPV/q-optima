"""
Schema Validation for Q-Optima
Enforces strict output format from each agent.
"""

import re

class SchemaValidator:

    @staticmethod
    def validate_code(code: str) -> tuple[bool, str]:
        """Validates architect/optimizer output is valid circuit code."""
        if not code or code.strip() == "":
            return False, "Empty code returned"
        
        if "qc" not in code:
            return False, "Variable 'qc' not defined"
        
        if "QuantumCircuit" not in code:
            return False, "QuantumCircuit not instantiated"
        
        if "measure" not in code:
            return False, "No measurement found in circuit"
        
        return True, "Code schema valid"

    @staticmethod
    def validate_status(status: str) -> tuple[bool, str]:
        """Validates verifier output has correct STATUS format."""
        if not status or status.strip() == "":
            return False, "Empty status returned"
        
        if "STATUS:" not in status:
            return False, f"Missing STATUS prefix in: {status[:100]}"
        
        if "SUCCESS" not in status and "FAIL" not in status:
            return False, f"STATUS must be SUCCESS or FAIL, got: {status[:100]}"
        
        return True, "Status schema valid"