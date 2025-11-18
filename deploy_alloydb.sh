#!/bin/bash
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

# This script automates the provisioning of a Google Cloud AlloyDB cluster,
# instance, and database for use as a persistent TaskStore for the A2A agent.
# It also creates a database user and stores the credentials in Secret Manager.

set -e

# --- Configuration ---
# Source environment variables from the .env file in the project root
if [ -f ".env" ]; then
  source .env
else
  echo "Error: .env file not found. Please create one with GOOGLE_CLOUD_PROJECT and LOCATION."
  exit 1
fi

# Use sourced variables, falling back to gcloud config if not set
PROJECT_ID=${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project)}
REGION=${LOCATION:-"us-central1"}

CLUSTER_ID="a2a-task-store-cluster"
INSTANCE_ID="a2a-task-store-instance"
DB_NAME="a2a_tasks"
DB_USER="a2a_agent_user"
NETWORK="default" # Assumes the 'default' VPC network.

# Secret names for storing credentials
DB_USER_SECRET_ID="alloydb-user-a2a-agent"
DB_PASS_SECRET_ID="alloydb-password-a2a-agent"
DB_INSTANCE_URI_SECRET_ID="alloydb-instance-uri"

# --- Script Logic ---

echo "Starting AlloyDB setup for project: $PROJECT_ID in region: $REGION"

# 1. Enable necessary APIs
echo "Enabling required Google Cloud APIs..."
gcloud services enable \
  alloydb.googleapis.com \
  secretmanager.googleapis.com \
  servicenetworking.googleapis.com \
  compute.googleapis.com

# 1.5. Ensure the default VPC network exists
echo "Checking for the 'default' VPC network..."
if ! gcloud compute networks describe "$NETWORK" --project="$PROJECT_ID" &>/dev/null; then
  echo "The 'default' network was not found. Creating it now..."
  gcloud compute networks create default --subnet-mode=auto --project="$PROJECT_ID"
  echo "'default' network created successfully."
else
  echo "'default' network already exists."
fi

# 2. Configure Private Services Access
# This is required for AlloyDB to connect to your VPC network.
echo "Configuring Private Services Access..."
# Check if the connection already exists
existing_connection=$(gcloud services vpc-peerings list --network=$NETWORK --service=servicenetworking.googleapis.com --format="value(peerings.name)")
existing_address=$(gcloud compute addresses list --global --filter="name=google-managed-services-$NETWORK" --format="value(name)")

if [ -z "$existing_connection" ] && [ -z "$existing_address" ]; then
    gcloud compute addresses create google-managed-services-$NETWORK \
        --global \
        --purpose=VPC_PEERING \
        --prefix-length=16 \
        --description="Private services access for $NETWORK" \
        --network=$NETWORK

    gcloud services vpc-peerings connect \
        --service=servicenetworking.googleapis.com \
        --ranges=google-managed-services-$NETWORK \
        --network=$NETWORK \
        --project=$PROJECT_ID
else
    echo "Private Services Access connection or address already exists. Skipping setup."
fi

# 3. Create AlloyDB Cluster
echo "Creating AlloyDB Cluster: $CLUSTER_ID..."
if ! gcloud alloydb clusters describe "$CLUSTER_ID" --region="$REGION" &>/dev/null; then
  # Set a known password for the initial postgres user
  INIT_PG_PASSWORD=$(openssl rand -base64 16)
  gcloud alloydb clusters create "$CLUSTER_ID" \
    --region="$REGION" \
    --password="$INIT_PG_PASSWORD" \
    --network="$NETWORK" \
    --project="$PROJECT_ID"
  echo "Cluster created. Postgres user password set."
  # Store this initial password if needed for recovery, e.g., in Secret Manager
  # echo -n "$INIT_PG_PASSWORD" | gcloud secrets create alloydb-initial-postgres-pass ...
else
  echo "AlloyDB Cluster '$CLUSTER_ID' already exists. Skipping creation."
fi

# 4. Create AlloyDB Primary Instance with Public IP
echo "Creating AlloyDB Primary Instance: $INSTANCE_ID..."
if ! gcloud alloydb instances describe "$INSTANCE_ID" --cluster="$CLUSTER_ID" --region="$REGION" &>/dev/null; then
  gcloud alloydb instances create "$INSTANCE_ID" \
    --cluster="$CLUSTER_ID" \
    --region="$REGION" \
    --instance-type=PRIMARY \
    --cpu-count=2 \
    --assign-inbound-public-ip=ASSIGN_IPV4 \
    --database-flags=password.enforce_complexity=on \
    --project="$PROJECT_ID"
else
  echo "AlloyDB Instance '$INSTANCE_ID' already exists. Skipping creation."
fi

# 5. Authorize Your Public IP for Connection
echo "Checking and authorizing your public IP for database connection..."
MY_IP=$(curl -s ifconfig.me)
if [ -z "$MY_IP" ]; then
    echo "Could not determine public IP address. Please add it manually to the AlloyDB instance's authorized networks."
    exit 1
fi
MY_IP_CIDR="$MY_IP/32"

EXISTING_NETWORKS=$(gcloud alloydb instances describe "$INSTANCE_ID" \
    --cluster="$CLUSTER_ID" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --format="value(networkConfig.authorizedExternalNetworks[].cidrRange)")

if echo "$EXISTING_NETWORKS" | grep -q "$MY_IP_CIDR"; then
    echo "Your IP address $MY_IP is already authorized."
else
    echo "Your IP address $MY_IP is not yet authorized. Adding it now..."
    if [ -z "$EXISTING_NETWORKS" ]; then
        UPDATED_NETWORKS="$MY_IP_CIDR"
    else
        # Combine existing and new, avoiding duplicates
        COMBINED=$(echo -e "$EXISTING_NETWORKS\n$MY_IP_CIDR" | tr ' ' '\n' | sort -u)
        UPDATED_NETWORKS=$(echo "$COMBINED" | paste -sd,)
    fi
    gcloud alloydb instances update "$INSTANCE_ID" \
      --cluster="$CLUSTER_ID" \
      --region="$REGION" \
      --authorized-external-networks="$UPDATED_NETWORKS" \
      --project="$PROJECT_ID"
    echo "Successfully updated authorized networks to: $UPDATED_NETWORKS. Waiting for 15 seconds for the rule to apply..."
    sleep 15
fi

# 5.5 Update postgres user password for script execution
echo "Updating 'postgres' user password for script access..."
TEMP_PG_PASSWORD=$(openssl rand -base64 16)
gcloud alloydb users set-password postgres \
  --cluster="$CLUSTER_ID" \
  --region="$REGION" \
  --password="$TEMP_PG_PASSWORD" \
  --project="$PROJECT_ID"
echo "'postgres' user password updated temporarily for script execution."

# Set PGPASSWORD for subsequent psql commands
export PGPASSWORD=$TEMP_PG_PASSWORD

# 6. Create the Database
echo "Creating Database: $DB_NAME..."
INSTANCE_IP=$(gcloud alloydb instances describe "$INSTANCE_ID" --cluster="$CLUSTER_ID" --region="$REGION" --format='value(publicIpAddress)')
echo "Instance Public IP: $INSTANCE_IP"
psql "host=$INSTANCE_IP user=postgres dbname=postgres" -c "CREATE DATABASE $DB_NAME;" || echo "Database '$DB_NAME' may already exist."

# 7. Create or Update the Database User & Grant Permissions
echo "Creating or updating Database User: $DB_USER..."
DB_PASSWORD=$(openssl rand -base64 16)

# Check if user exists. If so, alter password. If not, create user.
if psql "host=$INSTANCE_IP user=postgres dbname=postgres" -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
    echo "User '$DB_USER' exists. Altering password."
    psql "host=$INSTANCE_IP user=postgres dbname=postgres" -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
else
    echo "User '$DB_USER' does not exist. Creating user."
    psql "host=$INSTANCE_IP user=postgres dbname=postgres" -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
fi

# Grant CONNECT on the database (safe to run multiple times)
psql "host=$INSTANCE_IP user=postgres dbname=postgres" -c "GRANT CONNECT ON DATABASE $DB_NAME TO $DB_USER;"
echo "CONNECT privilege granted on database $DB_NAME to $DB_USER."

# Grant Schema privileges within the DB_NAME database (safe to run multiple times)
psql "host=$INSTANCE_IP user=postgres dbname=$DB_NAME" -c "GRANT ALL ON SCHEMA public TO $DB_USER;"
echo "USAGE and CREATE privileges granted on schema public to $DB_USER within $DB_NAME."

# Set default privileges for tables created by a2a_agent_user or other roles in the future (safe to run multiple times)
psql "host=$INSTANCE_IP user=postgres dbname=$DB_NAME" -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;"
echo "Default table privileges set for $DB_USER in schema public."

# Set default privileges for sequences created by a2a_agent_user or other roles in the future (safe to run multiple times)
psql "host=$INSTANCE_IP user=postgres dbname=$DB_NAME" -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;"
echo "Default sequence privileges set for $DB_USER in schema public."

echo "Database user $DB_USER privileges are set."

# Unset PGPASSWORD after use
unset PGPASSWORD

# 8. Store Credentials in Secret Manager
echo "Storing credentials in Secret Manager..."

# Function to create or update a secret
create_or_update_secret() {
  local secret_id=
  local data=$2
  if gcloud secrets describe "$secret_id" --project="$PROJECT_ID" &>/dev/null; then
    echo "Secret '$secret_id' exists. Adding new version."
    echo -n "$data" | gcloud secrets versions add "$secret_id" --data-file=- --project="$PROJECT_ID"
  else
    echo "Secret '$secret_id' does not exist. Creating it."
    echo -n "$data" | gcloud secrets create "$secret_id" \
      --data-file=-\
      --replication-policy=automatic \
      --project="$PROJECT_ID"
  fi
}

# Store DB User
create_or_update_secret "$DB_USER_SECRET_ID" "$DB_USER"

# Store DB Password
create_or_update_secret "$DB_PASS_SECRET_ID" "$DB_PASSWORD"

# Store Instance Connection Name
INSTANCE_URI=$(gcloud alloydb instances describe "$INSTANCE_ID" --cluster="$CLUSTER_ID" --region="$REGION" --format='value(name)')
create_or_update_secret "$DB_INSTANCE_URI_SECRET_ID" "$INSTANCE_URI"

echo "---"
echo "AlloyDB setup complete!"
echo "The following secrets have been created in Secret Manager:"
echo "- $DB_USER_SECRET_ID (Database User)"
echo "- $DB_PASS_SECRET_ID (Database Password)"
echo "- $DB_INSTANCE_URI_SECRET_ID (AlloyDB Instance URI)"
echo ""
echo "IMPORTANT: For your Agent Engine to connect, ensure its service account has the following IAM roles:"
echo "1. Cloud AlloyDB Client (roles/alloydb.client)"
echo "2. Secret Manager Secret Accessor (roles/secretmanager.secretAccessor)"
echo "3. Vertex AI User (roles/aiplatform.user)"
echo "---"