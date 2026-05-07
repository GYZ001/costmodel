import express from 'express';
import cors from 'cors';
import { analyzeStock, getKlineData, getNews, getConfig, updateConfig } from './routes/api';

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

app.use('/api', analyzeStock);
app.use('/api', getKlineData);
app.use('/api', getNews);
app.use('/api', getConfig);
app.use('/api', updateConfig);

app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.listen(PORT, () => {
  console.log(`API server running on http://localhost:${PORT}`);
});

export default app;
