import os
import re
from datetime import timedelta, datetime
import pytz
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import streamlit as st

# Carrega variáveis do .env
load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/calendar']
HORARIO_INICIO = 9
HORARIO_FIM = 18
DIAS_UTEIS = {0, 1, 2, 3, 4}

def parse_horario_manual(horario_preferencial: str):
    texto = horario_preferencial.lower().replace("às", "").replace("da manhã", "").replace("da tarde", "").strip()
    padrao = r"(\d{1,2}/\d{1,2}(?:/\d{4})?)\s+(\d{1,2})h"
    match = re.search(padrao, texto)
    if not match:
        raise ValueError(f"Formato inválido: {horario_preferencial}")
    data_str, hora_str = match.groups()
    if len(data_str.split("/")) == 2:
        data_str += f"/{datetime.now().year}"
    data_completa = f"{data_str} {hora_str}:00"
    dt = datetime.strptime(data_completa, "%d/%m/%Y %H:%M")
    return pytz.timezone("America/Sao_Paulo").localize(dt)

def horario_valido(data_inicio):
    return data_inicio.weekday() in DIAS_UTEIS and HORARIO_INICIO <= data_inicio.hour < HORARIO_FIM

def verificar_conflito(service, data_inicio, data_fim):
    eventos = service.events().list(
        calendarId='primary',
        timeMin=data_inicio.isoformat(),
        timeMax=data_fim.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute().get('items', [])
    return any(evento.get('status') != 'cancelled' for evento in eventos)

def sugerir_proximo_horario(service, inicio_busca=None):
    if inicio_busca is None:
        inicio_busca = datetime.now(pytz.timezone("America/Sao_Paulo")) + timedelta(minutes=30)
    inicio_busca = inicio_busca.replace(minute=0, second=0, microsecond=0)

    for dias in range(0, 15):
        data_base = inicio_busca + timedelta(days=dias)
        if data_base.weekday() not in DIAS_UTEIS:
            continue
        for hora in range(HORARIO_INICIO, HORARIO_FIM):
            inicio = data_base.replace(hour=hora)
            fim = inicio + timedelta(hours=1)
            if not verificar_conflito(service, inicio, fim):
                return inicio.strftime('%d/%m/%Y às %Hh')
    return None

def criar_evento_google_calendar(nome_cliente, horario_preferencial, detalhes, telefone):
    email_destinatario = os.getenv("SMTP_USER")
    if not email_destinatario:
        return "Erro", "#"

    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)

    if any(x in horario_preferencial.lower() for x in ["urgência", "urgente", "imediato", "agora", "o quanto antes"]):
        return "URGENTE", "#"

    try:
        data_inicio = parse_horario_manual(horario_preferencial)
    except Exception as e:
        return f"Erro de interpretação: {str(e)}", "#"

    if not horario_valido(data_inicio):
        sugestao = sugerir_proximo_horario(service, data_inicio)
        if sugestao:
            return "SUGESTAO", sugestao
        return "Fora do horário", "#"

    data_fim = data_inicio + timedelta(hours=1)

    if verificar_conflito(service, data_inicio, data_fim):
        sugestao = sugerir_proximo_horario(service, data_inicio)
        if sugestao:
            return "SUGESTAO", sugestao
        return "Conflito", "#"

    evento = {
        'summary': f'Atendimento Jurídico - {nome_cliente} ({telefone})',
        'description': f"{detalhes}\n\nTelefone: {telefone}",
        'start': {
            'dateTime': data_inicio.isoformat(),
            'timeZone': 'America/Sao_Paulo',
        },
        'end': {
            'dateTime': data_fim.isoformat(),
            'timeZone': 'America/Sao_Paulo',
        },
        'attendees': [{'email': email_destinatario}]
    }

    try:
        evento_criado = service.events().insert(calendarId='primary', body=evento).execute()
        return data_inicio.strftime('%d/%m/%Y %H:%M'), evento_criado.get('htmlLink')
    except Exception as e:
        return f"Erro ao criar evento: {str(e)}", "#"
