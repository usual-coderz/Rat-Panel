import { Router } from 'express';
import crypto from 'node:crypto';
import { Device } from '../models/Device.js';
import { Sim } from '../models/Sim.js';

export const agentRouter = Router();

// APK pehli baar yahan aata hai
agentRouter.post('/register', async (req, res) => {
  const { apiKey, device = {}, sims = [] } = req.body || {};
  if (!apiKey) return res.status(400).json({ error: 'apiKey required' });

  const uid = crypto.createHash('sha256').update(apiKey + (device.imei || '') + (device.model || '')).digest('hex').slice(0, 32);

  const doc = await Device.findOneAndUpdate(
    { uid },
    {
      $set: {
        apiKey,
        model: device.model,
        brand: device.brand,
        manufacturer: device.manufacturer,
        androidVersion: device.androidVersion,
        sdk: device.sdk,
        imei: device.imei,
        rooted: device.rooted,
        battery: device.battery,
        perms: device.perms || {},
        appType: device.appType || 'basic',
        lastSeen: new Date(),
      },
    },
    { upsert: true, new: true, setDefaultsOnInsert: true }
  );

  if (Array.isArray(sims) && sims.length) {
    await Promise.all(sims.map((s) =>
      Sim.findOneAndUpdate(
        { device: doc._id, slotIndex: s.slotIndex },
        { $set: { subId: s.subId, carrier: s.carrier, mcc: s.mcc, mnc: s.mnc, label: s.label, number: s.number, defaultSim: !!s.defaultSim } },
        { upsert: true }
      )
    ));
  }

  res.json({ deviceId: String(doc._id) });
});