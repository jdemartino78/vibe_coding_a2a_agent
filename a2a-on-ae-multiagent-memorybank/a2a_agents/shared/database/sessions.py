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

"""
This module provides the Session ID Translation Layer.

It addresses the fundamental mismatch between the A2A Protocol's `context_id`
(a client-provided UUID for conversations) and Vertex AI Agent Engine's internally
generated, opaque session resource names (e.g., `projects/.../sessions/abc-789`).

Without this layer, every A2A message with a consistent `context_id` would
result in the creation of a new, blank Vertex AI session.

This module maps the `(user_id, context_id)` composite key to the corresponding
Vertex AI `vertex_session_name`, enabling long-term memory and identity persistence
across multi-turn conversations.
"""

import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncEngine

# Define the table structure for storing session mappings.
# We use a composite primary key of (user_id, context_id, agent_name) for better normalization.
# Changed table name to 'session_mappings_v3' to force schema update and include agent scoping.
metadata = sqlalchemy.MetaData()
session_mappings_table = sqlalchemy.Table(
    "session_mappings_v3",
    metadata,
    sqlalchemy.Column("user_id", sqlalchemy.String(255), primary_key=True),
    sqlalchemy.Column("context_id", sqlalchemy.String(255), primary_key=True),
    sqlalchemy.Column("agent_name", sqlalchemy.String(255), primary_key=True),
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
    Creates the 'session_mappings_v3' table in the database if it does not already exist.

    Args:
        engine: The SQLAlchemy AsyncEngine to use for the connection.
    """
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


async def get_session_mapping(engine: AsyncEngine, user_id: str, context_id: str, agent_name: str) -> str | None:
    """
    Retrieves the Vertex AI session name for a given user_id, context_id, and agent_name.

    Args:
        engine: The SQLAlchemy AsyncEngine to use for the connection.
        user_id: The ID of the user.
        context_id: The ID of the A2A context.
        agent_name: The name of the agent (e.g., 'orchestrator', 'weather_agent').

    Returns:
        The Vertex AI session name if found, otherwise None.
    """
    async with engine.connect() as conn:
        stmt = sqlalchemy.select(session_mappings_table.c.vertex_session_name).where(
            sqlalchemy.and_(
                session_mappings_table.c.user_id == user_id,
                session_mappings_table.c.context_id == context_id,
                session_mappings_table.c.agent_name == agent_name
            )
        )
        result = await conn.execute(stmt)
        row = result.fetchone()
        return row[0] if row else None


async def set_session_mapping(engine: AsyncEngine, user_id: str, context_id: str, agent_name: str, vertex_session_name: str):
    """
    Saves or updates the mapping between user/context/agent and a Vertex AI session name.

    Args:
        engine: The SQLAlchemy AsyncEngine to use for the connection.
        user_id: The ID of the user.
        context_id: The ID of the A2A context.
        agent_name: The name of the agent.
        vertex_session_name: The Vertex AI session name to store.
    """
    async with engine.connect() as conn:
        # Use an "upsert" operation to either insert a new row or update an existing one.
        from sqlalchemy.dialects.postgresql import insert

        stmt = insert(session_mappings_table).values(
            user_id=user_id,
            context_id=context_id,
            agent_name=agent_name,
            vertex_session_name=vertex_session_name
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "context_id", "agent_name"],
            set_=dict(vertex_session_name=vertex_session_name),
        )
        await conn.execute(stmt)
        await conn.commit()