import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from specoracle.compare import values_equal

def test_strict_bool_vs_int():
    assert values_equal(True, 1) is False
    assert values_equal(False, 0) is False
    assert values_equal(1, True) is False
    assert values_equal(0, False) is False
    assert values_equal(True, True) is True
    assert values_equal(False, False) is True

def test_float_tolerances():
    assert values_equal(0.1 + 0.2, 0.3) is True
    assert values_equal(1.0000001, 1.0000002) is True
    assert values_equal(1.0, 1.1) is False

def test_sequence_equivalence():
    assert values_equal([1, 2, 3], (1, 2, 3)) is True
    assert values_equal([(1, 2), [3, 4]], ([1, 2], (3, 4))) is True
    assert values_equal([1, 2], [1, 2, 3]) is False

def test_nested_structures():
    d1 = {"key": [1, 2, (3, 4)], "val": 0.5}
    d2 = {"val": 0.5, "key": (1, 2, [3, 4])}
    assert values_equal(d1, d2) is True

def test_strings_and_none():
    assert values_equal("hello", "hello") is True
    assert values_equal("hello", "world") is False
    assert values_equal(None, None) is True
    assert values_equal(None, 0) is False
