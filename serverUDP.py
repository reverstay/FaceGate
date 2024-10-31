from flask import Flask, Response, render_template
import socket
import cv2
import numpy as np

app = Flask(__name__)

# Configuração do servidor UDP
UDP_IP = '0.0.0.0'
UDP_PORT = 8765
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((UDP_IP, UDP_PORT))

def udp_video_stream():
    while True:
        try:
            # Recebe os dados do frame via UDP
            data, _ = sock.recvfrom(65536)

            if not data:
                continue

            # Tenta decodificar o frame recebido como JPG
            frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)

            if frame is not None:
                # Codifica o frame para enviar para o navegador
                _, buffer = cv2.imencode('.jpg', frame)
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            else:
                print("Falha ao decodificar o frame.")
        except Exception as e:
            print(f"Erro ao receber ou processar dados UDP: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(udp_video_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)  # Servidor Flask na porta 5000
