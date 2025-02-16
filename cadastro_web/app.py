import os
import base64
import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.utils import secure_filename
from supabase import create_client, Client
from dotenv import load_dotenv  # 📌 Carrega variáveis de ambiente do .env
import bcrypt
import face_recognition  # Biblioteca para reconhecimento facial

# ================================
# 🔧 Carregando Configuração do Supabase via .env
# ================================
load_dotenv()  # Carrega as variáveis do .env
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("⚠️ ERRO: SUPABASE_URL ou SUPABASE_KEY não encontrados no .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================================
# 🔧 Configuração do Flask
# ================================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'MinhaChaveSuperSecreta_123!@#'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ================================
# 🔐 Autenticação de Usuário
# ================================

def hash_password(password):
    salt = bcrypt.gensalt()  # Gera um salt aleatório
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')  # Retorna o hash como string

def check_password(password, hashed_password):
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

class User(UserMixin):
    def __init__(self, id, username, role, organization_name="IdentifierFlow"):
        self.id = id
        self.username = username
        self.role = role
        self.organization_name = organization_name

@login_manager.user_loader
def load_user(user_id):
    """
    Percorre as tabelas 'admin', 'director' e 'receptionist' para carregar o usuário e
    adicionar o nome da organização (ou "IdentifierFlow" para admin ou não autenticado).
    """
    for table in ["admin", "director", "receptionist"]:
        response = supabase.table(table).select("*").eq("id", user_id).execute()
        if response.data:
            user = response.data[0]
            org_name = "IdentifierFlow"  # Valor padrão para admin ou se não encontrado
            if table == "director":
                # Para diretor, busque a organização associada
                director_resp = supabase.table("director").select("organization_id").eq("id", user_id).execute().data
                if director_resp and "organization_id" in director_resp[0]:
                    organization_id = director_resp[0]["organization_id"]
                    org_resp = supabase.table("organization").select("name").eq("id", organization_id).execute().data
                    if org_resp and "name" in org_resp[0]:
                        org_name = org_resp[0]["name"]
            elif table == "receptionist":
                # Para recepcionista, busque o director_id e, a partir dele, o organization_id
                recep_resp = supabase.table("receptionist").select("director_id").eq("id", user_id).execute().data
                if recep_resp and "director_id" in recep_resp[0]:
                    director_id = recep_resp[0]["director_id"]
                    dir_resp = supabase.table("director").select("organization_id").eq("id", director_id).execute().data
                    if dir_resp and "organization_id" in dir_resp[0]:
                        organization_id = dir_resp[0]["organization_id"]
                        org_resp = supabase.table("organization").select("name").eq("id", organization_id).execute().data
                        if org_resp and "name" in org_resp[0]:
                            org_name = org_resp[0]["name"]
            # Cria e retorna o objeto do usuário com a informação da organização
            return User(user["id"], user["username"], table, organization_name=org_name)
    return None

# ================================
# 🔑 Rotas de Login e Logout
# ================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        # Percorre as tabelas para encontrar o usuário
        for table in ["admin", "director", "receptionist"]:
            response = supabase.table(table).select("*").eq("username", username).execute()
            if response.data:
                user_data = response.data[0]
                if "password_hash" in user_data and user_data["password_hash"]:
                    if check_password(password, user_data["password_hash"]):
                        user = User(user_data["id"], user_data["username"], table)
                        login_user(user)
                        flash("Login realizado com sucesso!", "success")
                        return redirect(url_for(f"{table}_dashboard"))
                    else:
                        flash("Senha incorreta.", "danger")
                else:
                    flash("Erro: Senha não configurada corretamente.", "danger")
                    print(f"⚠️ ERRO: Senha ausente para {username} na tabela {table}")
        flash("Usuário ou senha incorretos.", "danger")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logout realizado com sucesso!", "success")
    return redirect(url_for('login'))

# ================================
# Rotas para Admin
# ================================

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != "admin":
        flash("Acesso restrito.", "danger")
        return redirect(url_for('login'))

    # Buscar organizações
    organizations = supabase.table("organization").select("*").execute().data

    # Buscar diretores e incluir informações da organização
    directors_data = supabase.table("director").select("id, username, organization_id").execute().data

    # Buscar todas as organizações e criar um dicionário {id: nome}
    org_dict = {org["id"]: org["name"] for org in organizations}

    # Adicionar o nome da organização para cada diretor
    directors = []
    for director in directors_data:
        director["organization_name"] = org_dict.get(director["organization_id"], "N/A")
        directors.append(director)

    return render_template('admin_dashboard.html', organizations=organizations, directors=directors)

@app.route('/admin/add_organization', methods=['GET', 'POST'])
@login_required
def add_organization():
    if current_user.role != "admin":
        flash("Acesso negado.", "danger")
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        name = request.form.get("name")
        supabase.table("organization").insert({"name": name}).execute()
        flash("Organização adicionada com sucesso!", "success")
        return redirect(url_for('admin_dashboard'))
    return render_template('add_organization.html')

@app.route('/admin/add_director', methods=['GET', 'POST'])
@login_required
def add_director():
    if current_user.role != "admin":
        flash("Acesso negado.", "danger")
        return redirect(url_for('admin_dashboard'))
    # Recupera organizações para seleção
    org_response = supabase.table("organization").select("*").execute()
    organizations = org_response.data if org_response.data else []
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        organization_id = request.form.get("organization_id")
        # Verifica se o diretor já existe
        resp = supabase.table("director").select("*").eq("username", username).execute()
        if resp.data:
            flash("Diretor já existe.", "danger")
        else:
            hashed_password = hash_password(password)
            supabase.table("director").insert({
                "username": username,
                "password_hash": hashed_password,
                "organization_id": organization_id,
                "created_at": datetime.datetime.utcnow().isoformat()
            }).execute()
            flash("Diretor adicionado com sucesso!", "success")
            return redirect(url_for('admin_dashboard'))
    return render_template('add_director.html', organizations=organizations)

# ================================
# Rotas para Diretor
# ================================
@app.route('/director/dashboard')
@login_required
def director_dashboard():
    if current_user.role != "director":
        flash("Acesso restrito.", "danger")
        return redirect(url_for('login'))
    # Recupera recepcionistas vinculados ao diretor atual
    resp = supabase.table("receptionist").select("*").eq("director_id", current_user.id).execute()
    receptionists = resp.data if resp.data else []
    return render_template('director_dashboard.html', receptionists=receptionists)

@app.route('/director/add_receptionist', methods=['GET', 'POST'])
@login_required
def add_receptionist():
    if current_user.role != "director":
        flash("Acesso restrito.", "danger")
        return redirect(url_for('director_dashboard'))

    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")

        # Verifica se o recepcionista já existe
        resp = supabase.table("receptionist").select("*").eq("username", username).execute()
        if resp.data:
            flash("Recepcionista já existe.", "danger")
        else:
            hashed_password = hash_password(password)

            # Obter a organização do diretor
            director_resp = supabase.table("director").select("organization_id").eq("id", current_user.id).execute()
            if not director_resp.data:
                flash("Erro ao obter a organização do diretor.", "danger")
                return redirect(url_for('director_dashboard'))

            # Insere o recepcionista com base no director_id
            supabase.table("receptionist").insert({
                "username": username,
                "password_hash": hashed_password,
                "director_id": current_user.id,  # O recepcionista pertence a um diretor
                "created_at": datetime.datetime.utcnow().isoformat()
            }).execute()

            flash("Recepcionista adicionado com sucesso!", "success")
            return redirect(url_for('director_dashboard'))

    return render_template('add_receptionist.html')

@app.route('/director/edit_receptionist/<int:receptionist_id>', methods=['GET', 'POST'])
@login_required
def edit_receptionist(receptionist_id):
    if current_user.role != "director":
        flash("Acesso restrito.", "danger")
        return redirect(url_for('director_dashboard'))
    # Recupera o recepcionista e verifica se pertence ao diretor atual
    resp = supabase.table("receptionist").select("*").eq("id", receptionist_id).execute()
    if not resp.data:
        flash("Recepcionista não encontrado.", "danger")
        return redirect(url_for('director_dashboard'))
    receptionist = resp.data[0]
    if receptionist.get("director_id") != current_user.id:
        flash("Acesso negado.", "danger")
        return redirect(url_for('director_dashboard'))
    if request.method == 'POST':
        new_username = request.form.get("username")
        new_password = request.form.get("password")
        update_data = {"username": new_username}
        if new_password:
            update_data["password_hash"] = hash_password(new_password)
        supabase.table("receptionist").update(update_data).eq("id", receptionist_id).execute()
        flash("Recepcionista atualizado com sucesso!", "success")
        return redirect(url_for('director_dashboard'))
    return render_template('edit_receptionist.html', receptionist=receptionist)

@app.route('/director/delete_receptionist/<int:receptionist_id>')
@login_required
def delete_receptionist(receptionist_id):
    if current_user.role != "director":
        flash("Acesso negado.", "danger")
        return redirect(url_for('director_dashboard'))
    resp = supabase.table("receptionist").select("*").eq("id", receptionist_id).execute()
    if not resp.data:
        flash("Recepcionista não encontrado.", "danger")
    else:
        receptionist = resp.data[0]
        if receptionist.get("director_id") != current_user.id:
            flash("Acesso negado.", "danger")
            return redirect(url_for('director_dashboard'))
        supabase.table("receptionist").delete().eq("id", receptionist_id).execute()
        flash("Recepcionista deletado com sucesso!", "success")
    return redirect(url_for('director_dashboard'))

# ================================
# Rotas para Recepcionista
# ================================
@app.route('/receptionist/dashboard')
@login_required
def receptionist_dashboard():
    if current_user.role != "receptionist":
        flash("Acesso restrito.", "danger")
        return redirect(url_for('login'))

    # 🔹 1️⃣ Obtém o `director_id` do recepcionista logado
    resp = supabase.table("receptionist").select("director_id").eq("id", current_user.id).execute()
    if not resp.data or "director_id" not in resp.data[0]:
        flash("Erro ao obter o diretor associado ao recepcionista.", "danger")
        return redirect(url_for('login'))

    director_id = resp.data[0]["director_id"]

    # 🔹 2️⃣ Obtém o `organization_id` do diretor associado
    director_resp = supabase.table("director").select("organization_id").eq("id", director_id).execute()
    if not director_resp.data or "organization_id" not in director_resp.data[0]:
        flash("Erro ao obter a organização do diretor.", "danger")
        return redirect(url_for('login'))

    organization_id = director_resp.data[0]["organization_id"]

    # 🔹 3️⃣ Busca todos os recepcionistas da mesma organização
    receptionists_resp = supabase.table("receptionist").select("id").eq("director_id", director_id).execute()
    if not receptionists_resp.data:
        flash("Nenhum recepcionista encontrado para esta organização.", "warning")
        return redirect(url_for('login'))

    receptionist_ids = [r["id"] for r in receptionists_resp.data]  # Lista de IDs dos recepcionistas

    # 🔹 4️⃣ Busca todos os usuários cadastrados por qualquer recepcionista da organização
    usuarios = (
        supabase
        .table("usuario")
        .select("*")
        .in_("receptionist_id", receptionist_ids)  # Busca usuários com base nos recepcionistas da organização
        .order("created_at", desc=True)  # Exibir os mais recentes primeiro
        .execute()
        .data
    )

    return render_template('receptionist_dashboard.html', usuarios=usuarios)

@app.route('/usuarios/<filename>')
def usuario_file(filename):
    # Define o caminho absoluto para a pasta "usuarios"
    usuarios_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'usuarios')
    return send_from_directory(usuarios_folder, filename)

# #############################################################################
# Rota para cadastro de usuário com cálculo do encoding da face
# #############################################################################
@app.route('/receptionist/add_usuario', methods=['GET', 'POST'])
@login_required
def add_usuario():
    if current_user.role != "receptionist":
        flash("Acesso restrito.", "danger")
        return redirect(url_for('receptionist_dashboard'))
    if request.method == 'POST':
        nome = request.form.get("nome")
        documento = request.form.get("documento")
        foto_data = request.form.get("foto_data")
        foto_filename = None
        face_encoding = None  # Variável para armazenar o encoding da face

        if foto_data:
            try:
                # Se a foto estiver em base64 com header, separa o header
                if "," in foto_data:
                    header, encoded = foto_data.split(',', 1)
                else:
                    encoded = foto_data
                data = base64.b64decode(encoded)
                # Cria a pasta 'usuarios' se não existir
                usuarios_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'usuarios')
                os.makedirs(usuarios_folder, exist_ok=True)
                # Gera o nome da foto com o formato "nome_documento.jpg"
                foto_filename = secure_filename(f"{nome}_{documento}.jpg")
                foto_path = os.path.join(usuarios_folder, foto_filename)
                with open(foto_path, "wb") as f:
                    f.write(data)
                # Calcula o encoding da face a partir da imagem salva
                image = face_recognition.load_image_file(foto_path)
                encodings = face_recognition.face_encodings(image)
                if encodings:
                    # Converte o encoding para lista para ser armazenado (ex: JSONB)
                    face_encoding = encodings[0].tolist()
                else:
                    flash("Nenhuma face detectada na foto. Tente novamente.", "danger")
                    return redirect(url_for('add_usuario'))
            except Exception as e:
                flash(f"Erro ao processar a foto: {str(e)}", "danger")
                return redirect(url_for('add_usuario'))
        else:
            flash("A foto é obrigatória.", "danger")
            return redirect(url_for('add_usuario'))
        
        # Insere os dados do usuário no Supabase, incluindo o encoding da face
        supabase.table("usuario").insert({
            "nome": nome,
            "documento": documento,
            "foto": foto_filename,
            "face_encoding": face_encoding,  # Novo campo com o encoding
            "receptionist_id": current_user.id,
            "created_at": datetime.datetime.utcnow().isoformat()
        }).execute()
        flash("Usuário adicionado com sucesso!", "success")
        return redirect(url_for('receptionist_dashboard'))
    return render_template('add_usuario.html')

# #############################################################################
# Rota para edição de usuário (atualiza foto e recalcula encoding se necessário)
# #############################################################################
@app.route('/receptionist/edit_usuario/<int:usuario_id>', methods=['GET', 'POST'])
@login_required
def edit_usuario(usuario_id):
    if current_user.role != "receptionist":
        flash("Acesso restrito.", "danger")
        return redirect(url_for('login'))

    # 1️⃣ Obtém o `director_id` do recepcionista logado
    resp = supabase.table("receptionist").select("director_id").eq("id", current_user.id).execute()
    if not resp.data or "director_id" not in resp.data[0]:
        flash("Erro ao obter o diretor associado ao recepcionista.", "danger")
        return redirect(url_for('login'))

    director_id = resp.data[0]["director_id"]

    # 2️⃣ Obtém o `organization_id` do diretor associado
    director_resp = supabase.table("director").select("organization_id").eq("id", director_id).execute()
    if not director_resp.data or "organization_id" not in director_resp.data[0]:
        flash("Erro ao obter a organização do diretor.", "danger")
        return redirect(url_for('login'))

    organization_id = director_resp.data[0]["organization_id"]

    # 3️⃣ Busca todos os recepcionistas da mesma organização
    receptionists_resp = supabase.table("receptionist").select("id").eq("director_id", director_id).execute()
    if not receptionists_resp.data:
        flash("Nenhum recepcionista encontrado para esta organização.", "warning")
        return redirect(url_for('login'))

    receptionist_ids = [r["id"] for r in receptionists_resp.data]  # Lista de IDs dos recepcionistas

    # 4️⃣ Verifica se o usuário foi cadastrado por um recepcionista da mesma organização
    usuario_resp = supabase.table("usuario").select("*").eq("id", usuario_id).execute()
    if not usuario_resp.data:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for('receptionist_dashboard'))

    usuario = usuario_resp.data[0]

    if usuario.get("receptionist_id") not in receptionist_ids:
        flash("Acesso negado. Você não tem permissão para editar este usuário.", "danger")
        return redirect(url_for('receptionist_dashboard'))

    if request.method == 'POST':
        nome = request.form.get("nome")
        documento = request.form.get("documento")
        update_data = {
            "nome": nome,
            "documento": documento,
            "updated_at": datetime.datetime.utcnow().isoformat(),  # Atualiza timestamp
            "receptionist_id": current_user.id  # Define quem fez a última edição
        }

        # Se nova foto for enviada, atualiza foto e recalcula o encoding
        foto_data = request.form.get("foto_data")
        if foto_data:
            try:
                if "," in foto_data:
                    header, encoded = foto_data.split(',', 1)
                else:
                    encoded = foto_data
                data = base64.b64decode(encoded)
                usuarios_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'usuarios')
                os.makedirs(usuarios_folder, exist_ok=True)
                foto_filename = secure_filename(f"{nome}_{documento}.jpg")
                foto_path = os.path.join(usuarios_folder, foto_filename)
                with open(foto_path, "wb") as f:
                    f.write(data)
                update_data["foto"] = foto_filename

                # Calcula o novo encoding a partir da foto atualizada
                image = face_recognition.load_image_file(foto_path)
                encodings = face_recognition.face_encodings(image)
                if encodings:
                    update_data["face_encoding"] = encodings[0].tolist()
                else:
                    flash("Nenhuma face detectada na foto. Tente novamente.", "danger")
                    return redirect(url_for("edit_usuario", usuario_id=usuario_id))
            except Exception as e:
                flash(f"Erro ao atualizar a foto: {str(e)}", "danger")
                return redirect(url_for("edit_usuario", usuario_id=usuario_id))

        # Atualiza os dados no banco
        supabase.table("usuario").update(update_data).eq("id", usuario_id).execute()

        flash("Usuário atualizado com sucesso!", "success")
        return redirect(url_for('receptionist_dashboard'))

    return render_template('edit_usuario.html', usuario=usuario)

@app.route('/receptionist/delete_usuario/<int:usuario_id>')
@login_required
def delete_usuario(usuario_id):
    if current_user.role != "receptionist":
        flash("Acesso restrito.", "danger")
        return redirect(url_for('login'))
        
    resp = supabase.table("usuario").select("*").eq("id", usuario_id).execute()
    if not resp.data:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for('receptionist_dashboard'))
        
    usuario = resp.data[0]
    if usuario.get("receptionist_id") != current_user.id:
        flash("Acesso negado.", "danger")
        return redirect(url_for('receptionist_dashboard'))
    
    # Exclui os registros em visit_log que referenciam esse usuário
    supabase.table("visit_log").delete().eq("usuario_id", usuario_id).execute()
    
    # Agora, deleta o usuário
    supabase.table("usuario").delete().eq("id", usuario_id).execute()
    
    flash("Usuário deletado com sucesso!", "success")
    return redirect(url_for('receptionist_dashboard'))

# ================================
# Rota para servir arquivos enviados
# ================================
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ================================
# Execução da Aplicação
# ================================
if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    print("Upload folder set:", app.config['UPLOAD_FOLDER'])
    # Cria usuário Admin padrão se não existir
    admin_username = "admin"
    admin_password = "123"
    response = supabase.table("admin").select("*").eq("username", admin_username).execute()
    if not response.data or "password_hash" not in response.data[0] or not response.data[0]["password_hash"]:
        hashed_password = hash_password(admin_password)
        supabase.table("admin").upsert({
            "username": admin_username,
            "password_hash": hashed_password,
            "created_at": datetime.datetime.utcnow().isoformat()
        }).execute()
        print("✅ Administrador criado com sucesso.")
    app.run(debug=True, host='0.0.0.0')
