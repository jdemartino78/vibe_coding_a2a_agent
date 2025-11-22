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
# We use a composite primary key of (user_id, context_id) for better normalization.
metadata = sqlalchemy.MetaData()
session_mappings_table = sqlalchemy.Table(
    "session_mappings",
    metadata,
    sqlalchemy.Column("user_id", sqlalchemy.String(255), primary_key=True),
    sqlalchemy.Column("context_id", sqlalchemy.String(255), primary_key=True),
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


async def get_session_mapping(engine: AsyncEngine, user_id: str, context_id: str) -> str | None:
    """
    Retrieves the Vertex AI session name for a given user_id and context_id.

    Args:
        engine: The SQLAlchemy AsyncEngine to use for the connection.
        user_id: The ID of the user.
        context_id: The ID of the A2A context.

    Returns:
        The Vertex AI session name if found, otherwise None.
    """
    async with engine.connect() as conn:
        stmt = sqlalchemy.select(session_mappings_table.c.vertex_session_name).where(
            sqlalchemy.and_(
                session_mappings_table.c.user_id == user_id,
                session_mappings_table.c.context_id == context_id
            )
        )
        result = await conn.execute(stmt)
        row = result.fetchone()
        return row[0] if row else None


async def set_session_mapping(engine: AsyncEngine, user_id: str, context_id: str, vertex_session_name: str):
    """
    Saves or updates the mapping between user/context and a Vertex AI session name.

    Args:
        engine: The SQLAlchemy AsyncEngine to use for the connection.
        user_id: The ID of the user.
        context_id: The ID of the A2A context.
        vertex_session_name: The Vertex AI session name to store.
    """
    async with engine.connect() as conn:
        # Use an "upsert" operation to either insert a new row or update an existing one.
        from sqlalchemy.dialects.postgresql import insert

        stmt = insert(session_mappings_table).values(
            user_id=user_id,
            context_id=context_id,
            vertex_session_name=vertex_session_name
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "context_id"],
            set_=dict(vertex_session_name=vertex_session_name),
        )
        await conn.execute(stmt)
        await conn.commit()
