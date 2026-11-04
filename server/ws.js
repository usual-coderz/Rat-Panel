import { WebSocketServer } from 'ws';
import { Device } from './models/Device.js';

const agents = new Map(); // deviceId -> socket

export function attachWs(server) {
  const wss = new WebSocketServer({ server, path: '/ws/agent' });

  wss.on('connection', async (socket, req) => {
    const key = new URL(req.url, 'http://x').searchParams.get('key');
    const device = key ? await Device.findOne({ apiKey: key }) : null;
    if (!device) return socket.close(4001, 'bad key');

    const id = String(device._id);
    agents.set(id, socket);
    await Device.updateOne({ _id: id }, { online: true, lastSeen: new Date() });

    socket.on('message', (raw) => {
      let msg;
      try { msg = JSON.parse(raw); } catch { return; }
      if (msg.type === 'pong') Device.updateOne({ _id: id }, { lastSeen: new Date() }).exec();
      // command results baad me yahan handle honge
    });

    socket.on('close', async () => {
      agents.delete(id);
      await Device.updateOne({ _id: id }, { online: false, lastSeen: new Date() });
    });
  });

  return { wss, agents };
}

export function sendToDevice(deviceId, payload) {
  const socket = agents.get(String(deviceId));
  if (!socket || socket.readyState !== 1) return false;
  socket.send(JSON.stringify(payload));
  return true;
}