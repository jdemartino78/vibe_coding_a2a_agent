import os
import logging

import asyncpg
import sqlalchemy
import sqlalchemy.ext.asyncio
from google.cloud.alloydb.connector import AsyncConnector
from google.cloud import secretmanager

from a2a.server.tasks import DatabaseTaskStore, TaskStore

logger = logging.getLogger(__name__)

# Global variable to hold the initialized store
_database_task_store: DatabaseTaskStore | None = None


def create_sqlalchemy_engine(
    inst_uri: str,
    user: str,
    password: str,
    db: str,
) -> sqlalchemy.ext.asyncio.engine.AsyncEngine:
    """Creates a connection pool for an AlloyDB instance."""
    connector = AsyncConnector()

    async def get_conn() -> asyncpg.Connection:
        connect_kwargs = {
            "db": db,
            "ip_type": "PUBLIC",
            "enable_iam_auth": False,
            "user": user,
            "password": password,
        }
        return await connector.connect(
            inst_uri,
            "asyncpg",
            **connect_kwargs,
        )

    engine = sqlalchemy.ext.asyncio.create_async_engine(
        "postgresql+asyncpg://",
        async_creator=get_conn,
        execution_options={"isolation_level": "AUTOCOMMIT"},
    )
    return engine


def build_database_task_store() -> TaskStore:
    """
    Synchronously builds the DatabaseTaskStore.
    Fetches credentials synchronously to satisfy the A2aAgent builder interface.
    """
    global _database_task_store

    if _database_task_store:
        return _database_task_store

    logger.info("Initializing DatabaseTaskStore (Synchronous)...")

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        # Fallback for local testing if env var isn't set, though it should be.
        # In deployment, this is always set.
        raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set.")

    # Synchronous Secret Manager Client
    client = secretmanager.SecretManagerServiceClient()

    def get_secret(secret_id: str) -> str:
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")

    try:
        logger.info("Fetching AlloyDB credentials from Secret Manager...")
        db_user = get_secret("alloydb-user-a2a-agent")
        db_pass = get_secret("alloydb-password-a2a-agent")
        db_instance_uri = get_secret("alloydb-instance-uri")
        db_name = os.environ.get("ALLOYDB_NAME", "a2a_tasks")

        # Create the async engine (this part is non-blocking)
        engine = create_sqlalchemy_engine(
            db_instance_uri,
            db_user,
            db_pass,
            db_name,
        )

        _database_task_store = DatabaseTaskStore(engine)
        
        # Note: We cannot 'await' initialization here in a sync function.
        # DatabaseTaskStore.initialize() (creating tables) usually needs to happen 
        # either on startup loop or lazily. 
        # However, since the 'tasks' table usually persists, we might skip strict 
        # table creation check here or rely on a separate init script.
        # Ideally, we'd run `await _database_task_store.initialize()` in a startup hook.
        
        logger.info("DatabaseTaskStore initialized successfully.")
        return _database_task_store

    except Exception as e:
        logger.exception("Failed to initialize DatabaseTaskStore.")
        raise RuntimeError("Could not initialize DatabaseTaskStore") from e

def get_database_task_store() -> DatabaseTaskStore:
    """Returns the initialized DatabaseTaskStore, initializing it if necessary."""
    if _database_task_store is None:
        return build_database_task_store()
    return _database_task_store

def get_db_engine() -> sqlalchemy.ext.asyncio.engine.AsyncEngine:
    """Returns the initialized SQLAlchemy engine."""
    if _database_task_store is None:
         build_database_task_store()
    return _database_task_store.engine
