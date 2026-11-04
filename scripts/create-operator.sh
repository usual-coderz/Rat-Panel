docker compose exec server node -e "
import('bcryptjs').then(async ({default: b}) => {
  const { Operator } = await import('./server/models/Operator.js');
  const { connectDb } = await import('./server/db.js');
  await connectDb(process.env.MONGO_URI);
  const op = new Operator({ username: 'admin' });
  await op.setPass('ChangeMe123');
  op.role = 'admin';
  await op.save();
  console.log('created'); process.exit(0);
});"