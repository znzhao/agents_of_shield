import os
import re
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='\033[94m%(asctime)s\033[0m - \033[92m%(name)s\033[0m - \033[93m%(levelname)s\033[0m - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

_PLACEHOLDER_KEY = "[Set your OpenAI API key here]"

def load_env(env_file: str = ".env") -> dict:
    """
    Load environment variables from a .env file.
    
    Args:
        env_file: Path to the .env file (default: ".env")
    
    Returns:
        Dictionary of loaded environment variables
    """
    load_dotenv(env_file)
    return dict(os.environ)


def is_openai_key_set(env_file: str = ".env") -> bool:
    """Return True if a real OpenAI API key has been configured."""
    load_dotenv(env_file, override=True)
    key = os.environ.get("OPENAI_API_KEY", "")
    return bool(key) and key != _PLACEHOLDER_KEY


def save_openai_api_key(key: str, env_file: str = ".env") -> None:
    """Persist *key* to the .env file and update the current process environment."""
    os.environ["OPENAI_API_KEY"] = key
    try:
        with open(env_file, "r", encoding="utf-8") as fh:
            content = fh.read()
        if re.search(r"^OPENAI_API_KEY=", content, re.MULTILINE):
            content = re.sub(r"^OPENAI_API_KEY=.*$", f"OPENAI_API_KEY={key}", content, flags=re.MULTILINE)
        else:
            content += f"\nOPENAI_API_KEY={key}\n"
        with open(env_file, "w", encoding="utf-8") as fh:
            fh.write(content)
        logger.info("OpenAI API key saved to %s", env_file)
    except Exception as exc:
        logger.warning("Could not write API key to %s: %s", env_file, exc)


if __name__ == "__main__":
    env_vars = load_env()
    print("Loaded environment variables")
    for key, value in env_vars.items():
        print(f"- {key}: {value}")