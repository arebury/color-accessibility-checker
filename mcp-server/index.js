/**
 * Color Accessibility Checker - MCP Server
 * Author: Rafael Areses Delgado-Brackenbury
 */

import express from 'express';
import cors from 'cors';
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { converter, formatHex, formatCss } from 'culori';
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const oklch = converter('oklch');

const server = new Server(
  { name: "color-accessibility-checker", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

function getRelativeLuminance(r, g, b) {
  const [rs, gs, bs] = [r, g, b].map(val => {
    const v = val / 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

function calculateContrastRatio(color1, color2) {
  const lum1 = getRelativeLuminance(color1.r, color1.g, color1.b);
  const lum2 = getRelativeLuminance(color2.r, color2.g, color2.b);
  const lighter = Math.max(lum1, lum2);
  const darker = Math.min(lum1, lum2);
  return (lighter + 0.05) / (darker + 0.05);
}

function evaluateWCAG(ratio) {
  return {
    aa: { normal_text: ratio >= 4.5, large_text: ratio >= 3.0 },
    aaa: { normal_text: ratio >= 7.0, large_text: ratio >= 4.5 }
  };
}

function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? {
    r: parseInt(result[1], 16),
    g: parseInt(result[2], 16),
    b: parseInt(result[3], 16)
  } : null;
}

function adjustLuminance(oklchColor, delta) {
  return { ...oklchColor, l: Math.max(0, Math.min(1, oklchColor.l + delta)) };
}

function generateColorSuggestions(bgHex, fgHex, targetRatio = 4.5) {
  const suggestions = [];
  const bgOKLCH = oklch(bgHex);
  const fgOKLCH = oklch(fgHex);
  if (!bgOKLCH || !fgOKLCH) return suggestions;
  
  for (let i = 0.1; i <= 0.5; i += 0.1) {
    const newBg = adjustLuminance(bgOKLCH, i);
    const newBgHex = formatHex(newBg);
    const bgRgb = hexToRgb(newBgHex);
    const fgRgb = hexToRgb(fgHex);
    if (bgRgb && fgRgb) {
      const ratio = calculateContrastRatio(bgRgb, fgRgb);
      if (ratio >= targetRatio) {
        suggestions.push({
          type: 'lighten_bg',
          background_oklch: formatCss(newBg),
          foreground_oklch: formatCss(fgOKLCH),
          new_contrast_ratio: Math.round(ratio * 10) / 10,
          preview_hex_bg: newBgHex,
          preview_hex_fg: fgHex
        });
        break;
      }
    }
  }
  
  for (let i = -0.1; i >= -0.5; i -= 0.1) {
    const newBg = adjustLuminance(bgOKLCH, i);
    const newBgHex = formatHex(newBg);
    const bgRgb = hexToRgb(newBgHex);
    const fgRgb = hexToRgb(fgHex);
    if (bgRgb && fgRgb) {
      const ratio = calculateContrastRatio(bgRgb, fgRgb);
      if (ratio >= targetRatio) {
        suggestions.push({
          type: 'darken_bg',
          background_oklch: formatCss(newBg),
          foreground_oklch: formatCss(fgOKLCH),
          new_contrast_ratio: Math.round(ratio * 10) / 10,
          preview_hex_bg: newBgHex,
          preview_hex_fg: fgHex
        });
        break;
      }
    }
  }
  return suggestions;
}

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [{
    name: "check_color_accessibility",
    description: "Analyzes color pairs for WCAG compliance",
    inputSchema: {
      type: "object",
      properties: {
        color_pairs: {
          type: "array",
          items: {
            type: "object",
            properties: {
              foreground: { type: "string" },
              background: { type: "string" },
              element: { type: "string" }
            },
            required: ["foreground", "background", "element"]
          }
        }
      },
      required: ["color_pairs"]
    }
  }]
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === "check_color_accessibility") {
    const { color_pairs } = request.params.arguments;
    try {
      const colorPairs = [];
      let passingPairs = 0, failingPairs = 0;
      
      for (let i = 0; i < color_pairs.length; i++) {
        const pair = color_pairs[i];
        const fgRgb = hexToRgb(pair.foreground);
        const bgRgb = hexToRgb(pair.background);
        if (!fgRgb || !bgRgb) continue;
        
        const ratio = calculateContrastRatio(fgRgb, bgRgb);
        const wcagEval = evaluateWCAG(ratio);
        const passes = wcagEval.aa.normal_text;
        const suggestions = !passes ? generateColorSuggestions(pair.background, pair.foreground, 4.5) : [];
        
        colorPairs.push({
          id: `pair-${i}`,
          text: pair.element,
          background: pair.background,
          foreground: pair.foreground,
          contrast_ratio: Math.round(ratio * 10) / 10,
          wcag_aa: wcagEval.aa,
          wcag_aaa: wcagEval.aaa,
          status: passes ? 'pass' : 'fail',
          suggestions
        });
        
        if (passes) passingPairs++; else failingPairs++;
      }
      
      const results = {
        summary: {
          total_pairs: colorPairs.length,
          passing_pairs: passingPairs,
          failing_pairs: failingPairs,
          detected_texts: colorPairs.length
        },
        color_pairs: colorPairs
      };
      
      const templatePath = path.join(__dirname, '../web/ui-template.html');
      let htmlContent = await fs.readFile(templatePath, 'utf-8');
      htmlContent = htmlContent.replace('const sampleData = {', `const sampleData = ${JSON.stringify(results)}; \n const _ignored = {`);
      
      return {
        content: [{
          type: "resource",
          resource: {
            uri: "ui://widget/color-accessibility.html",
            mimeType: "text/html",
            text: htmlContent
          }
        }]
      };
    } catch (error) {
      return { content: [{ type: "text", text: `Error: ${error.message}` }], isError: true };
    }
  }
  throw new Error(`Unknown tool: ${request.params.name}`);
});

const app = express();
app.use(cors());
app.use(express.json({ limit: '50mb' }));

app.get('/', (req, res) => {
  res.json({ status: 'active', service: 'Color Accessibility Checker', author: 'Rafael Areses' });
});

let transport;
app.get('/mcp/sse', async (req, res) => {
  console.log('SSE connection established');
  transport = new SSEServerTransport('/mcp/messages', res);
  await server.connect(transport);
});

app.post('/mcp/messages', async (req, res) => {
  if (transport) {
    await transport.handlePostMessage(req, res);
  } else {
    res.status(400).send('No active connection');
  }
});

const PORT = process.env.PORT || 8000;
app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
