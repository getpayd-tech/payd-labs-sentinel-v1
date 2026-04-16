"""Database browser service.

Uses asyncpg to connect to the managed PostgreSQL instance and provides
helpers for listing databases, tables, schemas, running read-only queries,
and creating new databases.

Connections are pooled per database name (max 3 connections per pool) to
avoid exhausting DigitalOcean's managed PostgreSQL connection limit.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import asyncpg

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection pool management
# ---------------------------------------------------------------------------

_pools: dict[str, asyncpg.Pool] = {}


async def _get_pool(database: str | None = None) -> asyncpg.Pool:
    """Get or create a connection pool for the given database."""
    db_name = database or settings.pg_admin_database
    if db_name not in _pools or _pools[db_name]._closed:
        _pools[db_name] = await asyncpg.create_pool(
            host=settings.pg_admin_host,
            port=settings.pg_admin_port,
            user=settings.pg_admin_user,
            password=settings.pg_admin_password,
            database=db_name,
            ssl="require" if settings.pg_admin_sslmode == "require" else None,
            min_size=1,
            max_size=3,
            command_timeout=30,
        )
    return _pools[db_name]


async def _get_admin_conn(database: str | None = None) -> asyncpg.pool.PoolConnectionProxy:
    """Acquire a connection from the pool for the given database."""
    pool = await _get_pool(database)
    return await pool.acquire()


async def _release_conn(conn: asyncpg.pool.PoolConnectionProxy) -> None:
    """Release a connection back to its pool."""
    await conn.close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def list_databases() -> list[dict[str, Any]]:
    """List all non-template databases on the managed PostgreSQL instance."""
    conn = await _get_admin_conn()
    try:
        rows = await conn.fetch(
            """
            SELECT
                d.datname AS name,
                pg_catalog.pg_get_userbyid(d.datdba) AS owner,
                CASE
                    WHEN has_database_privilege(d.datname, 'CONNECT')
                    THEN pg_catalog.pg_database_size(d.datname)
                    ELSE 0
                END AS size_bytes
            FROM pg_catalog.pg_database d
            WHERE d.datistemplate = false
              AND d.datname NOT IN ('_dodb', 'postgres', 'template0', 'template1')
            ORDER BY d.datname
            """
        )

        result: list[dict[str, Any]] = []
        for row in rows:
            name = row["name"]
            size_mb = round((row["size_bytes"] or 0) / (1024 * 1024), 2)

            # Count tables (connect to each DB individually)
            tables_count = 0
            try:
                db_conn = await _get_admin_conn(database=name)
                try:
                    count_row = await db_conn.fetchrow(
                        """
                        SELECT count(*) AS cnt
                        FROM information_schema.tables
                        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                        """
                    )
                    tables_count = count_row["cnt"] if count_row else 0
                finally:
                    await _release_conn(db_conn)
            except Exception as exc:
                logger.debug("Cannot count tables for %s (may lack CONNECT privilege): %s", name, exc)

            result.append({
                "name": name,
                "size_mb": size_mb,
                "owner": row["owner"],
                "tables_count": tables_count,
            })

        return result
    finally:
        await _release_conn(conn)


async def list_tables(db_name: str) -> list[dict[str, Any]]:
    """List tables in a specific database with row counts and sizes."""
    conn = await _get_admin_conn(database=db_name)
    try:
        rows = await conn.fetch(
            """
            SELECT
                t.table_schema AS schema,
                t.table_name AS name,
                pg_total_relation_size(quote_ident(t.table_schema) || '.' || quote_ident(t.table_name)) AS size_bytes,
                (
                    SELECT reltuples::bigint
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relname = t.table_name AND n.nspname = t.table_schema
                ) AS row_count
            FROM information_schema.tables t
            WHERE t.table_schema NOT IN ('pg_catalog', 'information_schema')
              AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_schema, t.table_name
            """
        )

        return [
            {
                "name": row["name"],
                "schema": row["schema"],
                "row_count": max(int(row["row_count"] or 0), 0),
                "size_kb": round((row["size_bytes"] or 0) / 1024, 2),
            }
            for row in rows
        ]
    finally:
        await _release_conn(conn)


async def get_table_schema(db_name: str, table_name: str) -> dict[str, Any]:
    """Get column definitions for a specific table."""
    conn = await _get_admin_conn(database=db_name)
    try:
        # Get columns
        columns = await conn.fetch(
            """
            SELECT
                c.column_name AS name,
                c.data_type AS type,
                c.is_nullable = 'YES' AS nullable,
                c.column_default AS default_value
            FROM information_schema.columns c
            WHERE c.table_name = $1
              AND c.table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY c.ordinal_position
            """,
            table_name,
        )

        if not columns:
            return {"table_name": table_name, "schema_name": "public", "columns": []}

        # Get primary key columns
        pk_rows = await conn.fetch(
            """
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            JOIN pg_class c ON c.oid = i.indrelid
            WHERE c.relname = $1 AND i.indisprimary
            """,
            table_name,
        )
        pk_columns = {row["attname"] for row in pk_rows}

        return {
            "table_name": table_name,
            "schema_name": "public",
            "columns": [
                {
                    "name": col["name"],
                    "type": col["type"],
                    "nullable": col["nullable"],
                    "default": col["default_value"],
                    "is_pk": col["name"] in pk_columns,
                }
                for col in columns
            ],
        }
    finally:
        await _release_conn(conn)


async def execute_query(db_name: str, sql: str) -> dict[str, Any]:
    """Execute a read-only SQL query against a specific database.

    Only SELECT statements are allowed. Returns columns, rows, and timing.

    Raises:
        ValueError: If the SQL is not a SELECT statement.
    """
    # Validate: only SELECT allowed
    cleaned = sql.strip().rstrip(";").strip()
    first_word = cleaned.split()[0].upper() if cleaned else ""
    if first_word != "SELECT":
        raise ValueError("Only SELECT queries are allowed")

    # Block dangerous keywords
    upper_sql = cleaned.upper()
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT", "REVOKE"]
    for keyword in forbidden:
        # Check for keyword as a word boundary (not part of a column name)
        if f" {keyword} " in f" {upper_sql} ":
            raise ValueError(f"Forbidden keyword in query: {keyword}")

    conn = await _get_admin_conn(database=db_name)
    try:
        start = time.time()

        # Use a read-only transaction
        async with conn.transaction(readonly=True):
            rows = await conn.fetch(cleaned)

        elapsed_ms = round((time.time() - start) * 1000, 2)

        if not rows:
            return {
                "columns": [],
                "rows": [],
                "row_count": 0,
                "execution_time_ms": elapsed_ms,
            }

        columns = list(rows[0].keys())
        result_rows = [dict(row) for row in rows]

        # Serialize any non-JSON-native types to strings
        for row_dict in result_rows:
            for key, value in row_dict.items():
                if not isinstance(value, (str, int, float, bool, type(None), list, dict)):
                    row_dict[key] = str(value)

        return {
            "columns": columns,
            "rows": result_rows,
            "row_count": len(result_rows),
            "execution_time_ms": elapsed_ms,
        }
    finally:
        await _release_conn(conn)


async def create_database(name: str, password: str) -> dict[str, Any]:
    """Create a new PostgreSQL database and a dedicated user.

    Steps:
    1. CREATE USER {name} WITH PASSWORD '{password}'
    2. CREATE DATABASE {name} OWNER {name}
    3. GRANT ALL PRIVILEGES ON DATABASE {name} TO {name}

    Raises:
        ValueError: If the database name is invalid or already exists.
    """
    conn = await _get_admin_conn()
    try:
        # Check if database already exists
        existing = await conn.fetchrow(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            name,
        )
        if existing:
            raise ValueError(f"Database '{name}' already exists")

        # Create user and database (can't use parameterised queries for DDL)
        # Sanitise name to prevent SQL injection (already validated by Pydantic)
        safe_name = name.replace('"', '""')
        safe_password = password.replace("'", "''")

        await conn.execute(f'CREATE USER "{safe_name}" WITH PASSWORD \'{safe_password}\'')
        await conn.execute(f'CREATE DATABASE "{safe_name}" OWNER "{safe_name}"')
        await conn.execute(f'GRANT ALL PRIVILEGES ON DATABASE "{safe_name}" TO "{safe_name}"')

        logger.info("Created database and user: %s", name)
        return {"name": name, "user": name, "created": True}
    finally:
        await _release_conn(conn)
