import mongoose from 'mongoose';

export async function connectDb(uri) {
  mongoose.set('strictQuery', true);
  await mongoose.connect(uri, {
    serverSelectionTimeoutMS: 10000,
    maxPoolSize: 20,
    autoIndex: process.env.NODE_ENV !== 'production',
  });
  mongoose.connection.on('disconnected', () => console.warn('[mongo] disconnected'));
  mongoose.connection.on('reconnected', () => console.info('[mongo] reconnected'));
  console.info('[mongo] connected');
  return mongoose.connection;
}

export async function closeDb() {
  await mongoose.connection.close();
}