import mongoose from 'mongoose';

const schema = new mongoose.Schema({
  device: { type: mongoose.Schema.Types.ObjectId, ref: 'Device', required: true, index: true },
  slotIndex: Number,
  subId: Number,
  carrier: String,
  mcc: String,
  mnc: String,
  label: String,
  number: String,
  defaultSim: Boolean,
}, { timestamps: true });

schema.index({ device: 1, slotIndex: 1 }, { unique: true });

export const Sim = mongoose.model('Sim', schema);