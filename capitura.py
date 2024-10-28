import os
import cv2

# Obter o diretório do script
diretorio_script = os.path.dirname(os.path.abspath(__file__))

# Definir o caminho do diretório "usuarios" dentro do diretório do script
diretorio_imagens = os.path.join(diretorio_script, "usuarios")

# Criar o diretório "usuarios" se ele não existir
if not os.path.exists(diretorio_imagens):
    os.makedirs(diretorio_imagens)

# Carregar o classificador de cascata Haar para detecção de rosto
cascata_face = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Inicializar a câmera
cap = cv2.VideoCapture(0)

user_name = input("Digite o nome do usuário: ")
image_count = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Converter o frame para escala de cinza para detecção de rosto
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detectar rostos no frame
    faces = cascata_face.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

    # Desenhar retângulos ao redor das faces detectadas
    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)  # Retângulo azul ao redor da face

    # Mostrar o frame na tela
    cv2.imshow("Captura de Imagem com Detecção de Face", frame)

    # Salvar a imagem se houver pelo menos uma face detectada e o usuário pressionar 's'
    if len(faces) > 0 and cv2.waitKey(1) & 0xFF == ord('s'):
        # Salvar a imagem no diretório "usuarios"
        caminho_imagem = os.path.join(diretorio_imagens, f"{user_name}_{image_count}.jpg")
        cv2.imwrite(caminho_imagem, frame)
        image_count += 1
        print(f"Imagem {image_count} salva em {caminho_imagem}.")

    # Sair ao pressionar 'q'
    elif cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
