"""Database browser schemas."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class DatabaseInfo(BaseModel):
    """Summary of a PostgreSQL database."""
    name: str
    size_mb: float = 0.0
    owner: str = ""
    tables_count: int = 0


class TableInfo(BaseModel):
    """Summary of a single table."""
    name: str
    schema: str = "public"
    row_count: int = 0
    size_kb: float = 0.0


class ColumnInfo(BaseModel):
    """Column metadata."""
    name: str
    type: str
    nullable: bool = True
    default: Optional[str] = None
    is_pk: bool = False


class TableSchema(BaseModel):
    """Full schema description for a table."""
    table_name: str
    schema_name: str = "public"
    columns: list[ColumnInfo]


class QueryRequest(BaseModel):
    """Request body for executing a read-only SQL query."""
    sql: str = Field(..., min_length=1, max_length=10000)


class QueryResponse(BaseModel):
    """Result of a SQL query execution."""
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    execution_time_ms: float


class CreateDatabaseRequest(BaseModel):
    """Request body for creating a new database."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=63,
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Database name (lowercase, alphanumeric + underscore)",
    )
    password: str = Field(..., min_length=8, description="Password for the new database user")
