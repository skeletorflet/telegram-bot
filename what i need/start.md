1. Ecosistema superior para IA/ML

Librerías maduras para Stable Diffusion (incluso podrías integrar directamente sin API)
Mejor manejo de procesamiento de imágenes (Pillow, OpenCV)
Familiaridad con el stack de A1111

2. Bibliotecas asíncronas robustas

asyncio nativo + aiohttp para llamadas a API
python-telegram-bot v20+ (totalmente asíncrono)
celery o dramatiq para colas de tareas pesadas
redis o RabbitMQ como broker

3. Ejemplo de arquitectura recomendada
Telegram Bot (asyncio) 
    ↓
Cola de tareas (Celery/Dramatiq)
    ↓
Workers procesando A1111 API
    ↓
Respuesta al usuario
4. Ventajas sobre Node.js

Mejor integración con herramientas de ML
Manejo de imágenes más directo
Comunidad más grande en este dominio específico
Scripts de prueba más simples

Stack recomendado:

Bot: python-telegram-bot (async)
Queue: Celery + Redis
HTTP: aiohttp para llamadas a A1111
Imágenes: Pillow

Node.js es excelente, pero Python domina completamente este nicho. La diferencia de performance es mínima y la experiencia de desarrollo será mucho mejor.