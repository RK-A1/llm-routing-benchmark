"""Grade an answer's result set against the frozen reference.

Rules (lenient on shape, strict on content):
- Row order never matters; rows must match one-to-one (no missing or extra rows).
- Columns are matched by content, not name or position, and extra columns are allowed
  (an agent that returns the name alongside the asked-for count is still right).
- Numbers compare within the question's tol (default: tiny); 3 == 3.0 == '3'.
- Strings compare case-insensitively, trimmed. A date-only answer matches a timestamp on that date.
- A one-row reference also matches when the same values come back spread over rows.

Usage:
    python -m bench.check --freeze     # run every reference query on the local DuckDB, write expected.json
    python -m bench.check --selftest   # grade each reference against itself plus a few reshaped variants
"""

import argparse
import datetime as dt
import decimal
import json

from .config import EXPECTED, LOCAL_DB

DEFAULT_TOL = 1e-6


def norm(v):
    """Comparable form: None, float, or lower-case string."""
    if v is None:
        return None
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float, decimal.Decimal)):
        return float(v)
    if isinstance(v, dt.timedelta):  # an interval answer to a "how many days" question
        return v.total_seconds() / 86400
    if isinstance(v, dt.datetime):
        return (v.date().isoformat() if v.time() == dt.time() else v.replace(microsecond=0).isoformat(" "))
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, (list, tuple, dict)):
        return json.dumps(v, default=str).lower()
    s = str(v).strip().lower()
    try:
        return float(s)
    except ValueError:
        return s.replace("t", " ", 1) if len(s) >= 19 and s[4] == "-" and s[10] == "t" else s


def equal(a, b, tol):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) <= max(tol, 1e-9 * max(abs(a), abs(b)))
    if isinstance(a, str) and isinstance(b, str):
        if a == b:
            return True
        # '2026-05-06' vs '2026-05-06 12:00:00'
        short, long_ = sorted((a, b), key=len)
        return len(short) == 10 and short[4] == "-" and long_.startswith(short)
    return False


def sort_key(v):
    return (0, v) if isinstance(v, float) else (1, "") if v is None else (2, v)


def same_column(ref_col, got_col, tol):
    return all(equal(a, b, tol) for a, b in zip(sorted(ref_col, key=sort_key), sorted(got_col, key=sort_key)))


def rows_match(ref_rows, got_rows, tol):
    """One-to-one multiset match with tolerance (greedy is fine at these sizes)."""
    unused = list(got_rows)
    for r in ref_rows:
        for i, g in enumerate(unused):
            if all(equal(a, b, tol) for a, b in zip(r, g)):
                del unused[i]
                break
        else:
            return False
    return not unused


def grade(ref_rows, got_rows, tol=DEFAULT_TOL):
    """Return (correct, reason). Rows are lists of raw values; ref_rows may be pre-normalized."""
    ref = [[norm(v) for v in r] for r in ref_rows]
    got = [[norm(v) for v in r] for r in got_rows]
    if not ref:
        return (not got, "both empty" if not got else f"expected no rows, got {len(got)}")
    if len(got) != len(ref):
        if len(ref) == 1 and got:
            return flattened(ref[0], got, tol)
        return False, f"expected {len(ref)} rows, got {len(got)}"

    n_ref, n_got = len(ref[0]), len(got[0])
    ref_cols = [[r[i] for r in ref] for i in range(n_ref)]
    got_cols = [[g[j] for g in got] for j in range(n_got)]
    candidates = [[j for j in range(n_got) if same_column(ref_cols[i], got_cols[j], tol)] for i in range(n_ref)]
    if missing := [i for i, c in enumerate(candidates) if not c]:
        return False, f"no column matches reference column(s) {missing}"

    def search(i, chosen):
        if i == n_ref:
            projected = [[g[j] for j in chosen] for g in got]
            return rows_match(ref, projected, tol)
        return any(search(i + 1, chosen + [j]) for j in candidates[i] if j not in chosen)

    return (True, "match") if search(0, []) else (False, "columns match separately but rows do not")


def flattened(ref_row, got, tol):
    """One reference row, answer spread over several rows (e.g. two counts as two rows)."""
    cells = [v for g in got for v in g]
    if len(cells) > 2 * len(ref_row):
        return False, f"expected 1 row, got {len(got)}"
    unused = list(cells)
    for r in ref_row:
        hit = next((i for i, c in enumerate(unused) if equal(r, c, tol)), None)
        if hit is None:
            return False, f"expected 1 row, got {len(got)}; value {r!r} not found"
        del unused[hit]
    return True, "match (values spread over rows)"


def load_expected():
    return json.loads(EXPECTED.read_text())


def freeze():
    import duckdb

    from .questions import TURNS

    con = duckdb.connect(str(LOCAL_DB), read_only=True)
    out = {}
    for qid, q in TURNS.items():
        cur = con.execute(q["sql"])
        rows = cur.fetchall()
        out[qid] = {"columns": [d[0] for d in cur.description],
                    "rows": [[norm(v) for v in r] for r in rows]}
        preview = rows[:3] if len(rows) > 1 else rows[0] if rows else rows
        print(f"{qid}: {len(rows)} row(s) {preview}")
    EXPECTED.write_text(json.dumps(out, indent=1))
    print(f"Wrote {EXPECTED}")


def selftest():
    import duckdb

    from .questions import TURNS

    con = duckdb.connect(str(LOCAL_DB), read_only=True)
    expected = load_expected()
    ok = True
    for qid, q in TURNS.items():
        rows = con.execute(q["sql"]).fetchall()
        ref = expected[qid]["rows"]
        tol = q.get("tol", DEFAULT_TOL)
        variants = {
            "itself": rows,
            "reversed rows+cols": [list(reversed(r)) for r in reversed(rows)],
            "extra column": [["extra"] + list(r) for r in rows],
        }
        for name, got in variants.items():
            good, why = grade(ref, got, tol)
            ok &= good
            if not good:
                print(f"FAIL {qid} {name}: {why}")
        # Must reject: one row dropped (when there are several), or a number nudged past tolerance.
        if len(rows) > 1:
            ok &= not grade(ref, rows[1:], tol)[0] or print(f"FAIL {qid}: accepted missing row") or False
        nums = [i for i, v in enumerate(rows[0]) if isinstance(v, (int, float, decimal.Decimal))] if rows else []
        if nums:
            bumped = [list(r) for r in rows]
            bumped[0][nums[0]] = float(bumped[0][nums[0]]) + max(1, 10 * tol)
            ok &= not grade(ref, bumped, tol)[0] or print(f"FAIL {qid}: accepted wrong number") or False
    # Shape leniency checks.
    assert grade([[8, 4]], [[8], [4]])[0], "two numbers as two rows"
    assert grade([["2026-05-06 12:00:00"]], [[dt.date(2026, 5, 6)]])[0], "date-only answer"
    assert grade([[44.7]], [[44.661]], 0.06)[0] and not grade([[44.7]], [[0.4466]], 0.06)[0], "tolerance"
    assert not grade([["galaxy", 129]], [["not_applicable", 596]])[0], "wrong subject"
    print("selftest passed" if ok else "selftest FAILED")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--freeze", action="store_true")
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.freeze:
        freeze()
    if a.selftest:
        selftest()
