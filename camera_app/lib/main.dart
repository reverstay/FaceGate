import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:udp/udp.dart';
import 'package:image/image.dart' as img;
import 'package:http/http.dart' as http;

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final cameras = await availableCameras();

  // Encontra a câmera frontal (se disponível)
  final frontCamera = cameras.firstWhere(
        (camera) => camera.lensDirection == CameraLensDirection.front,
    orElse: () => cameras.first, // Se não encontrar, usa a primeira disponível
  );

  runApp(MyApp(camera: frontCamera));
}

class MyApp extends StatelessWidget {
  final CameraDescription camera;

  MyApp({required this.camera});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: CameraStream(camera: camera),
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
        _isStreaming = true;
        try {
          // Converte o frame para JPG
          Uint8List bytes = _convertToJpg(image);

          // Envia dados via UDP
          await _udpSocket?.send(
            bytes,
            Endpoint.unicast(InternetAddress('192.168.163.84'), port: Port(8765)),
          );
          print("Dados JPG enviados via UDP.");
        } catch (e) {
          print("Erro ao enviar dados via UDP: $e");
          _initializeUdpSocket(); // Reinicializa o socket em caso de erro
        } finally {
          _isStreaming = false;
        }
      } else if (_udpSocket == null) {
        print("Socket UDP não está inicializado.");
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

  Future<void> _fetchProcessedImage() async {
    try {
      // Realiza a requisição GET para o servidor Flask
      final response = await http.get(Uri.parse('http://192.168.163.84:5000/video_feed'));

      if (response.statusCode == 200) {
        setState(() {
          // A imagem processada pode ser carregada aqui para exibição
        });
      } else {
        print("Erro ao buscar imagem processada: ${response.statusCode}");
      }
    } catch (e) {
      print("Erro ao buscar imagem processada: $e");
    }
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
