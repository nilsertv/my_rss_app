"""
Módulo opcional/experimental para interacción con agente de Mistral AI.
"""
import os
import logging
from typing import Any, Optional

logger = logging.getLogger('AgentPostFacebook')


def post_to_mistral_agent(url: str, agent_id: str = "ag_019a5a4b29c070488d4d6d56c6f4f435") -> Optional[dict]:
    """Envía una URL al agente de Mistral para generar resumen/post."""
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        logger.warning("MISTRAL_API_KEY not configured. Skipping Mistral agent call.")
        return None

    try:
        from mistralai import Mistral
        client = Mistral(api_key=api_key)
        
        inputs: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": url,
            }
        ]

        response = client.beta.conversations.start(
            inputs=inputs,  # type: ignore
            agent_id=agent_id,
        )
        
        response_dict = response.__dict__ if hasattr(response, '__dict__') else {}
        return response_dict
    except Exception as e:
        logger.error(f"Error calling Mistral agent: {e}")
        return None


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    test_url = "https://elpais.com/internacional/2025-11-07/el-cierre-del-gobierno-de-ee-uu-lastra-desde-el-viernes-el-trafico-de-los-principales-aeropuertos-del-pais.html"
    result = post_to_mistral_agent(test_url)
    print("Result:", result)