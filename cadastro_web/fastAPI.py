import os
import glob
import tempfile
import asyncio
from datetime import datetime, timezone
import numpy as np
import face_recognition
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
from PIL import Image, ImageOps

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

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
print(f"🔌 Conectando ao broker MQTT: {MQTT_BROKER}")
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

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
# Carregamento dos Encodings a partir do Banco de Dados
# =============================
# Dicionário para armazenar os encodings conhecidos: { usuario_id (int): encoding (np.array) }
usuarios = {}

def load_usuarios_from_db():
    """
    Carrega os encodings dos usuários a partir da coluna `face_encoding` da tabela `usuario`.
    Converte o encoding (armazenado como lista) para um array NumPy.
    """
    global usuarios
    usuarios = {}
    response = supabase.table("usuario").select("id, face_encoding, documento").execute()
    if response.data:
        for row in response.data:
            encoding_list = row.get("face_encoding")
            if encoding_list:
                arr = np.array(encoding_list)
                usuarios[row["id"]] = arr
                print(f"[INFO] Encoding do usuário id {row['id']} (doc: {row.get('documento')}) carregado com shape {arr.shape}.")
            else:
                print(f"[WARNING] Usuário id {row['id']} não possui face_encoding.")
    else:
        print("[WARNING] Nenhum usuário encontrado no banco de dados.")

# Carrega os encodings no início do servidor
load_usuarios_from_db()

# =============================
# Função Auxiliar para Download
# =============================
def download_file(bucket: str, filename: str) -> bytes:
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
    # Baixa a imagem do Supabase
    try:
        image_bytes = download_file("imagens", request.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao baixar a imagem: {str(e)}")
    
    # Salva a imagem temporariamente
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
            tmp_file.write(image_bytes)
            temp_filename = tmp_file.name
        print(f"Imagem salva temporariamente em: {temp_filename}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar a imagem temporária: {str(e)}")
    
    # Processa a imagem com PIL para corrigir orientação e converter para RGB
    try:
        pil_image = Image.open(temp_filename)
        print("Formato da imagem:", pil_image.format)
        print("Tamanho da imagem:", pil_image.size)
        pil_image = ImageOps.exif_transpose(pil_image)
        debug_filename = "debug_corrected_" + os.path.basename(temp_filename)
        pil_image.save(debug_filename)
        print("Imagem corrigida salva como:", debug_filename)
        image = np.array(pil_image.convert("RGB"))
        print("Imagem convertida para array com shape:", image.shape)
        os.remove(temp_filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar a imagem com PIL: {str(e)}")
    
    # Extrai o encoding da face usando modelo 'cnn'
    unknown_encodings = face_recognition.face_encodings(image, model='cnn')
    if len(unknown_encodings) == 0:
        enviar_comando("NEGADO")
        raise HTTPException(status_code=404, detail="Nenhuma face encontrada na imagem.")
    unknown_encoding = unknown_encodings[0]
    
    # Debug: imprimir dados do encoding
    print("Unknown encoding shape:", unknown_encoding.shape)
    print("Unknown encoding (primeiros 5):", unknown_encoding[:5])
    for user_id, known_encoding in usuarios.items():
        print(f"Usuário {user_id} known encoding shape: {known_encoding.shape}, primeiros 5: {known_encoding[:5]}")
    
    # Candidate Filtering: Colete candidatos com distância abaixo do tolerance
    tolerance = 0.63
    candidates = []
    for user_id, known_encoding in usuarios.items():
        distance = face_recognition.face_distance([known_encoding], unknown_encoding)[0]
        if distance < tolerance:
            candidates.append((user_id, distance))
    if not candidates:
        enviar_comando("NEGADO")
        return {"user_id": None, "distance": None, "message": "Nenhuma face correspondente encontrada."}
    
    # Extrai organização do nome do arquivo
    parts = request.filename.split('_')
    if len(parts) < 3:
        enviar_comando("NEGADO")
        return {"user_id": None, "distance": None, "message": "Formato do nome do arquivo inválido."}
    device_type = "entrada" if parts[0].lower() == "entrada" else ("saida" if parts[0].lower() == "saida" else "entrada")
    file_org = parts[1]
    
    # Filtra candidatos cuja organização confere
    filtered_candidates = []
    for user_id, distance in candidates:
        _, candidate_org = get_user_and_org_details(user_id)
        if candidate_org and candidate_org.lower() == file_org.lower():
            filtered_candidates.append((user_id, distance))
    if filtered_candidates:
        best_match, best_distance = min(filtered_candidates, key=lambda x: x[1])
    else:
        print(f"Nenhum candidato com organização {file_org} encontrado.")
        enviar_comando("NEGADO")
        best_distance = min(candidates, key=lambda x: x[1])[1]
        return {"user_id": None, "distance": best_distance, "message": "Organização não confere."}
    
    # Se for dispositivo de entrada, verifica se o usuário já entrou
    if device_type == "entrada":
        user_status_resp = supabase.table("usuario").select("entrou").eq("id", best_match).execute()
        if user_status_resp.data and user_status_resp.data[0].get("entrou", False):
            print(f"Usuário {best_match} já está marcado como tendo entrado. Entrada não permitida.")
            enviar_comando("NEGADO")
            return {"user_id": best_match, "distance": best_distance, "message": "Usuário já entrou."}
    
    enviar_comando("LIBERAR")
    return {"user_id": best_match, "distance": best_distance}

# --- Função de Sincronização, Identificação e Registro em Background ---
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
                    file_bytes = download_file("imagens", filename)
                    local_path = os.path.join(local_dir, filename)
                    with open(local_path, "wb") as f:
                        f.write(file_bytes)
                    print(f"Arquivo {filename} baixado com sucesso.")
                    
                    # Processa a imagem com PIL para corrigir orientação e converter para RGB
                    pil_image = Image.open(local_path)
                    pil_image = ImageOps.exif_transpose(pil_image)
                    image = np.array(pil_image.convert("RGB"))
                    print("Imagem convertida para array com shape:", image.shape)
                    
                    unknown_encodings = face_recognition.face_encodings(image, model='cnn')
                    if not unknown_encodings:
                        print(f"Nenhuma face encontrada em {filename}.")
                        enviar_comando("NEGADO")
                        continue
                    unknown_encoding = unknown_encodings[0]
                    
                    print("Unknown encoding shape:", unknown_encoding.shape)
                    print("Unknown encoding (primeiros 5):", unknown_encoding[:5])
                    for user_id, known_encoding in usuarios.items():
                        print(f"Usuário {user_id} known encoding shape: {known_encoding.shape}, primeiros 5: {known_encoding[:5]}")
                    
                    # Candidate Filtering
                    tolerance = 0.63
                    candidates = []
                    for user_id, known_encoding in usuarios.items():
                        distance = face_recognition.face_distance([known_encoding], unknown_encoding)[0]
                        if distance < tolerance:
                            candidates.append((user_id, distance))
                    if not candidates:
                        print(f"Usuário não identificado para o arquivo {filename} (distância acima do tolerance).")
                        enviar_comando("NEGADO")
                        continue
                    
                    # Extrai device_type e organização do nome do arquivo
                    parts = filename.split('_')
                    if len(parts) < 3:
                        print(f"Formato do nome do arquivo {filename} inválido para extração da organização.")
                        enviar_comando("NEGADO")
                        continue
                    device_type = "entrada" if parts[0].lower() == "entrada" else ("saida" if parts[0].lower() == "saida" else "entrada")
                    file_org = parts[1]
                    
                    # Filtra candidatos pela organização
                    filtered_candidates = []
                    for user_id, distance in candidates:
                        _, candidate_org = get_user_and_org_details(user_id)
                        if candidate_org and candidate_org.lower() == file_org.lower():
                            filtered_candidates.append((user_id, distance))
                    if filtered_candidates:
                        best_match, best_distance = min(filtered_candidates, key=lambda x: x[1])
                    else:
                        print(f"Nenhum candidato com organização {file_org} encontrado para o arquivo {filename}.")
                        enviar_comando("NEGADO")
                        best_distance = min(candidates, key=lambda x: x[1])[1]
                        continue
                    
                    now_iso = datetime.now(timezone.utc).isoformat()
                    
                    if device_type == "entrada":
                        user_status_resp = supabase.table("usuario").select("entrou").eq("id", best_match).execute()
                        if user_status_resp.data and user_status_resp.data[0].get("entrou", False):
                            print(f"Usuário {best_match} já está marcado como tendo entrado. Entrada não permitida.")
                            enviar_comando("NEGADO")
                            continue
                        
                        data_to_insert = {
                            "usuario_id": best_match,
                            "device_id": get_device_id(device_type),
                            "entry_time": now_iso,
                            "exit_time": None,
                            "ultima_foto": filename
                        }
                        response = supabase.table("visit_log").insert(data_to_insert).execute()
                        err = safe_get_error(response)
                        if err is not None:
                            print(f"Erro ao inserir log de entrada para o usuário {best_match}: {err.message}")
                        else:
                            nome_usuario, org_name = get_user_and_org_details(best_match)
                            print(f"Usuário reconhecido: {nome_usuario} - Organização: {org_name} - Entrou")
                            update_response = supabase.table("usuario").update(
                                {"entrou": True, "saiu": False}
                            ).eq("id", best_match).execute()
                            if safe_get_error(update_response):
                                print(f"Erro ao atualizar status de entrada do usuário {best_match}.")
                            else:
                                print(f"Status do usuário {best_match} atualizado: entrou=True, saiu=False.")
                            enviar_comando("LIBERAR")
                    
                    else:  # device_type == "saida"
                        user_status_resp = supabase.table("usuario").select("entrou").eq("id", best_match).execute()
                        if not user_status_resp.data or not user_status_resp.data[0].get("entrou", False):
                            print(f"Usuário {best_match} não está marcado como tendo entrado. Saída não permitida.")
                            enviar_comando("NEGADO")
                        else:
                            # Atualiza o registro de log com exit_time e registra o nome da imagem da saída
                            response = supabase.table("visit_log").update(
                                {"exit_time": now_iso, "ultima_foto": filename}
                            ).eq("usuario_id", best_match).is_("exit_time", None).execute()
                            if safe_get_error(response):
                                print(f"Erro ao atualizar log de saída para o usuário {best_match}.")
                                enviar_comando("NEGADO")
                            else:
                                update_response = supabase.table("usuario").update(
                                    {"entrou": False, "saiu": True}
                                ).eq("id", best_match).execute()
                                if safe_get_error(update_response):
                                    print(f"Erro ao atualizar status de saída do usuário {best_match}.")
                                    enviar_comando("NEGADO")
                                else:
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
    # Opcional: recarregar os encodings do DB periodicamente, se necessário
    # load_usuarios_from_db()
    asyncio.create_task(background_sync_and_identify())

# =============================
# Execução do Servidor
# =============================
# Para rodar este servidor, execute:
# uvicorn nome_do_arquivo:app --host 0.0.0.0 --port 8000 --reload
