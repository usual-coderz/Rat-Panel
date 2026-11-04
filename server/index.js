import 'dotenv/config';
import http from 'node:http';
import express from 'express';
import { connectDb } from './db.js';
import { attachWs } from './ws.js';
import { authRouter } from './routes/auth.js';
import { agentRouter } from './routes/agent.js';

const app = express();
app.use(express.json({ limit: '2mb' }));
app.use(express.static('public'));

app.get('/health', (_req, res) => res.json({ ok: true }));
app.use('/api/auth', authRouter);
app.use('/api/agent', agentRouter);

app.use((err, _req, res, _next) => {
  console.error(err);
  res.status(500).json({ error: 'internal' });
});

const server = http.createServer(app);
attachWs(server);

const port = Number(process.env.PORT || 8080);

connectDb(process.env.MONGO_URI)
  .then(() => server.listen(port, () => console.info(`[tpc] up on ${port}`)))
  .catch((e) => { console.error('[mongo] failed', e); process.exit(1); });