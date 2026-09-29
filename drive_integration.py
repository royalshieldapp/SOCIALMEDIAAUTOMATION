"""Google Drive integration for selecting brand media assets."""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger("socialmediaautomation.drive")

# Regex to extract Google Drive Folder ID from standard sharing URLs
DRIVE_FOLDER_REGEX = r"(?:folders\/|id=)([a-zA-Z0-9_-]{20,})"
DRIVE_FILE_REGEX = r"(?:file\/d\/|id=)([a-zA-Z0-9_-]{20,})"


def extract_folder_id(value: str) -> str:
    value = value.strip()
    match = re.search(DRIVE_FOLDER_REGEX, value)
    if match:
        return match.group(1)
    if re.fullmatch(r"^[a-zA-Z0-9_-]{20,}$", value):
        return value
    return value


def get_drive_api_key() -> str:
    return (os.getenv("GOOGLE_DRIVE_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()


def get_default_folder_id() -> str:
    raw = os.getenv("GOOGLE_DRIVE_FOLDER_ID") or os.getenv("GOOGLE_DRIVE_FOLDER_URL") or ""
    return extract_folder_id(raw)


def build_direct_download_url(file_id: str, base_host: Optional[str] = None) -> str:
    """Retorna la URL pública directa para que Meta Graph API descargue la imagen."""
    if base_host:
        return f"{base_host.rstrip('/')}/drive/proxy/{file_id}"
    return f"https://lh3.googleusercontent.com/d/{file_id}"


async def fetch_folder_images(folder_id_or_url: Optional[str] = None, base_host: Optional[str] = None) -> Dict[str, Any]:
    folder_id = extract_folder_id(folder_id_or_url or get_default_folder_id())
    if not folder_id:
        return {
            "ok": False,
            "error": "No se ha proporcionado una carpeta de Google Drive. Pega la URL o el ID de la carpeta compartida.",
            "images": []
        }

    api_key = get_drive_api_key()
    
    # 1. Si hay Google API Key, usamos la API oficial de Drive v3
    if api_key:
        query = f"'{folder_id}' in parents and (mimeType contains 'image/') and trashed = false"
        url = "https://www.googleapis.com/drive/v3/files"
        params = {
            "q": query,
            "key": api_key,
            "fields": "files(id, name, mimeType, thumbnailLink, webViewLink)",
            "pageSize": 50
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    files = data.get("files", [])
                    images = []
                    for f in files:
                        fid = f["id"]
                        images.append({
                            "id": fid,
                            "name": f.get("name", "imagen.jpg"),
                            "thumbnail": f.get("thumbnailLink") or f"https://lh3.googleusercontent.com/d/{fid}=s220",
                            "direct_url": build_direct_download_url(fid, base_host),
                            "view_url": f.get("webViewLink")
                        })
                    return {
                        "ok": True,
                        "folder_id": folder_id,
                        "count": len(images),
                        "images": images,
                        "source": "drive_api"
                    }
                else:
                    logger.warning("Drive API devolvió %s: %s", res.status_code, res.text[:200])
        except Exception as exc:
            logger.warning("Error al consultar Google Drive API: %s", exc)

    # 2. Modo fallback para carpetas públicas sin API Key:
    # Si la carpeta es pública ('Cualquier persona con el enlace'), podemos hacer scraping seguro del HTML inicial de Drive
    folder_url = f"https://drive.google.com/embeddedfolderview?id={folder_id}"
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            res = await client.get(folder_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            if res.status_code == 200:
                html = res.text
                # Buscar IDs de archivos en el HTML embebido
                matches = re.findall(r'id="entry-([a-zA-Z0-9_-]{25,})"', html)
                if not matches:
                    matches = list(set(re.findall(r'https:\/\/drive\.google\.com\/file\/d\/([a-zA-Z0-9_-]{25,})', html)))
                
                images = []
                for idx, fid in enumerate(matches[:40]):
                    images.append({
                        "id": fid,
                        "name": f"Imagen {idx + 1} de Drive",
                        "thumbnail": f"https://lh3.googleusercontent.com/d/{fid}=s300",
                        "direct_url": build_direct_download_url(fid, base_host),
                        "view_url": f"https://drive.google.com/file/d/{fid}/view"
                    })
                return {
                    "ok": True,
                    "folder_id": folder_id,
                    "count": len(images),
                    "images": images,
                    "source": "public_folder_view"
                }
    except Exception as exc:
        logger.warning("Error en scraping de carpeta pública de Drive: %s", exc)

    return {
        "ok": False,
        "folder_id": folder_id,
        "error": "No se pudieron listar las imágenes. Asegúrate de que la carpeta de Google Drive esté compartida como 'Cualquier persona con el enlace puede ver'.",
        "images": []
    }


async def stream_drive_file(file_id: str) -> httpx.Response:
    """Descarga el stream del archivo de Google Drive para servirlo a Meta como proxy."""
    # Google Drive export endpoint para descarga directa
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    response = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    return response
