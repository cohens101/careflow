# CareFlow — Local Development Setup

## Overview

This guide describes the local development requirements for CareFlow.

CareFlow uses Azure Data Lake Storage Gen2, Snowflake, dbt, and a Next.js analytics application.

The healthcare dataset is synthetic.

The repository does not yet automate the provisioning of all cloud resources, Snowflake roles, or external storage integrations.

## 1. Prerequisites

- Python and pip
- Node.js and npm compatible with the project's Next.js version
- Azure CLI
- Access to an Azure subscription
- Access to a Snowflake account
- macOS for the optional LaunchAgent workflow

The original development environment uses separate Python virtual environments for ingestion, audit synchronization, and dbt.

## 2. Clone the Repository

    git clone <REPOSITORY_URL>
    cd careflow

Replace the URL with the published GitHub repository address.

## 3. Python Environments

Create separate environments for the three Python workloads.

### Azure ingestion

    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements-ingestion.txt

### Snowflake audit synchronization

    python3.12 -m venv .venv-audit
    .venv-audit/bin/python -m pip install -r requirements-audit.txt

### dbt transformations

    python3.12 -m venv .venv-dbt
    .venv-dbt/bin/python -m pip install -r requirements-dbt.txt

The dbt environment's compatibility must be verified on the target Python installation.

Dependency installation has not yet been independently tested from a clean machine.

## 4. Azure Configuration

Sign in using Azure CLI:

    az login

CareFlow uses Azure Data Lake Storage Gen2 for raw FHIR resources.

Configure the storage account in your environment:

    export AZURE_STORAGE_ACCOUNT="<STORAGE_ACCOUNT_NAME>"

The Azure identity must have the required permissions to access the target storage container.

Cloud resources, storage permissions, and the Snowflake Azure storage integration must be configured separately.

## 5. Snowflake Configuration

CareFlow uses the following database layers:

- BRONZE: Raw FHIR resources
- SILVER: Structured clinical data
- GOLD: Analytics-ready models and reporting views
- MONITORING: Operational ingestion audit history

The original project uses the CAREFLOW database and CAREFLOW_WH warehouse.

Snowflake setup requires appropriate databases, schemas, warehouse permissions, integrations, and service users.

The audit synchronization service uses key-pair authentication.

The dashboard uses a separate read-only Snowflake role.

Private keys and passphrases must not be committed to the repository.

## 6. dbt Configuration

Configure your Snowflake connection using a local dbt profile.

Then validate the project:

    .venv-dbt/bin/dbt parse --project-dir careflow_dbt

List models:

    .venv-dbt/bin/dbt ls --project-dir careflow_dbt --resource-type model

Run cloud transformations only after verifying that the Snowflake environment and profile point to the intended resources.

## 7. Next.js Dashboard

Enter the frontend directory:

    cd careflow-web

Install dependencies from the lockfile:

    npm ci

Create a local .env.local configuration.

The application references SNOWFLAKE_ACCOUNT and SNOWFLAKE_PRIVATE_KEY_PATH.

Additional authentication and Snowflake settings should be configured according to the server-side application implementation.

The private-key passphrase is provided securely in the server execution environment.

Start development:

    npm run dev

Open the localhost address reported by Next.js.

Do not publicly expose the Snowflake API routes without application-level authentication and authorization.

## 8. Ingestion Execution

Return to the repository root.

After preparing the Azure environment and source dataset, run:

    .venv/bin/python scripts/run_ingestion.py

The ingestion workflow records execution outcomes, evaluates alert conditions, synchronizes audit history, and updates the notification outbox.

Snowflake synchronization requires CAREFLOW_AUDIT_KEY_PASSPHRASE and the configured audit service credentials.

## 9. Automated Tests

Run the Python alerting regression suite:

    .venv-audit/bin/python -m unittest discover -s tests -p "test_*.py" -v

These tests use temporary SQLite databases and simulated SMTP delivery.

They do not require live patient data or real emails.

## 10. Local Scheduling

The project includes scripts/run_scheduled_careflow.py.

The original development machine uses a macOS LaunchAgent with a daily 9:00 AM schedule.

The runner retrieves protected credentials from macOS Keychain, prevents overlapping executions, and maintains local logs.

The LaunchAgent configuration and Keychain secrets are machine-specific and are not included in this repository.

Calendar-triggered execution and unattended email delivery require further operational verification.

## 11. Security Considerations

- Use synthetic healthcare data only.
- Keep .env.local and private keys outside version control.
- Restrict Snowflake application permissions.
- Store credentials in an appropriate secrets manager.
- Protect the dashboard before public deployment.
- Review cloud costs and permissions before executing pipelines.

## 12. Known Limitations

- Cloud infrastructure is not fully provisioned through code.
- Local scheduling depends on an available Mac user session.
- SMTP acceptance does not guarantee final inbox delivery.
- Some interrupted notification attempts require manual review.
- The existing synthetic source dataset is static.
- Ingestion recency does not independently establish clinical data freshness.
- The original ingestion Python 3.9 environment emits a urllib3 LibreSSL compatibility warning.

The project is intended for engineering demonstration and is not a production clinical system.
