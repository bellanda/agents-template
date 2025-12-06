"""
Lightweight message builders for streaming UI feedback.

Format
- All helpers return strings in the pattern `[TAG:part1:part2]`.
- They are safe to stream as SSE text; the frontend can parse by splitting on `:`
  after the first `[` and before the last `]`.

Recommended client parsing
- Extract `TAG` (e.g., STATUS, TOOL_START, TOOL_END, RESULT, ERROR).
- Use the remaining parts as payload to render progress, tool states, or thoughts.
"""

# -----------------------------------------------------------------------------
# Internal helper
# -----------------------------------------------------------------------------


def _format(tag: str, *parts: str) -> str:
    """Keep a consistent bracketed pattern."""
    safe_parts = [str(p).replace("\n", " ").strip() for p in parts if p is not None]
    return f"[{tag}:{':'.join(safe_parts)}]"


# -----------------------------------------------------------------------------
# Tool lifecycle
# -----------------------------------------------------------------------------


def generate_tool_start_message(tool_name: str, tool_input: dict | None = None) -> str:
    """Signal the start of a tool execution with optional context."""

    tool_mappings = {
        "get_weather": {"name": "clima", "action": "Consultando informações meteorológicas"},
        "web_search": {"name": "busca_web", "action": "Pesquisando na internet"},
        "search": {"name": "busca", "action": "Realizando busca"},
        "calculator": {"name": "calculadora", "action": "Executando cálculos"},
        "database_query": {"name": "banco_dados", "action": "Consultando banco de dados"},
        "api_call": {"name": "api_externa", "action": "Chamando API externa"},
        "file_reader": {"name": "leitor_arquivo", "action": "Lendo arquivo"},
        "email_sender": {"name": "envio_email", "action": "Enviando email"},
        "image_generator": {"name": "gerador_imagem", "action": "Gerando imagem"},
        "translator": {"name": "tradutor", "action": "Traduzindo texto"},
    }

    tool_info = tool_mappings.get(
        tool_name, {"name": tool_name.replace("_", " "), "action": f"Executando {tool_name.replace('_', ' ')}"}
    )

    context_detail = ""
    if tool_input:
        if "city" in tool_input or "cidade" in tool_input:
            context_detail = f" para {tool_input.get('city') or tool_input.get('cidade')}"
        elif "query" in tool_input or "consulta" in tool_input:
            query = tool_input.get("query") or tool_input.get("consulta")
            query_preview = str(query)[:30]
            context_detail = f": '{query_preview}...'" if len(str(query)) > 30 else f": '{query}'"
        elif "url" in tool_input:
            context_detail = f" em {tool_input['url']}"
        elif "file" in tool_input or "arquivo" in tool_input:
            context_detail = f": {tool_input.get('file') or tool_input.get('arquivo')}"
        elif "to" in tool_input or "para" in tool_input:
            context_detail = f" para {tool_input.get('to') or tool_input.get('para')}"
        elif "expression" in tool_input or "expressao" in tool_input:
            expr = tool_input.get("expression") or tool_input.get("expressao")
            expr_preview = str(expr)[:20]
            context_detail = f": {expr_preview}..." if len(str(expr)) > 20 else f": {expr}"
        elif len(tool_input) > 0:
            for _, value in tool_input.items():
                if value and str(value).strip():
                    value_preview = str(value)[:25]
                    context_detail = f": {value_preview}..." if len(str(value)) > 25 else f": {value}"
                    break

    message = f"{tool_info['action']}{context_detail}..."
    return _format("TOOL_START", tool_info["name"], message)


def generate_tool_end_message(tool_name: str, success: bool = True, error_msg: str | None = None) -> str:
    """Signal the end of a tool execution (success or error)."""

    tool_mappings = {
        "get_weather": {"name": "clima"},
        "web_search": {"name": "busca_web"},
        "search": {"name": "busca"},
        "calculator": {"name": "calculadora"},
        "database_query": {"name": "banco_dados"},
        "api_call": {"name": "api_externa"},
        "file_reader": {"name": "leitor_arquivo"},
        "email_sender": {"name": "envio_email"},
        "image_generator": {"name": "gerador_imagem"},
        "translator": {"name": "tradutor"},
    }

    tool_info = tool_mappings.get(tool_name, {"name": tool_name.replace("_", " ")})
    message = "Operação concluída com sucesso" if success else f"Erro na execução: {error_msg or 'Erro na execução'}"
    return _format("TOOL_END", tool_info["name"], message)


# -----------------------------------------------------------------------------
# Generic status & progress
# -----------------------------------------------------------------------------


def generate_status_message(status: str, message: str) -> str:
    """Generic status update (processing, completed, warning, etc)."""
    return _format("STATUS", status, message)


def generate_thinking_message(thought: str) -> str:
    """High-level 'thinking' update (LLM reasoning)."""
    return _format("THINKING", thought)


def generate_progress_message(progress: float, message: str) -> str:
    """Percentual progress update (0-100)."""
    return _format("PROGRESS", f"{progress:.1f}", message)


def generate_result_message(result_type: str, message: str) -> str:
    """Result indicator (success, error, warning)."""
    return _format("RESULT", result_type, message)


def generate_step_message(step_number: int, description: str) -> str:
    """Explicit step update (1, 2, 3...)."""
    return _format("STEP", step_number, description)


# -----------------------------------------------------------------------------
# Misc helpers
# -----------------------------------------------------------------------------


def generate_highlight_message(text: str) -> str:
    """Highlight a key piece of info."""
    return _format("HIGHLIGHT", text)


def generate_warning_message(message: str) -> str:
    """Warn about a non-fatal issue."""
    return _format("WARNING", message)


def generate_error_message(message: str) -> str:
    """Report an error to the user."""
    return _format("ERROR", message)


def generate_code_message(language: str, code: str) -> str:
    """Send code snippets in a consistent format."""
    return _format("CODE", language, code)
