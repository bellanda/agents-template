# Scripts Directory

This directory contains standalone Python scripts for various tasks related to the project.

## Purpose

Unlike notebooks, which are interactive and focused on exploration and analysis, scripts in this directory are typically:

- Automated processes
- ETL (Extract, Transform, Load) jobs
- Data pipeline components
- Command-line utilities
- Scheduled tasks

## Best Practices

1. Add a docstring at the top of each script explaining:

   - The script's purpose
   - Required inputs
   - Expected outputs
   - Usage examples

2. Include proper error handling and logging

3. Use command-line arguments for flexibility

   ```python
   import argparse

   def parse_args():
       parser = argparse.ArgumentParser(description='Script description')
       parser.add_argument('--input', required=True, help='Input file path')
       parser.add_argument('--output', required=True, help='Output file path')
       return parser.parse_args()
   ```

4. Make scripts executable on Unix-like systems

   ```python
   #!/usr/bin/env python
   ```

5. Consider adding a `__main__` block for direct execution

   ```python
   if __name__ == "__main__":
       main()
   ```

6. Import utility functions from the `utilities` directory to avoid code duplication
