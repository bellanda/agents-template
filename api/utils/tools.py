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


def generate_tool_progress_message(tool_name: str, stage: str, tool_input: dict = None) -> str:
    """Generate dynamic progress messages based on tool name and stage."""

    # Tool name mappings for better user-friendly names
    tool_mappings = {
        "get_weather": {"name": "clima", "icon": "🌤️", "action": "consultando"},
        "web_search": {"name": "busca web", "icon": "🔍", "action": "pesquisando"},
        "search": {"name": "busca", "icon": "🔍", "action": "buscando"},
        "calculator": {"name": "calculadora", "icon": "🧮", "action": "calculando"},
        "database_query": {"name": "banco de dados", "icon": "🗄️", "action": "consultando"},
        "api_call": {"name": "API externa", "icon": "🌐", "action": "chamando"},
        "file_reader": {"name": "arquivo", "icon": "📄", "action": "lendo"},
        "email_sender": {"name": "email", "icon": "📧", "action": "enviando"},
        "image_generator": {"name": "imagem", "icon": "🎨", "action": "gerando"},
        "translator": {"name": "tradutor", "icon": "🌍", "action": "traduzindo"},
    }

    # Get tool info or create generic one
    tool_info = tool_mappings.get(tool_name, {"name": tool_name.replace("_", " "), "icon": "🔧", "action": "executando"})

    if stage == "start":
        # Add context from tool input if available
        context = ""
        if tool_input:
            # Weather-related context
            if "city" in tool_input or "cidade" in tool_input:
                city = tool_input.get("city") or tool_input.get("cidade")
                context = f" para {city}"
            # Search-related context
            elif "query" in tool_input or "consulta" in tool_input:
                query = tool_input.get("query") or tool_input.get("consulta")
                query_preview = str(query)[:30]
                context = f": '{query_preview}...'" if len(str(query)) > 30 else f": '{query}'"
            # URL-related context
            elif "url" in tool_input:
                context = f" em {tool_input['url']}"
            # File-related context
            elif "file" in tool_input or "arquivo" in tool_input:
                file_name = tool_input.get("file") or tool_input.get("arquivo")
                context = f": {file_name}"
            # Email-related context
            elif "to" in tool_input or "para" in tool_input:
                recipient = tool_input.get("to") or tool_input.get("para")
                context = f" para {recipient}"
            # Calculation context
            elif "expression" in tool_input or "expressao" in tool_input:
                expr = tool_input.get("expression") or tool_input.get("expressao")
                expr_preview = str(expr)[:20]
                context = f": {expr_preview}..." if len(str(expr)) > 20 else f": {expr}"
            # Generic context for any other input
            elif len(tool_input) > 0:
                # Get first meaningful value
                for key, value in tool_input.items():
                    if value and str(value).strip():
                        value_preview = str(value)[:25]
                        context = f": {value_preview}..." if len(str(value)) > 25 else f": {value}"
                        break

        return f"{tool_info['icon']} {tool_info['action'].capitalize()} {tool_info['name']}{context}..."

    elif stage == "error":
        return f"❌ Erro ao executar {tool_info['name']}"

    else:
        return f"🔧 Processando {tool_info['name']}..."
