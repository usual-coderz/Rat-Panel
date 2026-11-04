import mongoose from 'mongoose';

const schema = new mongoose.Schema({
  uid: { type: String, required: true, unique: true, index: true },
  apiKey: { type: String, required: true, index: true },
  model: String,
  brand: String,
  manufacturer: String,
  androidVersion: Number,
  sdk: Number,
  imei: String,
  rooted: Boolean,
  battery: Number,
  perms: { type: mongoose.Schema.Types.Mixed, default: {} },
  appType: { type: String, default: 'basic' },
  online: { type: Boolean, default: false, index: true },
  lastSeen: Date,
  note: String,
}, { timestamps: true });

schema.index({ online: 1, lastSeen: -1 });

export const Device = mongoose.model('Device', schema);