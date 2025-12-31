"""
Color Accessibility Checker - MCP Server
Author: Rafael Areses Delgado-Brackenbury
Description: WCAG color contrast analyzer with ChatGPT visual widget
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import re
from pathlib import Path
from coloraide import Color

app = FastAPI(
    title="Color Accessibility Checker",
    description="WCAG color contrast analyzer",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Funciones WCAG
def hex_to_rgb(hex_color: str) -> tuple:
    """Convierte hex a RGB"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def calculate_luminance(r: int, g: int, b: int) -> float:
    """Calcula luminancia relativa según WCAG 2.1"""
    def adjust(val):
        val = val / 255.0
        return val / 12.92 if val <= 0.03928 else ((val + 0.055) / 1.055) ** 2.4
    
    r, g, b = adjust(r), adjust(g), adjust(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def calculate_contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """Calcula ratio de contraste WCAG"""
    try:
        fg_rgb = hex_to_rgb(fg_hex)
        bg_rgb = hex_to_rgb(bg_hex)
        
        lum1 = calculate_luminance(*fg_rgb)
        lum2 = calculate_luminance(*bg_rgb)
        
        lighter = max(lum1, lum2)
        darker = min(lum1, lum2)
        
        return (lighter + 0.05) / (darker + 0.05)
    except Exception as e:
        print(f"Error calculating contrast for {fg_hex} on {bg_hex}: {e}")
        return 0.0

def evaluate_wcag(ratio: float) -> dict:
    """Evalúa conformidad WCAG AA y AAA"""
    return {
        "aa": {
            "normal_text": ratio >= 4.5,
            "large_text": ratio >= 3.0
        },
        "aaa": {
            "normal_text": ratio >= 7.0,
            "large_text": ratio >= 4.5
        }
    }

def generate_oklch_suggestions(bg_hex: str, fg_hex: str, target_ratio: float = 4.5) -> list:
    """Genera sugerencias de color en espacio OKLCH"""
    suggestions = []
    
    try:
        bg_color = Color(bg_hex)
        fg_color = Color(fg_hex)
        
        bg_oklch = bg_color.convert('oklch')
        fg_oklch = fg_color.convert('oklch')
        
        # Intentar aclarar background
        for delta in [0.1, 0.2, 0.3, 0.4, 0.5]:
            new_bg = bg_oklch.clone()
            new_bg['lightness'] = min(1.0, bg_oklch['lightness'] + delta)
            new_bg_hex = new_bg.convert('srgb').to_string(hex=True)
            
            ratio = calculate_contrast_ratio(fg_hex, new_bg_hex)
            if ratio >= target_ratio:
                suggestions.append({
                    "type": "lighten_bg",
                    "background_oklch": new_bg.to_string(),
                    "foreground_oklch": fg_oklch.to_string(),
                    "new_contrast_ratio": round(ratio, 1),
                    "preview_hex_bg": new_bg_hex,
                    "preview_hex_fg": fg_hex
                })
                break
        
        # Intentar oscurecer background
        for delta in [-0.1, -0.2, -0.3, -0.4, -0.5]:
            new_bg = bg_oklch.clone()
            new_bg['lightness'] = max(0.0, bg_oklch['lightness'] + delta)
            new_bg_hex = new_bg.convert('srgb').to_string(hex=True)
            
            ratio = calculate_contrast_ratio(fg_hex, new_bg_hex)
            if ratio >= target_ratio:
                suggestions.append({
                    "type": "darken_bg",
                    "background_oklch": new_bg.to_string(),
                    "foreground_oklch": fg_oklch.to_string(),
                    "new_contrast_ratio": round(ratio, 1),
                    "preview_hex_bg": new_bg_hex,
                    "preview_hex_fg": fg_hex
                })
                break
                
    except Exception as e:
        print(f"Error generating OKLCH suggestions: {e}")
    
    return suggestions

# MCP Tools definition
MCP_TOOLS = [
    {
        "name": "check_color_accessibility",
        "description": "Analyzes color pairs for WCAG compliance. ChatGPT extracts colors from images and passes them here.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "color_pairs": {
                    "type": "array",
                    "description": "Array of foreground/background color pairs",
                    "items": {
                        "type": "object",
                        "properties": {
                            "foreground": {"type": "string", "description": "Foreground color hex (#RRGGBB)"},
                            "background": {"type": "string", "description": "Background color hex (#RRGGBB)"},
                            "element": {"type": "string", "description": "UI element description"}
                        },
                        "required": ["foreground", "background", "element"]
                    }
                }
            },
            "required": ["color_pairs"]
        }
    }
]

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "active",
        "service": "Color Accessibility Checker",
        "author": "Rafael Areses Delgado-Brackenbury",
        "version": "1.0.0"
    }

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """Endpoint principal MCP - JSON-RPC 2.0"""
    try:
        body = await request.json()
        method = body.get("method")
        
        # Initialize
        if method == "initialize":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "color-accessibility-checker",
                        "version": "1.0.0"
                    }
                }
            })
        
        # List tools
        elif method == "tools/list":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {"tools": MCP_TOOLS}
            })
        
        # Call tool
        elif method == "tools/call":
            params = body.get("params", {})
            tool_name = params.get("name")
            
            if tool_name == "check_color_accessibility":
                arguments = params.get("arguments", {})
                color_pairs = arguments.get("color_pairs", [])
                
                results = []
                passing = 0
                failing = 0
                
                for i, pair in enumerate(color_pairs):
                    fg = pair.get("foreground")
                    bg = pair.get("background")
                    element = pair.get("element", "Unknown")
                    
                    ratio = calculate_contrast_ratio(fg, bg)
                    wcag = evaluate_wcag(ratio)
                    passes = wcag["aa"]["normal_text"]
                    
                    suggestions = [] if passes else generate_oklch_suggestions(bg, fg, 4.5)
                    
                    results.append({
                        "id": f"pair-{i}",
                        "text": element,
                        "foreground": fg,
                        "background": bg,
                        "contrast_ratio": round(ratio, 1),
                        "wcag_aa": wcag["aa"],
                        "wcag_aaa": wcag["aaa"],
                        "status": "pass" if passes else "fail",
                        "suggestions": suggestions
                    })
                    
                    if passes:
                        passing += 1
                    else:
                        failing += 1
                
                data = {
                    "summary": {
                        "total_pairs": len(results),
                        "passing_pairs": passing,
                        "failing_pairs": failing,
                        "detected_texts": len(results)
                    },
                    "color_pairs": results
                }
                
                # Cargar template HTML
                # Use absolute path resolving relative to this file
                template_path = Path(__file__).parent.parent / "web" / "ui-template.html"
                try:
                    html_content = template_path.read_text(encoding='utf-8')
                    
                    # Inyectar datos
                    import json
                    html_content = html_content.replace(
                        'const sampleData = {',
                        f'const sampleData = {json.dumps(data)}; \n const _ignored = {{'
                    )
                except Exception as e:
                    print(f"Error reading template: {e}")
                    # Fallback if template not found
                    html_content = f"<h1>Error loading template: {str(e)}</h1>"
                
                # CRÍTICO: Response con mime_type correcto para widget visual
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": html_content,
                                "mimeType": "text/html+skybridge"
                            }
                        ]
                    }
                })
            
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
            })
        
        # Unknown method
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        })
        
    except Exception as e:
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": body.get("id", None),
            "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
        })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
