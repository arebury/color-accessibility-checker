# 🎨 Color Accessibility Checker

Servidor MCP (Model Context Protocol) para ChatGPT que verifica la accesibilidad de colores según estándares WCAG 2.0. Calcula ratios de contraste y proporciona sugerencias de mejora usando el espacio de color OKLCH.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com)

## 📋 Características

- ✅ **Verificación WCAG 2.0**: Evalúa compliance con niveles AA y AAA
- 🎨 **Sugerencias OKLCH**: Ajustes perceptualmente uniformes de color
- 📊 **Widget Interactivo**: Visualización embebida en ChatGPT
- 🚀 **Deploy Automático**: Configurado para Render con auto-deploy desde GitHub
- ⚡ **FastAPI**: API rápida y moderna con JSON-RPC 2.0

## 🏗 Arquitectura

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│                 │    │                  │    │                 │
│   Usuario       │───▶│   ChatGPT        │───▶│   MCP Server    │
│ (sube imagen)   │    │   (Vision)       │    │   (FastAPI)     │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │                         │
                              │ Extrae colores          │ Calcula WCAG
                              │ hex (#RRGGBB)           │ + sugerencias
                              │                         │
                              ▼                         ▼
                       ┌──────────────────────────────────────┐
                       │                                      │
                       │        Widget HTML/JS                │
                       │     (embebido en ChatGPT)            │
                       │                                      │
                       └──────────────────────────────────────┘
```

## 📁 Estructura del Proyecto

```
color-accessibility-checker/
│
├── server/
│   ├── main.py              # Servidor FastAPI + lógica MCP
│   └── requirements.txt     # Dependencias Python
│
├── render.yaml              # Configuración de Render
├── .gitignore
└── README.md
```

## 🚀 Instalación

### Requisitos Previos

- Python 3.11+
- pip

### Instalación Local

```bash
# Clonar el repositorio
git clone https://github.com/rafa-areses-db/color-accessibility-checker.git
cd color-accessibility-checker

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r server/requirements.txt

# Ejecutar servidor
cd server
uvicorn main:app --reload
```

El servidor estará disponible en `http://localhost:8000`

### Deploy en Render

1. **Fork o clona este repositorio** en tu cuenta de GitHub

2. **Conecta tu repositorio a Render**:
   - Ve a [Render Dashboard](https://dashboard.render.com/)
   - Click en "New +" → "Blueprint"
   - Conecta tu repositorio de GitHub
   - Render detectará automáticamente el `render.yaml`

3. **Deploy automático**:
   - Cada push a la rama `main` desplegará automáticamente
   - El servicio estará disponible en: `https://color-accessibility-checker.onrender.com`

## 💻 Uso

### Configurar en ChatGPT

1. Ve a **ChatGPT** → **Settings** → **Actions**
2. Crea una nueva Action con:
   - **Name**: Color Accessibility Checker
   - **Schema URL**: `https://tu-dominio.onrender.com/mcp`
   - **Authentication**: None

### Analizar Colores

En ChatGPT, simplemente pregunta:

```
"Analiza la accesibilidad de estos colores:
- Texto #333333 sobre fondo #FFFFFF
- Enlace #0066CC sobre fondo #F5F5F5"
```

ChatGPT usará el MCP server para analizar los colores y mostrará un widget interactivo con:
- Ratios de contraste
- Badges AA/AAA (aprobado/fallido)
- Sugerencias de mejora con previews

## 🔌 API

### Endpoints

#### `GET /`
Health check del servidor.

**Response**:
```json
{
  "status": "healthy",
  "service": "Color Accessibility Checker MCP"
}
```

#### `POST /mcp`
Endpoint principal MCP (JSON-RPC 2.0).

**Métodos soportados**:
- `tools/list`: Lista las herramientas disponibles
- `tools/call`: Ejecuta la herramienta `check_color_accessibility`

**Ejemplo de request**:
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "check_color_accessibility",
    "arguments": {
      "color_pairs": [
        {
          "foreground": "#333333",
          "background": "#FFFFFF",
          "element": "Título principal"
        }
      ]
    }
  },
  "id": 1
}
```

**Ejemplo de response**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Análisis completado: 1 pares aprobados, 0 pares fallidos"
      },
      {
        "type": "resource",
        "resource": {
          "uri": "widget://color-accessibility-results",
          "mimeType": "text/html+skybridge",
          "text": "<!DOCTYPE html>..."
        }
      }
    ]
  }
}
```

#### `GET /widget`
Endpoint de prueba que retorna un widget HTML de ejemplo.

**Response**: HTML con `Content-Type: text/html+skybridge`

## 📊 Estándares WCAG

El servidor evalúa los siguientes niveles de conformidad:

| Nivel | Texto Normal | Texto Grande |
|-------|--------------|--------------|
| **AA** | 4.5:1 | 3:1 |
| **AAA** | 7:1 | 4.5:1 |

**Texto grande** se define como:
- 18pt (24px) o mayor
- 14pt (18.66px) en negrita o mayor

## 🛠 Tecnologías

- **[FastAPI](https://fastapi.tiangolo.com/)**: Framework web moderno y rápido
- **[Uvicorn](https://www.uvicorn.org/)**: Servidor ASGI de alto rendimiento
- **[ColorAide](https://facelessuser.github.io/coloraide/)**: Manipulación de colores en OKLCH
- **[Render](https://render.com/)**: Plataforma de deployment con auto-deploy

## 📝 Licencia

MIT License - ver [LICENSE](LICENSE) para más detalles.

## 👤 Autor

**Rafael Areses**
- GitHub: [@rafa-areses-db](https://github.com/rafa-areses-db)

## 🙏 Agradecimientos

- [WCAG 2.0 Guidelines](https://www.w3.org/TR/WCAG20/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [OpenAI Apps SDK](https://github.com/openai/openai-apps-sdk-examples)

---

**¿Preguntas o sugerencias?** Abre un [issue](https://github.com/rafa-areses-db/color-accessibility-checker/issues) en GitHub.
