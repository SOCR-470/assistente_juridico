import os
import re
import json
import requests
import smtplib
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
import openai
from email.message import EmailMessage
from google_agenda import criar_evento_google_calendar

# Carrega variáveis de ambiente
print("✅ Iniciando app5.py")
load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
EMAIL_DEST = os.getenv("EMAIL_DEST") or SMTP_USER

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_CONTRATUAL")



# Configuração dinâmica por escritório
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
Você é uma assistente virtual jurídico de atendimento ao público chamada Cris, do escritório {ESCRITORIO['nome_display']}.
Siga estas instruções com precisão:

1. Inicie sempre com:
"{SAUDACAO}"

2. Se o nome completo ou telefone com DDD não forem fornecidos inicialmente, prossiga com educação, mas **reitere educadamente o pedido** de nome e telefone na próxima oportunidade.

3. Depois de obter o nome e telefone, repita o nome do cliente e pergunte:
   - "Como posso lhe ajudar?"

4. Se o objetivo for agendamento de reunião e o assunto principal da reunião não foi informado, repita o nome do cliente e pergunte:
   - "Qual seria o assunto principal da reunião para que eu possa direcionar da melhor forma?"

5. Em seguida, pergunte:
   - "Qual dia e horário seriam mais convenientes para essa reunião?"

6. Depois, pergunte:
   - "Você já está sendo atendido por algum dos nossos advogados ou será seu primeiro contato com o escritório?"

7. Quando reunir todas as informações necessárias, responda:
"[ATENDIMENTO CONFIRMADO] Cliente: ... | Horário preferencial: ... | Detalhes: ..."

8. Seja cordial, mantenha linguagem profissional e não ofereça diagnósticos jurídicos.

9. Se faltar dados ou houver ambiguidade, solicite com clareza.
"""
        }
    ]


def enviar_telegram_agendamento_juridico(nome_cliente, detalhes_atendimento, horario_preferencial, telefone):
    mensagem = (
        f"\U0001F4DD *Novo atendimento agendado*\n"
        f"Cliente: {nome_cliente}\n"
        f"Telefone: {telefone}\n"
        f"Horário preferencial: {horario_preferencial}\n"
        f"Resumo: {detalhes_atendimento}"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    response = requests.post(url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown"
    })
    print("📲 Telegram:", response.status_code, response.text)
    return response.status_code == 200

def enviar_email_confirmacao(nome, horario, detalhes, link):
    try:
        msg = EmailMessage()
        msg['Subject'] = f'Confirmação de Atendimento Jurídico - {nome}'
        msg['From'] = SMTP_USER
        msg['To'] = EMAIL_DEST
        corpo = (
            f"Atendimento confirmado para {nome}.\n\n"
            f"📅 Horário: {horario}\n"
            f"📄 Assunto: {detalhes}\n"
            f"🔗 Ver no Google Calendar: {link}\n"
        )
        msg.set_content(corpo)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)
        print("✅ E-mail de confirmação enviado.")
    except Exception as e:
        print("❌ Falha ao enviar e-mail:", str(e))

def processar_resposta_gpt():
    response = openai.chat.completions.create(
        model="gpt-4-turbo",
        messages=st.session_state.historico_chat,
        temperature=0.7
    )
    return response.choices[0].message.content

def finalizar_agendamento(resposta):
    blocos = [b for b in resposta.split("[ATENDIMENTO CONFIRMADO]") if b.strip()]
    sucesso_geral = False

    # 🔍 Extração do telefone a partir do histórico
    telefone = "Não informado"
    for msg in st.session_state.historico_chat:
        if msg["role"] == "user":
            telefone_match = re.search(r'\(?\d{2}\)?\s?\d{4,5}-?\d{4}', msg["content"])
            if telefone_match:
                telefone = telefone_match.group(0)
                break

    for bloco in blocos:
        try:
            partes = bloco.strip().split("|")
            if len(partes) != 3:
                continue

            nome = partes[0].split(":")[1].strip()
            horario = partes[1].split(":")[1].strip()
            detalhes = partes[2].split(":")[1].strip()

            if any(x in horario.lower() for x in ["urgência", "urgente", "agora", "imediato", "o quanto antes"]):
                enviar_telegram_agendamento_juridico(nome, detalhes, "URGENTE - contato imediato", telefone)
                st.warning("🔴 Atendimento marcado como urgente. A equipe será notificada.")
                return True

            data, link = criar_evento_google_calendar(nome, horario, detalhes, telefone)

            if data == "SUGESTAO":
                st.info(f"📌 Horário indisponível. Sugerido: {link}")
                data, link = criar_evento_google_calendar(nome, link, detalhes, telefone)

            elif "Erro" in data or link == "#":
                st.warning(f"❌ Não foi possível agendar: {data}")
                return False

            elif data == "URGENTE":
                st.warning("🔴 Atendimento marcado como urgente.")
                return True

            sucesso_telegram = enviar_telegram_agendamento_juridico(nome, detalhes, data, telefone)
            registrar_agendamento(nome, detalhes, data, sucesso_telegram)

            st.markdown(f"📅 **Evento confirmado para:** {data}")
            st.markdown(f"🔗 [Ver no Google Calendar]({link})")
            st.success("✅ Atendimento agendado com sucesso!")

            enviar_email_confirmacao(nome, data, detalhes, link)
            sucesso_geral = True

        except Exception as e:
            st.error(f"Erro ao processar agendamento: {str(e)}")

    return sucesso_geral

def registrar_agendamento(nome, detalhes, horario, sucesso):
    registro = {
        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "nome": nome,
        "detalhes": detalhes,
        "horario": horario,
        "status": "sucesso" if sucesso else "falha"
    }
    try:
        with open("agendamentos.json", "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except Exception as e:
        st.error(f"Erro ao salvar agendamento: {str(e)}")

# Interface visual com logo e subtítulo institucional
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

# Renderização do histórico com emojis mais atrativos
for msg in st.session_state.historico_chat[1:]:
    if msg["role"] == "user":
        with st.chat_message("user", avatar="🧑‍💼"):
            st.write(msg["content"])
    elif msg["role"] == "assistant":
        with st.chat_message("assistant", avatar="🤖"):
            st.write(msg["content"])

# Entrada e resposta com spinner ajustado
if prompt := st.chat_input("Como posso ajudá-lo juridicamente hoje?"):
    st.session_state.historico_chat.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💼"):
        st.write(prompt)

    with st.spinner("Digitando..."):
        resposta = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=st.session_state.historico_chat,
            temperature=0.7
        ).choices[0].message.content

        st.session_state.historico_chat.append({"role": "assistant", "content": resposta})
        with st.chat_message("assistant", avatar="🤖"):
            st.write(resposta)

    st.rerun()
