import asyncio
import os
import logging

import asyncpg
import sqlalchemy
import sqlalchemy.ext.asyncio
from google.cloud.alloydb.connector import AsyncConnector
from google.cloud import secretmanager

from a2a.server.tasks import DatabaseTaskStore

logger = logging.getLogger(__name__)

# Global variable to hold the initialized TaskStore
database_task_store: DatabaseTaskStore | None = None

async def create_sqlalchemy_engine(
    inst_uri: str,
    user: str,
    password: str,
    db: str,
) -> tuple[sqlalchemy.ext.asyncio.engine.AsyncEngine, AsyncConnector]:
    """Creates a connection pool for an AlloyDB instance and returns the pool
    and the connector. Callers are responsible for closing the pool and the
    connector.

    Args:
        instance_uri (str):
            The instance URI specifies the instance relative to the project,
            region, and cluster. For example:
            "projects/my-project/locations/us-central1/clusters/my-cluster/instances/my-instance"
        user (str):
            The database user name, e.g., postgres
        password (str):
            The database user's password, e.g., secret-password
        db (str):
            The name of the database, e.g., mydb
    """
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

    # Test the database connection
    try:
        async with engine.connect() as conn:
            result = await conn.execute(sqlalchemy.text("SELECT 1"))
            if result.scalar_one() == 1:
                logger.info("✅ Successfully connected to the database.")
            else:
                logger.error("❌ DB connection test failed: Did not receive expected result.")
    except Exception as e:
        logger.exception(f"❌ Failed to connect to the database: {e}")
        raise
    return engine, connector

async def initialize_dependencies():
    global database_task_store

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set.")

    secret_client = secretmanager.SecretManagerServiceClient()

    # Retrieve secrets
    try:
        db_user_secret_name = f"projects/{project_id}/secrets/alloydb-user-a2a-agent/versions/latest"
        db_pass_secret_name = f"projects/{project_id}/secrets/alloydb-password-a2a-agent/versions/latest"
        db_instance_uri_secret_name = f"projects/{project_id}/secrets/alloydb-instance-uri/versions/latest"

        db_user_response = await asyncio.to_thread(secret_client.access_secret_version, request={"name": db_user_secret_name})
        db_pass_response = await asyncio.to_thread(secret_client.access_secret_version, request={"name": db_pass_secret_name})
        db_instance_uri_response = await asyncio.to_thread(secret_client.access_secret_version, request={"name": db_instance_uri_secret_name})

        db_user = db_user_response.payload.data.decode("UTF-8")
        db_pass = db_pass_response.payload.data.decode("UTF-8")
        db_instance_uri = db_instance_uri_response.payload.data.decode("UTF-8")

        db_name = os.environ.get("ALLOYDB_NAME", "a2a_tasks") # Default to 'a2a_tasks' if not set

    except Exception as e:
        logger.exception("Failed to retrieve AlloyDB credentials from Secret Manager.")
        raise RuntimeError("Failed to retrieve AlloyDB credentials.") from e

    # Create SQLAlchemy engine
    engine, connector = await create_sqlalchemy_engine(
        db_instance_uri,
        db_user,
        db_pass,
        db_name,
    )

    # Initialize DatabaseTaskStore
    database_task_store = DatabaseTaskStore(engine)
    await database_task_store.initialize()

    logger.info("Dependencies initialized: DatabaseTaskStore is ready.")

def get_database_task_store() -> DatabaseTaskStore:
    if database_task_store is None:
        raise RuntimeError("DatabaseTaskStore has not been initialized. Call initialize_dependencies first.")
    return database_task_store
