import '@testing-library/jest-dom/vitest';

import i18n from '@/i18n';

void i18n.changeLanguage('ru');

/** Tests never open real sockets; `FakeWebSocket.instances` lets a test push messages. */
export class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }
  close() {
    this.onclose = null;
  }
  send() {}
}
globalThis.WebSocket = FakeWebSocket as unknown as typeof WebSocket;
