import mongoose from 'mongoose';
import bcrypt from 'bcryptjs';

const schema = new mongoose.Schema({
  username: { type: String, required: true, unique: true, lowercase: true, trim: true },
  passHash: { type: String, required: true },
  role: { type: String, enum: ['admin', 'operator'], default: 'operator' },
  active: { type: Boolean, default: true },
  lastLogin: Date,
}, { timestamps: true });

schema.methods.setPass = async function (plain) {
  this.passHash = await bcrypt.hash(plain, 12);
};

schema.methods.checkPass = function (plain) {
  return bcrypt.compare(plain, this.passHash);
};

export const Operator = mongoose.model('Operator', schema);