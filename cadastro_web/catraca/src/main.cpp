#include <WiFi.h>
#include <PubSubClient.h>

// Configuração do WiFi
const char* ssid = "Ramon MPM";
const char* password = "ramon1234";

// Configuração do MQTT
const char* mqtt_server = "broker.hivemq.com";
const int mqtt_port = 1883;
const char* mqtt_topic = "catraca/acesso";

// Definição dos pinos
#define LED_WIFI      2    // LED embutido no ESP32 (indica conexão WiFi)
#define LED_VERDE    12    // LED verde para liberação da catraca
#define LED_VERMELHO 13    // LED vermelho para negação

WiFiClient espClient;
PubSubClient client(espClient);

// Variável global para armazenar comando MQTT
String comandoMQTT = "";
bool mqttWasConnected = false;  // Flag para monitorar se estava conectado

// Prototipação das funções
void taskWiFi(void *pvParameters);
void taskMQTT(void *pvParameters);
void taskAcesso(void *pvParameters);
void callback(char* topic, byte* payload, unsigned int length);

void setup() {
  Serial.begin(115200);

  // Configuração dos pinos
  pinMode(LED_WIFI, OUTPUT);
  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_VERMELHO, OUTPUT);

  // Inicializar WiFi e MQTT
  WiFi.begin(ssid, password);
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);

  // Criar tarefas FreeRTOS
  xTaskCreatePinnedToCore(taskWiFi, "TaskWiFi", 4096, NULL, 1, NULL, 0);
  xTaskCreatePinnedToCore(taskMQTT, "TaskMQTT", 4096, NULL, 2, NULL, 1);
  xTaskCreatePinnedToCore(taskAcesso, "TaskAcesso", 2048, NULL, 1, NULL, 1);
}

// 🔹 Tarefa para manter a conexão WiFi ativa
void taskWiFi(void *pvParameters) {
  while (true) {
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("Reconectando ao WiFi...");
      WiFi.disconnect();
      WiFi.begin(ssid, password);

      // Enquanto não conectar, pisca o LED_WIFI a cada 500ms
      while (WiFi.status() != WL_CONNECTED) {
        digitalWrite(LED_WIFI, !digitalRead(LED_WIFI));
        vTaskDelay(500 / portTICK_PERIOD_MS);
        Serial.print(".");
      }
      Serial.println("\nWiFi Reconectado!");
      digitalWrite(LED_WIFI, HIGH);
      Serial.print("IP Local: ");
      Serial.println(WiFi.localIP());
    }
    vTaskDelay(5000 / portTICK_PERIOD_MS);
  }
}

// 🔹 Tarefa para manter a conexão MQTT ativa e processar mensagens
void taskMQTT(void *pvParameters) {
  while (true) {
    if (!client.connected()) {
      // Se estava conectado e a conexão caiu, exibe aviso
      if (mqttWasConnected) {
        Serial.println("⚠️ MQTT connection lost!");
        mqttWasConnected = false;
      }
      
      // Gera um clientID único
      String clientId = "ESP32_Client_" + String(random(0xffff), HEX);
      Serial.print("Conectando ao MQTT com ID: ");
      Serial.println(clientId);

      // Tenta conectar sem parâmetros extras
      if (client.connect(clientId.c_str())) {
        Serial.println("Conectado!");
        mqttWasConnected = true;
        client.subscribe(mqtt_topic);
      } else {
        Serial.print("Falha, rc=");
        Serial.print(client.state());
        Serial.println(" Tentando novamente em 5s...");
        vTaskDelay(5000 / portTICK_PERIOD_MS);
        continue; // Tenta novamente
      }
    }
    client.loop();  // Processa as mensagens MQTT
    vTaskDelay(10 / portTICK_PERIOD_MS);
  }
}

// 🔹 Callback do MQTT (executa quando mensagem é recebida)
void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Mensagem recebida: ");
  comandoMQTT = "";  // Reseta o comando
  for (int i = 0; i < length; i++) {
    comandoMQTT += (char)payload[i];
  }
  Serial.println(comandoMQTT);
}

// 🔹 Tarefa para processar comandos MQTT (liberar ou negar acesso)
void taskAcesso(void *pvParameters) {
  while (true) {
    if (comandoMQTT == "LIBERAR") {
      Serial.println("🔓 Catraca Liberada!");
      digitalWrite(LED_VERDE, HIGH);
      digitalWrite(LED_VERMELHO, LOW);
      vTaskDelay(5000 / portTICK_PERIOD_MS); // Mantém o relé ativado por 5 segundos
      digitalWrite(LED_VERDE, LOW);
      Serial.println("🔒 Catraca Fechada!");
    } else if (comandoMQTT == "NEGADO") {
      Serial.println("❌ Acesso Negado!");
      digitalWrite(LED_VERMELHO, HIGH);
      vTaskDelay(5000 / portTICK_PERIOD_MS);
      digitalWrite(LED_VERMELHO, LOW);
    }
    comandoMQTT = "";  // Reseta o comando após processamento
    vTaskDelay(500 / portTICK_PERIOD_MS);
  }
}

void loop() {
  // Não é utilizado, pois o processamento ocorre nas tarefas do FreeRTOS
  vTaskDelete(NULL);
}
