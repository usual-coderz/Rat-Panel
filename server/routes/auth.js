import { Router } from 'express';
import jwt from 'jsonwebtoken';
import { Operator } from '../models/Operator.js';

export const authRouter = Router();

authRouter.post('/login', async (req, res) => {
  const { username, password } = req.body || {};
  if (!username || !password) return res.status(400).json({ error: 'missing fields' });

  const op = await Operator.findOne({ username: String(username).toLowerCase() });
  if (!op || !op.active || !(await op.checkPass(password))) {
    return res.status(401).json({ error: 'bad credentials' });
  }

  op.lastLogin = new Date();
  await op.save();

  const token = jwt.sign({ sub: String(op._id), role: op.role }, process.env.JWT_SECRET, { expiresIn: '12h' });
  res.json({ token, role: op.role, username: op.username });
});