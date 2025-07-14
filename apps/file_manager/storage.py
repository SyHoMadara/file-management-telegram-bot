from django_minio_backend.storage import MinioBackend
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

class DispositionMinioBackend(MinioBackend):
    def url(self, name):
        # Get the original signed URL
        url = super().url(name)
        
        # Parse the URL
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        
        # Add response-content-disposition
        filename = name.split('/')[-1]  # Extract the filename from the object name
        query['response-content-disposition'] = [f'attachment; filename="{filename}"']
        
        # Reconstruct the query string
        new_query = urlencode(query, doseq=True)
        
        # Reconstruct the URL with the new query string
        new_url = urlunparse(parsed._replace(query=new_query))
        
        return new_url