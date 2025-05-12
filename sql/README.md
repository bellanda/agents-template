# SQL Directory

This directory contains SQL queries and scripts used in the project.

## Contents

- `temporary.sql` - A file for temporary SQL queries during development
- Other SQL scripts should be saved with descriptive names

## Best Practices

1. Name SQL files clearly to indicate their purpose
2. Comment your SQL code, especially complex queries
3. Structure queries for readability (indentation, line breaks)
4. Consider organizing SQL files by purpose:
   ```
   sql/
   ├── data_extraction/   # Queries to pull data from source systems
   ├── data_preparation/  # Data cleaning and preparation
   ├── analysis/          # Analytical queries
   └── reports/           # Queries for specific reports
   ```
5. Include a brief description at the top of each SQL file explaining its purpose
6. For complex queries, add comments explaining the logic of different sections

## Note

The `temporary.sql` file is intended for experimental queries during development. Once a query is finalized, it should be saved to an appropriately named file.
