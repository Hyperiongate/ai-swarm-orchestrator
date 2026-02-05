"""
CLOUD FILE HANDLER - Stream downloads from cloud storage
Created: February 5, 2026
Last Updated: February 5, 2026 - ADDED GOOGLE SERVICE ACCOUNT AUTHENTICATION

CHANGE LOG:
- February 5, 2026 (v3): MAJOR FIX - Google Drive API authentication
  * HTTP 432 error: Google blocks unauthenticated server-side downloads
  * Added Google Service Account authentication via GOOGLE_SERVICE_ACCOUNT_JSON env var
  * Uses google-api-python-client for proper authenticated downloads
  * Falls back to unauthenticated requests.get() for Dropbox/OneDrive
  * Streaming download preserved to prevent RAM exhaustion on large files
  * Service account credentials loaded from environment variable (JSON string)
  * Requires: google-api-python-client, google-auth in requirements.txt
  * Requires: GOOGLE_SERVICE_ACCOUNT_JSON env var in Render
  * Requires: Google Sheet shared with service account email (Viewer access)

- February 5, 2026 (v2): FIXED Google Drive URL regex
  * Enhanced regex to handle /spreadsheets/d/FILE_ID/ format
  * Now supports both /d/FILE_ID/ and /spreadsheets/d/FILE_ID/
  * Handles /export?format= URLs for Google Sheets

- February 5, 2026 (v1): Initial creation
  * Streaming downloads from Google Drive, Dropbox, OneDrive
  * 8KB chunk streaming to prevent RAM exhaustion
  * 500MB max file size, 5-minute download timeout

This module handles streaming downloads from cloud storage services
to prevent RAM exhaustion on large files (56MB+).

Author: Jim @ Shiftwork Solutions LLC
"""

import requests
import re
import os
import io
import json
import tempfile
from typing import Dict, Tuple, Optional
from urllib.parse import urlparse, parse_qs

# Google API imports for authenticated downloads
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    print("⚠️ Google API libraries not installed. Install: google-api-python-client google-auth")


class CloudFileHandler:
    """
    Handles downloads from Google Drive, Dropbox, OneDrive
    Uses streaming to prevent RAM exhaustion
    
    For Google Drive: Uses Service Account authentication to avoid HTTP 432 blocks
    For Dropbox/OneDrive: Uses direct URL conversion with requests
    """
    
    def __init__(self):
        self.chunk_size = 8192  # 8KB chunks for streaming
        self.max_file_size = 500 * 1024 * 1024  # 500MB absolute max
        self._drive_service = None  # Cached Google Drive service
        
    def _get_drive_service(self):
        """
        Initialize Google Drive API service using service account credentials.
        Credentials are loaded from GOOGLE_SERVICE_ACCOUNT_JSON environment variable.
        
        Returns: Google Drive API service object, or None if not configured
        """
        if self._drive_service is not None:
            return self._drive_service
            
        if not GOOGLE_API_AVAILABLE:
            print("❌ Google API libraries not available")
            return None
        
        # Load service account JSON from environment variable
        sa_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
        if not sa_json:
            print("❌ GOOGLE_SERVICE_ACCOUNT_JSON environment variable not set")
            return None
        
        try:
            # Parse the JSON string into credentials
            sa_info = json.loads(sa_json)
            credentials = service_account.Credentials.from_service_account_info(
                sa_info,
                scopes=['https://www.googleapis.com/auth/drive.readonly']
            )
            
            # Build the Drive API service
            self._drive_service = build('drive', 'v3', credentials=credentials)
            print("✅ Google Drive API service initialized with service account")
            return self._drive_service
            
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in GOOGLE_SERVICE_ACCOUNT_JSON: {e}")
            return None
        except Exception as e:
            print(f"❌ Failed to initialize Google Drive API: {e}")
            return None
        
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
        
        Handles multiple URL formats:
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
    
    def _is_google_sheet(self, url: str) -> bool:
        """Check if the URL points to a Google Sheets document (not a regular file)"""
        return 'spreadsheets' in url.lower() or 'docs.google.com/spreadsheets' in url.lower()
    
    def download_google_drive_authenticated(self, url: str) -> Tuple[Optional[str], Dict]:
        """
        Download file from Google Drive using Service Account authentication.
        This avoids the HTTP 432 error that blocks unauthenticated server downloads.
        
        For Google Sheets: Uses export to xlsx format
        For regular files: Uses direct media download
        
        Returns: (local_filepath, metadata)
        """
        metadata = {
            'service': 'google_drive',
            'original_url': url,
            'success': False,
            'error': None,
            'size_bytes': 0,
            'filename': None
        }
        
        # Get authenticated Drive service
        drive_service = self._get_drive_service()
        if not drive_service:
            metadata['error'] = (
                "Google Drive API not configured. "
                "Set GOOGLE_SERVICE_ACCOUNT_JSON environment variable in Render "
                "and share the file with the service account email."
            )
            return None, metadata
        
        # Extract file ID
        file_id = self.extract_google_drive_id(url)
        if not file_id:
            metadata['error'] = "Could not extract file ID from Google Drive URL"
            return None, metadata
        
        print(f"🔑 Authenticated download for file ID: {file_id}")
        
        try:
            # First, get file metadata to determine type and name
            file_metadata = drive_service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, size'
            ).execute()
            
            file_name = file_metadata.get('name', f'file_{file_id}')
            mime_type = file_metadata.get('mimeType', '')
            file_size = file_metadata.get('size')
            
            print(f"📄 File: {file_name}")
            print(f"📋 MIME type: {mime_type}")
            if file_size:
                print(f"📊 Size: {int(file_size) / 1024 / 1024:.2f}MB")
            
            metadata['filename'] = file_name
            
            # Determine if this is a Google Workspace file (Sheets, Docs, etc.)
            # These need to be EXPORTED, not downloaded directly
            is_google_workspace = mime_type.startswith('application/vnd.google-apps.')
            
            if is_google_workspace or self._is_google_sheet(url):
                # Google Sheets/Docs: Export to a standard format
                print(f"📊 Google Workspace file detected - exporting to xlsx...")
                
                # Determine export format based on type
                if 'spreadsheet' in mime_type or self._is_google_sheet(url):
                    export_mime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    suffix = '.xlsx'
                    if not file_name.endswith('.xlsx'):
                        file_name = file_name + '.xlsx'
                elif 'document' in mime_type:
                    export_mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                    suffix = '.docx'
                    if not file_name.endswith('.docx'):
                        file_name = file_name + '.docx'
                elif 'presentation' in mime_type:
                    export_mime = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                    suffix = '.pptx'
                    if not file_name.endswith('.pptx'):
                        file_name = file_name + '.pptx'
                else:
                    export_mime = 'application/pdf'
                    suffix = '.pdf'
                    if not file_name.endswith('.pdf'):
                        file_name = file_name + '.pdf'
                
                metadata['filename'] = file_name
                
                # Export the file
                request_obj = drive_service.files().export_media(
                    fileId=file_id,
                    mimeType=export_mime
                )
            else:
                # Regular file (uploaded Excel, PDF, etc.): Direct download
                print(f"📥 Regular file - downloading directly...")
                suffix = os.path.splitext(file_name)[1] or '.tmp'
                
                request_obj = drive_service.files().get_media(fileId=file_id)
            
            # Create temp file and download with streaming
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            
            # Use MediaIoBaseDownload for chunked/streamed download
            downloader = MediaIoBaseDownload(temp_file, request_obj, chunksize=1024*1024)
            
            done = False
            bytes_downloaded = 0
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    bytes_downloaded = status.resumable_progress if hasattr(status, 'resumable_progress') else 0
                    print(f"⬇️  Download progress: {progress}%")
            
            temp_file.close()
            
            # Get actual file size
            actual_size = os.path.getsize(temp_file.name)
            metadata['success'] = True
            metadata['size_bytes'] = actual_size
            
            print(f"✅ Download complete: {actual_size / 1024 / 1024:.2f}MB")
            print(f"📁 Saved to: {temp_file.name}")
            
            return temp_file.name, metadata
            
        except Exception as e:
            error_str = str(e)
            
            # Provide helpful error messages for common issues
            if '404' in error_str or 'not found' in error_str.lower():
                metadata['error'] = (
                    f"File not found (404). Make sure the Google Sheet is shared with "
                    f"the service account email address (check GOOGLE_SERVICE_ACCOUNT_JSON for client_email)."
                )
            elif '403' in error_str or 'forbidden' in error_str.lower():
                metadata['error'] = (
                    f"Access denied (403). The file must be shared with the service account email. "
                    f"Go to the Google Sheet → Share → add the service account email as Viewer."
                )
            elif '401' in error_str or 'unauthorized' in error_str.lower():
                metadata['error'] = (
                    f"Authentication failed (401). Check that GOOGLE_SERVICE_ACCOUNT_JSON "
                    f"contains valid service account credentials."
                )
            else:
                metadata['error'] = f"Google Drive API error: {error_str}"
            
            print(f"❌ Download failed: {metadata['error']}")
            return None, metadata
    
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
        Download file using streaming to prevent RAM exhaustion.
        Used for Dropbox and OneDrive (non-authenticated).
        
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
            if service == 'dropbox':
                download_url, filename = self.convert_dropbox_url(url)
            elif service == 'onedrive':
                download_url, filename = self.convert_onedrive_url(url)
            else:
                raise ValueError(f"Unsupported service for unauthenticated download: {service}")
            
            if not download_url:
                raise ValueError(f"Could not convert {service} URL to download link")
            
            metadata['filename'] = filename
            
            # Start streaming download
            print(f"🌐 Starting streaming download from {service}...")
            print(f"📥 Download URL: {download_url[:100]}...")
            
            response = requests.get(download_url, stream=True, timeout=(30, 300))
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
        
        For Google Drive: Uses authenticated API download (avoids HTTP 432)
        For Dropbox/OneDrive: Uses URL conversion + streaming download
        
        Returns: (local_filepath, metadata)
        """
        print(f"🔗 Processing cloud link: {url[:80]}...")
        
        service = self.detect_service(url)
        
        if not service:
            return None, {
                'success': False,
                'error': 'Unsupported cloud storage service. Use Google Drive, Dropbox, or OneDrive.',
                'original_url': url
            }
        
        print(f"🔗 Detected service: {service}")
        
        # Route to appropriate download method
        if service == 'google_drive':
            # Use authenticated Google Drive API (fixes HTTP 432 error)
            return self.download_google_drive_authenticated(url)
        else:
            # Use streaming download for Dropbox/OneDrive
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
            is_sheet = handler._is_google_sheet(url)
            print(f"   Is Google Sheet: {is_sheet}")

# I did no harm and this file is not truncated
