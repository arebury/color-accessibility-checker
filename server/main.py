"""
🎨 Color Accessibility Checker - MCP Server
FastAPI server that checks color accessibility according to WCAG standards
"""

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import math
from coloraide import Color

app = FastAPI(title="Color Accessibility Checker MCP")

# Enable CORS for ChatGPT
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Data Models
# ============================================================================

class ColorPair(BaseModel):
    foreground: str
    background: str
    element: str


class CheckColorAccessibilityInput(BaseModel):
    color_pairs: List[ColorPair]


class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[int] = None


# ============================================================================
# Color Utility Functions
# ============================================================================

def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to RGB tuple (0-255)"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def calculate_luminance(rgb: tuple) -> float:
    """
    Calculate relative luminance according to WCAG 2.0
    https://www.w3.org/TR/WCAG20/#relativeluminancedef
    """
    r, g, b = [x / 255.0 for x in rgb]
    
    # Apply gamma correction
    r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
    g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
    b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
    
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def calculate_contrast_ratio(color1: str, color2: str) -> float:
    """
    Calculate contrast ratio between two colors
    https://www.w3.org/TR/WCAG20/#contrast-ratiodef
    """
    rgb1 = hex_to_rgb(color1)
    rgb2 = hex_to_rgb(color2)
    
    lum1 = calculate_luminance(rgb1)
    lum2 = calculate_luminance(rgb2)
    
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    
    return (lighter + 0.05) / (darker + 0.05)


def evaluate_wcag(ratio: float) -> Dict[str, bool]:
    """
    Evaluate WCAG compliance levels
    AA Normal: 4.5:1, AA Large: 3:1
    AAA Normal: 7:1, AAA Large: 4.5:1
    """
    return {
        "passes_aa_normal": ratio >= 4.5,
        "passes_aa_large": ratio >= 3.0,
        "passes_aaa_normal": ratio >= 7.0,
        "passes_aaa_large": ratio >= 4.5,
    }


def generate_oklch_suggestions(fg_hex: str, bg_hex: str, current_ratio: float) -> List[Dict[str, Any]]:
    """
    Generate color adjustment suggestions using OKLCH color space
    Returns suggestions to improve contrast if it fails WCAG AA
    """
    suggestions = []
    
    if current_ratio >= 4.5:
        return suggestions  # Already passes AA, no suggestions needed
    
    try:
        fg_color = Color(fg_hex)
        bg_color = Color(bg_hex)
        
        # Convert to OKLCH for perceptually uniform adjustments
        fg_oklch = fg_color.convert("oklch")
        bg_oklch = bg_color.convert("oklch")
        
        # Suggestion 1: Darken background
        bg_darker = bg_oklch.clone()
        bg_darker["lightness"] = max(0, bg_oklch["lightness"] - 0.15)
        new_bg_hex = bg_darker.convert("srgb").to_string(hex=True)
        new_ratio = calculate_contrast_ratio(fg_hex, new_bg_hex)
        
        if new_ratio > current_ratio:
            suggestions.append({
                "type": "darken_bg",
                "description": "Oscurecer el fondo",
                "new_contrast_ratio": round(new_ratio, 2),
                "preview_hex_fg": fg_hex,
                "preview_hex_bg": new_bg_hex,
            })
        
        # Suggestion 2: Lighten background
        bg_lighter = bg_oklch.clone()
        bg_lighter["lightness"] = min(1, bg_oklch["lightness"] + 0.15)
        new_bg_hex = bg_lighter.convert("srgb").to_string(hex=True)
        new_ratio = calculate_contrast_ratio(fg_hex, new_bg_hex)
        
        if new_ratio > current_ratio:
            suggestions.append({
                "type": "lighten_bg",
                "description": "Aclarar el fondo",
                "new_contrast_ratio": round(new_ratio, 2),
                "preview_hex_fg": fg_hex,
                "preview_hex_bg": new_bg_hex,
            })
        
        # Suggestion 3: Darken foreground
        fg_darker = fg_oklch.clone()
        fg_darker["lightness"] = max(0, fg_oklch["lightness"] - 0.15)
        new_fg_hex = fg_darker.convert("srgb").to_string(hex=True)
        new_ratio = calculate_contrast_ratio(new_fg_hex, bg_hex)
        
        if new_ratio > current_ratio:
            suggestions.append({
                "type": "darken_fg",
                "description": "Oscurecer el texto",
                "new_contrast_ratio": round(new_ratio, 2),
                "preview_hex_fg": new_fg_hex,
                "preview_hex_bg": bg_hex,
            })
        
        # Suggestion 4: Lighten foreground
        fg_lighter = fg_oklch.clone()
        fg_lighter["lightness"] = min(1, fg_oklch["lightness"] + 0.15)
        new_fg_hex = fg_lighter.convert("srgb").to_string(hex=True)
        new_ratio = calculate_contrast_ratio(new_fg_hex, bg_hex)
        
        if new_ratio > current_ratio:
            suggestions.append({
                "type": "lighten_fg",
                "description": "Aclarar el texto",
                "new_contrast_ratio": round(new_ratio, 2),
                "preview_hex_fg": new_fg_hex,
                "preview_hex_bg": bg_hex,
            })
        
        # Sort by best improvement
        suggestions.sort(key=lambda x: x["new_contrast_ratio"], reverse=True)
        
        # Return top 2 suggestions
        return suggestions[:2]
        
    except Exception as e:
        print(f"Error generating suggestions: {e}")
        return []


# ============================================================================
# MCP Tool Implementation
# ============================================================================

def check_color_accessibility(color_pairs: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Main MCP tool: Check color accessibility for multiple color pairs
    """
    results = []
    passed_count = 0
    failed_count = 0
    
    for pair in color_pairs:
        fg = pair["foreground"]
        bg = pair["background"]
        element = pair["element"]
        
        # Calculate contrast ratio
        ratio = calculate_contrast_ratio(fg, bg)
        
        # Evaluate WCAG compliance
        wcag_results = evaluate_wcag(ratio)
        
        # Generate suggestions if needed
        suggestions = generate_oklch_suggestions(fg, bg, ratio)
        
        # Determine if pair passes AA normal (most common requirement)
        if wcag_results["passes_aa_normal"]:
            passed_count += 1
        else:
            failed_count += 1
        
        results.append({
            "text_sample": element,
            "foreground": fg,
            "background": bg,
            "ratio": round(ratio, 2),
            **wcag_results,
            "suggestions": suggestions,
        })
    
    return {
        "total_pairs": len(color_pairs),
        "passed_pairs": passed_count,
        "failed_pairs": failed_count,
        "color_pairs": results,
    }


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Color Accessibility Checker MCP"}


@app.post("/mcp")
async def mcp_endpoint(request: JSONRPCRequest):
    """
    MCP JSON-RPC 2.0 endpoint
    Handles initialize, tools/list, and tools/call methods
    """
    
    # 1. Initialize Handshake
    if request.method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "color-accessibility-checker",
                    "version": "1.0.0"
                }
            }
        }
    
    # 2. List Available Tools
    elif request.method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": {
                "tools": [
                    {
                        "name": "check_color_accessibility",
                        "description": "Analiza pares de colores y evalúa su accesibilidad según estándares WCAG 2.0. Calcula ratios de contraste y proporciona sugerencias de mejora usando el espacio de color OKLCH.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "color_pairs": {
                                    "type": "array",
                                    "description": "Array de pares de colores a analizar",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "foreground": {
                                                "type": "string",
                                                "description": "Color del texto en formato hex (ej: #333333)"
                                            },
                                            "background": {
                                                "type": "string",
                                                "description": "Color del fondo en formato hex (ej: #FFFFFF)"
                                            },
                                            "element": {
                                                "type": "string",
                                                "description": "Descripción del elemento (ej: 'Título principal')"
                                            }
                                        },
                                        "required": ["foreground", "background", "element"]
                                    }
                                }
                            },
                            "required": ["color_pairs"]
                        }
                    }
                ]
            }
        }
    
    # 3. Call Tool
    elif request.method == "tools/call":
        tool_name = request.params.get("name")
        arguments = request.params.get("arguments", {})
        
        if tool_name == "check_color_accessibility":
            try:
                result = check_color_accessibility(arguments["color_pairs"])
                return {
                    "jsonrpc": "2.0",
                    "id": request.id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Análisis completado: {result['passed_pairs']} pares aprobados, {result['failed_pairs']} pares fallidos"
                            },
                            {
                                "type": "resource",
                                "resource": {
                                    "uri": f"widget://color-accessibility-results",
                                    "mimeType": "text/html+skybridge",
                                    "text": generate_widget_html(result)
                                }
                            }
                        ]
                    }
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": request.id,
                    "error": {
                        "code": -32603,
                        "message": f"Error processing request: {str(e)}"
                    }
                }
        else:
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "error": {
                    "code": -32601,
                    "message": f"Tool not found: {tool_name}"
                }
            }
            
    # Handle Ping (optional but good practice)
    elif request.method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": {}
        }
    
    # Unknown Method
    else:
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {request.method}"
            }
        }


@app.get("/widget")
async def widget_endpoint():
    """
    Test widget endpoint - returns sample HTML widget
    """
    sample_data = {
        "total_pairs": 2,
        "passed_pairs": 1,
        "failed_pairs": 1,
        "color_pairs": [
            {
                "text_sample": "Título principal",
                "foreground": "#333333",
                "background": "#FFFFFF",
                "ratio": 12.63,
                "passes_aa_normal": True,
                "passes_aa_large": True,
                "passes_aaa_normal": True,
                "passes_aaa_large": True,
                "suggestions": []
            },
            {
                "text_sample": "Enlace de navegación",
                "foreground": "#0066CC",
                "background": "#F5F5F5",
                "ratio": 4.12,
                "passes_aa_normal": False,
                "passes_aa_large": True,
                "passes_aaa_normal": False,
                "passes_aaa_large": False,
                "suggestions": [
                    {
                        "type": "darken_bg",
                        "description": "Oscurecer el fondo",
                        "new_contrast_ratio": 5.2,
                        "preview_hex_fg": "#0066CC",
                        "preview_hex_bg": "#E0E0E0"
                    }
                ]
            }
        ]
    }
    
    html = generate_widget_html(sample_data)
    return Response(content=html, media_type="text/html+skybridge")


# ============================================================================
# Widget HTML Generator
# ============================================================================

def generate_widget_html(data: Dict[str, Any]) -> str:
    """Generate interactive HTML widget for ChatGPT using user-provided template"""
    
    # Generate pairs HTML
    pairs_html = ""
    for pair in data["color_pairs"]:
        # Status classes and icons
        status_class = "pass" if pair["passes_aa_normal"] else "fail"
        ratio_class = "pass" if pair["passes_aa_normal"] else "fail"
        status_icon = "✅" if pair["passes_aa_normal"] else "❌"
        
        # AA/AAA badges
        aa_normal_class = "pass" if pair["passes_aa_normal"] else "fail"
        aa_normal_icon = "✓" if pair["passes_aa_normal"] else "✗"
        
        aa_large_class = "pass" if pair["passes_aa_large"] else "fail"
        aa_large_icon = "✓" if pair["passes_aa_large"] else "✗"
        
        aaa_normal_class = "pass" if pair["passes_aaa_normal"] else "fail"
        aaa_normal_icon = "✓" if pair["passes_aaa_normal"] else "✗"
        
        aaa_large_class = "pass" if pair["passes_aaa_large"] else "fail"
        aaa_large_icon = "✓" if pair["passes_aaa_large"] else "✗"
        
        # Suggestions
        suggestions_html = ""
        has_suggestions = bool(pair["suggestions"])
        
        if has_suggestions:
            sug_items = ""
            for sug in pair["suggestions"]:
                sug_items += f'<div class="suggestion-item">→ {sug["description"]} (Nuevo ratio: {sug["new_contrast_ratio"]}:1)</div>'
            
            suggestions_html = f"""
            <div class="suggestions">
                <div class="suggestions-title">💡 OKLCH Suggestions:</div>
                {sug_items}
            </div>
            """
        
        pairs_html += f"""
        <div class="pair-card {status_class}">
            <div class="pair-header">
                <span class="element-name">{pair['text_sample']}</span>
                <span class="ratio {ratio_class}">{pair['ratio']}:1 {status_icon}</span>
            </div>
            
            <div class="color-preview">
                <div class="color-box" style="background: {pair['background']}; color: {pair['foreground']};">Aa</div>
                <div class="color-info">
                    <div class="color-label">Text:</div>
                    <div class="color-hex">{pair['foreground']}</div>
                    <div class="color-label" style="margin-top: 8px;">Background:</div>
                    <div class="color-hex">{pair['background']}</div>
                </div>
            </div>

            <div class="badges">
                <span class="badge {aa_normal_class}">AA Normal {aa_normal_icon}</span>
                <span class="badge {aa_large_class}">AA Large {aa_large_icon}</span>
                <span class="badge {aaa_normal_class}">AAA Normal {aaa_normal_icon}</span>
                <span class="badge {aaa_large_class}">AAA Large {aaa_large_icon}</span>
            </div>

            {suggestions_html}
        </div>
        """
        
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            padding: 20px;
            background: white;
        }}
        .header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 24px;
        }}
        .header h1 {{
            font-size: 24px;
            font-weight: 600;
            color: #1a1a1a;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin-bottom: 24px;
        }}
        .summary-card {{
            padding: 16px;
            border-radius: 12px;
            text-align: center;
        }}
        .summary-card.total {{ background: #f5f5f5; }}
        .summary-card.passed {{ background: #d4f4dd; }}
        .summary-card.failed {{ background: #ffd4d4; }}
        .summary-card .number {{
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 4px;
        }}
        .summary-card .label {{
            font-size: 14px;
            color: #666;
        }}
        .pair-card {{
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 12px;
        }}
        .pair-card.fail {{
            border-color: #ff6b6b;
            background: #fff5f5;
        }}
        .pair-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}
        .element-name {{
            font-weight: 600;
            font-size: 16px;
            color: #1a1a1a;
        }}
        .ratio {{
            font-size: 18px;
            font-weight: 700;
        }}
        .ratio.pass {{ color: #2ea44f; }}
        .ratio.fail {{ color: #ff6b6b; }}
        .color-preview {{
            display: flex;
            gap: 16px;
            margin-bottom: 12px;
        }}
        .color-box {{
            width: 80px;
            height: 80px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            font-weight: 700;
            border: 2px solid #e0e0e0;
        }}
        .color-info {{
            flex: 1;
        }}
        .color-label {{
            font-size: 12px;
            color: #666;
            margin-bottom: 4px;
        }}
        .color-hex {{
            font-family: 'Courier New', monospace;
            font-size: 14px;
            color: #1a1a1a;
        }}
        .badges {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .badge {{
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
        }}
        .badge.pass {{
            background: #d4f4dd;
            color: #1a7f37;
        }}
        .badge.fail {{
            background: #ffd4d4;
            color: #cf222e;
        }}
        .suggestions {{
            margin-top: 12px;
            padding: 12px;
            background: #f8f9fa;
            border-radius: 8px;
        }}
        .suggestions-title {{
            font-size: 12px;
            color: #666;
            margin-bottom: 8px;
        }}
        .suggestion-item {{
            font-size: 14px;
            color: #1a1a1a;
            padding: 4px 0;
        }}
    </style>
</head>
<body>
    <div class="header">
        <span style="font-size: 28px;">🎨</span>
        <h1>Color Accessibility Check</h1>
    </div>

    <div class="summary">
        <div class="summary-card total">
            <div class="number">{data['total_pairs']}</div>
            <div class="label">Total Pairs</div>
        </div>
        <div class="summary-card passed">
            <div class="number">✅ {data['passed_pairs']}</div>
            <div class="label">Passed</div>
        </div>
        <div class="summary-card failed">
            <div class="number">❌ {data['failed_pairs']}</div>
            <div class="label">Failed</div>
        </div>
    </div>

    {pairs_html}
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
