# Color Accessibility Checker - MCP Server

A Model Context Protocol (MCP) server that provides WCAG color contrast analysis and suggestions, rendering results in a visual widget within ChatGPT.

## Features
- **WCAG Analysis**: Checks color pairs for AA and AAA compliance.
- **OKLCH Suggestions**: Generates alternative colors using the OKLCH color space for better perceptual uniformity.
- **Visual Widget**: Renders a rich HTML/CSS widget in ChatGPT using `text/html+skybridge`.

## Stack
- **Python 3.10+**
- **FastAPI**: For handling HTTP and JSON-RPC 2.0.
- **Coloraide**: For advanced color manipulation.
- **Render**: For deployment.

## Local Development

1. **Install dependencies**:
   ```bash
   pip install -r server/requirements.txt
   ```

2. **Run server**:
   ```bash
   uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
   ```

3. **Test Endpoint**:
   The server exposes a single JSON-RPC 2.0 endpoint at `https://color-accessibility-checker-se8r.onrender.com/mcp`.

## Deployment
Deployed automatically to Render.com via `render.yaml`.

## License
MIT
