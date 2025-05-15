import os
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime
import requests
import openai

# Carrega variáveis de ambiente
print("✅ Iniciando app_pmp.py")
load_dotenv()

# Configurações da API OpenAI
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
EMAIL_DEST = os.getenv("EMAIL_DEST") or SMTP_USER
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_CONTRATUAL")
LINK_GOOGLE_CALENDAR = os.getenv("LINK_CALENDAR") or "https://calendar.google.com/calendar/u/0/selfsched?sstoken=XXXXXXXXXX"

# Configuração do escritório
ESCRITORIO = {
    "nome_display": "Pinheiro Machado & Pinto",
    "logo_url": "https://raw.githubusercontent.com/SOCR-470/assistente_juridico/main/logo_pmp.png",
    "titulo_sub": "Canal de Atendimento - Pinheiro Machado & Pinto"
}

SAUDACAO = (
    f"Olá, seja bem-vindo ao {ESCRITORIO['nome_display']}. Meu nome é Luana e irei cuidar de seu atendimento. "
    "Poderia, primeiramente, me informar seu *nome completo* e *telefone com DDD*, por gentileza?"
)

if "historico_chat" not in st.session_state:
    st.session_state.historico_chat = [
        {
            "role": "system",
            "content": f"""
Você é uma assistente virtual jurídico chamada Cris, do escritório {ESCRITORIO['nome_display']}.
Siga estas instruções:

1. Inicie com:
"{SAUDACAO}"

2. Se o nome completo ou telefone com DDD não forem fornecidos, reitere educadamente.

3. Após obter nome e telefone, repita o nome.

4. Se o objetivo da reunião estiver claro, pergunte o horário. Caso contrário, pergunte o assunto.

5. Pergunte se é cliente novo ou recorrente.

6. Ao final, envie o link do google calendar para o usuário agendar a reunião: {LINK_GOOGLE_CALENDAR}

7. Seja cordial, profissional e evite diagnósticos jurídicos.
"""
        }
    ]

# Interface Streamlit
st.set_page_config(
    page_title=f"{ESCRITORIO['nome_display']}",
    page_icon=ESCRITORIO['logo_url']
)

st.markdown(
    f"""
    <div style='text-align: center'>
        <img src='{ESCRITORIO['logo_url']}' width='260'/>
        <h4 style='margin-top: 0.5em; color: gray;'>{ESCRITORIO['titulo_sub']}</h4>
    </div>
    """,
    unsafe_allow_html=True
)

def enviar_conversa_telegram(historico):
    mensagem = "📋 *Resumo do atendimento realizado:*\n\n"
    for msg in historico:
        if msg["role"] == "user":
            mensagem += f"👤 *Cliente:* {msg['content']}\n"
        elif msg["role"] == "assistant":
            mensagem += f"🤖 *Assistente:* {msg['content']}\n"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, data=payload)
    print("📲 Enviado ao Telegram:", response.status_code)

# Exibe o histórico completo antes da entrada do usuário
for msg in st.session_state.historico_chat[1:]:
    if msg["role"] == "user":
        with st.chat_message("user", avatar="🧑‍💼"):
            st.write(msg["content"])
    elif msg["role"] == "assistant":
        with st.chat_message("assistant", avatar="🤖"):
            st.write(msg["content"])

# Campo de entrada SEMPRE após o histórico
entrada_usuario = st.chat_input("Digite aqui sua mensagem...")

if entrada_usuario:
    st.session_state.historico_chat.append({"role": "user", "content": entrada_usuario})
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Cris está digitando..."):
            resposta = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=st.session_state.historico_chat
            )
            conteudo = resposta.choices[0].message.content
            st.session_state.historico_chat.append({"role": "assistant", "content": conteudo})
            st.write(conteudo)

    mensagens = " ".join([m["content"] for m in st.session_state.historico_chat])
    if "http" not in mensagens and "telefone" in mensagens.lower() and any(x in mensagens.lower() for x in ["reunião", "atendimento", "consulta"]):
        with st.chat_message("assistant"):
            st.markdown(f"📅 Para agendar sua reunião, acesse o link abaixo conforme sua disponibilidade:\n\n👉 [Agendar reunião]({LINK_GOOGLE_CALENDAR})")
        enviar_conversa_telegram(st.session_state.historico_chat)
