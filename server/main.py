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
    """Generate interactive HTML widget for ChatGPT"""
    
    pairs_html = ""
    for pair in data["color_pairs"]:
        # Status badges
        aa_badge = "✓ AA" if pair["passes_aa_normal"] else "✗ AA"
        aaa_badge = "✓ AAA" if pair["passes_aaa_normal"] else "✗ AAA"
        aa_class = "pass" if pair["passes_aa_normal"] else "fail"
        aaa_class = "pass" if pair["passes_aaa_normal"] else "fail"
        
        # Suggestions section
        suggestions_html = ""
        if pair["suggestions"]:
            suggestions_html = "<div class='suggestions'><strong>💡 Sugerencias:</strong><ul>"
            for sug in pair["suggestions"]:
                suggestions_html += f"""
                <li>
                    <span>{sug['description']}</span>
                    <span class='suggestion-ratio'>Nuevo ratio: {sug['new_contrast_ratio']}:1</span>
                    <div class='suggestion-preview' style='background: {sug["preview_hex_bg"]}; color: {sug["preview_hex_fg"]}'>
                        Aa
                    </div>
                </li>
                """
            suggestions_html += "</ul></div>"
        
        pairs_html += f"""
        <div class='color-pair'>
            <div class='pair-header'>
                <h3>{pair['text_sample']}</h3>
                <div class='badges'>
                    <span class='badge {aa_class}'>{aa_badge}</span>
                    <span class='badge {aaa_class}'>{aaa_badge}</span>
                </div>
            </div>
            <div class='color-preview' style='background: {pair["background"]}; color: {pair["foreground"]}'>
                <span class='preview-text'>Aa</span>
            </div>
            <div class='pair-details'>
                <div class='detail-row'>
                    <span class='label'>Contraste:</span>
                    <span class='value'>{pair['ratio']}:1</span>
                </div>
                <div class='detail-row'>
                    <span class='label'>Texto:</span>
                    <span class='value'>{pair['foreground']}</span>
                </div>
                <div class='detail-row'>
                    <span class='label'>Fondo:</span>
                    <span class='value'>{pair['background']}</span>
                </div>
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
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 24px;
                color: #1a202c;
            }}
            
            .container {{
                max-width: 800px;
                margin: 0 auto;
            }}
            
            .header {{
                background: white;
                border-radius: 16px;
                padding: 24px;
                margin-bottom: 20px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            }}
            
            .header h1 {{
                font-size: 28px;
                margin-bottom: 16px;
                color: #2d3748;
                display: flex;
                align-items: center;
                gap: 12px;
            }}
            
            .summary {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 16px;
                margin-top: 16px;
            }}
            
            .summary-item {{
                text-align: center;
                padding: 16px;
                background: #f7fafc;
                border-radius: 12px;
                border: 2px solid #e2e8f0;
            }}
            
            .summary-item .number {{
                font-size: 32px;
                font-weight: bold;
                display: block;
                margin-bottom: 4px;
            }}
            
            .summary-item.total .number {{ color: #667eea; }}
            .summary-item.passed .number {{ color: #48bb78; }}
            .summary-item.failed .number {{ color: #f56565; }}
            
            .summary-item .label {{
                font-size: 14px;
                color: #718096;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            
            .color-pair {{
                background: white;
                border-radius: 16px;
                padding: 24px;
                margin-bottom: 16px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.08);
                transition: transform 0.2s, box-shadow 0.2s;
            }}
            
            .color-pair:hover {{
                transform: translateY(-2px);
                box-shadow: 0 8px 30px rgba(0,0,0,0.12);
            }}
            
            .pair-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 16px;
            }}
            
            .pair-header h3 {{
                font-size: 20px;
                color: #2d3748;
            }}
            
            .badges {{
                display: flex;
                gap: 8px;
            }}
            
            .badge {{
                padding: 6px 12px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            
            .badge.pass {{
                background: #c6f6d5;
                color: #22543d;
            }}
            
            .badge.fail {{
                background: #fed7d7;
                color: #742a2a;
            }}
            
            .color-preview {{
                height: 100px;
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                margin-bottom: 16px;
                border: 2px solid #e2e8f0;
            }}
            
            .preview-text {{
                font-size: 48px;
                font-weight: bold;
            }}
            
            .pair-details {{
                background: #f7fafc;
                border-radius: 8px;
                padding: 16px;
            }}
            
            .detail-row {{
                display: flex;
                justify-content: space-between;
                padding: 8px 0;
                border-bottom: 1px solid #e2e8f0;
            }}
            
            .detail-row:last-child {{
                border-bottom: none;
            }}
            
            .detail-row .label {{
                font-weight: 600;
                color: #4a5568;
            }}
            
            .detail-row .value {{
                font-family: 'Courier New', monospace;
                color: #2d3748;
            }}
            
            .suggestions {{
                margin-top: 16px;
                padding: 16px;
                background: #fffaf0;
                border-radius: 8px;
                border-left: 4px solid #ed8936;
            }}
            
            .suggestions strong {{
                display: block;
                margin-bottom: 12px;
                color: #744210;
            }}
            
            .suggestions ul {{
                list-style: none;
            }}
            
            .suggestions li {{
                padding: 12px;
                background: white;
                border-radius: 6px;
                margin-bottom: 8px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 12px;
            }}
            
            .suggestion-ratio {{
                font-size: 12px;
                color: #718096;
                font-weight: 600;
            }}
            
            .suggestion-preview {{
                width: 40px;
                height: 40px;
                border-radius: 6px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                border: 2px solid #e2e8f0;
            }}
        </style>
    </head>
    <body>
        <div class='container'>
            <div class='header'>
                <h1>🎨 Análisis de Accesibilidad de Colores</h1>
                <div class='summary'>
                    <div class='summary-item total'>
                        <span class='number'>{data['total_pairs']}</span>
                        <span class='label'>Total</span>
                    </div>
                    <div class='summary-item passed'>
                        <span class='number'>{data['passed_pairs']}</span>
                        <span class='label'>Aprobados</span>
                    </div>
                    <div class='summary-item failed'>
                        <span class='number'>{data['failed_pairs']}</span>
                        <span class='label'>Fallidos</span>
                    </div>
                </div>
            </div>
            {pairs_html}
        </div>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
