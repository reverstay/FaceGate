import paho.mqtt.client as mqtt

# Configuração do broker MQTT
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "catraca/acesso"

# Função chamada quando o cliente conecta ao broker
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Conectado ao MQTT Broker!")
    else:
        print(f"⚠️ Falha ao conectar, código de retorno: {rc}")

# Inicializa o cliente MQTT
client = mqtt.Client()
client.on_connect = on_connect

# Conecta ao broker
print(f"🔌 Conectando ao broker MQTT: {MQTT_BROKER}")
client.connect(MQTT_BROKER, MQTT_PORT, 60)

# Função para enviar comando MQTT
def enviar_comando(comando):
    client.publish(MQTT_TOPIC, comando)
    print(f"📡 Enviado: {comando}")

# Loop para interagir com o usuário
while True:
    comando = input("Digite 'LIBERAR' para abrir ou 'NEGADO' para negar acesso (ou 'sair' para sair): ").strip().upper()
    
    if comando in ["LIBERAR", "NEGADO"]:
        enviar_comando(comando)
    elif comando == "SAIR":
        print("🚪 Saindo do programa...")
        break
    else:
        print("⚠️ Comando inválido! Use 'LIBERAR' ou 'NEGADO'.")

# Finaliza a conexão MQTT
client.disconnect()
print("🔌 Desconectado do MQTT Broker.")
