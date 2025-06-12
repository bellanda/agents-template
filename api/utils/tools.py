def should_agent_process_tool_result(tool_name: str) -> bool:
    """Determine if a tool's result should be processed by the agent or streamed directly."""

    # Tools that return raw data that needs agent processing/formatting
    agent_processed_tools = {
        "get_weather",
        "weather",
        "clima",
        "calculator",
        "calc",
        "calculadora",
        "translator",
        "translate",
        "tradutor",
        "database_query",
        "db_query",
        "sql_query",
        "api_call",
        "api_request",
        "data_analyzer",
        "analyze_data",
        "web_search",  # Moved here - web search results need agent processing when return_direct=False
        "search",
        "busca",
    }

    # Tools that return user-ready content that can be streamed directly
    # Only include tools that have return_direct=True or are meant for direct streaming
    direct_stream_tools = {
        "file_reader",
        "read_file",
        "ler_arquivo",
        "email_sender",
        "send_email",
        "enviar_email",
        "image_generator",
        "generate_image",
        "gerar_imagem",
    }

    # Check if tool should be processed by agent
    if tool_name.lower() in agent_processed_tools:
        return True

    # Check if tool can be streamed directly
    if tool_name.lower() in direct_stream_tools:
        return False

    # Default: let agent process unknown tools for safety
    return True


def generate_tool_start_message(tool_name: str, tool_input: dict = None) -> str:
    """Generate tool start message using HPEAgents markup format."""

    # Tool name mappings for better user-friendly names
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

    # Get tool info or create generic one
    tool_info = tool_mappings.get(
        tool_name, {"name": tool_name.replace("_", " "), "action": f"Executando {tool_name.replace('_', ' ')}"}
    )

    # Add context from tool input if available
    context_detail = ""
    if tool_input:
        # Weather-related context
        if "city" in tool_input or "cidade" in tool_input:
            city = tool_input.get("city") or tool_input.get("cidade")
            context_detail = f" para {city}"
        # Search-related context
        elif "query" in tool_input or "consulta" in tool_input:
            query = tool_input.get("query") or tool_input.get("consulta")
            query_preview = str(query)[:30]
            context_detail = f": '{query_preview}...'" if len(str(query)) > 30 else f": '{query}'"
        # URL-related context
        elif "url" in tool_input:
            context_detail = f" em {tool_input['url']}"
        # File-related context
        elif "file" in tool_input or "arquivo" in tool_input:
            file_name = tool_input.get("file") or tool_input.get("arquivo")
            context_detail = f": {file_name}"
        # Email-related context
        elif "to" in tool_input or "para" in tool_input:
            recipient = tool_input.get("to") or tool_input.get("para")
            context_detail = f" para {recipient}"
        # Calculation context
        elif "expression" in tool_input or "expressao" in tool_input:
            expr = tool_input.get("expression") or tool_input.get("expressao")
            expr_preview = str(expr)[:20]
            context_detail = f": {expr_preview}..." if len(str(expr)) > 20 else f": {expr}"
        # Generic context for any other input
        elif len(tool_input) > 0:
            # Get first meaningful value
            for key, value in tool_input.items():
                if value and str(value).strip():
                    value_preview = str(value)[:25]
                    context_detail = f": {value_preview}..." if len(str(value)) > 25 else f": {value}"
                    break

    message = f"{tool_info['action']}{context_detail}..."
    return f"[TOOL_START:{tool_info['name']}:{message}]"


def generate_tool_end_message(tool_name: str, success: bool = True, error_msg: str = None) -> str:
    """Generate tool end message using HPEAgents markup format."""

    # Tool name mappings for better user-friendly names
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

    # Get tool info or create generic one
    tool_info = tool_mappings.get(tool_name, {"name": tool_name.replace("_", " ")})

    if success:
        message = "Operação concluída com sucesso"
        return f"[TOOL_END:{tool_info['name']}:{message}]"
    else:
        message = f"Erro na execução: {error_msg}" if error_msg else "Erro na execução"
        return f"[TOOL_END:{tool_info['name']}:{message}]"


def generate_status_message(status: str, message: str) -> str:
    """Generate status message using HPEAgents markup format."""
    return f"[STATUS:{status}:{message}]"


def generate_thinking_message(thought: str) -> str:
    """Generate thinking message using HPEAgents markup format."""
    return f"[THINKING:{thought}]"


def generate_progress_message(progress: float, message: str) -> str:
    """Generate progress message using HPEAgents markup format."""
    return f"[PROGRESS:{progress}:{message}]"


def generate_result_message(result_type: str, message: str) -> str:
    """Generate result message using HPEAgents markup format."""
    return f"[RESULT:{result_type}:{message}]"


def generate_step_message(step_number: int, description: str) -> str:
    """Generate step message using HPEAgents markup format."""
    return f"[STEP:{step_number}:{description}]"


def generate_highlight_message(text: str) -> str:
    """Generate highlight message using HPEAgents markup format."""
    return f"[HIGHLIGHT:{text}]"


def generate_warning_message(message: str) -> str:
    """Generate warning message using HPEAgents markup format."""
    return f"[WARNING:{message}]"


def generate_error_message(message: str) -> str:
    """Generate error message using HPEAgents markup format."""
    return f"[ERROR:{message}]"


def generate_code_message(language: str, code: str) -> str:
    """Generate code message using HPEAgents markup format."""
    return f"[CODE:{language}:{code}]"


# Backward compatibility - keep the old function but update it to use new format
def generate_tool_progress_message(tool_name: str, stage: str, tool_input: dict = None) -> str:
    """Generate dynamic progress messages based on tool name and stage (backward compatibility)."""

    if stage == "start":
        return generate_tool_start_message(tool_name, tool_input)
    elif stage == "error":
        return generate_tool_end_message(tool_name, success=False)
    else:
        return generate_status_message("processing", f"Processando {tool_name.replace('_', ' ')}...")
