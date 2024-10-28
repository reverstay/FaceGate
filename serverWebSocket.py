import asyncio
import threading
import websockets
import cv2
import numpy as np
from flask import Flask, render_template, Response

app = Flask(__name__)
last_processed_frame = None  # Armazena o último frame processado

# Função para o servidor WebSocket
async def handle_websocket_connection(websocket, path):
    global last_processed_frame
    print(f"Novo cliente WebSocket conectado de: {websocket.remote_address}")
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    try:
        while True:
            frame_bytes = await websocket.recv()
            print("Frame recebido do cliente.")

            # Converte bytes para um array numpy
            np_arr = np.frombuffer(frame_bytes, np.uint8)

            # Converte o array para uma imagem OpenCV
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is not None:
                # Realiza a detecção de rostos
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.1, 4)

                # Desenha retângulos em torno dos rostos detectados
                for (x, y, w, h) in faces:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

                # Atualiza o último frame processado
                last_processed_frame = frame

                # Codifica o frame processado para JPEG
                _, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()

                # Envia o frame processado de volta para o Flutter
                await websocket.send(frame_bytes)
            else:
                print("Frame recebido é inválido ou está vazio")

    except websockets.ConnectionClosed:
        print("Cliente WebSocket desconectado.")

# Inicia o servidor WebSocket em uma nova thread
def start_websocket_server():
    asyncio.set_event_loop(asyncio.new_event_loop())
    loop = asyncio.get_event_loop()
    server = websockets.serve(handle_websocket_connection, "0.0.0.0", 8765)
    loop.run_until_complete(server)
    print("Servidor WebSocket rodando na porta 8765")
    loop.run_forever()

# Rota para a página principal
@app.route('/')
def index():
    return render_template('index.html')

# Função para gerar frames para o navegador
def generate_frames():
    global last_processed_frame
    while True:
        if last_processed_frame is not None:
            # Converte o último frame processado para bytes
            _, buffer = cv2.imencode('.jpg', last_processed_frame)
            frame_bytes = buffer.tobytes()

            # Envia o frame para o navegador
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        else:
            # Se não há frame processado, aguarda brevemente
            continue

# Rota para o vídeo em tempo real
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# Inicia o servidor Flask em uma nova thread
def start_flask_server():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

if __name__ == "__main__":
    # Cria as threads para WebSocket e Flask
    websocket_thread = threading.Thread(target=start_websocket_server)
    flask_thread = threading.Thread(target=start_flask_server)

    # Inicia as threads
    websocket_thread.start()
    flask_thread.start()

    # Aguarda a execução das threads
    websocket_thread.join()
    flask_thread.join()
