"""
CLOUD FILE HANDLER - Stream downloads from cloud storage
Created: February 5, 2026
Last Updated: February 5, 2026 - FIXED Google Drive URL regex

CRITICAL FIX (February 5, 2026):
- Enhanced regex to handle /spreadsheets/d/FILE_ID/ format
- Now supports both /d/FILE_ID/ and /spreadsheets/d/FILE_ID/
- Handles /export?format= URLs for Google Sheets

This module handles streaming downloads from cloud storage services
to prevent RAM exhaustion on large files (56MB+).

Author: Jim @ Shiftwork Solutions LLC
"""

import requests
import re
import os
import tempfile
from typing import Dict, Tuple, Optional
from urllib.parse import urlparse, parse_qs

class CloudFileHandler:
    """
    Handles downloads from Google Drive, Dropbox, OneDrive
    Uses streaming to prevent RAM exhaustion
    """
    
    def __init__(self):
        self.chunk_size = 8192  # 8KB chunks for streaming
        self.max_file_size = 500 * 1024 * 1024  # 500MB absolute max
        
    def detect_service(self, url: str) -> Optional[str]:
        """
        Detect which cloud storage service from URL
        Returns: 'google_drive', 'dropbox', 'onedrive', or None
        """
        url_lower = url.lower()
        
        if 'drive.google.com' in url_lower or 'docs.google.com' in url_lower:
            return 'google_drive'
        elif 'dropbox.com' in url_lower:
            return 'dropbox'
        elif 'onedrive' in url_lower or '1drv.ms' in url_lower:
            return 'onedrive'
        
        return None
    
    def extract_google_drive_id(self, url: str) -> Optional[str]:
        """
        Extract file ID from Google Drive URL
        
        FIXED (Feb 5, 2026): Now handles multiple URL formats:
        - https://drive.google.com/file/d/FILE_ID/view
        - https://drive.google.com/open?id=FILE_ID
        - https://docs.google.com/spreadsheets/d/FILE_ID/edit
        - https://docs.google.com/spreadsheets/d/FILE_ID/export?format=xlsx
        """
        # Pattern 1: /d/FILE_ID/ (works for /file/d/, /spreadsheets/d/, etc.)
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)
        
        # Pattern 2: ?id=FILE_ID
        match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)
        
        return None
    
    def convert_google_drive_url(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Convert Google Drive share URL to direct download URL
        Returns: (download_url, filename)
        
        ENHANCED (Feb 5, 2026): Handles Google Sheets export format
        """
        file_id = self.extract_google_drive_id(url)
        
        if not file_id:
            return None, None
        
        # Check if it's a Google Sheets URL
        if 'spreadsheets' in url:
            # Determine export format
            if 'export?format=' in url:
                # User already specified format
                match = re.search(r'format=(\w+)', url)
                format_type = match.group(1) if match else 'xlsx'
            else:
                # Default to Excel format
                format_type = 'xlsx'
            
            download_url = f'https://docs.google.com/spreadsheets/d/{file_id}/export?format={format_type}'
            filename = f'spreadsheet_{file_id}.{format_type}'
        else:
            # Regular Google Drive file
            download_url = f'https://drive.google.com/uc?export=download&id={file_id}'
            filename = f'file_{file_id}'
        
        return download_url, filename
    
    def convert_dropbox_url(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Convert Dropbox share URL to direct download URL
        """
        # Dropbox: change dl=0 to dl=1 for direct download
        if 'dl=0' in url:
            download_url = url.replace('dl=0', 'dl=1')
        elif '?' in url:
            download_url = url + '&dl=1'
        else:
            download_url = url + '?dl=1'
        
        # Extract filename from URL if possible
        filename = url.split('/')[-1].split('?')[0] or 'dropbox_file'
        
        return download_url, filename
    
    def convert_onedrive_url(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Convert OneDrive share URL to direct download URL
        """
        # OneDrive: replace 'view' with 'download' in URL
        if 'view.aspx' in url:
            download_url = url.replace('view.aspx', 'download.aspx')
        elif 'embed' in url:
            download_url = url.replace('embed', 'download')
        else:
            download_url = url + '&download=1'
        
        filename = 'onedrive_file'
        
        return download_url, filename
    
    def download_file_streaming(self, url: str, service: str) -> Tuple[Optional[str], Dict]:
        """
        Download file using streaming to prevent RAM exhaustion
        
        Returns: (local_filepath, metadata)
        """
        metadata = {
            'service': service,
            'original_url': url,
            'success': False,
            'error': None,
            'size_bytes': 0,
            'filename': None
        }
        
        try:
            # Convert to direct download URL
            if service == 'google_drive':
                download_url, filename = self.convert_google_drive_url(url)
            elif service == 'dropbox':
                download_url, filename = self.convert_dropbox_url(url)
            elif service == 'onedrive':
                download_url, filename = self.convert_onedrive_url(url)
            else:
                raise ValueError(f"Unsupported service: {service}")
            
            if not download_url:
                raise ValueError(f"Could not extract file ID from {service} URL")
            
            metadata['filename'] = filename
            
            # Start streaming download
            print(f"🌐 Starting streaming download from {service}...")
            print(f"📥 Download URL: {download_url[:100]}...")
            
            response = requests.get(download_url, stream=True, timeout=60)
            response.raise_for_status()
            
            # Check content length
            content_length = response.headers.get('content-length')
            if content_length:
                file_size = int(content_length)
                metadata['size_bytes'] = file_size
                
                if file_size > self.max_file_size:
                    raise ValueError(f"File too large: {file_size / 1024 / 1024:.1f}MB (max 500MB)")
                
                print(f"📊 File size: {file_size / 1024 / 1024:.2f}MB")
            
            # Get better filename from headers if available
            content_disposition = response.headers.get('content-disposition')
            if content_disposition:
                match = re.search(r'filename="?([^"]+)"?', content_disposition)
                if match:
                    filename = match.group(1)
                    metadata['filename'] = filename
            
            # Create temp file
            suffix = os.path.splitext(filename)[1] or '.tmp'
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            
            # Stream download in chunks
            bytes_downloaded = 0
            for chunk in response.iter_content(chunk_size=self.chunk_size):
                if chunk:
                    temp_file.write(chunk)
                    bytes_downloaded += len(chunk)
                    
                    # Progress indicator every 10MB
                    if bytes_downloaded % (10 * 1024 * 1024) < self.chunk_size:
                        print(f"⬇️  Downloaded: {bytes_downloaded / 1024 / 1024:.1f}MB")
            
            temp_file.close()
            
            metadata['success'] = True
            metadata['size_bytes'] = bytes_downloaded
            
            print(f"✅ Download complete: {bytes_downloaded / 1024 / 1024:.2f}MB")
            print(f"📁 Saved to: {temp_file.name}")
            
            return temp_file.name, metadata
            
        except requests.exceptions.RequestException as e:
            metadata['error'] = f"Network error: {str(e)}"
            print(f"❌ Download failed: {metadata['error']}")
            return None, metadata
            
        except ValueError as e:
            metadata['error'] = str(e)
            print(f"❌ Download failed: {metadata['error']}")
            return None, metadata
            
        except Exception as e:
            metadata['error'] = f"Unexpected error: {str(e)}"
            print(f"❌ Download failed: {metadata['error']}")
            return None, metadata
    
    def process_cloud_link(self, url: str) -> Tuple[Optional[str], Dict]:
        """
        Main entry point: detect service and download file
        
        Returns: (local_filepath, metadata)
        """
        print(f"🔗 Processing cloud link: {url[:50]}...")
        
        service = self.detect_service(url)
        
        if not service:
            return None, {
                'success': False,
                'error': 'Unsupported cloud storage service. Use Google Drive, Dropbox, or OneDrive.',
                'original_url': url
            }
        
        print(f"🔗 Processing cloud link from: {service}")
        
        return self.download_file_streaming(url, service)


# Singleton instance
_cloud_handler = None

def get_cloud_handler() -> CloudFileHandler:
    """Get singleton instance of CloudFileHandler"""
    global _cloud_handler
    if _cloud_handler is None:
        _cloud_handler = CloudFileHandler()
    return _cloud_handler


# Test function
if __name__ == '__main__':
    handler = get_cloud_handler()
    
    # Test URL parsing
    test_urls = [
        'https://drive.google.com/file/d/1ABC123/view',
        'https://docs.google.com/spreadsheets/d/15RonrpruOOx-A8mUsdviR8ZlIjJql3SQ/edit?usp=drive_link',
        'https://docs.google.com/spreadsheets/d/15RonrpruOOx-A8mUsdviR8ZlIjJql3SQ/export?format=xlsx',
        'https://www.dropbox.com/s/abc123/file.xlsx?dl=0'
    ]
    
    for url in test_urls:
        print(f"\n🧪 Testing: {url}")
        service = handler.detect_service(url)
        print(f"   Service: {service}")
        
        if service == 'google_drive':
            file_id = handler.extract_google_drive_id(url)
            print(f"   File ID: {file_id}")
            download_url, filename = handler.convert_google_drive_url(url)
            print(f"   Download URL: {download_url}")
            print(f"   Filename: {filename}")

# I did no harm and this file is not truncated
