"""
🎨 Color Accessibility Checker - MCP Server
FastAPI server that checks color accessibility according to WCAG standards
"""

import os
import json
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
    Legacy function - mostly replaced by logic inside mcp_endpoint for new format,
    but kept for reference if needed.
    """
    # This logic is now moved to mcp_endpoint to format specifically for the new widget structure
    pass


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
                # Process color pairs
                color_pairs = arguments.get("color_pairs", [])
                processed_pairs = []
                passed_count = 0
                failed_count = 0
                
                for idx, pair in enumerate(color_pairs):
                    fg = pair["foreground"]
                    bg = pair["background"]
                    element = pair["element"]
                    
                    ratio = calculate_contrast_ratio(fg, bg)
                    wcag = evaluate_wcag(ratio)
                    suggestions = generate_oklch_suggestions(fg, bg, ratio)
                    
                    is_pass = wcag["passes_aa_normal"]
                    if is_pass:
                        passed_count += 1
                    else:
                        failed_count += 1
                    
                    # Map suggestions to new format
                    formatted_suggestions = []
                    for sug in suggestions:
                        formatted_suggestions.append({
                            "type": sug["type"],
                            "background_oklch": "", # Advanced OKLCH string could be added here
                            "foreground_oklch": "",
                            "new_contrast_ratio": sug["new_contrast_ratio"],
                            "preview_hex_bg": sug["preview_hex_bg"],
                            "preview_hex_fg": sug["preview_hex_fg"]
                        })

                    processed_pairs.append({
                        "id": f"pair-{idx}",
                        "text": element,
                        "background": bg,
                        "foreground": fg,
                        "contrast_ratio": round(ratio, 2),
                        "wcag_aa": {
                            "normal_text": wcag["passes_aa_normal"],
                            "large_text": wcag["passes_aa_large"]
                        },
                        "wcag_aaa": {
                            "normal_text": wcag["passes_aaa_normal"],
                            "large_text": wcag["passes_aaa_large"]
                        },
                        "status": "pass" if is_pass else "fail",
                        "suggestions": formatted_suggestions
                    })
                
                # Construct final results object matching reference schema
                results = {
                    "summary": {
                        "total_pairs": len(color_pairs),
                        "passing_pairs": passed_count,
                        "failing_pairs": failed_count,
                        "detected_texts": len(color_pairs)
                    },
                    "color_pairs": processed_pairs
                }
                
                # Read template and inject data
                template_path = os.path.join(os.path.dirname(__file__), 'widget-template.html')
                with open(template_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                # Inject data into template
                results_json = json.dumps(results)
                html_content = html_content.replace(
                    'const sampleData = {',
                    f'const sampleData = {results_json}; \n const _ignored = {{'
                )
                
                return {
                    "jsonrpc": "2.0",
                    "id": request.id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Analysis complete: {passed_count} passed, {failed_count} failed."
                            },
                            {
                                "type": "resource",
                                "resource": {
                                    "uri": "ui://widget/color-accessibility.html",
                                    "mimeType": "text/html",
                                    "text": html_content
                                }
                            }
                        ]
                    }
                }
            except Exception as e:
                import traceback
                print(traceback.format_exc())
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
            
    elif request.method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": {}
        }
    
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
    # For quick testing, using dummy data with the new template mechanism
    sample_results = {
        "summary": {
            "total_pairs": 1,
            "passing_pairs": 0,
            "failing_pairs": 1,
            "detected_texts": 1
        },
        "color_pairs": [
             {
                "id": "pair-0",
                "text": "Example Text",
                "background": "#FFFFFF",
                "foreground": "#EEEEEE",
                "contrast_ratio": 1.08,
                "wcag_aa": {"normal_text": False, "large_text": False},
                "wcag_aaa": {"normal_text": False, "large_text": False},
                "status": "fail",
                "suggestions": []
            }
        ]
    }
    
    template_path = os.path.join(os.path.dirname(__file__), 'widget-template.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    results_json = json.dumps(sample_results)
    html_content = html_content.replace(
        'const sampleData = {',
        f'const sampleData = {results_json}; \n const _ignored = {{'
    )
    
    return Response(content=html_content, media_type="text/html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
