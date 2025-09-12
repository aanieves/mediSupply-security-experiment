# Context.md — Experimento de Seguridad (MediSupply)

> **Objetivo**: Documentar las restricciones del experimento y las decisiones de diseño.

---

## 1) Propósito, Alcance y Éxito del Experimento

- **Título del experimento**: *Alerta de ataques a través de autorización mediante JSON Web Tokens (JWT)*.
- **Propósito**: Determinar si la táctica de seguridad basada en **control de acceso** con **JWT** y el componente de *
  *Seguridad y Auditoría** **favorecen la seguridad**, cumpliendo que ante una consulta de un **usuario no autorizado**
  se **genera una alerta en < 2 segundos**.
- **ASR asociado (requisito de atributo de calidad)**: **ASR-12** — Como administrador, ante una consulta de estado de
  pedido por un **usuario no autorizado**, el módulo de **seguridad y auditoría** debe **detectar automáticamente** la
  operación y **generar una alerta** al administrador **en menos de 2 s**.
- **Resultado esperado / métrica**: Medir el tiempo entre la detección del acceso no autorizado y la recepción de la
  alerta por el componente de alertas. **El tiempo no debe superar los 2 s**.
- **Nivel de incertidumbre**: Medio.
- **Alcance (MVP del experimento)**: Autenticación básica con JWT, autorización por **propiedad del dato** (el `subject`
  del token debe coincidir con el `customer_id` consultado), detección de intentos no autorizados y **notificación
  asíncrona** al administrador. No se incluyen capas de UI, persistencia transaccional ni orquestaciones complejas.

---

## 2) Arquitectura Lógica, Estilo y Tácticas

### 2.1 Estilo de Arquitectura

- **Microservicios** detrás de **API Gateway**.
- Ventajas relevantes: **aislamiento** funcional, **recuperación** del sistema ante ataques, **disponibilidad**.
- Desventajas a considerar: mayor **superficie de ataque**, necesidad de **definir niveles de acceso** por servicio.

### 2.2 Tácticas aplicadas (seguridad)

- **Resistir ataques – Autorizar actores**: Validación de identidad y permisos del usuario antes de exponer datos.
- **Detectar ataques – Detectar intrusiones**: Identificación de solicitudes no autorizadas y clasificación de causas.
- **Reaccionar a ataques – Informar actores**: **Envió de alerta** al administrador de manera **asíncrona** para
  minimizar impacto en latencia del endpoint funcional.

### 2.3 Componentes (microservicios) del experimento

1. **API Gateway (NGINX)**  
   Puerta de entrada única: enruta hacia los servicios internos. Expuesto en `http://localhost:8080`.
2. **Autorizador** (FastAPI)
    - **Login** con credenciales; emite **JWT**.
    - **Validación** de tokens (estructura, firma, expiración).
3. **Seguridad y Auditoría** (FastAPI)
    - Expone el endpoint protegido: `GET /orders/{customer_id}/status`.
    - **Casos** que evalúa ante cada solicitud:  
      a) **Sin token** ⇒ **401** + **alerta**.  
      b) **Token inválido** ⇒ **401** + **alerta**.  
      c) **Token válido, pero `sub` ≠ `customer_id`** ⇒ **403** + **alerta**.  
      d) **Token válido, `sub` = `customer_id`** ⇒ **200** (sin alerta).
    - **Registra** y dispara la alerta cuando aplica.
4. **Detector/Servicio de Alertas** (FastAPI)
    - Recibe la **alerta** junto con marcas de tiempo; **calcula latencia** y expone métricas (p50, p95, max) en
      `/metrics`.

---

## 3) Diseño de la Solución Implementada

### 3.1 Tecnologías

- **Lenguaje**: Python 3.11.
- **Framework**: FastAPI (+ Uvicorn).
- **JWT**: algoritmo **HS256** con **secreto común** (`JWT_SECRET`).
- **Infraestructura**: Docker y Docker Compose.
- **Gateway**: NGINX (reverse proxy L7).
- **Medición de carga**: Apache **JMeter** (plan incluido).
- **Librerías**: PyJWT, Pydantic, httpx.

> Nota: Los artefactos de base de datos (p. ej., PostgreSQL) forman parte de la visión tecnológica general, pero **no
son necesarios en este MVP**.

### 3.2 Topología y Enrutamiento (Gateway)

- **`/auth/*` ⇒ Autorizador**
- **`/api/*` ⇒ Seguridad y Auditoría**
- **`/alerts/*` ⇒ Alertas**
- Puerto externo: **8080**.

### 3.3 Contratos de Interfaces (API)

#### 3.3.1 Autorización

- **POST** `/auth/login`  
  **Body**: `{"username": "user1", "password": "pass1"}`  
  **200**: `{"access_token": "<jwt>", "token_type":"bearer"}`  
  **401**: `{"detail":"invalid credentials"}`

- **POST** `/auth/validate`  
  **Body**: `{"token": "<jwt>"}`  
  **200** (token válido): `{"valid": true, "claims": {...}}`  
  **200** (token inválido): `{"valid": false}`

#### 3.3.2 Endpoint protegido

- **GET** `/api/orders/{customer_id}/status`  
  **Headers**: `Authorization: Bearer <jwt>`  
  **200** (autorizado): `{"customer_id":"u1","status":"delivered"}`  
  **401** (sin token o token inválido)  
  **403** (token válido pero sujeto ≠ propietario del dato)

#### 3.3.3 Servicio de alertas

- **POST** `/alerts/alert`  
  **Body** ejemplo:
  ```json
  {
    "reason": "no_token | bad_token | unauthorized_access",
    "customer_id": "u1",
    "subject": "u2 | null",
    "t0": 1726000000.123
  }
  ```
  **200**: `{"received": true, "latency_ms": 30.2, "count": 5}`

- **GET** `/alerts/metrics`  
  **200**: `{"count": 10, "p50_ms": 20.5, "p95_ms": 90.1, "max_ms": 112.4}`

### 3.4 Semántica de Autorización

- El **claim `sub`** del JWT representa el **dueño del dato**; se **debe** corresponder con `customer_id` solicitado.
- La ausencia de token, token inválido o **no correspondencia** de `sub` ⇒ **no se retorna el dato** y se **dispara
  alerta**.
- **Códigos de estado**: 401 (no autenticado / inválido), 403 (autenticado pero no autorizado), 200 (autorizado).

### 3.5 Concurrencia y Alertas

- Al detectar condición no autorizada, el servicio **Seguridad y Auditoría** ejecuta el envío de alerta **de forma
  asíncrona** (background task) para **no bloquear** la respuesta al cliente.
- El **t0** se marca en Seguridad y Auditoría; el **servicio de Alertas** computa la **latencia** hasta la recepción (*
  *t1**).

### 3.6 Estrategia de Medición de la Métrica (< 2 s)

- La métrica del experimento es el tiempo entre **detección** (t0) y **recepción** de la alerta (t1) medido en *
  *milisegundos**.
- **Éxito**: *latency_ms* ≤ **2000** en **todos** los intentos (según el ASR).
- En práctica operativa, se monitorean **p50/p95** en `/alerts/metrics` para validar estabilidad durante pruebas de
  carga.

---

## 4) Reglas, Restricciones y Suposiciones (Exhaustivas)

1. **ASR-12 – Alerta < 2 s** ante acceso no autorizado (**obligatorio**).
2. **Confidencialidad**: Un usuario **no** puede acceder a datos de otro; el sistema debe **impedir y alertar**.
3. **Autenticación** mediante **JWT** emitido por **Autorizador**; **firma HS256** y **expiración** (exp).
4. **Autorización por propiedad**: `sub` debe **igualar** `customer_id` consultado para acceder al recurso.
5. **Tres escenarios de evaluación** por Solicitud:  
   a) sin token (401 + alerta), b) token inválido (401 + alerta), c) token válido de **otro usuario** (403 + alerta), d)
   token válido y **dueño** (200, **sin alerta**).
6. **Gateway obligatorio**: todos los accesos externos pasan por **NGINX** (API Gateway) hacia servicios internos.
7. **Separación de responsabilidades**:
    - **Autorizador** solo **emite/valida** tokens.
    - **Seguridad y Auditoría** protege recursos y dispara alertas.
    - **Servicio de Alertas** mide latencia y expone métricas.
8. **Concurrencia / No bloqueo**: **envío de alertas asíncrono** para proteger la latencia del endpoint funcional.
9. **Tecnologías mínimas del experimento**: Python, FastAPI, Uvicorn, PyJWT, Pydantic, httpx, Docker/Compose, NGINX,
   JMeter.
10. **Tecnologías de la visión general** (no requeridas en el MVP): PostgreSQL, caching, balanceadores internos,
    replicación (documentadas para el sistema, **no** necesarias aquí).
11. **Instrumentación obligatoria**: **t0** en Seguridad y Auditoría; **medición** en Servicio de Alertas; exposición de
    **/alerts/metrics**.
12. **Seguridad operativa** adicional (lineamientos generales de proyecto):
    - Realizar **DAST** con **OWASP ZAP** sin hallazgos **Altos/Críticos** al cierre.
    - Endurecimiento de endpoints (headers, validación de entradas) — aplicable en mejora continua.
13. **Pruebas**:
    - **JMeter** con escenarios: *sin token*, *token de otro usuario*, *token válido*.
    - Validación de la métrica < 2 s durante las ejecuciones.
    - (Lineamientos transversales del proyecto) Cobertura automatizada y pruebas de integración/contrato en FastAPI,
      cuando se amplíe el alcance.
14. **Usuarios/roles del experimento**:
    - **Usuario registrado (propietario)**: acceso a **sus** datos.
    - **Usuario registrado (no propietario)**: **no** debe acceder a datos de **otro**.
    - **Usuario no registrado**: sin acceso a recursos protegidos.
15. **Estados y respuestas** estandarizadas: 200/401/403; mensajes de error sin filtrar detalles sensibles.
16. **Parámetros configurables**:
    - `JWT_SECRET` (secreto HS256).
    - `ALERT_URL` (endpoint del servicio de alertas).
    - Puertos y mapeos del Gateway.
17. **No funcionales (relevantes)**:
    - Disponibilidad/recuperación fomentadas por microservicios y Gateway.
    - Desempeño: no degradar indebidamente latencia del endpoint por envío de alertas (uso de async).
    - Observabilidad: métricas de latencia de alertas.

---

## 5) Flujo de Fin a Fin

1. **Login** (cliente → Gateway → Autorizador). Si credenciales válidas ⇒ **JWT**.
2. **Solicitud de recurso** (cliente → Gateway → Seguridad y Auditoría) con `Authorization: Bearer <jwt>`.
3. **Validaciones** en Seguridad y Auditoría: existencia del token, decodificación, exp/iat, **match `sub`
   vs `customer_id`**.
4. **Autorización**:
    - Si **no autorizado**: retorna **401/403** y lanza **tarea asíncrona** para **POST /alerts/alert** (**t0**
      incluido).
    - Si **autorizado**: **200** con el estado del pedido.
5. **Servicio de Alertas**: registra recepción (**t1**), calcula **latency_ms** y expone métricas agregadas en
   `/alerts/metrics`.

---

## 6) Topología de Despliegue (Docker Compose)

- **Gateway (nginx:alpine)** publica **8080** y monta `nginx.conf`.
- **authorizer** (FastAPI) con `JWT_SECRET`.
- **security_audit** (FastAPI) con `JWT_SECRET` y `ALERT_URL`.
- **alert_sink** (FastAPI) expone `/alerts/alert` y `/alerts/metrics`.
- Red Docker de microservicios (`ms`).

---

## 7) Pruebas y Validación

### 7.1 JMeter

- Tres **ThreadGroups** que ejercitan:  
  a) **No token** → 401 + alerta,  
  b) **Token de otro usuario** → 403 + alerta,  
  c) **Token dueño** → 200 sin alerta.
- Extracción de `access_token` por JSONPath y encabezado `Authorization`.
- Se recomienda ejecutar y consultar `GET /alerts/metrics` para verificar **p95** y **max**.

### 7.2 Seguridad

- Escaneo DAST con **OWASP ZAP**; objetivo: **0** vulnerabilidades **Altas/Críticas**.
- Recomendación: automatizar verificación de cabeceras, validación de entradas y tiempos de expiración de JWT.

### 7.3 Criterio de aceptación del experimento

- **Cumplido** si **todas** las alertas por solicitudes no autorizadas **llegan en ≤ 2 s** (idealmente p95 ≤ 2 s) y se
  respeta la **confidencialidad** (no exposición de datos a terceros).

---

## 8) Operación y Mantenimiento

- **Configuración**: ver `README.md` para las variables de entorno requeridas.
- **Monitoreo**: `/alerts/metrics` (p50/p95/max y conteo).
- **Rotación de secreto**: actualizar `JWT_SECRET` y reiniciar servicios.
- **Estrategia de fallos**: si el servicio de alertas no está disponible, el envío asíncrono **no bloquea** el endpoint
   protegido; se registra el intento fallido en logs del servicio.

---

## 9) Mapas a artefactos del proyecto

- **ASR-12 y métrica < 2 s** (seguridad/confidencialidad).
- **Estilo microservicios + Gateway**.
- **Tácticas**: Autorizar, Detectar intrusiones, Informar (alertar).
- **Concurrencia**: envío **asíncrono** de alerta.
- **Tecnología**: Python/FastAPI, JWT HS256, Docker/NGINX, JMeter.
- **Lineamientos de pruebas transversales**: DAST (OWASP ZAP), cobertura automatizada, objetivos SMART de pruebas.

---

