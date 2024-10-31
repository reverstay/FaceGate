import cv2
from ultralytics import YOLO
import os

# Carregar o modelo YOLOv8 para detecção de faces
# Use 'yolov8n.pt' ou um modelo específico de faces se disponível
model = YOLO('yolov8n.pt')  # Substitua por 'yolov8_face.pt' se houver um modelo treinado para faces

# Inicializar a captura de vídeo
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Fazer a inferência usando o YOLOv8
    results = model(frame, conf=0.8)  # Ajuste o nível de confiança conforme necessário

    # Obter coordenadas das caixas delimitadoras das faces detectadas
    for bbox in results[0].boxes.xyxy:  # Acesso às coordenadas das caixas
        x1, y1, x2, y2 = map(int, bbox)

        # Desenhar um quadrado vermelho ao redor do rosto detectado
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)

        # Exibir uma mensagem indicando que uma face foi detectada
        cv2.putText(frame, "Face detectada", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

    # Se nenhuma face for detectada, mostrar uma mensagem
    if len(results[0].boxes) == 0:
        cv2.putText(frame, "Nenhuma face detectada", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    # Mostrar o frame na tela
    cv2.imshow("Detecção de Faces em Tempo Real com YOLOv8", frame)

    # Sair ao pressionar 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Libera a captura de vídeo e fecha todas as janelas
cap.release()
cv2.destroyAllWindows()
