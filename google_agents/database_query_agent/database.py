import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

import polars as pl
from sqlalchemy import text

from utilities.database.oracle import engine

BASE_DIR = pathlib.Path(__file__).parent.parent.parent


def get_database_documentation():
    """
    Helper function to get the documentation of the current database.
    Must be used along side the tool do_database_query to create a valid query and return data to the user.
    """
    with open(BASE_DIR / "docs" / "database_documentation.md", "r", encoding="utf-8") as file:
        file_content = file.read()

    return {"documentation": file_content}


def do_database_query(query: str):
    """
    Função de consulta ao banco de dados.
    O parâmetro query é uma consulta SQL SELECT.
    Para encontrar instruções sobre o banco de dados atual, use a ferramenta get_database_documentation.

    Warnings:
        - A query deve ser uma consulta SQL SELECT válida.
        - Nunca use `;` no final da query. Isso causará um erro.
        - A query deve ser um nome de tabela válido.
        - A query deve ser um nome de coluna válido.
        - A query deve ser um valor válido.
        - A query deve ser uma data válida.
        - A query deve ser um horário válido.

    Returns:
        str: URL path to the JSON file containing the query result
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text(query))
            df = pl.DataFrame(result.fetchall())
    except Exception as e:
        return {"query_success": False, "error": str(e)}

    file_path = BASE_DIR / "data" / "server" / "query_result.json"
    df.write_json(file_path)

    with open(file_path, "r", encoding="utf-8") as file:
        file_content = file.read()

    if len(file_content) > 1000:
        return {
            "url": f"http://localhost:8005/download_file?file_name={file_path.name}",
            "query_success": True,
        }
    else:
        return {
            "url": f"http://localhost:8005/download_file?file_name={file_path.name}",
            "query_success": True,
            "file_content": file_content,
        }
