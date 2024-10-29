import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'dart:typed_data';
import 'package:image/image.dart' as img;

List<CameraDescription> cameras = [];

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  cameras = await availableCameras();
  runApp(CameraApp());
}

class CameraApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: CameraHome(),
    );
  }
}

class CameraHome extends StatefulWidget {
  @override
  _CameraHomeState createState() => _CameraHomeState();
}

class _CameraHomeState extends State<CameraHome> {
  CameraController? controller;
  WebSocketChannel? channel;
  bool _isStreaming = false;
  Uint8List? processedFrame;

  @override
  void initState() {
    super.initState();
    _initializeCamera();
    _connectToWebSocket();
  }

  @override
  void dispose() {
    controller?.dispose();
    channel?.sink.close();
    super.dispose();
  }

  void _initializeCamera() {
    // Obtém a câmera frontal
    CameraDescription? frontCamera = cameras.firstWhere(
          (camera) => camera.lensDirection == CameraLensDirection.front,
      orElse: () => cameras[0], // Usa a primeira câmera disponível se não houver câmera frontal
    );

    // Inicializa a câmera frontal
    controller = CameraController(
      frontCamera,
      ResolutionPreset.medium,
      enableAudio: false,
    );

    controller?.initialize().then((_) {
      if (!mounted) return;
      setState(() {});
      _startVideoStream();
    }).catchError((e) {
      print('Erro ao inicializar a câmera: $e');
    });
  }

  void _connectToWebSocket() {
    try {
      // Inicializa o WebSocket
      print('Tentando conectar ao servidor WebSocket...');
      channel = WebSocketChannel.connect(
        Uri.parse('ws://192.168.18.39:8765'), // IP do servidor WebSocket
      );

      // Conexão estabelecida
      print('Conectado ao servidor WebSocket.');

      // Recebe os frames processados do servidor
      channel?.stream.listen(
            (data) {
          setState(() {
            processedFrame = data;
          });
          print('Frame processado recebido do servidor.');
        },
        onError: (error) {
          print('Erro na conexão WebSocket: $error');
          _reconnectToWebSocket();
        },
        onDone: () {
          print('Conexão WebSocket encerrada.');
          _reconnectToWebSocket();
        },
      );
    } catch (e) {
      print('Falha ao conectar ao WebSocket: $e');
      _reconnectToWebSocket();
    }
  }

  void _reconnectToWebSocket() {
    // Tenta reconectar após um pequeno atraso
    Future.delayed(Duration(seconds: 5), () {
      print('Tentando reconectar ao servidor WebSocket...');
      _connectToWebSocket();
    });
  }

  void _startVideoStream() {
    controller?.startImageStream((CameraImage image) {
      if (!_isStreaming) {
        _isStreaming = true;
        _sendFrameToServer(image);
      }
    });
  }

  void _sendFrameToServer(CameraImage image) async {
    try {
      final int width = image.width;
      final int height = image.height;
      final img.Image convertedImage = img.Image(width, height);

      for (int i = 0; i < height; i++) {
        for (int j = 0; j < width; j++) {
          final int pixelIndex = i * width + j;
          final int pixelValue = image.planes[0].bytes[pixelIndex];
          convertedImage.setPixel(j, i, img.getColor(pixelValue, pixelValue, pixelValue));
        }
      }

      // Converte a imagem para JPEG
      final Uint8List jpegBytes = Uint8List.fromList(img.encodeJpg(convertedImage));

      // Envia o frame para o servidor
      print('Enviando frame para o servidor...');
      channel?.sink.add(jpegBytes);

      // Aguarda um curto intervalo para evitar sobrecarga
      await Future.delayed(Duration(milliseconds: 16));
    } catch (e) {
      print('Erro ao enviar o frame: $e');
    } finally {
      _isStreaming = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Detecção de Rosto em Tempo Real')),
      body: Center(
        child: AspectRatio(
          aspectRatio: 3 / 4, // Ajusta a proporção para 3:4
          child: processedFrame != null
              ? Image.memory(
            processedFrame!,
            fit: BoxFit.cover, // Ajuste para preencher a área
          )
              : controller!.value.isInitialized
              ? CameraPreview(controller!)
              : CircularProgressIndicator(),
        ),
      ),
    );
  }
}
