

from sklearn.datasets import load_iris
from sklearn.preprocessing import MinMaxScaler
import numpy as np


def get_iris_features(sample_index: int = 0, num_features: int = 2):
    """
    Load Iris dataset and extract normalized features for quantum encoding.
    
    Args:
        sample_index: which iris sample to encode (0-149)
        num_features: how many features to encode (2 or 4, default 2)
    
    Returns:
        features: normalized feature values between 0 and 2*pi
        feature_names: names of features used
        class_name: flower class name
    """
    iris = load_iris()
    X = iris.data
    
    # Normalize features to [0, 2*pi] for quantum angle encoding
    scaler = MinMaxScaler(feature_range=(0, 2 * np.pi))
    X_scaled = scaler.fit_transform(X)
    
    # Extract selected sample
    sample = X_scaled[sample_index, :num_features]
    feature_names = iris.feature_names[:num_features]
    class_name = iris.target_names[iris.target[sample_index]]
    
    return sample.tolist(), feature_names, class_name


def generate_zz_prompt(features: list, feature_names: list) -> str:
    """
    Generates Q-Optima prompt for ZZ Feature Map circuit.
    
    ZZ Feature Map structure for 2 features (x0, x1):
    Layer 1: H on all qubits
    Layer 2: Rz(2*x_i) on each qubit i
    Layer 3: CNOT + Rz(2*(pi-x0)*(pi-x1)) + CNOT (ZZ interaction)
    Layer 4: H on all qubits (second repetition)
    Layer 5: Rz(2*x_i) on each qubit i
    Layer 6: CNOT + Rz(2*(pi-x0)*(pi-x1)) + CNOT
    
    Args:
        features: list of normalized feature values [x0, x1]
        feature_names: list of feature names for display
    
    Returns:
        prompt string for Q-Optima architect
    """
    n = len(features)
    x = features
    
    # Calculate ZZ interaction angle
    zz_angle = round(2 * (np.pi - x[0]) * (np.pi - x[1]), 4)
    
    # Format rotation angles
    rz_angles = [round(2 * xi, 4) for xi in x]
    
    prompt = (
        f"Create a ZZ Feature Map quantum circuit with {n} qubits and {n} classical bits "
        f"to encode classical data features {feature_names} with values {[round(xi, 4) for xi in x]}.\n"
        f"Follow these EXACT steps:\n"
        f"Step 1: Create circuit: qc = QuantumCircuit({n}, {n})\n"
        f"Step 2: Apply H gate to all qubits: qc.h(0), qc.h(1)\n"
        f"Step 3: Apply Rz rotation for feature encoding: qc.rz({rz_angles[0]}, 0), qc.rz({rz_angles[1]}, 1)\n"
        f"Step 4: Apply ZZ interaction — CNOT then Rz then CNOT:\n"
        f"  qc.cx(0, 1)\n"
        f"  qc.rz({zz_angle}, 1)\n"
        f"  qc.cx(0, 1)\n"
        f"Step 5: Apply H gate again to all qubits: qc.h(0), qc.h(1)\n"
        f"Step 6: Apply Rz rotation again: qc.rz({rz_angles[0]}, 0), qc.rz({rz_angles[1]}, 1)\n"
        f"Step 7: Apply ZZ interaction again:\n"
        f"  qc.cx(0, 1)\n"
        f"  qc.rz({zz_angle}, 1)\n"
        f"  qc.cx(0, 1)\n"
        f"Step 8: Measure all qubits: qc.measure([0, 1], [0, 1])\n"
        f"STRICT: Write EXACTLY these gates in this order. "
        f"No loops, no variables, no extra gates. "
        f"Qubit 0 and qubit 1 ARE directly connected on this hardware. "
        f"The transpiler handles any routing automatically."
    )
    
    return prompt


def get_zz_description(features: list, feature_names: list, class_name: str) -> dict:
    """
    Returns display information about the encoding for terminal output.
    """
    return {
        "features": features,
        "feature_names": feature_names,
        "class_name": class_name,
        "encoding": "ZZ Feature Map (2 repetitions)",
        "num_qubits": len(features)
    }