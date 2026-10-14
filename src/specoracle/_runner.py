import sys
import io
import json
import copy
import traceback

def set_limits(memory_mb: int):
    """Apply memory limits on Unix systems; safe no-op on Windows."""
    try:
        import resource
        limit_bytes = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
    except (ImportError, AttributeError, Exception):
        pass

def main():
    try:
        raw_in = sys.stdin.read()
        payload = json.loads(raw_in)
    except Exception as e:
        sys.__stdout__.write(json.dumps([{"status": "error", "error": f"Failed to parse runner stdin: {str(e)}"}]))
        return

    code = payload.get("code", "")
    entry_point = payload.get("entry_point", "")
    cases = payload.get("cases", [])
    memory_mb = payload.get("memory_mb", 512)

    set_limits(memory_mb)

    namespace = {}
    
    # Execute code in isolated namespace while redirecting stdout/stderr to prevent noise
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    sys.stdout = stdout_buf
    sys.stderr = stderr_buf

    try:
        exec(code, namespace)
    except Exception as e:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        err_msg = traceback.format_exc()
        results = [{"status": "error", "error": f"Code execution failed: {err_msg}"} for _ in cases]
        sys.__stdout__.write(json.dumps(results))
        return

    func = namespace.get(entry_point)
    if not callable(func):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        results = [{"status": "error", "error": f"Entry point '{entry_point}' not found or not callable"} for _ in cases]
        sys.__stdout__.write(json.dumps(results))
        return

    results = []
    for c in cases:
        args = c.get("args", []) if isinstance(c, dict) else c
        # Deep-copy args so function mutations do not corrupt test data
        try:
            call_args = copy.deepcopy(args)
        except Exception:
            call_args = args

        try:
            case_out = io.StringIO()
            sys.stdout = case_out
            sys.stderr = case_out
            val = func(*call_args)
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__
            results.append({"status": "ok", "value": val})
        except Exception as e:
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__
            results.append({"status": "error", "error": traceback.format_exc()})

    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    try:
        sys.__stdout__.write(json.dumps(results))
    except (TypeError, OverflowError):
        cleaned_results = []
        for r in results:
            if r.get("status") == "ok":
                try:
                    json.dumps(r["value"])
                    cleaned_results.append(r)
                except Exception:
                    cleaned_results.append({"status": "ok", "value": str(r["value"])})
            else:
                cleaned_results.append(r)
        sys.__stdout__.write(json.dumps(cleaned_results))

if __name__ == "__main__":
    main()
