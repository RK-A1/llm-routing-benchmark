"""The agent's database: a read-only DuckDB connection with no file access.

DuckDB enforces read-only itself, so there is no SQL keyword filtering here.
"""

import json
import threading
import time

import duckdb

from config import CHAR_CAP, LOCAL_DB, ROW_CAP, SQL_TIMEOUT_S


def cell(v):
    if v is None:
        return "NULL"
    return json.dumps(v, default=str) if isinstance(v, (list, dict)) else str(v)


class DB:
    def __init__(self, path=LOCAL_DB):
        self.con = duckdb.connect(str(path), read_only=True,
                                  config={"enable_external_access": False, "lock_configuration": True})

    def list_tables(self):
        rows = self.con.execute(
            "SELECT table_name, estimated_size, comment FROM duckdb_tables() ORDER BY table_name").fetchall()
        return "\n".join(f"{t} (~{n} rows): {c or ''}" for t, n, c in rows)

    def describe_table(self, table):
        rows = self.con.execute("SELECT column_name, data_type FROM duckdb_columns() WHERE table_name = ? "
                                "ORDER BY column_index", [table]).fetchall()
        if not rows:
            return f"ERROR: no table named {table!r}. Use list_tables."
        return f"{table}\n" + "\n".join(f"  {c} {t}" for c, t in rows)

    def query(self, sql, max_rows):
        """Return (columns, rows, truncated). Interrupted after SQL_TIMEOUT_S."""
        timer = threading.Timer(SQL_TIMEOUT_S, self.con.interrupt)
        timer.start()
        try:
            cur = self.con.execute(sql)
            rows = cur.fetchmany(max_rows + 1)
            return [d[0] for d in cur.description], rows[:max_rows], len(rows) > max_rows
        finally:
            timer.cancel()

    def run_sql(self, sql):
        """Tool body: a capped text table for the model, plus timing and any error."""
        start = time.perf_counter()
        try:
            columns, rows, truncated = self.query(sql, ROW_CAP)
        except Exception as e:
            msg = str(e).strip().splitlines()[0][:500]
            return {"ok": False, "text": f"ERROR: {msg}", "error": msg,
                    "elapsed_s": round(time.perf_counter() - start, 3)}
        text = "\n".join([" | ".join(columns)] + [" | ".join(cell(v) for v in r) for r in rows])
        if len(text) > CHAR_CAP:
            text = text[:CHAR_CAP] + "\n... (output truncated)"
        text += f"\n({len(rows)} rows{', more rows not shown' if truncated else ''})"
        return {"ok": True, "text": text, "elapsed_s": round(time.perf_counter() - start, 3)}
