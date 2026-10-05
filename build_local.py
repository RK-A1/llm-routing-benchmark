"""Build data/jwst.duckdb from the parquet files committed in data/.

The parquet files are exported from the jwst-image-pipeline project
(https://github.com/RK-A1/jwst-image-pipeline): photos and labels from its warehouse, plus
the published jwst_space_images dataset. Embeddings are left out.

Usage:
    python build_local.py
"""

import duckdb

from config import DATA_DIR, LOCAL_DB

# Short descriptions, the kind a real warehouse carries. Shown by list_tables.
TABLES = {
    "photos": "Every JWST photo ingested from the NASA Webb Flickr account, one row per photo.",
    "labels": "Model-generated classification of a photo, at most one row per photo.",
    "jwst_space_images": "Published dataset: the labelled photos kept as astronomical observations.",
}


def main():
    LOCAL_DB.unlink(missing_ok=True)
    con = duckdb.connect(str(LOCAL_DB))
    for table, comment in TABLES.items():
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM read_parquet('{DATA_DIR / table}.parquet')")
        con.execute(f"COMMENT ON TABLE {table} IS '{comment}'")
        print(f"{table:<18} {con.execute(f'SELECT count(*) FROM {table}').fetchone()[0]:>5} rows")
    con.close()
    print(f"Built {LOCAL_DB}")


if __name__ == "__main__":
    main()
