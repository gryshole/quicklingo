from quicklingo.providers.openai_compat import OpenAICompatProvider


class GroqProvider(OpenAICompatProvider):
    def __init__(self) -> None:
        super().__init__("groq", "https://api.groq.com/openai/v1")
