import os
from typing import Any

from mistralai import Mistral

# Initialize the client
api_key = "ZG1KyJW1XXLnHFNfUorFAnJscX2AugWC"  #os.environ.get("MISTRAL_API_KEY")
client = Mistral(api_key)

inputs: list[dict[str, Any]] = [
  {
    "role": "user",
    "content": "https://elpais.com/internacional/2025-11-07/el-cierre-del-gobierno-de-ee-uu-lastra-desde-el-viernes-el-trafico-de-los-principales-aeropuertos-del-pais.html",
  }
]

try:
    # Make the API call
    response = client.beta.conversations.start(
        inputs=inputs,  # type: ignore
        agent_id="ag_019a5a4b29c070488d4d6d56c6f4f435",
    )
    
    # Acceder a los atributos dinámicamente para evitar errores de tipo
    response_dict = response.__dict__ if hasattr(response, '__dict__') else {}
    print(response_dict)
    
    # Si sabes la estructura exacta, puedes acceder así:
    # print(response.conversation_id)  # o similar
except Exception as e:
    print(f"Error: {str(e)}")