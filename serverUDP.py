import socket
import cv2
import numpy as np
from flask import Flask, render_template, Response
from threading import Thread

app = Flask(__name__)
last_frame = None  # Armazena o último frame recebido

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

                # Envia o frame para o navegador
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    # Inicia o servidor UDP em uma thread separada
    udp_thread = Thread(target=udp_receiver, daemon=True)
    udp_thread.start()

    # Inicia o servidor Flask
    app.run(host='0.0.0.0', port=5000, debug=False)
