# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncEngine

# Define the table structure for storing session mappings.
# This metadata object will be used to create the table if it doesn't exist.
metadata = sqlalchemy.MetaData()
session_mappings_table = sqlalchemy.Table(
    "session_mappings",
    metadata,
    sqlalchemy.Column("session_key", sqlalchemy.String(255), primary_key=True),
    sqlalchemy.Column("vertex_session_name", sqlalchemy.String(255), nullable=False),
    sqlalchemy.Column(
        "last_updated",
        sqlalchemy.TIMESTAMP(timezone=True),
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    ),
)


async def initialize_session_store(engine: AsyncEngine):
    """
    Creates the 'session_mappings' table in the database if it does not already exist.

    Args:
        engine: The SQLAlchemy AsyncEngine to use for the connection.
    """
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


async def get_session_mapping(engine: AsyncEngine, key: str) -> str | None:
    """
    Retrieves the Vertex AI session name for a given key from the database.

    Args:
        engine: The SQLAlchemy AsyncEngine to use for the connection.
        key: The key (e.g., 'user_id-context_id') to look up.

    Returns:
        The Vertex AI session name if found, otherwise None.
    """
    async with engine.connect() as conn:
        stmt = sqlalchemy.select(session_mappings_table.c.vertex_session_name).where(
            session_mappings_table.c.session_key == key
        )
        result = await conn.execute(stmt)
        row = result.fetchone()
        return row[0] if row else None


async def set_session_mapping(engine: AsyncEngine, key: str, vertex_session_name: str):
    """
    Saves or updates the mapping between a key and a Vertex AI session name in the database.

    Args:
        engine: The SQLAlchemy AsyncEngine to use for the connection.
        key: The key (e.g., 'user_id-context_id') to save.
        vertex_session_name: The Vertex AI session name to store.
    """
    async with engine.connect() as conn:
        # Use an "upsert" operation to either insert a new row or update an existing one.
        # This is more robust than separate INSERT and UPDATE statements.
        from sqlalchemy.dialects.postgresql import insert

        stmt = insert(session_mappings_table).values(
            session_key=key, vertex_session_name=vertex_session_name
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["session_key"],
            set_=dict(vertex_session_name=vertex_session_name),
        )
        await conn.execute(stmt)
        await conn.commit()
