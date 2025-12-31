
import express from 'express';
import cors from 'cors';
import { McpServer, ResourceTemplate } from '@modelcontextprotocol/sdk/server/mcp.js';
import { SSEServerTransport } from '@modelcontextprotocol/sdk/server/sse.js';
import Color from 'colorjs.io';
import { z } from 'zod';
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

// Setup dirname equivalent for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 8000;

app.use(cors());
app.use(express.json({ limit: '50mb' }));

// Health check
app.get('/', (req, res) => {
    res.json({ status: "healthy", service: "Color Accessibility Checker MCP (Node)" });
});

// Initialize MCP Server
const server = new McpServer({
    name: "color-accessibility-mcp",
    version: "1.0.0"
});

// Helper Functions
function calculateContrast(fg, bg) {
    try {
        const c1 = new Color(fg);
        const c2 = new Color(bg);
        return c1.contrast(c2, "WCAG21");
    } catch (e) {
        console.error("Error calculating contrast:", e);
        return 1;
    }
}

function evaluateWCAG(ratio) {
    return {
        passes_aa_normal: ratio >= 4.5,
        passes_aa_large: ratio >= 3.0,
        passes_aaa_normal: ratio >= 7.0,
        passes_aaa_large: ratio >= 4.5
    };
}

function generateSuggestions(fgHex, bgHex, currentRatio) {
    const suggestions = [];
    if (currentRatio >= 4.5) return suggestions;

    try {
        const fg = new Color(fgHex);
        const bg = new Color(bgHex);

        // Convert to OKLCH for uniform adjustments
        // We'll increment lightness in steps of 0.05

        // 1. Darken Background
        let bgDark = bg.to("oklch");
        bgDark.l = Math.max(0, bgDark.l - 0.15);
        let newBgHex = bgDark.to("srgb").toString({ format: "hex" });
        let newRatio = calculateContrast(fgHex, newBgHex);

        if (newRatio > currentRatio) {
            suggestions.push({
                type: "darken_bg",
                description: "Oscurecer el fondo",
                new_contrast_ratio: Number(newRatio.toFixed(2)),
                preview_hex_fg: fgHex,
                preview_hex_bg: newBgHex
            });
        }

        // 2. Lighten Background
        let bgLight = bg.to("oklch");
        bgLight.l = Math.min(1, bgLight.l + 0.15);
        newBgHex = bgLight.to("srgb").toString({ format: "hex" });
        newRatio = calculateContrast(fgHex, newBgHex);

        if (newRatio > currentRatio) {
            suggestions.push({
                type: "lighten_bg",
                description: "Aclarar el fondo",
                new_contrast_ratio: Number(newRatio.toFixed(2)),
                preview_hex_fg: fgHex,
                preview_hex_bg: newBgHex
            });
        }

        // 3. Adjust Foreground (Darken)
        let fgDark = fg.to("oklch");
        fgDark.l = Math.max(0, fgDark.l - 0.15);
        let newFgHex = fgDark.to("srgb").toString({ format: "hex" });
        newRatio = calculateContrast(newFgHex, bgHex);

        if (newRatio > currentRatio) {
            suggestions.push({
                type: "darken_fg",
                description: "Oscurecer el texto",
                new_contrast_ratio: Number(newRatio.toFixed(2)),
                preview_hex_fg: newFgHex,
                preview_hex_bg: bgHex
            });
        }

        // 4. Adjust Foreground (Lighten)
        let fgLight = fg.to("oklch");
        fgLight.l = Math.min(1, fgLight.l + 0.15);
        newFgHex = fgLight.to("srgb").toString({ format: "hex" });
        newRatio = calculateContrast(newFgHex, bgHex);

        if (newRatio > currentRatio) {
            suggestions.push({
                type: "lighten_fg",
                description: "Aclarar el texto",
                new_contrast_ratio: Number(newRatio.toFixed(2)),
                preview_hex_fg: newFgHex,
                preview_hex_bg: bgHex
            });
        }

        return suggestions.sort((a, b) => b.new_contrast_ratio - a.new_contrast_ratio).slice(0, 2);

    } catch (e) {
        console.error("Suggestion error:", e);
        return [];
    }
}

// Define MCP Tool
server.tool(
    "check_color_accessibility",
    {
        color_pairs: z.array(z.object({
            foreground: z.string(),
            background: z.string(),
            element: z.string()
        }))
    },
    async ({ color_pairs }) => {
        let passedCount = 0;
        let failedCount = 0;
        const processedPairs = [];

        for (const [idx, pair] of color_pairs.entries()) {
            const ratio = calculateContrast(pair.foreground, pair.background);
            const wcag = evaluateWCAG(ratio);
            const suggestions = generateSuggestions(pair.foreground, pair.background, ratio);

            if (wcag.passes_aa_normal) passedCount++;
            else failedCount++;

            processedPairs.push({
                id: `pair-${idx}`,
                text: pair.element,
                background: pair.background,
                foreground: pair.foreground,
                contrast_ratio: Number(ratio.toFixed(2)),
                wcag_aa: {
                    normal_text: wcag.passes_aa_normal,
                    large_text: wcag.passes_aa_large
                },
                wcag_aaa: {
                    normal_text: wcag.passes_aaa_normal,
                    large_text: wcag.passes_aaa_large
                },
                status: wcag.passes_aa_normal ? "pass" : "fail",
                suggestions: suggestions.map(s => ({
                    type: s.type,
                    background_oklch: "",
                    foreground_oklch: "",
                    new_contrast_ratio: s.new_contrast_ratio,
                    preview_hex_bg: s.preview_hex_bg,
                    preview_hex_fg: s.preview_hex_fg,
                    description: s.description
                }))
            });
        }

        const results = {
            summary: {
                total_pairs: color_pairs.length,
                passing_pairs: passedCount,
                failing_pairs: failedCount,
                detected_texts: color_pairs.length
            },
            color_pairs: processedPairs
        };

        // Inject Data into Template
        try {
            const templatePath = path.join(__dirname, 'widget-template.html');
            let htmlContent = await fs.readFile(templatePath, 'utf-8');

            const resultsJson = JSON.stringify(results);
            htmlContent = htmlContent.replace(
                'const sampleData = {',
                `const sampleData = ${resultsJson}; \n const _ignored = {`
            );

            return {
                content: [
                    {
                        type: "resource",
                        resource: {
                            uri: "ui://widget/color-accessibility.html",
                            mimeType: "text/html",
                            text: htmlContent
                        }
                    }
                ]
            };

        } catch (e) {
            console.error("Error generating widget:", e);
            return {
                content: [
                    { type: "text", text: "Error executing tool: " + e.message }
                ],
                isError: true
            };
        }
    }
);

// logic implementation detached if needed, but SDK handles tool calls mostly.

// CRÍTICO: SSE Endpoint Implementation
// Must handle proper headers via SSEServerTransport
let transport;

app.get('/mcp/sse', async (req, res) => {
    console.log('=== SSE CONNECTION ATTEMPT ===');
    console.log('Headers received:', req.headers);

    try {
        console.log('Creating SSEServerTransport...');
        transport = new SSEServerTransport('/mcp/messages', res);

        console.log('Connecting to MCP server...');
        await server.connect(transport);

        console.log('✅ SSE connected successfully');
    } catch (error) {
        console.error('❌ SSE connection error:', error);
        if (!res.headersSent) {
            res.status(500).send('SSE setup failed');
        }
    }
});

app.post('/mcp/messages', async (req, res) => {
    if (transport) {
        await transport.handlePostMessage(req, res);
    } else {
        res.status(400).send('No active connection');
    }
});


// Manual router for POST /mcp is NOT NEEDED if using SSE. 
// BUT for compatibility or fallback, we can keep it if it does not conflict.
// If user wants STRICT adherence, maybe we remove it?
// User said: "Verificar y corregir el endpoint /mcp/sse ... que use EXACTAMENTE este patrón".
// I will comment out the manual POST /mcp to force usage of SSE if that's what's intended,
// OR keep it separate.
// I'll keep it as a separate path just in case, but it shouldn't interfere with /mcp/sse.
// WAIT - The user says "ChatGPT intenta conectarse al endpoint SSE".
// So I must ensure SSE works. Extra endpoints don't hurt unless they overlap.
// I will keep POST /mcp just for my own debugging via curl if needed, or for old configs.

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});
