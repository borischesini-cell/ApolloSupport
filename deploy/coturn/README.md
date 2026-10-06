# TURN para el canal rápido WebRTC

El canal rápido es P2P UDP entre el navegador del técnico y el agente. Con solo STUN
falla cuando alguno de los dos está detrás de NAT symmetric / firewall estricto.
Un TURN propio relaya el video por UDP 3478 y elimina esa causa de caida.

## Backend (ya soportado, sin cambio de código)

En el `.env` del backend (`C:\Django\ApolloSupport\backend\.env` en el VM .20):

```
WEBRTC_TURN_URL=turn:192.168.11.20:3478
WEBRTC_TURN_USER=apollo
WEBRTC_TURN_PASS=<misma que turnadmin>
```

El endpoint `/api/centinelas/webrtc/ice` ya las devuelve al visor y el visor ya las
envía al agente en el `webrtc_offer` (`ice_servers`). Reiniciar el servicio
ApolloSupport del VM después de editar el `.env`.

## Hosting

Opciones (en orden de preferencia):

1. **Docker en el VM .20** (Windows): `docker compose up -d` en esta carpeta.
   Requiere Docker Desktop / Mirantis en el VM. `network_mode: host` en Windows
   no funciona igual que en Linux — si falla, mapear puertos:
   `ports: ["3478:3478", "3478:3478/udp", "5349:5349", "49152-65535:49152-65535/udp"]`
   (el rango grande es pesado; alternativa: `min-port=49152 max-port=49252` y mapear ese rango).
2. **Cualquier Linux en la LAN** con docker (la 223 donde está PostgreSQL, si tiene docker).
3. **TURN cloud** (arrancar ya sin infra): Metered.ca free tier u Open Relay
   (`turn:openrelay.metered.ca:80`, credenciales abiertas) — suficiente para
   diagnóstico, no recomendado en producción por depender de terceros.

## Firewall / NAT

- Abrir UDP 3478 (y TCP 3478) en el firewall del host del TURN.
- Si el host está detrás de NAT: forwarding 3478/udp + `external-ip=ip_publica`
  (o `external-ip=privada/publica`).

## Alta de credencial

```
docker exec apollo-coturn turnadmin -a -u apollo -p '<PASSWORD>' -r apollo
```

Después de levantarlo, probar con:

```
turnutils_uclient -u apollo -w '<PASSWORD>' -r apollo <ip_del_turn>
```
