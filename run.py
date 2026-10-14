#!/usr/bin/env python3
"""
SpecOracle Unified CLI Entrypoint.
Usage:
  python run.py streamlit    # Launch the interactive Streamlit GUI
  python run.py smoke        # Run rapid 3-problem end-to-end smoke test
  python run.py experiments  # Run full benchmark evaluation matrix
  python run.py report       # Generate LaTeX/CSV tables and figures
  python run.py tests        # Execute full unit test suite
  python run.py mock         # Run dry run offline without consuming API quota
"""
import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def run_tests():
    # Try pytest first if installed
    try:
        import pytest
        sys.exit(pytest.main(["tests", "-v"]))
    except ImportError:
        pass

    # Built-in lightweight runner for offline environments
    import glob
    import importlib
    
    src_dir = str(ROOT / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    passed, failed = 0, 0
    print("=== Running SpecOracle Unit Tests ===")
    for f in sorted(glob.glob(str(ROOT / "tests" / "test_*.py"))):
        mod_name = Path(f).stem
        mod_path = f"tests.{mod_name}"
        mod = importlib.import_module(mod_path)
        print(f"Testing {mod_name}:")
        for attr in sorted(dir(mod)):
            if attr.startswith("test_"):
                fn = getattr(mod, attr)
                if callable(fn):
                    try:
                        fn()
                        print(f"  ✓ {attr}")
                        passed += 1
                    except Exception as e:
                        print(f"  ✗ {attr}: {e}")
                        failed += 1

    print(f"\nTest Summary: {passed} passed, {failed} failed.")
    if failed > 0:
        sys.exit(1)
    print("ALL TESTS PASSED!")

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1].lower()
    if cmd == "streamlit":
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "streamlit_app.py")])
    elif cmd == "smoke":
        subprocess.run([sys.executable, str(ROOT / "scripts" / "02_smoke_test.py")])
    elif cmd == "experiments":
        subprocess.run([sys.executable, str(ROOT / "scripts" / "03_run_experiments.py")])
    elif cmd == "report":
        subprocess.run([sys.executable, str(ROOT / "scripts" / "04_make_report.py")])
    elif cmd == "tests":
        run_tests()
    elif cmd == "mock":
        env = os.environ.copy()
        env.pop("GROQ_API_KEY", None)
        env.pop("OPENAI_API_KEY", None)
        subprocess.run([sys.executable, str(ROOT / "scripts" / "02_smoke_test.py")], env=env)
    else:
        print(f"[!] Unknown command '{cmd}'.\n{__doc__}")

if __name__ == "__main__":
    main()
