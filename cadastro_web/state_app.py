from graphviz import Digraph

# Cria o objeto Digraph para o statechart
dot = Digraph("Statechart_Flutter_App", comment="Statechart do App Flutter")

# Ajustes gerais para layout
dot.attr(
    rankdir="TB",        # Layout horizontal (Paisagem)
    size="A4", 
    splines="ortho",     # Conexões ortogonais (mais legível)
    nodesep="0.6",         # Espaçamento horizontal
    ranksep="0.6",       # Espaçamento vertical
    dpi="100",           # Resolução melhor
    fontname="Arial"
)

# ---------- Conexão: App Start → Login ----------
dot.edge("Inicializa", "DisplayLogin", label="Inicializa", fontsize="10", minlen="0.2")

# ========== Cluster: Login ==========
with dot.subgraph(name="cluster_login") as login:
    login.attr(label="Login", style="rounded,filled", color="lightyellow", fontsize="14")
    login.node("DisplayLogin", "Exibe \nFormularios de login", shape="box", fontsize="10")
    login.node("SignIn", "Usuário clica \n'Acessar'", shape="box", fontsize="10")
    login.node("Auth", "Chama AuthService.loginUser", shape="box", fontsize="10")
    login.node("LoginSuccess", "Login bem-sucedido", shape="box", fontsize="10")
    login.node("LoginFail", "Falha no Login\nExibe AlertDialog", shape="box", fontsize="10")

    # Conexões internas
    login.edge("DisplayLogin", "SignIn", label="Interação", fontsize="8")
    login.edge("SignIn", "Auth", label="Validação", fontsize="8")
    login.edge("Auth", "LoginSuccess", label="Válido", fontsize="8", color="green")
    login.edge("Auth", "LoginFail", label="Inválido", fontsize="8", color="red")


# ========== Cluster: Pagina Inicial ==========
with dot.subgraph(name="cluster_Pagina Inicial") as pi:
    pi.attr(label="Pagina Inicial", style="rounded,filled", color="lightgreen", fontsize="14")
    pi.node("DisplayPagina Inicial", "Exibe Pagina Inicial\n(seleção de dispositivo)", shape="box", fontsize="10")
    pi.node("SelectDevice", "Seleciona dispositivo\n(entrada/saída)", shape="box", fontsize="10")
    pi.node("AtualizarDevice", "Chama atualizarDevice()", shape="box", fontsize="10")
    pi.node("StartRecognition", "Navega para FaceDetectorView", shape="box", fontsize="10")

    # Conexões internas
    pi.edge("DisplayPagina Inicial", "SelectDevice", label="Interação", fontsize="8")
    pi.edge("SelectDevice", "AtualizarDevice", label="Atualiza", fontsize="8")
    pi.edge("AtualizarDevice", "StartRecognition", label="Reconhecimento", fontsize="8")

# ---------- Conexão: LoginSuccess → Pagina Inicial ----------
dot.edge("LoginSuccess", "DisplayPagina Inicial", label="Avança", fontsize="10", minlen="0.2", constraint="false")

# ========== Cluster: FaceDetectorView ==========
with dot.subgraph(name="cluster_faceDetector") as fd:
    fd.attr(label="FaceDetectorView", style="rounded,filled", color="lightblue", fontsize="14")
    fd.node("InitCamera", "Inicializa câmera", shape="box", fontsize="10")
    fd.node("DisplayFeed", "Exibe feed", shape="box", fontsize="10")
    fd.node("DetectFace", "Detecta face\n(Google MLKit)", shape="box", fontsize="10")
    fd.node("CapturePhoto", "Captura foto", shape="box", fontsize="10")
    fd.node("UploadPhoto", "Envia foto\n(Supabase Storage)", shape="box", fontsize="10")
    fd.node("ShowResult", "Exibe resultado", shape="box", fontsize="10")

    # Conexões internas
    fd.edge("InitCamera", "DisplayFeed", label="Feed ativo", fontsize="8")
    fd.edge("DisplayFeed", "DetectFace", label="Processa frame", fontsize="8")
    fd.edge("DetectFace", "CapturePhoto", label="Face detectada", fontsize="8", color="green")
    fd.edge("CapturePhoto", "UploadPhoto", label="Foto salva", fontsize="8")
    fd.edge("UploadPhoto", "ShowResult", label="Mostra resultado", fontsize="8")

# ---------- Conexão: Pagina Inicial → FaceDetectorView ----------
dot.edge("StartRecognition", "InitCamera", label="Inicia reconhecimento", fontsize="10", minlen="0.2", constraint="false")

# Renderiza e salva o diagrama em um arquivo PDF
dot.render("statechart_flutter_app", format="pdf", view=True)
