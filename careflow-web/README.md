# CareFlow Analytics Dashboard

A healthcare analytics and pipeline monitoring dashboard built with Next.js, TypeScript, and Tailwind CSS.

This application is the presentation layer of the CareFlow data engineering platform.

## Overview

CareFlow transforms synthetic FHIR healthcare data through Azure Data Lake Storage Gen2, Snowflake, and dbt.

The dashboard queries secured Snowflake reporting views and presents analytics and operational monitoring information.

## Dashboard Features

- Healthcare KPI summaries
- Encounter and diagnosis analytics
- Data quality and reconciliation results
- Ingestion execution history
- Pipeline file activity
- Data freshness indicators
- Pipeline health monitoring

## Technology Stack

- Next.js
- React
- TypeScript
- Tailwind CSS
- Snowflake Node.js SDK
- Server-side API routes

## Application Structure

src/
├── app/
│   ├── api/snowflake/
│   │   ├── charts/
│   │   ├── freshness/
│   │   ├── health/
│   │   ├── pipeline/
│   │   └── quality/
│   ├── page.tsx
│   └── globals.css
└── components/
    ├── LiveCharts.tsx
    ├── LiveFreshness.tsx
    ├── LiveHealth.tsx
    ├── LiveMetrics.tsx
    ├── LivePipeline.tsx
    └── LiveQuality.tsx

## Local Development

Install dependencies:

    npm ci

Start the development server:

    npm run dev

Open the local address printed by Next.js, typically:

    http://localhost:3000

If port 3000 is occupied, Next.js may select another port.

## Snowflake Integration

The application uses server-side Snowflake key-pair authentication with restricted read-only reporting access.

Local configuration is stored in `.env.local` and is excluded from version control.

Private keys and passphrases must never be committed to Git.

## Security

- Snowflake queries execute on the server.
- The application uses restricted reporting permissions.
- Local credentials and private keys are excluded from Git.
- The healthcare dataset is synthetic.

The current API routes require application-level authentication and access controls before public deployment.

## Related Documentation

See the root [CareFlow README](../README.md) and [Architecture Documentation](../docs/architecture.md) for information about the complete platform.

## Project Status

The dashboard has been tested locally against Snowflake reporting views.

CareFlow remains an engineering portfolio project and is not intended for clinical decision-making or production patient data.
