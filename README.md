# MediSupply - Experimento de Seguridad (JWT + Alerta &lt; 2s)

## Resumen

Implementación mínima viable de los microservicios **Autorizador**, **Seguridad y Auditoría** y **Servicio de Alertas**
para comprobar que ante un acceso no autorizado se dispara una alerta en &lt;= 2s, mediante JWT, en arquitectura de
microservicios, con orquestación por *API Gateway* (NGINX) y plan de carga en JMeter.

## Estructura

Detalles de cada microservicio se encuentran en `Context.md`.

- `authorizer/`
- `security_audit/`
- `alert_sink/`
- `nginx/`
- `jmeter/mediSupply-security.jmx`
- `postman/mediSupply.postman_collection.json`

## Requisitos

Docker y Docker Compose.

## Ejecución

```bash
docker compose up --build
```

## Prueba rápida

1) Autorizado OK

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/auth/login -H 'content-type: application/json' -d '{"username":"user1","password":"pass1"}' | jq -r .access_token)
curl -i -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/orders/u1/status
```

2) No token → 401 y alerta asíncrona

```bash
curl -i http://localhost:8080/api/orders/u1/status
```

3) Token de otro usuario → 403 y alerta asíncrona

```bash
TOKEN2=$(curl -s -X POST http://localhost:8080/auth/login -H 'content-type: application/json' -d '{"username":"user2","password":"pass2"}' | jq -r .access_token)
curl -i -H "Authorization: Bearer $TOKEN2" http://localhost:8080/api/orders/u1/status
```

4) Métricas de la alerta

```bash
curl -s http://localhost:8080/alerts/metrics | jq
```

## JMeter

Abrir `jmeter/mediSupply-security.jmx` en Apache JMeter 5.6+ y ejecutar. Los escenarios están descritos en `Context.md`.

## Postman

Importar `postman/mediSupply.postman_collection.json` en Postman para ejecutar los escenarios de autenticación,
accesos autorizados y no autorizados y consultar las métricas.

## Variables

- `JWT_SECRET` y `ALERT_URL` ajustables vía variables de entorno.