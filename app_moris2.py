import os
import re
import streamlit as st
from dotenv import load_dotenv
import requests
import openai

# Configurações iniciais
print("✅ Iniciando app_pmp.py")
load_dotenv()

# Configuração da API OpenAI
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Áreas de atuação do escritório (campo configurável)
AREAS_ATUACAO = [
    "Direito Civil",
    "Direito Contratual",
    "Direito do Consumidor",
    "Responsabilidade Civil",
    "Assessoria Empresarial"
]

# Constantes e configurações
ESCRITORIO = {
    "nome_display": "Moris Advogados",
    "logo_url": "https://raw.githubusercontent.com/SOCR-470/assistente_juridico/main/assets/logo_moris.png",
    "titulo_sub": "Canal de Atendimento"
}

LINK_GOOGLE_CALENDAR = os.getenv("LINK_CALENDAR") or "https://calendar.google.com/calendar/u/0/selfsched?sstoken=XXXXXXXXXX"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Configuração da interface
st.set_page_config(
    page_title=ESCRITORIO["nome_display"],
    page_icon=ESCRITORIO["logo_url"]
)

def exibir_cabecalho():
    st.markdown(
        f"""
        <div style='text-align: center'>
            <img src='{ESCRITORIO["logo_url"]}' width='260'/>
            <h4 style='margin-top: 0.5em; color: gray;'>{ESCRITORIO["titulo_sub"]}</h4>
        </div>
        """,
        unsafe_allow_html=True
    )

def inicializar_estados():
    if "etapa" not in st.session_state:
        st.session_state.etapa = "coleta_dados"
        st.session_state.dados_cliente = {}
        st.session_state.agendamento_solicitado = False
        intencao_detectada = st.session_state.dados_cliente.get("intencao", "não identificada")

        st.session_state.historico_chat = [{
            "role": "system",
            "content": f"""
        Você é Luana, assistente virtual do escritório {ESCRITORIO["nome_display"]}. Siga ESTRITAMENTE ESTA SEQUÊNCIA:

        1. SAUDAÇÃO INICIAL:
        - Mensagem fixa: "Olá, seja bem-vindo ao {ESCRITORIO["nome_display"]}! Meu nome é Luana. Para iniciar, preciso de seu *nome completo* e *telefone com DDD*."

        2. VALIDAÇÃO DE DADOS (Temperatura 0):
        - Se faltar algum dado: "Para continuarmos, preciso do seu *nome completo* e *telefone com DDD*."
        - Com dados completos: "Obrigada, {{nome}}! Sobre qual assunto gostaria de conversar hoje?"

        3. DETECÇÃO DE INTENÇÃO (Temperatura 0.3):
        - Intenção identificada: {intencao_detectada}
        - Se reconhecer área específica: "Entendi, você precisa de ajuda com {intencao_detectada.lower()}."
        - Se intenção desconhecida: "{{nome}}, para direcionar melhor seu atendimento, poderia descrever brevemente sua situação?"

        4. ENCERRAMENTO (Temperatura 0.3:
        - Após contexto claro: "Gostaria de agendar uma consulta personalizada com nosso especialista?"
        - Se a resposta for afirmativa, enviar calendário + "Escolha o melhor horário 📅"
        - Não: "Estamos à disposição! Você pode nos contatar pelo WhatsApp (11) 98765-4321"

        REGRAS CRÍTICAS:
        ❗ Valide nome/telefone ANTES de qualquer pergunta
        ❗ Nunca sugira áreas não listadas
        ❗ Mantenha máx. 3 turnos de conversa
        ❗ Use {{nome}} 2-3 vezes para personalização
        ❗ Priorize detecção de urgência (ex: "acidente", "demissão", "bloqueio")
        """
                }]



def formatar_telefone(texto):
    match = re.search(r"(\d{2})\D*(\d{4,5})\D*(\d{4})", texto)
    if match:
        return f"({match.group(1)}) {match.group(2)}-{match.group(3)}"
    return None

def extrair_intencao(mensagem):
    prompt = f"""
    Com base nesta mensagem de um possível cliente: \"{mensagem}\", diga resumidamente (1 linha) qual é o provável tema jurídico ou intenção. 
    Responda com uma dessas categorias, se possível: {", ".join(AREAS_ATUACAO)}. 
    Caso não seja possível classificar, diga apenas: \"Não identificado\".
    """
    resposta = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return resposta.choices[0].message.content.strip()

def enviar_telegram(historico):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    mensagem = "📋 *Novo Atendimento*\n\n"
    for msg in historico:
        if msg["role"] == "user":
            mensagem += f"👤: {msg['content']}\n"
        elif msg["role"] == "assistant":
            mensagem += f"🤖: {msg['content']}\n"
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensagem,
            "parse_mode": "Markdown"
        }
    )

exibir_cabecalho()
inicializar_estados()

entrada_usuario = st.chat_input("Digite aqui sua mensagem...")

if entrada_usuario:
    st.session_state.historico_chat.append({"role": "user", "content": entrada_usuario})

    if "intencao" not in st.session_state.dados_cliente:
        st.session_state.dados_cliente["intencao"] = extrair_intencao(entrada_usuario)

    if st.session_state.etapa == "coleta_dados":
        # Verifica se já temos nome e telefone armazenados
        nome_atual = st.session_state.dados_cliente.get("nome")
        telefone_atual = st.session_state.dados_cliente.get("telefone")

        # Captura nome, se ainda não houver
        if not nome_atual:
            nome_match = re.search(r"[A-Za-zÀ-ÿ]{3,}(?:\s+[A-Za-zÀ-ÿ]{2,})+", entrada_usuario)
            if nome_match:
                st.session_state.dados_cliente["nome"] = nome_match.group(0).title()

        # Captura telefone, se ainda não houver
        if not telefone_atual:
            tel_formatado = formatar_telefone(entrada_usuario)
            if tel_formatado:
                st.session_state.dados_cliente["telefone"] = tel_formatado

        # Avança etapa se ambos estiverem preenchidos
        if (
            st.session_state.dados_cliente.get("nome") and
            st.session_state.dados_cliente.get("telefone")
        ):
            st.session_state.etapa = "assunto"


    with st.spinner("Luana está digitando..."):
        resposta = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=st.session_state.historico_chat,
            temperature=0.2
        )
        conteudo = resposta.choices[0].message.content

        if "agendar" in conteudo.lower() and not st.session_state.agendamento_solicitado:
            conteudo += f"\n\n📅 [Agendar reunião aqui]({LINK_GOOGLE_CALENDAR})"
            st.session_state.agendamento_solicitado = True

        st.session_state.historico_chat.append({"role": "assistant", "content": conteudo})

    if st.session_state.etapa == "assunto" and not st.session_state.agendamento_solicitado:
        enviar_telegram(st.session_state.historico_chat)

for msg in st.session_state.historico_chat[1:]:
    with st.chat_message("user" if msg["role"] == "user" else "assistant"):
        st.write(msg["content"])
        if msg["role"] == "assistant" and LINK_GOOGLE_CALENDAR in msg["content"]:
            st.markdown(f"<a href='{LINK_GOOGLE_CALENDAR}' target='_blank'>📅 Agendar diretamente</a>", unsafe_allow_html=True)
