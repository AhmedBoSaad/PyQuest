"""PyQuest entry point. Launch with: python run.py"""

# IMPORTANT: onnxruntime must be imported BEFORE PySide6 on Windows.
# Qt/PySide6 loads Microsoft Visual C++ runtime DLLs in a way that breaks
# onnxruntime's pybind11 state if it's imported afterwards. Doing it here
# means Kokoro can lazily load later without DLL errors.
try:
    import onnxruntime  # noqa: F401
except Exception:  # noqa: BLE001
    # Kokoro will fail later with a friendly error in Settings; don't crash here.
    pass

from pyquest.app import main

if __name__ == "__main__":
    raise SystemExit(main())
