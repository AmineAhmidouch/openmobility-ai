import os
import sys

import requests

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434",
)
OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "gemma4:26b",
)


def main() -> None:
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are OpenMobility AI, an assistant "
                            "for public transport data analysis."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Introduce yourself in one short sentence."
                        ),
                    },
                ],
                "stream": False,
            },
            timeout=300,
        )
        response.raise_for_status()

        print("Ollama connection successful.")
        print(f"Model: {OLLAMA_MODEL}")
        print(f"Response: {response.json()['message']['content']}")

    except requests.ConnectionError:
        print("ERROR: Ollama is not reachable at", OLLAMA_URL)
        sys.exit(1)

    except requests.Timeout:
        print("ERROR: The model took too long to respond.")
        print("Check available RAM/VRAM and Ollama's status.")
        sys.exit(1)

    except requests.HTTPError as exc:
        print(f"ERROR: Ollama returned HTTP {exc.response.status_code}.")
        print(exc.response.text)
        sys.exit(1)


if __name__ == "__main__":
    main()
