import os
import socket
import time

from flask import Flask, jsonify, request
from prometheus_flask_exporter import PrometheusMetrics

app = Flask(__name__)

# El nombre lo inyectamos desde docker-compose (variable de entorno SERVER_NAME)
SERVER_NAME = os.getenv("SERVER_NAME", "sin-nombre")

# group_by="endpoint": agrupa por ruta de Flask (evita una serie por cada URL distinta)
# default_labels: etiqueta "backend" en todas las métricas, útil para las gráficas
# excluded_paths: no cuenta el healthcheck de Docker, que llega cada 5 s
metrics = PrometheusMetrics(
    app,
    group_by="endpoint",
    default_labels={"backend": SERVER_NAME},
    excluded_paths=["/health"],
)
metrics.info("app_info", "Información del backend", server=SERVER_NAME)


@app.route("/")
def index():
    return (
        f"<h1>Hello from {SERVER_NAME}</h1>\n"
        f"<p>Contenedor: {socket.gethostname()}</p>\n"
    )


@app.route("/health")
def health():
    return jsonify(status="ok", server=SERVER_NAME)


@app.route("/headers")
def headers():
    # Muestra qué cabeceras recibe realmente el backend (útil para ver X-Forwarded-For)
    return jsonify(
        server=SERVER_NAME,
        ip_que_ve_flask=request.remote_addr,
        cabeceras=dict(request.headers),
    )


@app.route("/slow")
def slow():
    # Simula trabajo pesado: /slow?ms=500 tarda 500 ms en responder
    ms = min(int(request.args.get("ms", 1000)), 30000)
    time.sleep(ms / 1000)
    return jsonify(server=SERVER_NAME, esperó_ms=ms)


@app.after_request
def marcar_backend(resp):
    resp.headers["X-Backend"] = SERVER_NAME
    return resp
