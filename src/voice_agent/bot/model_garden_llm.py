from pipecat.services.openai.llm import OpenAILLMService


class ModelGardenLLMService(OpenAILLMService):
    """LLM service for the model garden's OpenAI-compatible Chat Completions endpoint."""

    supports_developer_role = False
