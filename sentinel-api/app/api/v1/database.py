"""Database browser routes - list databases, tables, schemas, run queries, create databases."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.database import get_db
from app.schemas.database import (
    CreateDatabaseRequest,
    DatabaseInfo,
    QueryRequest,
    QueryResponse,
    TableInfo,
    TableSchema,
)
from app.services.audit_service import log_action
from app.services.db_service import (
    create_database,
    execute_query,
    get_table_schema,
    list_databases,
    list_tables,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/database", tags=["Database"])


@router.get("/databases", response_model=list[DatabaseInfo])
async def get_all_databases(claims: dict = Depends(require_admin)):
    """List all databases on the managed PostgreSQL instance."""
    try:
        dbs = await list_databases()
        return [DatabaseInfo(**d) for d in dbs]
    except Exception as exc:
        logger.error("Failed to list databases: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to list databases: {exc}")


@router.get("/databases/{db_name}/tables", response_model=list[TableInfo])
async def get_database_tables(
    db_name: str,
    claims: dict = Depends(require_admin),
):
    """List tables in a specific database with row counts."""
    try:
        tables = await list_tables(db_name)
        return [TableInfo(**t) for t in tables]
    except Exception as exc:
        logger.error("Failed to list tables for %s: %s", db_name, exc)
        raise HTTPException(status_code=500, detail=f"Failed to list tables: {exc}")


@router.get("/databases/{db_name}/tables/{table_name}", response_model=TableSchema)
async def get_table_schema_route(
    db_name: str,
    table_name: str,
    claims: dict = Depends(require_admin),
):
    """Get column definitions for a specific table."""
    try:
        schema = await get_table_schema(db_name, table_name)
        return TableSchema(**schema)
    except Exception as exc:
        logger.error("Failed to get schema for %s.%s: %s", db_name, table_name, exc)
        raise HTTPException(status_code=500, detail=f"Failed to get table schema: {exc}")


@router.post("/databases/{db_name}/query", response_model=QueryResponse)
async def run_query(
    db_name: str,
    body: QueryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Execute a read-only SQL query against a specific database.

    Only SELECT statements are allowed.
    """
    try:
        result = await execute_query(db_name, body.sql)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Query failed on %s: %s", db_name, exc)
        raise HTTPException(status_code=500, detail=f"Query execution failed: {exc}")

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="database.query",
        target=db_name,
        details={"sql": body.sql[:500], "row_count": result["row_count"]},
        ip_address=request.client.host if request and request.client else None,
    )

    return QueryResponse(**result)


@router.post("/databases", status_code=201)
async def create_new_database(
    body: CreateDatabaseRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_admin),
):
    """Create a new PostgreSQL database and dedicated user."""
    try:
        result = await create_database(body.name, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to create database %s: %s", body.name, exc)
        raise HTTPException(status_code=500, detail=f"Failed to create database: {exc}")

    await log_action(
        db,
        user_id=claims.get("sub"),
        action="database.create",
        target=body.name,
        ip_address=request.client.host if request and request.client else None,
    )

    return result
