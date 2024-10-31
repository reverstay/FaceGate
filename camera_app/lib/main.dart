import 'dart:io';
import 'dart:typed_data';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:udp/udp.dart';
import 'package:image/image.dart' as img;

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final cameras = await availableCameras();
  runApp(MyApp(camera: cameras.isNotEmpty ? cameras.first : null));
}

class MyApp extends StatelessWidget {
  final CameraDescription? camera;

  MyApp({this.camera});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: camera != null ? CameraStream(camera: camera!) : NoCameraScreen(),
    );
  }
}

class CameraStream extends StatefulWidget {
  final CameraDescription camera;

  CameraStream({required this.camera});

  @override
  _CameraStreamState createState() => _CameraStreamState();
}

class _CameraStreamState extends State<CameraStream> {
  late CameraController _controller;
  UDP? _udpSocket;
  bool _isStreaming = false;
  final int _fps = 10; // Define a taxa de quadros para 10 FPS
  DateTime _lastSentTime = DateTime.now();

  @override
  void initState() {
    super.initState();
    _initializeCamera();
  }

  void _initializeCamera() async {
    try {
      _controller = CameraController(widget.camera, ResolutionPreset.low);
      await _controller.initialize();
      setState(() {}); // Atualiza a interface quando a câmera é inicializada
      _initializeUdpSocket();
    } catch (e) {
      print("Erro ao inicializar a câmera: $e");
    }
  }

  void _initializeUdpSocket() async {
    try {
      // Inicializa o socket UDP
      _udpSocket = await UDP.bind(Endpoint.any(port: Port(0)));
      if (_udpSocket == null) {
        print("Falha ao inicializar o socket UDP.");
        return;
      }
      print("Socket UDP inicializado.");
      _startStreaming();
    } catch (e) {
      print("Erro ao inicializar o socket UDP: $e");
    }
  }

  void _startStreaming() {
    _controller.startImageStream((CameraImage image) async {
      if (_udpSocket != null && !_isStreaming) {
        // Limita a taxa de quadros para evitar sobrecarga
        final now = DateTime.now();
        if (now.difference(_lastSentTime).inMilliseconds < (1000 / _fps)) return;

        _isStreaming = true;
        try {
          // Converte o frame para JPG
          Uint8List bytes = _convertToJpg(image);

          // Envia dados via UDP
          await _udpSocket?.send(
            bytes,
            Endpoint.unicast(InternetAddress('192.168.1.100'), port: Port(8765)),
          );
          print("Dados JPG enviados via UDP.");
          _lastSentTime = now; // Atualiza o tempo do último envio
        } catch (e) {
          print("Erro ao enviar dados via UDP: $e");
          _initializeUdpSocket(); // Reinicializa o socket em caso de erro
        } finally {
          _isStreaming = false;
        }
      }
    });
  }

  Uint8List _convertToJpg(CameraImage image) {
    // Converte o frame para um formato de imagem utilizável
    img.Image convertedImage = img.Image.fromBytes(
      image.width,
      image.height,
      image.planes[0].bytes,
      format: img.Format.luminance, // Ajuste para monocromático
    );

    // Codifica a imagem para JPG
    List<int> jpgData = img.encodeJpg(convertedImage);

    return Uint8List.fromList(jpgData);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Streaming de Vídeo')),
      body: _controller.value.isInitialized
          ? CameraPreview(_controller)
          : Center(child: Text("Inicializando câmera...")),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    _udpSocket?.close();
    super.dispose();
  }
}

class NoCameraScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Câmera não encontrada')),
      body: Center(child: Text("Nenhuma câmera foi encontrada no dispositivo.")),
    );
  }
}
