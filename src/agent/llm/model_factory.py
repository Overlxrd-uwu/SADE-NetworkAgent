import os

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

load_dotenv()


def load_model(llm_backend: str = "openai", model: str = "gpt-5-mini") -> BaseChatModel:
    if llm_backend == "ollama":
        return ChatOllama(
            model=model,
            temperature=0,
            validate_model_on_init=True,
            base_url=os.getenv("OLLAMA_API_URL"),
        )

    if llm_backend == "openai":
        return ChatOpenAI(
            model_name=model,
        )

    if llm_backend == "deepseek":
        return ChatDeepSeek(
            model=model,
            base_url="https://api.deepseek.com",
        )

    raise ValueError(f"Unsupported llm backend: {llm_backend}")
