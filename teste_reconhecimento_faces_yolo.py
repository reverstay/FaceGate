import cv2
import numpy as np
from ultralytics import YOLO
from tensorflow.keras.applications import InceptionResNetV2
from tensorflow.keras.layers import GlobalAveragePooling2D
from tensorflow.keras.models import Model
import os
from sklearn.metrics.pairwise import cosine_similarity

# Carregar o modelo YOLOv8 para detecção de faces
model_yolo = YOLO('yolov8n.pt')  # Use 'yolov8_face.pt' se disponível

# Definir o modelo de embeddings faciais usando o InceptionResNetV2
def carregar_modelo_facial():
    base_model = InceptionResNetV2(weights='imagenet', include_top=False, input_shape=(160, 160, 3))
    x = GlobalAveragePooling2D()(base_model.output)
    modelo_facial = Model(inputs=base_model.input, outputs=x)
    print("Modelo de reconhecimento facial baseado no InceptionResNetV2 carregado com sucesso!")
    return modelo_facial

# Inicializar o modelo de reconhecimento facial
facenet = carregar_modelo_facial()

# Função para calcular o embedding facial
def get_embedding(face_pixels):
    face_pixels = cv2.resize(face_pixels, (160, 160))  # Redimensionar para o tamanho esperado
    face_pixels = face_pixels.astype('float32')
    mean, std = face_pixels.mean(), face_pixels.std()
    face_pixels = (face_pixels - mean) / std
    face_pixels = np.expand_dims(face_pixels, axis=0)
    embedding = facenet.predict(face_pixels)
    return embedding[0]

# Função para codificar múltiplas faces dos usuários registrados
def codificar_usuarios(pasta_usuarios="usuarios"):
    usuarios_codificados = {}

    for arquivo in os.listdir(pasta_usuarios):
        if arquivo.endswith(".jpg") or arquivo.endswith(".png"):
            imagem = cv2.imread(os.path.join(pasta_usuarios, arquivo))
            imagem_rgb = cv2.cvtColor(imagem, cv2.COLOR_BGR2RGB)

            # Assumindo que a imagem contém apenas um rosto
            face_encoding = get_embedding(imagem_rgb)
            nome = arquivo.split("_")[0]  # Nome antes do "_"
            if nome not in usuarios_codificados:
                usuarios_codificados[nome] = []
            usuarios_codificados[nome].append(face_encoding)
    
    return usuarios_codificados

# Codificar os usuários registrados
usuarios_codificados = codificar_usuarios()

# Função para comparar embeddings usando similaridade do cosseno
def comparar_embeddings(face_embedding, embeddings_usuario, threshold=0.80):
    similaridades = [cosine_similarity([face_embedding], [user_embedding])[0][0] for user_embedding in embeddings_usuario]
    melhor_similaridade = max(similaridades)
    return melhor_similaridade >= threshold, melhor_similaridade

# Função para atualizar embeddings incrementais para cada usuário
def atualizar_embeddings_usuario(nome_usuario, novo_embedding, threshold=0.85, max_embeddings=10):
    if nome_usuario in usuarios_codificados:
        # Verificar se o novo embedding é suficientemente diferente dos existentes
        similaridades = [cosine_similarity([novo_embedding], [embedding])[0][0] for embedding in usuarios_codificados[nome_usuario]]
        if all(sim < threshold for sim in similaridades):
            # Manter apenas os embeddings mais representativos até o limite `max_embeddings`
            if len(usuarios_codificados[nome_usuario]) >= max_embeddings:
                usuarios_codificados[nome_usuario].pop(0)  # Remove o embedding mais antigo
            usuarios_codificados[nome_usuario].append(novo_embedding)
            print(f"Novo embedding adicionado para {nome_usuario}. Total de embeddings: {len(usuarios_codificados[nome_usuario])}")
    else:
        # Inicializar o usuário com o primeiro embedding se ele ainda não existir
        usuarios_codificados[nome_usuario] = [novo_embedding]
        print(f"Usuário {nome_usuario} inicializado com o primeiro embedding.")

# Inicializar a captura de vídeo
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Fazer a inferência usando o YOLOv8 para detectar faces
    results = model_yolo(frame, conf=0.5)

    for bbox in results[0].boxes.xyxy:
        x1, y1, x2, y2 = map(int, bbox)

        # Extrair a face detectada e converter para RGB
        face_frame = frame[y1:y2, x1:x2]
        face_rgb = cv2.cvtColor(face_frame, cv2.COLOR_BGR2RGB)

        # Obter o embedding da face detectada
        face_embedding = get_embedding(face_rgb)

        reconhecido = False
        melhor_nome = "Desconhecido"
        melhor_similaridade = 0

        # Comparar o embedding com os usuários registrados
        for nome, embeddings_usuario in usuarios_codificados.items():
            corresponde, similaridade = comparar_embeddings(face_embedding, embeddings_usuario, threshold=0.80)

            print(f"Similaridade com {nome}: {similaridade}")
            if corresponde and similaridade > melhor_similaridade:
                reconhecido = True
                melhor_nome = nome
                melhor_similaridade = similaridade
                atualizar_embeddings_usuario(nome, face_embedding)  # Atualizar embeddings

        # Exibir o resultado com base na similaridade
        if reconhecido:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)  # Quadrado verde
            cv2.putText(frame, f"{melhor_nome} ({melhor_similaridade:.2f})", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        else:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)  # Quadrado vermelho
            cv2.putText(frame, "Desconhecido", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

    # Mostrar o frame na tela
    cv2.imshow("Reconhecimento de Faces com YOLOv8", frame)

    # Sair ao pressionar 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Libera a captura de vídeo e fecha todas as janelas
cap.release()
cv2.destroyAllWindows()
