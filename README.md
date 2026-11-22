<<<<<<< HEAD
# Proyecto Final – Proxy Inverso Nginx + Monitoreo

**Integrantes:**
- Karen Juliana Dueñas Castro
- Sara Mesa Lenis
- Sofía Valencia Velasco
- Emily Suárez González

**Curso:** Sistemas Operativos
**Docente:** Juan Manuel Álvarez Quiñonez
**Institución:** Universidad Autónoma de Occidente – Facultad de Ciencias Básicas

---

## 1. Descripción del proyecto

Este proyecto implementa una infraestructura con Docker Compose en la que **Nginx** actúa como proxy inverso y balanceador de carga entre tres instancias de una aplicación **Flask**. Sobre esa base se integra un sistema de monitoreo con **Prometheus** y **Grafana**, alimentado por tres fuentes de métricas: los propios backends, el **Nginx Prometheus Exporter** y **cAdvisor**.

Todo el entorno se levanta con un solo comando (`docker compose up -d --build`).

La infraestructura está compuesta por los siguientes servicios. 
**Nginx** (`nginx:1.27-alpine`) es el proxy inverso y balanceador round-robin; publica el puerto 8080 en el host y es el único punto de entrada a la aplicación. 
**app1, app2 y app3** se construyen desde `./backend` (Flask + Gunicorn), son tres instancias idénticas identificadas como `server 1`, `server 2` y `server 3`, y no publican puertos (escuchan en el 5000 interno). 
**nginx-exporter** (`nginx/nginx-prometheus-exporter`, puerto interno 9113) traduce el `stub_status` de Nginx a métricas de Prometheus. 
**cAdvisor** (`ghcr.io/google/cadvisor`, publicado en el 8081) entrega CPU, memoria, red y disco por contenedor. 
**Prometheus** (`prom/prometheus`, puerto 9090) recolecta y almacena las métricas
**Grafana** (`grafana/grafana`, puerto 3000) las visualiza en dashboards. Opcionalmente existe un servicio 
**artillery** (`artilleryio/artillery`) que ejecuta pruebas de carga dentro de la red Docker; pertenece al perfil `test` y no se levanta por defecto.

## 2. Arquitectura

Todos los contenedores están en una red Docker personalizada llamada `lab-proxy-net` (driver `bridge`) y se comunican por el nombre de su servicio. Nginx es el único punto de entrada **a la aplicación**; los backends no publican puertos. Prometheus, Grafana y cAdvisor sí se publican en el host para poder consultarlos desde el navegador.

```text
Host :8080 ──> NGINX ──> app1 / app2 / app3   (Flask + Gunicorn, :5000)
                 │
                 │ :8088 /stub_status (puerto interno, no publicado)
                 └──> nginx-exporter :9113 ──────┐
                                                  │
app1 / app2 / app3  /metrics (directo) ───────────┼──> Prometheus :9090 ──> Grafana :3000
                                                  │
cAdvisor :8080 (publicado en el host como :8081) ─┘
```

Prometheus consulta `/metrics` de cada backend **directamente**, sin pasar por Nginx. Prometheus y Grafana usan volúmenes persistentes: `prometheus-data` y `grafana-data`.

## 3. Estructura del repositorio

```text
lab-proxy/
├── .env
├── .gitignore
├── README.md
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── app.py
│   └── requirements.txt
├── nginx/
│   └── nginx.conf
├── monitoring/
│   ├── prometheus/
│   │   └── prometheus.yml
│   └── grafana/
│       ├── dashboards/
│       │   └── lab-proxy.json
│       └── provisioning/
│           ├── dashboards/dashboards.yml
│           └── datasources/prometheus.yml
└── tests/
    ├── load-test.js                 (k6, se ejecuta desde el host)
    ├── performance-test.yml         (Artillery)
    └── performance-test-slow.yml    (Artillery, backend lento)
```

## 4. Configuración resumida

**Backend (`backend/`).** El `Dockerfile` parte de `python:3.12-slim`, instala las dependencias en una capa separada para aprovechar la caché y arranca con `gunicorn -w 1 --threads 8 -b 0.0.0.0:5000 app:app`. La aplicación (`app.py`) expone la ruta `/` (responde "Hello from server N" y el nombre del contenedor), `/health` (usada por el healthcheck y excluida de las métricas), `/headers` (muestra las cabeceras que recibe el backend, útil para ver `X-Forwarded-For`), `/slow?ms=500` (responde tras 500 ms, con un máximo de 30 000, para simular trabajo pesado) y `/metrics` (métricas de Prometheus mediante `prometheus-flask-exporter`, con la etiqueta `backend`). Todas las respuestas incluyen la cabecera `X-Backend` con el nombre del servidor.

**Docker Compose (`docker-compose.yml`).** Un bloque `x-backend` (ancla YAML) compartido por `app1`, `app2` y `app3` define el build, `restart: unless-stopped`, la red y el healthcheck (cada 5 s, timeout de 3 s, 5 reintentos y `start_period` de 3 s); cada servicio solo cambia `SERVER_NAME`. Nginx espera a que los tres backends estén `healthy` (`depends_on` con `service_healthy`). Grafana arranca con acceso anónimo y rol Admin, sin formulario de login, solo para laboratorio local.

**Nginx (`nginx/nginx.conf`).** El `upstream backend_pool` contiene `app1:5000`, `app2:5000` y `app3:5000` y balancea con **round-robin** (el método por defecto). Se envían las cabeceras `Host`, `X-Real-IP`, `X-Forwarded-For` y `X-Forwarded-Proto`. La tolerancia a fallos se logra con `proxy_connect_timeout 2s` y `proxy_next_upstream error timeout http_502 http_503 http_504`. Para auditar el reparto existe un `log_format lb` que incluye `upstream=IP:5000` y la cabecera de respuesta `X-Upstream`. Un segundo `server` escucha en el puerto interno `8088` y sirve `/stub_status`; ese puerto no se publica y solo lo lee `nginx-exporter`.

**Prometheus (`monitoring/prometheus/prometheus.yml`).** Consulta cada 5 s seis targets: `prometheus`, `app1`, `app2` y `app3` (job `backends`), `nginx-exporter` (job `nginx`) y `cadvisor`.

## 5. Requisitos previos

Se necesita Docker, Docker Compose v2 (para orquestar los servicios) y k6 (para las pruebas de carga ejecutadas desde el host). Verifica las instalaciones:

```bash
docker --version
docker compose version
k6 version
```

Instalación de k6: https://grafana.com/docs/k6/latest/set-up/install-k6/

### Puertos necesarios

Deben estar libres los puertos 8080 (Nginx), 8081 (cAdvisor), 9090 (Prometheus) y 3000 (Grafana). Si alguno está ocupado, descomenta y cambia la variable correspondiente en el archivo `.env`: `NGINX_PORT`, `CADVISOR_PORT`, `PROMETHEUS_PORT` o `GRAFANA_PORT`. Por defecto todas están comentadas y se usan los valores indicados. Si cambias `NGINX_PORT`, recuerda pasarle el nuevo puerto a k6 (ver sección 10).

## 6. Levantar la infraestructura

Desde la raíz del proyecto (donde está `docker-compose.yml`):

```bash
docker compose up -d --build
```

Este comando construye la imagen del backend, crea la red `lab-proxy-net` y los volúmenes, e inicia todos los servicios en segundo plano. Nginx arranca solo cuando los tres backends están `healthy`.

Verificar el estado:

```bash
docker compose ps
```

Los backends y cAdvisor deben aparecer como `healthy`, y el resto como `running`.

Ver los registros:

```bash
docker compose logs -f
```

(`Ctrl + C` sale de los registros sin detener los contenedores.)

## 7. URLs de acceso

Con la infraestructura en marcha puedes abrir en el navegador: la aplicación a través del proxy inverso en http://localhost:8080; Prometheus en http://localhost:9090, donde se consultan las métricas y el estado de los targets; Grafana en http://localhost:3000, que entra directo, sin usuario ni contraseña (acceso anónimo con rol Admin); y cAdvisor en http://localhost:8081, con los recursos de los contenedores.

En Grafana abre el dashboard **Laboratorio Proxy Reverso**. Ya está aprovisionado junto con el datasource de Prometheus, así que no requiere configuración manual.

## 8. Verificar el balanceo de carga

Nginx reparte las solicitudes de forma rotativa entre `server 1` (app1), `server 2` (app2) y `server 3` (app3).

**Desde el navegador:** abre http://localhost:8080 y actualiza varias veces; debe alternar entre `server 1`, `server 2` y `server 3`.

**Desde la terminal (nueve solicitudes):**

```bash
for i in $(seq 1 9); do
  curl -s http://localhost:8080/ | grep -o "server [0-9]"
done
```

Debe repetirse el patrón `server 1`, `server 2`, `server 3`.

**Cabeceras que identifican al backend.** `X-Backend` indica el nombre del servidor que respondió (lo agrega Flask) y `X-Upstream` la IP y el puerto del contenedor al que Nginx envió la petición:

```bash
curl -sI http://localhost:8080/ | grep -i -E "x-backend|x-upstream"
```

**Registros de Nginx.** Cada línea muestra `upstream=IP:5000`, el estado y el tiempo de la petición:

```bash
docker compose logs nginx --tail 10
```

### Prueba de tolerancia a fallos

1. Detener una instancia (por ejemplo `app1`):

   ```bash
   docker compose stop app1
   ```

2. Enviar solicitudes de nuevo:

   ```bash
   for i in $(seq 1 9); do
     curl -s http://localhost:8080/ | grep -o "server [0-9]"
   done
   ```

   La aplicación debe seguir respondiendo con `server 2` y `server 3`. Las primeras peticiones pueden tardar hasta ~2 s, porque Nginx espera el `proxy_connect_timeout` antes de reenviar al siguiente backend.

3. Restaurar la instancia:

   ```bash
   docker compose start app1
   ```

4. Repetir el bucle del paso 2 y comprobar que `server 1` vuelve a aparecer. Si no recibe tráfico, reinicia Nginx para que vuelva a resolver los nombres de los backends:

   ```bash
   docker compose restart nginx
   ```

## 9. Monitoreo con Prometheus y Grafana

### Prometheus

1. Abre http://localhost:9090.
2. Ve a **Status → Targets**. Deben aparecer los **6 targets en `UP`**: `prometheus`, `app1`, `app2`, `app3`, `nginx-exporter` y `cadvisor`.
3. En **Graph** puedes probar consultas como:

   ```promql
   rate(flask_http_request_total[30s])
   ```
   ```promql
   nginx_http_requests_total
   ```
   ```promql
   container_memory_working_set_bytes{name!=""}
   ```

### Dashboard "Laboratorio Proxy Reverso" (Grafana)

La fila superior tiene cuatro indicadores: los targets arriba (esperado: 6), las peticiones por segundo en Nginx, las conexiones activas y las respuestas 5xx por segundo. Este último se calcula con las métricas de los backends Flask, por lo que cuenta los errores 5xx emitidos por la aplicación y no los que pudiera generar el propio Nginx. Debajo hay dos paneles por backend: las peticiones por segundo, que permiten ver el reparto entre `server 1`, `server 2` y `server 3`, y la latencia p95 de cada instancia. Después vienen los paneles de infraestructura obtenidos de cAdvisor: CPU por contenedor (en núcleos), memoria usada (working set), red recibida y enviada por contenedor (bytes por segundo) y, por último, disco por contenedor (lectura y escritura en bytes por segundo).

## 10. Pruebas de carga

### Con k6 (desde el host)

El script `tests/load-test.js` envía tráfico a `http://localhost:8080` (o a la URL de la variable `BASE_URL`) con este perfil:

- **Etapas:** 30 s de rampa hasta 50 usuarios virtuales, 60 s sostenidos en 50 y 15 s de descenso (1 min 45 s en total).
- **Mezcla de peticiones:** 80 % a `/` (rápidas) y 20 % a `/slow?ms=200` (200 ms de trabajo simulado), con una pausa de 0,1 s entre iteraciones.
- **Umbrales:** menos de 1 % de peticiones fallidas y p95 de latencia inferior a 800 ms.

Ejecutar desde la raíz del proyecto:

```bash
k6 run tests/load-test.js
```

Si cambiaste el puerto de Nginx en `.env`:

```bash
k6 run -e BASE_URL=http://localhost:<puerto> tests/load-test.js
```

Si usas `--vus` y `--duration` (por ejemplo `k6 run --vus 10 --duration 30s tests/load-test.js`), esos parámetros reemplazan las etapas definidas en el script.

Al terminar, k6 muestra un resumen. Las métricas principales son `http_reqs` (total de solicitudes y tasa por segundo), `http_req_duration` (tiempo de respuesta: promedio, mediana, p90 y p95), `http_req_failed` (porcentaje de solicitudes fallidas), `checks` (verificaciones exitosas de `status 200`), `vus` y `vus_max` (usuarios virtuales activos y máximos) e `iterations` (iteraciones completadas). Como el 20 % de las peticiones simula 200 ms de trabajo, es normal que el p95 ronde los 200 ms aunque la mediana sea de pocos milisegundos.

### Con Artillery (opcional, dentro de la red Docker)

Los servicios del perfil `test` no se levantan con `docker compose up`; se invocan de forma explícita:

```bash
# Carga sostenida contra "/" (tests/performance-test.yml)
docker compose --profile test run --rm artillery

# Carga contra "/slow?ms=500" (tests/performance-test-slow.yml)
docker compose --profile test run --rm artillery run /scripts/performance-test-slow.yml
```

### Qué observar durante la prueba

1. **Grafana:** peticiones/s, conexiones activas, latencia p95 por backend y consumo de CPU, memoria y red.
2. **Prometheus:** que los targets sigan en `UP`.
3. **Nginx:** el reparto entre backends en los registros:

   ```bash
   docker compose logs -f nginx
   ```

Para evaluar la tolerancia a fallos bajo carga, detén una instancia (`docker compose stop app1`) y repite la prueba: Nginx debe repartir el tráfico entre las dos restantes sin peticiones fallidas.

## 11. Detener la infraestructura

```bash
docker compose down
```

Detiene y elimina los contenedores y la red. Los volúmenes `prometheus-data` y `grafana-data` **se conservan**, por lo que las métricas y la configuración de Grafana siguen ahí al volver a levantar el entorno:

```bash
docker compose up -d --build
```

Para eliminar también los volúmenes (borra todas las métricas almacenadas):

```bash
docker compose down -v
```

## 12. Resultado esperado

Al seguir estos pasos se debe poder comprobar que:

1. Todos los servicios se levantan con `docker compose up -d --build`.
2. Nginx distribuye las solicitudes entre las tres instancias de Flask con round-robin.
3. El sistema sigue atendiendo solicitudes cuando una instancia se detiene, mientras haya otras operativas.
4. Prometheus tiene los 6 targets en `UP`.
5. Grafana muestra el dashboard "Laboratorio Proxy Reverso" con datos en tiempo real.
6. cAdvisor aporta el consumo de CPU, memoria, red y disco de cada contenedor.
7. Las pruebas de carga con k6 reportan solicitudes procesadas, tiempos de respuesta y porcentaje de errores.
=======
# arquitectura-ngnx-docker
Implementación de proxy inverso, balanceo de carga y tolerancia a fallos con Nginx y Docker.
>>>>>>> 171aa4b31df049c28c22d6024ae97cc410c1f234
