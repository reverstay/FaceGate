import cv2
import face_recognition
import numpy as np
import os

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

# Inicializar a captura de vídeo
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Converter o frame para RGB
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Detectar rosqtos no frame
    face_locations = face_recognition.face_locations(rgb_frame)

    # Verificar se foram encontradas faces
    if face_locations:
        # Codificar rostos no frame
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        # Loop para percorrer cada rosto detectado
        for face_encoding, face_location in zip(face_encodings, face_locations):
            # Colocar um quadrado vermelho ao redor do rosto detectado
            y1, x2, y2, x1 = face_location
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)  # Quadrado vermelho

            # Comparar o rosto capturado com usuários conhecidos
            resultados = face_recognition.compare_faces(codigos_usuarios, face_encoding, tolerance=0.6)
            distancias = face_recognition.face_distance(codigos_usuarios, face_encoding)

            # Verificar se o rosto é de um usuário registrado
            melhor_indice = np.argmin(distancias)

            if resultados[melhor_indice]:
                nome = nomes_usuarios[melhor_indice]
                # Mudar o quadrado para verde após a confirmação
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)  # Quadrado verde
                cv2.putText(frame, f"{nome} reconhecido", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            else:
                cv2.putText(frame, "Desconhecido", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    else:
        # Se nenhuma face for detectada, mostrar uma mensagem
        cv2.putText(frame, "Nenhuma face detectada", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    # Mostrar o frame na tela
    cv2.imshow("Reconhecimento Facial em Tempo Real", frame)

    # Sair ao pressionar 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Libera a captura de vídeo e fecha todas as janelas
cap.release()
cv2.destroyAllWindows()