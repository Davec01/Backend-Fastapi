from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import json  # Importar json para procesar las líneas

app = FastAPI()

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AskRequest(BaseModel):
    query: str

@app.post("/api/ask")
async def ask(request: AskRequest):
    # Imprimir la pregunta recibida en el backend
    print(f"Pregunta recibida en el backend: {request.query}")

    if not request.query:
        raise HTTPException(status_code=400, detail="La pregunta es obligatoria.")

    try:
        # Consulta a la API externa
        response = requests.post(
            "http://35.223.72.198:8081/ask",
            json={"query": request.query},
            headers={"Content-Type": "application/json"}
        )
        print(f"Respuesta de la API externa (status {response.status_code}): {response.text}")

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Error en API externa: {response.status_code}"
            )

        # Procesar la respuesta línea por línea
        lines = response.text.split("\n")  # Dividir en líneas
        final_answer = ""
        for line in lines:
            try:
                if line.strip():  # Verificar que la línea no esté vacía
                    parsed = json.loads(line)  # Procesar la línea como JSON
                    final_answer += parsed.get("result", {}).get("chunk", "")
            except json.JSONDecodeError as e:
                print(f"Error al procesar línea: {e}: {line}")
            except Exception as e:
                print(f"Error inesperado al procesar línea: {e}: {line}")

        # Imprimir la respuesta final procesada
        print(f"Respuesta final enviada al frontend: {final_answer}")
        return {"answer": final_answer or "No se obtuvo respuesta."}

    except Exception as e:
        print(f"Error al consultar API externa: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor.")

