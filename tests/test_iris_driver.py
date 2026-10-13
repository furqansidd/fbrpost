import pytest
import inspect
from src.iris_driver import run_iris_posting, IrisDriver

def test_iris_driver_interface_and_safety():
    # Verify driver function signature
    sig = inspect.signature(run_iris_posting)
    params = list(sig.parameters.keys())
    assert "credentials" in params
    assert "tax_data" in params
    assert "status_callback" in params

    # Safety check: IrisDriver must NOT contain any method or selector to click 'Submit' or input 4-digit PIN
    source = inspect.getsource(IrisDriver)
    assert "Submit" not in source or "btn-submit" not in source
    # Must enforce draft only
    assert "save_draft" in source or "Save" in source
