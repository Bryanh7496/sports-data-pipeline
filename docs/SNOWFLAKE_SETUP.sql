-- Least-privilege role for dbt. Run once as ACCOUNTADMIN.
-- Same idea as the scoped IAM policy: dbt can read RAW, build in its own
-- schemas, and use the warehouse. Nothing else.

USE ROLE ACCOUNTADMIN;

CREATE ROLE IF NOT EXISTS DBT_ROLE;

-- Compute
GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE DBT_ROLE;

-- Read access to raw data (existing and future tables)
GRANT USAGE ON DATABASE SPORTS_DB TO ROLE DBT_ROLE;
GRANT USAGE ON SCHEMA SPORTS_DB.RAW TO ROLE DBT_ROLE;
GRANT SELECT ON ALL TABLES IN SCHEMA SPORTS_DB.RAW TO ROLE DBT_ROLE;
GRANT SELECT ON FUTURE TABLES IN SCHEMA SPORTS_DB.RAW TO ROLE DBT_ROLE;

-- Let dbt create its own schemas (STAGING, MARTS, ANALYTICS); it owns what it creates
GRANT CREATE SCHEMA ON DATABASE SPORTS_DB TO ROLE DBT_ROLE;

-- Attach the role to your user (replace YOUR_SNOWFLAKE_USER)
GRANT ROLE DBT_ROLE TO USER YOUR_SNOWFLAKE_USER;
