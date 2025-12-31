import express from 'express';
import { SSEServerTransport } from '@modelcontextprotocol/sdk/server/sse.js';

const app = express();
app.get('/debug', (req, res) => {
    const transport = new SSEServerTransport('/endpoint', res);
    console.log('Transport keys:', Object.keys(transport));
    console.log('Transport sessionId:', transport.sessionId);
    console.log('Transport _sessionId:', transport._sessionId);
    res.send('ok');
});
app.listen(8001, () => console.log('Debug server on 8001'));
