import httpx
from typing import Optional, Dict, Any

class MetadataFetcher:
    """Busca metadados na web usando a API pública do Google Books."""
    
    BASE_URL = "https://www.googleapis.com/books/v1/volumes"
    
    def __init__(self):
        self._client = httpx.Client(timeout=10.0)
        
    def search_book(self, title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Busca um livro por título e autor e retorna seus metadados."""
        query = f"intitle:{title}"
        if author:
            query += f"+inauthor:{author}"
            
        params = {
            "q": query,
            "maxResults": 1,
            "langRestrict": "pt"  # Pode ser customizável
        }
        
        try:
            response = self._client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            items = data.get("items", [])
            if not items:
                # Tenta sem langRestrict se não encontrar
                params.pop("langRestrict")
                response = self._client.get(self.BASE_URL, params=params)
                data = response.json()
                items = data.get("items", [])
                
            if items:
                volume = items[0].get("volumeInfo", {})
                return self._parse_volume_info(volume)
        except Exception as e:
            print(f"Erro ao buscar metadados: {e}")
            return None
            
        return None

    def _parse_volume_info(self, volume: Dict[str, Any]) -> Dict[str, Any]:
        """Extrai apenas os campos necessários do JSON retornado pelo Google."""
        metadata = {
            "title": volume.get("title", ""),
            "author": ", ".join(volume.get("authors", [])),
            "publisher": volume.get("publisher", ""),
            "published_year": volume.get("publishedDate", "")[:4] if volume.get("publishedDate") else "",
            "description": volume.get("description", ""),
            "page_count": volume.get("pageCount", 0),
            "categories": volume.get("categories", []),
            "isbn": "",
            "cover_url": ""
        }
        
        for identifier in volume.get("industryIdentifiers", []):
            if identifier.get("type") in ("ISBN_13", "ISBN_10"):
                metadata["isbn"] = identifier.get("identifier")
                break
                
        image_links = volume.get("imageLinks", {})
        # Tenta pegar a maior resolução possível
        for key in ["extraLarge", "large", "medium", "small", "thumbnail", "smallThumbnail"]:
            if key in image_links:
                metadata["cover_url"] = image_links[key].replace("http:", "https:")
                break
                
        return metadata
        
    def download_cover(self, url: str) -> Optional[bytes]:
        """Faz o download da capa de um livro como bytes."""
        if not url:
            return None
            
        try:
            response = self._client.get(url)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"Erro ao baixar capa: {e}")
            return None
            
    def close(self):
        """Fecha a sessão do cliente HTTP."""
        self._client.close()
