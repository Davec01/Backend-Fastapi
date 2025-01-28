
import logging
from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove, Update,
                      InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton)
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, ConversationHandler, MessageHandler, filters)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
from telegram import WebAppInfo
import pytz
import os
import re
import requests
import json
import asyncio


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Definición de estados de la conversación
(CAR_TYPE, CAR_COLOR, CAR_MILEAGE_DECISION, CAR_MILEAGE, PHOTO, LOCATION, SUMMARY, 
 ADMIN_MENU, ADMIN_SELECT, ADMIN_USERNAME, ADMIN_PASSWORD, ASK_ENDPOINT, ASK_QUESTION, NAME, ID, LOCATION) = range(16)



CHAT_ID_FILE_PATH = r"C:\Tools\X\chats_id.txt"
user_chat_ids = set()
user_locations = {}

# Credenciales del administrador
ADMIN_USER = "Admin"
ADMIN_PASS = "123"
TIMEOUT_SECONDS = 120


# Funciones auxiliares
def leer_chat_id():
    """Leer chat IDs del archivo."""
    if os.path.exists(CHAT_ID_FILE_PATH):
        with open(CHAT_ID_FILE_PATH, "r") as file:
            for line in file:
                user_chat_ids.add(int(line.strip()))

def save_chat_ids():
    """Guardar chat IDs en el archivo."""
    with open(CHAT_ID_FILE_PATH, "w") as file:
        for chat_id in user_chat_ids:
            file.write(f"{chat_id}\n")

# Funciones de la conversación
async def start_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra el menú de inicio."""
    reply_keyboard = [['Formulario', 'Pregunta', 'Administrador', 'Compartir ubicación']]
    await update.message.reply_text(
        '<b>Seleccione una opción:</b>',
        parse_mode='HTML',
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return ADMIN_MENU


async def request_live_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Inicia el flujo de solicitud de datos antes de pedir la ubicación.
    """
    await update.message.reply_text("Por favor, dime tu nombre completo:")
    return NAME



async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Pregunta el nombre del usuario.
    """
    await update.message.reply_text("Por favor, dime tu nombre completo:")
    return NAME

async def ask_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Guarda el nombre y pregunta la cédula.
    """
    chat_id = update.effective_chat.id
    context.user_data[chat_id] = {"name": update.message.text}  # Almacena el nombre
    await update.message.reply_text("Gracias. Ahora, por favor, dime tu cédula:")
    return ID

async def ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Guarda la cédula y pide la ubicación.
    """
    chat_id = update.effective_chat.id
    context.user_data[chat_id]["id"] = update.message.text  # Almacena la cédula

    location_button = KeyboardButton("Compartir mi ubicación 📍", request_location=True)
    reply_markup = ReplyKeyboardMarkup([[location_button]], resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "Gracias. Ahora comparte tu ubicación en tiempo real:",
        reply_markup=reply_markup
    )
    return LOCATION

async def handle_live_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Maneja la ubicación compartida por el usuario y programa el envío periódico.
    """
    chat_id = update.effective_chat.id
    user_location = update.message.location

    # Guardar la ubicación actual del usuario
    user_locations[chat_id] = user_location

    # JSON a enviar al backend
    user_data = context.user_data[chat_id]
    data = {
        "name": user_data["name"],
        "id": user_data["id"],
        "latitude": user_location.latitude,
        "longitude": user_location.longitude,
    }

    # Programar el envío periódico de ubicación
    job_name = f"send_location_{chat_id}"
    if context.job_queue.get_jobs_by_name(job_name):
        # Eliminar cualquier job existente para evitar duplicados
        context.job_queue.get_jobs_by_name(job_name)[0].schedule_removal()

    context.job_queue.run_repeating(
        send_live_location,
        interval=60,  # Cada 60 segundos
        first=datetime.now() + timedelta(seconds=60),  # Empieza en 1 minuto
        name=job_name,
        data={"chat_id": chat_id, "data": data},
    )

    await update.message.reply_text("¡Gracias! los datos y tu ubicación se estarán enviando cada minuto")
    return ConversationHandler.END





async def timeout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Notifica al usuario que el formulario se cerró por inactividad."""
    await update.message.reply_text(
        "<b>El formulario se ha cerrado por inactividad.\nPor favor, vuelve a comenzar con /start</b>",
        parse_mode='HTML'
    )
    return ConversationHandler.END
    

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_chat_id = update.effective_chat.id
    user_chat_ids.add(user_chat_id)
    save_chat_ids()
    context.user_data[user_chat_id] = {}
    logger.info(f"User with chat ID {user_chat_id} started the bot.")

    # Definir botones con emojis
    buttons = [
        [InlineKeyboardButton('🚜 Cargador de Ruedas', callback_data='Orugas')],
        [InlineKeyboardButton('🚧 Cargador de Ruedas (pequeño)', callback_data='Ruedas')],
        [InlineKeyboardButton('🏗️ Largo Alcance', callback_data='Largo alcance')],
        [InlineKeyboardButton('🚜 Miniexcavadora', callback_data='Miniexcavadoras')],
    ]
    
    reply_markup = InlineKeyboardMarkup(buttons)

    await update.message.reply_text(
        '<b>Buenos días! Por favor compártenos esta información antes de iniciar tu jornada laboral.\n'
        'Dime el tipo de vehículo</b>\n\n'
        '👇 <i>Selecciona una opción del menú de abajo</i>',
        parse_mode='HTML',
        reply_markup=reply_markup
    )

    return CAR_TYPE


# Manejo de selección de vehículo
async def car_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    selected_vehicle = query.data
    chat_id = update.effective_chat.id
    context.user_data[chat_id]['car_type'] = selected_vehicle

    vehicle_names = {
        "Orugas": "🚜 Cargador de Ruedas",
        "Ruedas": "🚧 Cargador de Ruedas (pequeño)",
        "Largo alcance": "🏗️ Largo Alcance",
        "Miniexcavadoras": "🚜 Miniexcavadora"
    }

    await query.edit_message_text(
        text=f'<b>Seleccionaste: {vehicle_names[selected_vehicle]}.</b>\n'
             'Dime el nivel de combustible:',
        parse_mode='HTML'
    )

    # Teclado de selección de nivel de combustible
    keyboard = [
        [InlineKeyboardButton('Menos de 1/4', callback_data='Menos de 1/4')],
        [InlineKeyboardButton('1/4 a 1/2', callback_data='1/4 a 1/2')],
        [InlineKeyboardButton('Más de medio', callback_data='Mas de medio')],
        [InlineKeyboardButton('Completo', callback_data='Completo')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text(
        '<b>Por favor seleccione el nivel de combustible:</b>',
        parse_mode='HTML',
        reply_markup=reply_markup
    )

    return CAR_COLOR


WEB_APP_URL = "https://benevolent-dragon-5ef0e0.netlify.app/"

async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    web_app_url_with_chat_id = f"{WEB_APP_URL}?chat_id={chat_id}"  # Incluir el chat_id en la URL

    web_app_button = InlineKeyboardButton(
        "Haz tu pregunta aquí",
        web_app=WebAppInfo(url=web_app_url_with_chat_id)
    )

    reply_markup = InlineKeyboardMarkup([[web_app_button]])

    await update.message.reply_text(
        "Presiona el botón para hacer tu pregunta desde la Web App:",
        reply_markup=reply_markup
    )
    return ConversationHandler.END


async def ask_endpoint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Almacena el endpoint seleccionado y solicita la pregunta."""
    selected_endpoint = update.message.text

    if selected_endpoint == 'Docs':
        context.user_data['endpoint'] = "https://35.223.72.198:8081/ask"
        context.user_data['query_type'] = "docs"
    elif selected_endpoint == 'Base de datos':
        context.user_data['endpoint'] = "https://35.223.72.198:8082/structure_data"
        context.user_data['query_type'] = "database"
    else:
        await update.message.reply_text(
            '<b>Opción inválida. Por favor seleccione nuevamente.</b>',
            parse_mode='HTML',  
        )
        return ASK_ENDPOINT

    await update.message.reply_text(
        '<b>Por favor, ingrese su pregunta:</b>',
        parse_mode='HTML'
    )
    return ASK_QUESTION


async def process_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Procesa la pregunta del usuario y hace una petición al endpoint seleccionado."""
    pregunta = update.message.text
    endpoint = context.user_data.get('endpoint')
    query_type = context.user_data.get('query_type')


    if query_type == "docs":
        data = {"query": pregunta}
    elif query_type == "database":
        data = {"question": pregunta, "index_name": "pae_2024_2"}

    loading_message = await update.message.reply_text("⠋ Esperando respuesta...")

    spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    is_spinner_running = True

    async def spinner():
        while is_spinner_running:
            for frame in spinner_frames:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=loading_message.message_id,
                    text=f"{frame} Esperando respuesta..."
                )
                await asyncio.sleep(0.3)

    spinner_task = asyncio.create_task(spinner())

    try:
  
        response = requests.post(endpoint, json=data)
        logger.info(f"Respuesta completa de la API: {response.text}")

        if query_type == "docs":

            respuesta_completa = ""
            for line in response.text.splitlines():
                try:
                    chunk_data = json.loads(line)
                    respuesta_completa += chunk_data.get("result", {}).get("chunk", "")
                except json.JSONDecodeError:
                    logger.warning("Un chunk no es JSON válido, se ignorará.")

            if not respuesta_completa:
                respuesta_completa = "No se pudo obtener una respuesta válida."

        elif query_type == "database":
  
            json_response = response.json()
            respuesta_completa = json_response.get("natural_language_response", "No se encontró respuesta en el JSON.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error al realizar la petición a la API: {e}")
        respuesta_completa = "Hubo un problema al conectarse con la API. Por favor, inténtelo más tarde."

    is_spinner_running = False
    await spinner_task


    if len(respuesta_completa) > 4096:
        respuesta_completa = f"{respuesta_completa[:4093]}..."

    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=loading_message.message_id,
        text=f"<b>Respuesta:</b>\n{respuesta_completa}",
        parse_mode='HTML'
    )

    return ConversationHandler.END


async def car_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    chat_id = update.effective_chat.id
    context.user_data[chat_id]['car_type'] = update.message.text
    cars = {"Orugas": "🚗", "Ruedas": "🚙", "Largo alcance": "🏎️", "Miniexcavadoras": "⚡"}
    logger.info('Car type of %s: %s', user.first_name, update.message.text)

    try:
        await asyncio.wait_for(
            update.message.reply_text(
                f'<b>Seleccionaste: {update.message.text}, vehículo: {cars[update.message.text]}.\n'
                f'Dime el nivel de combustible</b>',
                parse_mode='HTML',
                reply_markup=ReplyKeyboardRemove(),
            ),
            timeout=TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        return await timeout_handler(update, context)

    keyboard = [
        [InlineKeyboardButton('Menos de 1/4', callback_data='Menos de 1/4')],
        [InlineKeyboardButton('1/4 a 1/5', callback_data='1/4 a 1/5')],
        [InlineKeyboardButton('Mas de medio', callback_data='Mas de medio')],
        [InlineKeyboardButton('Completo', callback_data='Completo')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await asyncio.wait_for(
            update.message.reply_text('<b>Por favor seleccione:</b>', parse_mode='HTML', reply_markup=reply_markup),
            timeout=TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        return await timeout_handler(update, context)

    return CAR_COLOR

async def car_color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    context.user_data[chat_id]['car_color'] = query.data

    try:
        await asyncio.wait_for(
            query.edit_message_text(
                text=f'<b>Seleccionaste {query.data}.\nDanos por favor el kilometraje del vehículo</b>',
                parse_mode='HTML'
            ),
            timeout=TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        return await timeout_handler(update, context)

    keyboard = [
        [InlineKeyboardButton('Fill', callback_data='Fill')],
        [InlineKeyboardButton('Skip', callback_data='Skip')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await asyncio.wait_for(
            query.message.reply_text('<b>Elige una opción:</b>', parse_mode='HTML', reply_markup=reply_markup),
            timeout=TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        return await timeout_handler(update, context)

    return CAR_MILEAGE_DECISION

async def car_mileage_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Pregunta al usuario si desea ingresar el kilometraje o saltarse el paso."""
    query = update.callback_query
    await query.answer()
    decision = query.data

    if decision == 'Fill':
        await query.edit_message_text(text='<b>Ejemplo de kilometraje (e.g., 50000): (no coloques ni puntos ni comas"</b>', parse_mode='HTML')
        return CAR_MILEAGE
    else:
        await query.edit_message_text(text='<b>Kilometraje omitido.</b>', parse_mode='HTML')
        return await skip_mileage(update, context)

async def car_mileage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Almacena el kilometraje del vehículo después de validarlo y formatearlo correctamente."""
    chat_id = update.effective_chat.id
    mileage_text = update.message.text

    if not re.match(r'^\d+$', mileage_text):
        await update.message.reply_text(
            '<b>Por favor ingrese un número válido para el kilometraje (solo dígitos):</b>',
            parse_mode='HTML'
        )
        return CAR_MILEAGE 

    if len(mileage_text) > 3:
        mileage_text = f"{int(mileage_text):,}".replace(",", ".")

    context.user_data[chat_id]['car_mileage'] = mileage_text
    await update.message.reply_text('<b>Kilometraje registrado.\n'
                                    'Envía una foto del vehículo 📷, o presiona /skip.</b>',
                                    parse_mode='HTML')
    return PHOTO

async def skip_mileage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Omite la entrada de kilometraje."""
    chat_id = update.effective_chat.id
    context.user_data[chat_id]['car_mileage'] = 'No proporcionado'

    text = '<b>Envía una foto del vehículo 📷, o presiona /skip.</b>'

    if update.callback_query:
        chat_id = update.callback_query.message.chat_id
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML')
        await update.callback_query.answer()
    elif update.message:
        await update.message.reply_text(text)
    else:
        logger.warning('skip_mileage fue llamado sin un contexto de message o callback_query.')

    return PHOTO

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Almacena la foto del vehículo."""
    chat_id = update.effective_chat.id
    photo_file = await update.message.photo[-1].get_file()
    context.user_data[chat_id]['car_photo'] = photo_file.file_id

    await update.message.reply_text('<b>Foto cargada correctamente.\n'
                                    'Este es un resumen de tus datos.</b>',
                                    parse_mode='HTML')

    location_button = KeyboardButton(text="Enviar mi ubicación 📍", request_location=True)
    reply_keyboard = [[location_button]]
   
    await update.message.reply_text(
        '<b>Envia por favor tu ubicación!\n'
        '....</b>',
        parse_mode='HTML',
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return LOCATION

async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Omite la subida de la foto."""
    chat_id = update.effective_chat.id
    context.user_data[chat_id]['car_photo'] = 'No proporcionada'

    await update.message.reply_text('<b>Ninguna foto fue cargada.\n'
                                    'Por favor comparte tu ubicación</b>',
                                    parse_mode='HTML')

    location_button = KeyboardButton(text="Enviar mi ubicación 📍", request_location=True)
    reply_keyboard = [[location_button]]
   
    await update.message.reply_text(
        '<b>Envia por favor tu ubicación!\n'
        '....</b>',
        parse_mode='HTML',
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return LOCATION



async def location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Almacena la ubicación del usuario."""
    chat_id = update.effective_chat.id
    user_location = update.message.location
    context.user_data[chat_id]['location'] = user_location
    logger.info("Location of %s: %f / %f", update.message.from_user.first_name, user_location.latitude, user_location.longitude)

    await update.message.reply_text(
        '<b>Ubicación recibida correctamente.\nEste es un resumen de tus datos:</b>',
        parse_mode='HTML',
        reply_markup=ReplyKeyboardRemove()
    )

    await summary(update, context)
    return ConversationHandler.END 

async def skip_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Omite la entrada de ubicación."""
    chat_id = update.effective_chat.id
    context.user_data[chat_id]['location'] = 'No proporcionada'

    await update.message.reply_text('<b>Sin ubicación.\n'
                                    '...</b>',
                                    parse_mode='HTML')
    await summary(update, context)

async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Resume las selecciones del usuario y finaliza la conversación."""
    chat_id = update.effective_chat.id
    reply_markup = ReplyKeyboardRemove()
    selections = context.user_data[chat_id]
    summary_text = (f"<b>Estos son los datos que suministraste\n</b>"
                    f"<b>Tipo de vehículo:</b> {selections.get('car_type')}\n"
                    f"<b>Nivel de combustible:</b> {selections.get('car_color')}\n"
                    f"<b>Kilometraje:</b> {selections.get('car_mileage')}\n"
                    f"<b>Foto:</b> {'No cargada' if 'car_photo' in selections else 'No proporcionada'}\n"
                    f"<b>Ubicación:</b> {selections.get('location')}")

    if 'car_photo' in selections and selections['car_photo'] != 'No proporcionada':
        await context.bot.send_photo(chat_id=chat_id, photo=selections['car_photo'], caption=summary_text, parse_mode='HTML')
    else:
        await context.bot.send_message(chat_id=chat_id, text=summary_text, parse_mode='HTML')
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela y finaliza la conversación."""
    chat_id = update.effective_chat.id

    # Eliminar el job asociado al envío de ubicación
    job_name = f"send_location_{chat_id}"
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()

    await update.message.reply_text(
        'Adiós! Esperamos hablar contigo pronto.',
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END



async def administrador(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Solicita el nombre de usuario del administrador."""
    await update.message.reply_text('<b>Por favor, ingrese su nombre de usuario:</b>', parse_mode='HTML')
    return ADMIN_USERNAME

async def validar_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Valida el nombre de usuario."""
    username = update.message.text
    if (username == ADMIN_USER):
        await update.message.reply_text('<b>Nombre de usuario correcto. Ahora, ingrese su contraseña:</b>', parse_mode='HTML')
        return ADMIN_PASSWORD
    else:
        await update.message.reply_text('<b>Nombre de usuario incorrecto. Acceso denegado.</b>', parse_mode='HTML')
        return ConversationHandler.END

async def validar_contraseña(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Valida la contraseña."""
    password = update.message.text
    if password == ADMIN_PASS:
        await update.message.reply_text('<b>Acceso concedido.</b>', parse_mode='HTML')
        return await mostrar_chat_ids(update, context)
    else:
        await update.message.reply_text('<b>Contraseña incorrecta. Acceso denegado.</b>', parse_mode='HTML')
        return ConversationHandler.END

async def mostrar_chat_ids(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra la lista de chat IDs registrados."""
    chat_ids_list = list(user_chat_ids)

    if not chat_ids_list:
        await update.message.reply_text("No hay chat IDs registrados todavía.")
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(str(chat_id), callback_data=str(chat_id))] for chat_id in chat_ids_list]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "<b>Seleccione un chat ID para ver las respuestas:</b>",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    return ADMIN_SELECT

async def mostrar_respuestas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra las respuestas del chat ID seleccionado."""
    query = update.callback_query
    await query.answer()
    selected_chat_id = int(query.data)

    respuestas = context.user_data.get(selected_chat_id, None)

    if not respuestas:
        await query.edit_message_text(
            f"<b>No hay respuestas registradas para el chat ID {selected_chat_id}.</b>",
            parse_mode='HTML'
        )
        return ConversationHandler.END

    resumen = (
        f"<b>Respuestas del chat ID {selected_chat_id}:</b>\n"
        f"Tipo de vehículo: {respuestas.get('car_type', 'No proporcionado')}\n"
        f"Nivel de combustible: {respuestas.get('car_color', 'No proporcionado')}\n"
        f"Kilometraje: {respuestas.get('car_mileage', 'No proporcionado')}\n"
        f"Ubicación: {respuestas.get('location', 'No proporcionada')}\n"
    )

    await query.edit_message_text(
        resumen,
        parse_mode='HTML'
    )
    return ConversationHandler.END

# Función de recordatorio
async def recordatorio(context: ContextTypes.DEFAULT_TYPE):
    """Enviar un recordatorio a todos los usuarios para que rellenen el formulario."""
    leer_chat_id()
    for chat_id in user_chat_ids:
        await context.bot.send_message(chat_id=chat_id, text="¡Recordatorio! Por favor, llena el formulario.")
        
async def send_live_location(context: ContextTypes.DEFAULT_TYPE):
    """
    Envía la ubicación actual del usuario al backend periódicamente.
    """
    job_data = context.job.data
    chat_id = job_data.get("chat_id")
    data = job_data.get("data")
    
    # Obtener la ubicación actual del usuario
    user_location = user_locations.get(chat_id)
    if not user_location:
        logger.warning(f"No se encontró ubicación para el chat ID: {chat_id}")
        return

    # Actualizar los datos con la ubicación más reciente
    data.update({
        "latitude": user_location.latitude,
        "longitude": user_location.longitude,
    })

    # URL del backend
    backend_url = "https://35b0-181-205-228-202.ngrok-free.app/api/location"
    try:
        response = requests.post(backend_url, json=data, timeout=10)
        if response.status_code == 200:
            logger.info(f"Ubicación de {chat_id} enviada correctamente al backend.")
        else:
            logger.error(f"Error al enviar ubicación de {chat_id}: {response.status_code}, {response.text}")
    except requests.RequestException as e:
        logger.error(f"Error al conectar con el backend para {chat_id}: {e}")



# Función principal
def main() -> None:
    """Correr el bot."""
    leer_chat_id()
    application = Application.builder().token("8098373821:AAHPjdhdPtpuvyfWN_8tQJKRvcpHmzWVrbk").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_menu)],
        states={
            ADMIN_MENU: [
                MessageHandler(filters.Regex('^Formulario$'), start),
                MessageHandler(filters.Regex('^Pregunta$'), ask_question),
                MessageHandler(filters.Regex('^Administrador$'), administrador),
                MessageHandler(filters.Regex('^Compartir ubicación$'), request_live_location),  # Aquí inicia el flujo
            ],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_id)],  # Pide el nombre
            ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_location)],  # Pide la cédula
            LOCATION: [MessageHandler(filters.LOCATION, handle_live_location)],  # Recibe la ubicación
            ASK_ENDPOINT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_endpoint)],
            ASK_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_question)],
            ADMIN_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, validar_usuario)],
            ADMIN_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, validar_contraseña)],
            CAR_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, car_type)],
            CAR_COLOR: [CallbackQueryHandler(car_color)],
            CAR_TYPE: [CallbackQueryHandler(car_type_handler)],
            CAR_MILEAGE_DECISION: [CallbackQueryHandler(car_mileage_decision)],
            CAR_MILEAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, car_mileage)],
            PHOTO: [
                MessageHandler(filters.PHOTO, photo),
                CommandHandler('skip', skip_photo)
            ],
            SUMMARY: [MessageHandler(filters.ALL, summary)],
            ADMIN_SELECT: [CallbackQueryHandler(mostrar_respuestas)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )


    application.add_handler(conv_handler)
    scheduler = AsyncIOScheduler(timezone=pytz.timezone('America/Bogota'))
    scheduler.add_job(recordatorio, 'cron', hour=14, minute=2, args=[application])
    scheduler.start()

    application.run_polling()
    save_chat_ids()
    

if __name__ == '__main__':
    main()
