"""Contract of the system prompt composition: platform base vs tenant instructions.

Ported from kailos 2026-10-09 (`tests/agents/test_prompt_composition.py`): the tenant Markdown
comes wrapped by a header that declares it complementary to the base prompt, and the identity
rule is always the last block.
"""

from langchain_core.messages import SystemMessage

from api.core.agents.tenant_instructions import (
    DISCLOSURE_RULE,
    TENANT_SECTION_HEADER,
    compose_system_message,
)

BASE_PROMPT = "Você é o assistente da plataforma."
TENANT_MARKDOWN = "# Negócio Exemplo\nO assistente se chama Bia."


def test_tenant_markdown_comes_wrapped_by_the_precedence_header():
    text = compose_system_message(SystemMessage(content=BASE_PROMPT), TENANT_MARKDOWN).text

    assert text.index(BASE_PROMPT) < text.index(TENANT_SECTION_HEADER) < text.index(TENANT_MARKDOWN)
    assert text.endswith(DISCLOSURE_RULE)
    assert "complementa" in TENANT_SECTION_HEADER


def test_disclosure_rule_forbids_denying_being_an_ai():
    assert "NUNCA" in DISCLOSURE_RULE and "humano" in DISCLOSURE_RULE
