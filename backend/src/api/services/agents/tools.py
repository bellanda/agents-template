"""
Lightweight message builders for streaming UI feedback using XML tags.
Safe for Vercel AI SDK consumption (parsed by frontend).
"""

import html

# -----------------------------------------------------------------------------
# Internal helper
# -----------------------------------------------------------------------------


def _tag(type_name: str, name: str | None = None, content: str = "") -> str:
    """Build an XML-like tag: <agent:status type="..." name="...">Content</agent:status>"""
    attrs = f' type="{type_name}"'
    if name:
        attrs += f' name="{html.escape(name)}"'

    safe_content = html.escape(str(content))
    return f"<agent:status{attrs}>{safe_content}</agent:status>"


# -----------------------------------------------------------------------------
# Tool lifecycle
# -----------------------------------------------------------------------------


def generate_tool_start_message(tool_name: str, tool_input: dict | None = None) -> str:
    """Signal the start of a tool execution."""
    tool_mappings = {
        "get_weather": "clima",
        "web_search": "busca_web",
        "search": "busca",
        "calculator": "calculadora",
        "database_query": "banco_dados",
        "api_call": "api_externa",
        "file_reader": "leitor_arquivo",
        "email_sender": "envio_email",
        "image_generator": "gerador_imagem",
        "translator": "tradutor",
    }

    friendly_name = tool_mappings.get(tool_name, tool_name.replace("_", " "))

    # We serialize the input as a string for the content, or just a summary
    content = ""
    if tool_input:
        # Simple string representation of input for debug/UI
        content = str(tool_input)

    return _tag("tool_start", friendly_name, content)


def generate_tool_end_message(tool_name: str, success: bool = True, error_msg: str | None = None) -> str:
    """Signal the end of a tool execution."""
    friendly_name = tool_name.replace("_", " ")
    if not success:
        return _tag("tool_error", friendly_name, error_msg or "Unknown error")
    return _tag("tool_end", friendly_name, "success")


# -----------------------------------------------------------------------------
# Generic status & progress
# -----------------------------------------------------------------------------


def generate_status_message(status: str, message: str) -> str:
    """Generic status update."""
    return _tag("status", status, message)


def generate_thinking_message(thought: str) -> str:
    """High-level 'thinking' update."""
    return _tag("thinking", None, thought)


def generate_error_message(message: str) -> str:
    """Report a general error."""
    return _tag("error", None, message)


def generate_result_message(result_type: str, message: str) -> str:
    """Report a result."""
    return _tag("result", result_type, message)


def generate_step_message(step_number: int, message: str) -> str:
    """Report a step in a multi-step process."""
    return _tag("step", str(step_number), message)
