#!/usr/bin/env python3
"""REST API for Spooky2 search using Neon Postgres."""
from fastapi import FastAPI, Query, HTTPException, Request
from pathlib import Path
import json
import os
from datetime import datetime, timezone
import psycopg
from psycopg.rows import dict_row

app = FastAPI(title="Spooky2 Search API", version="1.0.0")

API_VERSION = "1.0.0"

# Path to local data directory for Telegram timestamps
DATA_DIR = Path(os.environ.get("DATA_DIR", "data/presets"))

# Neon connection — deferred until first database call
CONN_STRING = os.environ.get("NEON_CONN_STRING")

if not CONN_STRING:
    import warnings
    warnings.warn(
        "NEON_CONN_STRING not set. Database endpoints (/search, /program, /collections) "
        "will return errors. Static endpoints (/telegram-updates, /health) still work."
    )


@app.get("/")
def read_root():
    return {
        "message": "Spooky2 Frequency Search API",
        "version": API_VERSION,
        "frontend": "https://papersplx.github.io/spooky-db/",
        "endpoints": {
            "search": "/search?q=lung&limit=100",
            "program": "/program?id=<uuid>",
            "collections": "/collections",
            "categories": "/categories",
            "telegram-updates": "/telegram-updates",
            "health": "/health"
        }
    }


# CORS — allow frontend origins; disable credentials when using wildcard
@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "https://papersplx.github.io"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

@app.get("/search")
def search(
    q: str = Query(default=""),
    mode: list[str] = Query(default=[]),
    collection: list[str] = Query(default=[]),
    category: list[str] = Query(default=[]),
    limit: int = Query(default=100),
    offset: int = Query(default=0)
):
    conn = psycopg.connect(CONN_STRING, row_factory=dict_row)
    try:
        where = []
        params = []

        if q:
            where.append("to_tsvector('english', name || ' ' || COALESCE(description, '')) @@ plainto_tsquery('english', %s)")
            params.append(q)

        if mode:
            where.append("mode = ANY(%s)")
            params.append(mode)

        if collection:
            where.append("collection = ANY(%s)")
            params.append(collection)

        if category:
            where.append("category = ANY(%s)")
            params.append(category)

        where_clause = f"WHERE {' AND '.join(where)}" if where else ""

        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT COUNT(*) as total
                FROM programs
                {where_clause}
            """, params)
            total = cur.fetchone()['total']

            cur.execute(f"""
                SELECT id, name, description, collection, mode, entry_type
                FROM programs
                {where_clause}
                ORDER BY name
                LIMIT %s OFFSET %s
            """, [*params, limit, offset])
            results = cur.fetchall()
            return {"results": results, "total": total}
    finally:
        conn.close()

@app.get("/program")
def get_program(id: str):
    conn = psycopg.connect(CONN_STRING, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM programs WHERE id = %s LIMIT 1", (id,))
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Program not found")
            return result
    finally:
        conn.close()

@app.get("/collections")
def get_collections():
    conn = psycopg.connect(CONN_STRING, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT collection, mode, COUNT(*) as count
                FROM programs
                GROUP BY collection, mode
                ORDER BY collection
            """)
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/categories")
def get_categories():
    conn = psycopg.connect(CONN_STRING, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT category, COUNT(*) as count
                FROM programs
                WHERE category IS NOT NULL AND category != ''
                GROUP BY category
                ORDER BY category
            """)
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/telegram-updates")
def telegram_updates():
    """Return last-updated timestamps for each Telegram group."""
    timestamp_path = DATA_DIR / "telegram_group_timestamps.json"

    result = {}

    if timestamp_path.exists():
        try:
            with open(timestamp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for group_slug, info in data.items():
                if isinstance(info, str):
                    result[group_slug] = info
                elif isinstance(info, dict):
                    result[group_slug] = info.get("last_updated")
        except Exception:
            pass

    # Also check for manifest files in each group directory
    telegram_dir = DATA_DIR / "telegram_raw"
    if telegram_dir.exists():
        for group_dir in telegram_dir.iterdir():
            if not group_dir.is_dir():
                continue
            manifest_path = group_dir / "postprocess_manifest.json"
            if manifest_path.exists():
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                    group_name = group_dir.name
                    if group_name not in result or result[group_name] is None:
                        result[group_name] = manifest.get("completed_at")
                except Exception:
                    pass

    # Fall back to progress.json timestamps if no other source
    for group_slug in list(result.keys()):
        if result[group_slug] is None:
            progress_path = DATA_DIR / "telegram_raw" / group_slug / "progress.json"
            if progress_path.exists():
                try:
                    mtime = progress_path.stat().st_mtime
                    result[group_slug] = datetime.fromtimestamp(
                        mtime, tz=timezone.utc
                    ).isoformat()
                except Exception:
                    pass

    return result
