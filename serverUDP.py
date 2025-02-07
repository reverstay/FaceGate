import socket
import cv2
import numpy as np
from flask import Flask, render_template, Response
from threading import Thread
import face_recognition
import os

app = Flask(__name__)
last_frame = None  # Armazena o último frame recebido

# Carregar codificações dos usuários registrados
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

# Carregar codificações de usuários
codigos_usuarios, nomes_usuarios = codificar_usuarios()

# Configuração do servidor UDP
UDP_IP = "0.0.0.0"
UDP_PORT = 8765
BUFFER_SIZE = 65507

def udp_receiver():
    global last_frame

    # Cria o socket UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"Servidor UDP rodando na porta {UDP_PORT}")

    while True:
        try:
            # Recebe dados do cliente
            data, addr = sock.recvfrom(BUFFER_SIZE)
            print(f"Dados recebidos de {addr}, tamanho: {len(data)} bytes")

            # Converte bytes para um array numpy
            np_arr = np.frombuffer(data, np.uint8)

            # Converte o array para uma imagem OpenCV
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is not None:
                # Processamento da imagem (reconhecimento facial)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                face_locations = face_recognition.face_locations(rgb_frame)

                if face_locations:
                    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

                    for face_encoding, face_location in zip(face_encodings, face_locations):
                        y1, x2, y2, x1 = face_location
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)  # Quadrado vermelho

                        resultados = face_recognition.compare_faces(codigos_usuarios, face_encoding, tolerance=0.6)
                        distancias = face_recognition.face_distance(codigos_usuarios, face_encoding)

                        melhor_indice = np.argmin(distancias)

                        if resultados[melhor_indice]:
                            nome = nomes_usuarios[melhor_indice]
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)  # Quadrado verde
                            cv2.putText(frame, f"{nome} reconhecido", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                        else:
                            cv2.putText(frame, "Desconhecido", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

                else:
                    cv2.putText(frame, "Nenhuma face detectada", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

                last_frame = frame  # Atualiza o último frame recebido
            else:
                print("Frame recebido é inválido ou está vazio.")
        except Exception as e:
            print(f"Erro ao processar frame: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    def generate_frames():
        global last_frame
        while True:
            if last_frame is not None:
                # Codifica o frame em JPEG
                _, buffer = cv2.imencode('.jpg', last_frame)
                frame_bytes = buffer.tobytes()

                # Envia o frame processado para o navegador
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    # Inicia o servidor UDP em uma thread separada
    udp_thread = Thread(target=udp_receiver, daemon=True)
    udp_thread.start()

    # Inicia o servidor Flask
    app.run(host='0.0.0.0', port=5000, debug=False)
