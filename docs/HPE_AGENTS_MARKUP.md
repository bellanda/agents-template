# HPEAgents Markup System

Este documento descreve o sistema de marcações especiais do HPEAgents que permite criar interfaces visuais ricas no frontend através de mensagens estruturadas do backend.

## Visão Geral

O sistema funciona em duas partes:

1. **Backend (Python)**: Gera marcações especiais usando funções utilitárias
2. **Frontend (JavaScript)**: Processa as marcações e converte em componentes visuais

## Marcações Disponíveis

### 1. Progresso

```python
# Backend
from api.utils.tools import generate_progress_message
message = generate_progress_message(75.0, "Analisando documentos...")
# Resultado: [PROGRESS:75.0:Analisando documentos...]
```

**Frontend**: Renderiza uma barra de progresso com porcentagem e mensagem.

### 2. Início de Ferramenta

```python
# Backend
from api.utils.tools import generate_tool_start_message
message = generate_tool_start_message("web_search", {"query": "Python tutorial"})
# Resultado: [TOOL_START:busca_web:Pesquisando na internet: 'Python tutorial'...]
```

**Frontend**: Mostra card animado com ícone de ferramenta e spinner de carregamento.

### 3. Fim de Ferramenta

```python
# Backend
from api.utils.tools import generate_tool_end_message
message = generate_tool_end_message("web_search", success=True)
# Resultado: [TOOL_END:busca_web:Operação concluída com sucesso]
```

**Frontend**: Mostra card com ícone de sucesso e checkmark.

### 4. Status Geral

```python
# Backend
from api.utils.tools import generate_status_message
message = generate_status_message("processing", "Processando informações...")
# Resultado: [STATUS:processing:Processando informações...]
```

**Tipos de status**: `processing`, `completed`, `error`, `waiting`, `analyzing`

### 5. Pensamento do Agente

```python
# Backend
from api.utils.tools import generate_thinking_message
message = generate_thinking_message("Analisando a melhor abordagem...")
# Resultado: [THINKING:Analisando a melhor abordagem...]
```

**Frontend**: Renderiza em estilo itálico com ícone de pensamento.

### 6. Resultados

```python
# Backend
from api.utils.tools import generate_result_message
message = generate_result_message("success", "Operação concluída com sucesso")
# Resultado: [RESULT:success:Operação concluída com sucesso]
```

**Tipos de resultado**: `success`, `error`, `warning`, `info`

### 7. Destaques

```python
# Backend
from api.utils.tools import generate_highlight_message
message = generate_highlight_message("texto importante")
# Resultado: [HIGHLIGHT:texto importante]
```

### 8. Avisos

```python
# Backend
from api.utils.tools import generate_warning_message
message = generate_warning_message("Atenção: verificar configuração")
# Resultado: [WARNING:Atenção: verificar configuração]
```

### 9. Erros

```python
# Backend
from api.utils.tools import generate_error_message
message = generate_error_message("Erro ao conectar com o servidor")
# Resultado: [ERROR:Erro ao conectar com o servidor]
```

### 10. Código

```python
# Backend
from api.utils.tools import generate_code_message
message = generate_code_message("javascript", "console.log('hello')")
# Resultado: [CODE:javascript:console.log('hello')]
```

### 11. Passos

```python
# Backend
from api.utils.tools import generate_step_message
message = generate_step_message(1, "Conectando ao servidor")
# Resultado: [STEP:1:Conectando ao servidor]
```

## Como Usar no Backend

### 1. Importar as Funções

```python
from api.utils.tools import (
    generate_progress_message,
    generate_tool_start_message,
    generate_tool_end_message,
    generate_status_message,
    generate_thinking_message,
    generate_result_message,
    generate_step_message,
    generate_highlight_message,
    generate_warning_message,
    generate_error_message,
    generate_code_message
)
```

### 2. Usar no Streaming

```python
async def stream_response():
    # Início da operação
    start_msg = generate_tool_start_message("web_search", {"query": "Python"})
    yield f"data: {json.dumps({'content': start_msg})}\n\n"

    # Progresso
    progress_msg = generate_progress_message(50.0, "Processando resultados...")
    yield f"data: {json.dumps({'content': progress_msg})}\n\n"

    # Pensamento
    thinking_msg = generate_thinking_message("Analisando os melhores resultados...")
    yield f"data: {json.dumps({'content': thinking_msg})}\n\n"

    # Resultado final
    result_msg = generate_result_message("success", "Busca concluída com sucesso")
    yield f"data: {json.dumps({'content': result_msg})}\n\n"
```

### 3. Usar em Ferramentas

```python
def my_tool(query: str) -> str:
    # Início
    start_msg = generate_step_message(1, f"Iniciando busca para: {query}")
    print(start_msg)

    try:
        # Processamento
        result = do_search(query)

        # Sucesso
        success_msg = generate_result_message("success", "Busca concluída")
        print(success_msg)

        return result

    except Exception as e:
        # Erro
        error_msg = generate_error_message(f"Erro na busca: {str(e)}")
        print(error_msg)
        return f"Erro: {str(e)}"
```

## Processamento no Frontend

O frontend JavaScript automaticamente detecta e processa essas marcações, convertendo-as em componentes visuais usando Tailwind CSS e shadcn/ui.

### Exemplo de Processamento

```javascript
const processor = new HPEAgentsTextProcessor();
const processedText = processor.processText(rawText);
// As marcações são automaticamente convertidas em HTML estilizado
```

## Melhores Práticas

1. **Use marcações consistentemente** em todo o código
2. **Combine diferentes tipos** para criar experiências ricas
3. **Mantenha mensagens claras** e informativas
4. **Use passos numerados** para operações sequenciais
5. **Indique progresso** em operações longas
6. **Mostre pensamentos** para transparência do processo
7. **Destaque informações importantes** com highlights
8. **Trate erros** com mensagens claras

## Exemplo Completo

```python
async def complex_operation(query: str):
    # Início
    yield generate_status_message("processing", "Iniciando operação complexa...")

    # Passo 1
    yield generate_step_message(1, "Validando entrada...")
    yield generate_progress_message(20.0, "Validação em andamento...")

    # Passo 2
    yield generate_step_message(2, "Processando dados...")
    yield generate_thinking_message("Escolhendo a melhor estratégia...")
    yield generate_progress_message(60.0, "Processamento avançado...")

    # Passo 3
    yield generate_step_message(3, "Finalizando...")
    yield generate_progress_message(90.0, "Quase pronto...")

    # Resultado
    yield generate_result_message("success", "Operação concluída com sucesso!")
    yield generate_highlight_message("Resultado: dados processados com êxito")
```

Este sistema permite criar interfaces de usuário ricas e informativas sem modificar o frontend, apenas enviando as marcações corretas do backend.
