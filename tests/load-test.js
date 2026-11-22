// Prueba de carga con k6, ejecutada DESDE EL HOST:  k6 run tests/load-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL || 'http://localhost:8080';

export const options = {
  stages: [
    { duration: '30s', target: 50 },  // calentamiento
    { duration: '60s', target: 50 },  // carga sostenida
    { duration: '15s', target: 0 },   // enfriamiento
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<800'],
  },
};

export default function () {
  // 80% peticiones rápidas, 20% con trabajo simulado (200 ms)
  const url = Math.random() < 0.8 ? `${BASE}/` : `${BASE}/slow?ms=200`;
  const res = http.get(url);
  check(res, { 'status 200': (r) => r.status === 200 });
  sleep(0.1);
}
