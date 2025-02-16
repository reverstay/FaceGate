import os
import glob
import tempfile
import asyncio
from datetime import datetime, timezone

import face_recognition
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import paho.mqtt.client as mqtt  # Importa a biblioteca MQTT

# Carrega as variáveis do arquivo .env
load_dotenv()

# =============================
# Configurações do MQTT
# =============================
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "catraca/acesso"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Conectado ao MQTT Broker!")
    else:
        print(f"⚠️ Falha ao conectar, código de retorno: {rc}")

# Inicializa o cliente MQTT e conecta ao broker
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
print(f"🔌 Conectando ao broker MQTT: {MQTT_BROKER}")
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()  # Inicia o loop em thread separada

def enviar_comando(comando):
    mqtt_client.publish(MQTT_TOPIC, comando)
    print(f"📡 Enviado: {comando}")

# =============================
# Configurações do Supabase
# =============================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("As variáveis de ambiente SUPABASE_URL e SUPABASE_KEY precisam estar definidas no .env.")

from supabase import create_client, Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =============================
# Função Auxiliar para Acessar Erro de Forma Segura
# =============================
def safe_get_error(response):
    try:
        return response.error
    except AttributeError:
        return None

# =============================
# Carregamento de Faces Conhecidas
# =============================
# Dicionário para armazenar os encodings conhecidos: { usuario_id (int): encoding }
usuarios = {}

def load_usuarios():
    """
    Carrega as imagens da pasta 'usuarios' e computa o encoding de cada face.
    O nome do arquivo (sem extensão) deve estar no formato "Nome_documento.jpg", onde
    a parte após o underscore é o documento do usuário. Esse documento é usado para
    consultar a tabela "usuario" e obter o id real do usuário.
    """
    for file_path in glob.glob("usuarios/*.jpg"):
        basename = os.path.splitext(os.path.basename(file_path))[0]
        parts = basename.split('_')
        if len(parts) > 1:
            documento = parts[-1]  # Supomos que o documento está na última parte
        else:
            print(f"[WARNING] Nome de arquivo inválido: {basename}. Esperado 'Nome_documento'.")
            continue

        # Consulta a tabela "usuario" para obter o id baseado no documento
        response = supabase.table("usuario").select("id").eq("documento", documento).execute()
        if response.data and len(response.data) > 0:
            usuario_id = response.data[0]["id"]
        else:
            print(f"[WARNING] Usuário com documento {documento} não encontrado no banco de dados.")
            continue

        image = face_recognition.load_image_file(file_path)
        encodings = face_recognition.face_encodings(image)
        if encodings:
            usuarios[usuario_id] = encodings[0]
            print(f"[INFO] Face do usuário com id {usuario_id} (documento {documento}) carregada com sucesso.")
        else:
            print(f"[WARNING] Nenhuma face encontrada em {file_path}.")

# Carrega as faces conhecidas no início do servidor
load_usuarios()

# =============================
# Função Auxiliar para Download
# =============================
def download_file(bucket: str, filename: str) -> bytes:
    """
    Faz o download de um arquivo do bucket do Supabase.
    Se o retorno for do tipo bytes, retorna-o diretamente.
    Caso contrário, tenta acessar o atributo de erro usando safe_get_error.
    """
    result = supabase.storage.from_(bucket).download(filename)
    if isinstance(result, bytes):
        return result
    err = safe_get_error(result)
    if err is not None:
        raise Exception(err.message)
    return result.data

# =============================
# Função Auxiliar para Obter o device_id
# =============================
def get_device_id(device_type: str) -> int:
    """
    Consulta a tabela "devices" para obter o id do dispositivo com base no tipo.
    device_type: "entrada" ou "saida".
    Retorna o id do dispositivo.
    """
    target_value = "1" if device_type == "entrada" else "2"
    response = supabase.table("devices").select("id").eq("device_type", target_value).execute()
    if not response.data or len(response.data) == 0:
        raise Exception(f"Nenhum dispositivo encontrado para o tipo {device_type}")
    device_id = response.data[0]["id"]
    print(f"[INFO] Dispositivo para '{device_type}' encontrado: {device_id}")
    return device_id

# =============================
# Função Auxiliar para Obter Detalhes do Usuário e Organização
# =============================
def get_user_and_org_details(user_id: int):
    """
    Dado o id do usuário, retorna (nome_usuario, org_name) consultando as tabelas:
      - usuario: para obter o nome e receptionist_id;
      - receptionist: para obter o director_id;
      - director: para obter o organization_id;
      - organization: para obter o nome da organização.
    Retorna uma tupla (nome_usuario, org_name) ou (nome_usuario, None) se não for possível obter a organização.
    """
    user_resp = supabase.table("usuario").select("nome, receptionist_id").eq("id", user_id).execute()
    if not user_resp.data or len(user_resp.data) == 0:
        return None, None
    user = user_resp.data[0]
    nome_usuario = user.get("nome", "N/A")
    receptionist_id = user.get("receptionist_id")
    if not receptionist_id:
        return nome_usuario, None
    rep_resp = supabase.table("receptionist").select("director_id").eq("id", receptionist_id).execute()
    if not rep_resp.data or len(rep_resp.data) == 0:
        return nome_usuario, None
    director_id = rep_resp.data[0].get("director_id")
    if not director_id:
        return nome_usuario, None
    dir_resp = supabase.table("director").select("organization_id").eq("id", director_id).execute()
    if not dir_resp.data or len(dir_resp.data) == 0:
        return nome_usuario, None
    organization_id = dir_resp.data[0].get("organization_id")
    if not organization_id:
        return nome_usuario, None
    org_resp = supabase.table("organization").select("name").eq("id", organization_id).execute()
    if not org_resp.data or len(org_resp.data) == 0:
        return nome_usuario, None
    org_name = org_resp.data[0].get("name")
    return nome_usuario, org_name

# =============================
# Modelo de Requisição para Identificação (Endpoint /identify/)
# =============================
class ImageRequest(BaseModel):
    """
    Modelo para requisição com o nome do arquivo armazenado no Supabase.
    Exemplo: {"filename": "fotos/entrada_1645123456789.jpg"}
    """
    filename: str

# =============================
# Criação do Servidor FastAPI
# =============================
app = FastAPI(
    title="Serviço de Sincronização e Identificação Facial",
    description="Sincroniza fotos do Supabase com a pasta local, identifica usuários e registra logs de visita.",
    version="1.0.0"
)

# --- Endpoint para identificação manual (para testes) ---
@app.post("/identify/")
async def identify_image(request: ImageRequest):
    try:
        image_bytes = download_file("imagens", request.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao baixar a imagem: {str(e)}")
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
            tmp_file.write(image_bytes)
            temp_filename = tmp_file.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar a imagem temporária: {str(e)}")
    try:
        image = face_recognition.load_image_file(temp_filename)
        os.remove(temp_filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao carregar a imagem para processamento: {str(e)}")
    unknown_encodings = face_recognition.face_encodings(image)
    if len(unknown_encodings) == 0:
        enviar_comando("NEGADO")
        raise HTTPException(status_code=404, detail="Nenhuma face encontrada na imagem.")
    unknown_encoding = unknown_encodings[0]
    best_match = None
    best_distance = float("inf")
    for user_id, known_encoding in usuarios.items():
        distance = face_recognition.face_distance([known_encoding], unknown_encoding)[0]
        if distance < best_distance:
            best_distance = distance
            best_match = user_id
    tolerance = 0.63
    if best_distance > tolerance:
        enviar_comando("NEGADO")
        return {"user_id": None, "distance": best_distance, "message": "Nenhuma face correspondente encontrada."}
    enviar_comando("LIBERAR")
    return {"user_id": best_match, "distance": best_distance}

# --- Endpoint para sincronização manual (para testes) ---
@app.get("/sync-files/")
async def sync_files():
    local_dir = "static/uploads"
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
    local_files = set(os.listdir(local_dir))
    try:
        remote_files = supabase.storage.from_("imagens").list()
        if not isinstance(remote_files, list):
            remote_files = remote_files.data
    except Exception as e:
        raise HTTPException(status_code=500, detail="Erro ao listar arquivos do Supabase: " + str(e))
    downloaded_files = []
    missing_files = []
    for remote_file in remote_files:
        remote_filename = remote_file.get("name")
        if remote_filename not in local_files:
            missing_files.append(remote_filename)
            try:
                file_bytes = download_file("imagens", remote_filename)
                local_path = os.path.join(local_dir, remote_filename)
                with open(local_path, "wb") as f:
                    f.write(file_bytes)
                downloaded_files.append(remote_filename)
            except Exception as e:
                print(f"Erro ao baixar {remote_filename}: {e}")
    return {
        "downloaded_files": downloaded_files,
        "already_present": list(local_files),
        "missing_files": missing_files,
        "message": "Sincronização concluída."
    }

# =============================
# Função de Sincronização, Identificação e Registro em Background
# =============================
async def background_sync_and_identify():
    local_dir = "static/uploads"
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
    while True:
        try:
            local_files = set(os.listdir(local_dir))
            remote_files = supabase.storage.from_("imagens").list()
            if not isinstance(remote_files, list):
                remote_files = remote_files.data
            new_files = []
            for remote_file in remote_files:
                remote_filename = remote_file.get("name")
                if remote_filename not in local_files:
                    new_files.append(remote_filename)
            for filename in new_files:
                try:
                    # Baixa o arquivo novo
                    file_bytes = download_file("imagens", filename)
                    local_path = os.path.join(local_dir, filename)
                    with open(local_path, "wb") as f:
                        f.write(file_bytes)
                    print(f"Arquivo {filename} baixado com sucesso.")
                    
                    # Processa a imagem para reconhecimento facial
                    image = face_recognition.load_image_file(local_path)
                    unknown_encodings = face_recognition.face_encodings(image)
                    if not unknown_encodings:
                        print(f"Nenhuma face encontrada em {filename}.")
                        enviar_comando("NEGADO")
                        continue
                    unknown_encoding = unknown_encodings[0]
                    best_match = None
                    best_distance = float("inf")
                    for user_id, known_encoding in usuarios.items():
                        distance = face_recognition.face_distance([known_encoding], unknown_encoding)[0]
                        if distance < best_distance:
                            best_distance = distance
                            best_match = user_id
                    tolerance = 0.63
                    if best_distance > tolerance:
                        print(f"Usuário não identificado para o arquivo {filename} (distância: {best_distance}).")
                        enviar_comando("NEGADO")
                        continue
                    
                    # Define o tipo de dispositivo com base no nome do arquivo
                    if filename.startswith("entrada_"):
                        device_type = "entrada"
                    elif filename.startswith("saida_"):
                        device_type = "saida"
                    else:
                        device_type = "entrada"
                    
                    try:
                        device_id = get_device_id(device_type)
                    except Exception as e:
                        print(f"Erro ao obter device_id para {device_type}: {e}")
                        continue
                    
                    now_iso = datetime.now(timezone.utc).isoformat()
                    
                    if device_type == "entrada":
                        # Registra o log de entrada na tabela visit_log
                        data_to_insert = {
                            "usuario_id": best_match,
                            "device_id": device_id,
                            "entry_time": now_iso,
                            "exit_time": None,
                            "ultima_foto": filename
                        }
                        response = supabase.table("visit_log").insert(data_to_insert).execute()
                        err = safe_get_error(response)
                        if err is not None:
                            print(f"Erro ao inserir log de entrada para o usuário {best_match}: {err.message}")
                        else:
                            print(f"Log de entrada inserido para o usuário {best_match} (arquivo: {filename}).")
                            nome_usuario, org_name = get_user_and_org_details(best_match)
                            print(f"Usuário reconhecido: {nome_usuario} - Organização: {org_name} - Entrou")
                            
                            # Atualiza o status do usuário na tabela 'usuario'
                            update_response = supabase.table("usuario").update(
                                {"entrou": True, "saiu": False}
                            ).eq("id", best_match).execute()
                            if safe_get_error(update_response):
                                print(f"Erro ao atualizar status de entrada do usuário {best_match}.")
                            else:
                                print(f"Status do usuário {best_match} atualizado: entrou=True, saiu=False.")
                            
                            enviar_comando("LIBERAR")
                    
                    else:  # device_type == "saida"
                        # Verifica se o usuário está marcado como tendo entrado na tabela 'usuario'
                        user_status_resp = supabase.table("usuario")\
                            .select("entrou")\
                            .eq("id", best_match)\
                            .execute()
                        if not user_status_resp.data or not user_status_resp.data[0].get("entrou", False):
                            print(f"Usuário {best_match} não está marcado como tendo entrado. Saída não permitida.")
                            enviar_comando("NEGADO")
                        else:
                            # Se o usuário está marcado como dentro, atualiza o status para saída
                            update_response = supabase.table("usuario").update(
                                {"entrou": False, "saiu": True}
                            ).eq("id", best_match).execute()
                            if safe_get_error(update_response):
                                print(f"Erro ao atualizar status de saída do usuário {best_match}.")
                                enviar_comando("NEGADO")
                            else:
                                print(f"Status do usuário {best_match} atualizado: entrou=False, saiu=True.")
                                nome_usuario, org_name = get_user_and_org_details(best_match)
                                print(f"Usuário reconhecido: {nome_usuario} - Organização: {org_name} - Saiu")
                                enviar_comando("LIBERAR")
                except Exception as e:
                    print(f"Erro ao processar o arquivo {filename}: {e}")
        except Exception as e:
            print(f"Erro no loop de sincronização: {e}")
        await asyncio.sleep(3)

# Registra a tarefa em background no startup do FastAPI
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_sync_and_identify())

# =============================
# Execução do Servidor
# =============================
# Para rodar este servidor, execute:
# uvicorn nome_do_arquivo:app --host 0.0.0.0 --port 8000 --reload
