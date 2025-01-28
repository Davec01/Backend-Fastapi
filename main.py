from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import requests
from datetime import datetime

# Configurar FastAPI
app = FastAPI()

# Configurar logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API_LOGS")

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cambiar en producción para dominios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Credenciales de Elasticsearch
ELASTICSEARCH_URL = "https://my-deployment-8b59f0.es.southamerica-east1.gcp.elastic-cloud.com"  # Reemplaza con tu URL
ELASTICSEARCH_API_KEY = "QThabHJwUUJhQ2hyUWhIR3VNRU46TGJVZFp5YXhTMm0xVFRtNV85LXNHUQ=="
ELASTICSEARCH_INDEX = "bot_veh"  # Nombre del índice en Elasticsearch

# Modelo de datos para ubicación
class LocationRequest(BaseModel):
    name: str
    id: str
    latitude: float
    longitude: float

# Crear índice en Elasticsearch (si no existe)
def create_index():
    try:
        url = f"{ELASTICSEARCH_URL}/{ELASTICSEARCH_INDEX}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"ApiKey {ELASTICSEARCH_API_KEY}",
        }

        # Verificar si el índice existe
        response = requests.head(url, headers=headers)
        if response.status_code == 200:
            logger.info(f"El índice '{ELASTICSEARCH_INDEX}' ya existe.")
            return

        # Crear índice con mapeo inicial
        index_mapping = {
            "mappings": {
                "properties": {
                    "name": {"type": "text"},
                    "id": {"type": "keyword"},
                    "latitude": {"type": "float"},
                    "longitude": {"type": "float"},
                    "location": {"type": "geo_point"},  # Definimos el campo como geo_point
                    "timestamp": {"type": "date", "format": "strict_date_optional_time||epoch_millis"}
                }
            }
        }

        response = requests.put(url, headers=headers, json=index_mapping)
        if response.status_code == 200:
            logger.info(f"Índice '{ELASTICSEARCH_INDEX}' creado exitosamente.")
        else:
            logger.error(f"Error al crear el índice '{ELASTICSEARCH_INDEX}': {response.text}")
    except Exception as e:
        logger.error(f"Error al verificar/crear el índice: {e}")

@app.on_event("startup")
def on_startup():
    # Crear el índice al iniciar la aplicación
    create_index()

@app.post("/api/location")
async def receive_location(location: LocationRequest):
    """
    Recibe el nombre, cédula y ubicación enviados por el bot, y los sube a Elasticsearch.
    """
    try:
        logger.info(f"Datos recibidos: {location.name}, {location.id}, {location.latitude}, {location.longitude}")

        # Crear documento para Elasticsearch
        document = {
            "name": location.name,
            "id": location.id,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "location": f"{location.latitude},{location.longitude}",  # Formato compatible con geo_point
            "timestamp": datetime.utcnow().isoformat()  # Marca de tiempo en formato ISO 8601
        }

        # Subir documento a Elasticsearch
        response = requests.post(
            f"{ELASTICSEARCH_URL}/{ELASTICSEARCH_INDEX}/_doc",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"ApiKey {ELASTICSEARCH_API_KEY}",
            },
            json=document,
        )

        # Verificar respuesta de Elasticsearch
        if response.status_code == 201:  # Código 201: creado exitosamente
            logger.info(f"Documento subido a Elasticsearch: {response.json()}")
            return {"status": "ok", "message": "Datos recibidos y almacenados en Elasticsearch."}
        else:
            logger.error(f"Error al subir documento a Elasticsearch: {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Error al guardar en Elasticsearch: {response.text}",
            )

    except Exception as e:
        logger.error(f"Error al procesar los datos: {e}")
        raise HTTPException(status_code=500, detail="Error al procesar los datos.")
