import os
import pytz
import time
import requests
import smtplib
from dotenv import load_dotenv
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from email.message import EmailMessage
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/calendar']
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_CONTRATUAL")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
EMAIL_DEST = os.getenv("EMAIL_DEST") or SMTP_USER

def enviar_lembrete_telegram(evento):
    nome = evento.get('summary', 'Reunião')
    inicio = evento['start']['dateTime']
    link = evento.get('htmlLink', '#')

    mensagem = (
        f"🔔 *Lembrete de Reunião*\n"
        f"Evento: {nome}\n"
        f"Início: {inicio}\n"
        f"🔗 [Ver no Google Calendar]({link})"
    )

    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensagem,
            "parse_mode": "Markdown"
        }
    )
    print("📲 Telegram:", response.status_code)

def enviar_lembrete_email(evento):
    try:
        nome = evento.get('summary', 'Reunião')
        inicio = evento['start']['dateTime']
        descricao = evento.get('description', '')
        link = evento.get('htmlLink', '#')

        msg = EmailMessage()
        msg['Subject'] = f'Lembrete: Reunião - {nome}'
        msg['From'] = SMTP_USER
        msg['To'] = EMAIL_DEST

        corpo = (
            f"🔔 Lembrete automático de reunião.\n\n"
            f"📌 Evento: {nome}\n"
            f"🕒 Início: {inicio}\n"
            f"📄 Detalhes: {descricao}\n"
            f"🔗 Ver no Google Calendar: {link}\n"
        )

        msg.set_content(corpo)

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)

        print("📧 E-mail de lembrete enviado.")
    except Exception as e:
        print("❌ Erro ao enviar e-mail:", str(e))

def buscar_e_enviar_lembretes():
    if not os.path.exists("token.json"):
        print("❌ token.json não encontrado.")
        return

    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    service = build('calendar', 'v3', credentials=creds)

    agora = datetime.now(pytz.timezone("America/Sao_Paulo"))
    depois = agora + timedelta(minutes=65)

    eventos = service.events().list(
        calendarId='primary',
        timeMin=agora.isoformat(),
        timeMax=depois.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute().get('items', [])

    for evento in eventos:
        inicio = evento['start'].get('dateTime')
        if not inicio:
            continue

        dt_evento = datetime.fromisoformat(inicio)
        delta = (dt_evento - agora).total_seconds()

        if 3540 <= delta <= 3660:  # entre 59 e 61 minutos
            enviar_lembrete_telegram(evento)
            enviar_lembrete_email(evento)

# Agendador para rodar a cada 15 minutos
scheduler = BackgroundScheduler()
scheduler.add_job(buscar_e_enviar_lembretes, 'interval', minutes=15)
scheduler.start()

print("⏰ Serviço de lembretes iniciado.")
try:
    while True:
        time.sleep(60)
except (KeyboardInterrupt, SystemExit):
    scheduler.shutdown()
