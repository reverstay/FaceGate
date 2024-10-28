import cv2
import face_recognition
import numpy as np
import os
import time
import threading

# Variáveis globais
frame_atual = None
fps = 0
processando = False
face_atual = None  # Localização do rosto detectado atualmente
nome_atual = ""    # Nome do usuário identificado

# Intervalo de tempo para executar o reconhecimento (em segundos)
intervalo_reconhecimento = 1  # 500 ms
ultimo_reconhecimento = time.time()

# Função para codificar imagens de usuários registrados
def codificar_usuarios(pasta_usuarios="usuarios"):
    usuarios_codificados = []
    nomes_usuarios = []

    for arquivo in os.listdir(pasta_usuarios):
        if arquivo.endswith(".jpg"):
            imagem = face_recognition.load_image_file(os.path.join(pasta_usuarios, arquivo))
            codificacoes = face_recognition.face_encodings(imagem)
            if codificacoes:  # Verifica se alguma codificação foi encontrada
                usuarios_codificados.append(codificacoes[0])
                nomes_usuarios.append(arquivo.split("_")[0])  # Nome do usuário é extraído antes do "_"
    
    return np.array(usuarios_codificados), nomes_usuarios

# Carregar codificações dos usuários registrados
codigos_usuarios, nomes_usuarios = codificar_usuarios()

# Função de captura de vídeo
def capturar_video():
    global frame_atual
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        # Atualiza o frame atual para exibição
        frame_atual = frame

    cap.release()

# Função de inferência em segundo plano
def inferencia_assincrona():
    global frame_atual, processando, face_atual, nome_atual, ultimo_reconhecimento

    while True:
        # Limitar a frequência de reconhecimento
        if time.time() - ultimo_reconhecimento < intervalo_reconhecimento:
            continue

        if frame_atual is not None and not processando:
            processando = True

            # Redimensionar o frame para aceleração do processamento
            pequeno_frame = cv2.resize(frame_atual, (320, 240))
            rgb_frame = cv2.cvtColor(pequeno_frame, cv2.COLOR_BGR2RGB)

            # Detectar rostos no frame usando o modelo HOG
            face_locations = face_recognition.face_locations(rgb_frame, model='hog')

            if face_locations:
                # Codificar rostos no frame
                face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

                # Considerar apenas o primeiro rosto detectado
                face_location = face_locations[0]
                face_encoding = face_encodings[0]
                y1, x2, y2, x1 = [v * 2 for v in face_location]  # Ajustar coordenadas ao tamanho original

                # Comparar o rosto capturado com usuários conhecidos
                resultados = face_recognition.compare_faces(codigos_usuarios, face_encoding, tolerance=0.6)
                distancias = face_recognition.face_distance(codigos_usuarios, face_encoding)

                # Verificar se o rosto é de um usuário registrado
                melhor_indice = np.argmin(distancias)

                if resultados[melhor_indice]:
                    nome_atual = nomes_usuarios[melhor_indice]
                    face_atual = (x1, y1, x2, y2)
                else:
                    face_atual = (x1, y1, x2, y2)  # Rosto desconhecido, mas manter o quadrado
                    nome_atual = "Desconhecido"

            ultimo_reconhecimento = time.time()
            processando = False

# Iniciar threads de captura e inferência
thread_captura = threading.Thread(target=capturar_video, daemon=True)
thread_inferencia = threading.Thread(target=inferencia_assincrona, daemon=True)

thread_captura.start()
thread_inferencia.start()

# Exibir vídeo na thread principal
tempo_anterior = time.time()
while True:
    if frame_atual is not None:
        # Calcular o FPS
        tempo_atual = time.time()
        fps = 1 / (tempo_atual - tempo_anterior)
        tempo_anterior = tempo_atual

        # Mostrar o quadrado verde ou vermelho no rosto detectado
        if face_atual is not None:
            x1, y1, x2, y2 = face_atual
            cor = (0, 255, 0) if nome_atual != "Desconhecido" else (0, 0, 255)
            cv2.rectangle(frame_atual, (x1, y1), (x2, y2), cor, 2)
            cv2.putText(frame_atual, nome_atual, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, cor, 2)

        # Mostrar o FPS no canto superior direito
        cv2.putText(frame_atual, f"FPS: {int(fps)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
        cv2.imshow("Reconhecimento Facial em Tempo Real", frame_atual)

    # Sair ao pressionar 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cv2.destroyAllWindows()
