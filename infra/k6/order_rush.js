// SPEC 13: 500 students order within 5 minutes into 6 slots of 30 places and limited portions.
//
//   python -m scripts.load_setup            # in backend/, writes load_users.json
//   k6 run infra/k6/order_rush.js           # -e USERS=/absolute/path.json for another file
//   python -m scripts.load_check            # slots and portions are not oversold
//
// open() resolves paths against this file, so the default points to backend/load_users.json.
// BASE_URL defaults to the local API. There are fewer places (180) than students (500), so
// most late orders must end with 409 (slot or portions gone), never with a 5xx or an oversell.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000/api/v1';
const data = JSON.parse(open(__ENV.USERS || '../../backend/load_users.json'));

const created = new Counter('orders_created');
const rejected = new Counter('orders_rejected');
const serverErrors = new Counter('server_errors');

export const options = {
  scenarios: {
    rush: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '1m', target: 100 },
        { duration: '2m', target: 500 },
        { duration: '2m', target: 500 },
      ],
      gracefulRampDown: '10s',
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<500'],
    server_errors: ['count==0'],
    checks: ['rate>0.99'],
  },
};

const ordered = {}; // per VU: order id once it has tried to order (0 when it was rejected)

function headers(token) {
  return { headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } };
}

function track(res) {
  if (res.status >= 500) serverErrors.add(1);
  return res;
}

function pick(list) {
  return list[Math.floor(Math.random() * list.length)];
}

export default function () {
  const token = data.tokens[(__VU - 1) % data.tokens.length];
  const h = headers(token);
  const c = data.canteen_id;

  const menu = track(http.get(`${BASE_URL}/canteens/${c}/menu?date=${data.date}`, h));
  check(menu, { 'menu 200': (r) => r.status === 200 });

  if (ordered[__VU] === undefined) {
    const slots = track(http.get(`${BASE_URL}/canteens/${c}/slots?date=${data.date}`, h));
    check(slots, { 'slots 200': (r) => r.status === 200 });
    const open = slots.status === 200 ? slots.json('slots').filter((s) => s.free > 0) : [];
    // Half of the students rush the earliest slot that still looks free, the rest spread out.
    const slot = open.length ? (Math.random() < 0.5 ? open[0] : pick(open)) : null;
    if (slot === null) {
      ordered[__VU] = 0;
    } else {
      sleep(Math.random() * 2); // choosing a dish
      const body = JSON.stringify({
        canteen_id: c,
        pickup_slot_id: slot.id,
        items: [{ menu_item_id: pick(data.menu_item_ids), quantity: 1 + Math.floor(Math.random() * 2) }],
      });
      const res = track(http.post(`${BASE_URL}/orders`, body, h));
      check(res, { 'order 201 or 409': (r) => r.status === 201 || r.status === 409 });
      if (res.status === 201) {
        created.add(1);
        ordered[__VU] = res.json('id');
      } else {
        rejected.add(1);
        ordered[__VU] = 0;
      }
    }
  } else if (ordered[__VU] > 0) {
    // The student keeps the order page open: it polls its status.
    const res = track(http.get(`${BASE_URL}/orders/${ordered[__VU]}`, h));
    check(res, { 'order 200': (r) => r.status === 200 });
  }
  sleep(3 + Math.random() * 2);
}
