"""
Cloud File Handler - Streaming Downloads from Cloud Storage
Created: February 5, 2026
Last Updated: February 5, 2026

This module handles downloading large files from cloud storage services
using streaming downloads to avoid loading entire files into RAM.

Supports:
- Google Drive (share links)
- Dropbox (share links)
- OneDrive (share links)
- Direct HTTP/HTTPS links

CRITICAL: Uses streaming downloads (chunked) to prevent memory issues
with large files (50MB+).

Author: Jim @ Shiftwork Solutions LLC
"""

import re
import requests
from urllib.parse import urlparse, parse_qs
import os
from datetime import datetime

class CloudFileHandler:
    """
    Handle downloading files from cloud storage services using streaming.
    
    Key feature: Downloads in chunks to avoid loading full file into RAM.
    """
    
    def __init__(self):
        self.chunk_size = 8192  # 8KB chunks (small to minimize RAM usage)
        self.max_file_size = 100 * 1024 * 1024  # 100MB limit
        
    def detect_service(self, url):
        """
        Detect which cloud service the URL is from.
        
        Args:
            url (str): The cloud storage URL
            
        Returns:
            str: Service name ('google_drive', 'dropbox', 'onedrive', 'direct', 'unknown')
        """
        url_lower = url.lower()
        
        if 'drive.google.com' in url_lower or 'docs.google.com' in url_lower:
            return 'google_drive'
        elif 'dropbox.com' in url_lower:
            return 'dropbox'
        elif 'onedrive' in url_lower or '1drv.ms' in url_lower:
            return 'onedrive'
        elif url_lower.startswith('http://') or url_lower.startswith('https://'):
            return 'direct'
        else:
            return 'unknown'
    
    def extract_google_drive_id(self, url):
        """
        Extract file ID from Google Drive URL.
        
        Supports formats:
        - https://drive.google.com/file/d/FILE_ID/view
        - https://drive.google.com/open?id=FILE_ID
        """
        # Pattern 1: /file/d/FILE_ID/
        match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)
        
        # Pattern 2: ?id=FILE_ID
        match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)
        
        return None
    
    def convert_google_drive_url(self, url):
        """
        Convert Google Drive share link to direct download URL.
        """
        file_id = self.extract_google_drive_id(url)
        if not file_id:
            return None
        
        # Use the direct download endpoint
        return f'https://drive.google.com/uc?export=download&id={file_id}'
    
    def convert_dropbox_url(self, url):
        """
        Convert Dropbox share link to direct download URL.
        """
        # Dropbox: change ?dl=0 to ?dl=1 or add ?dl=1
        if '?dl=0' in url:
            return url.replace('?dl=0', '?dl=1')
        elif '?dl=1' in url:
            return url
        else:
            separator = '&' if '?' in url else '?'
            return f'{url}{separator}dl=1'
    
    def convert_onedrive_url(self, url):
        """
        Convert OneDrive share link to direct download URL.
        """
        # OneDrive: replace 'redir' with 'download'
        if 'onedrive.live.com' in url:
            return url.replace('redir', 'download')
        elif '1drv.ms' in url:
            # Short links need to be resolved first
            return url  # Will handle via requests redirect
        else:
            return url
    
    def get_download_url(self, url):
        """
        Convert any cloud storage URL to a direct download URL.
        
        Args:
            url (str): Cloud storage share link
            
        Returns:
            dict: {
                'success': bool,
                'download_url': str or None,
                'service': str,
                'error': str or None
            }
        """
        service = self.detect_service(url)
        
        if service == 'unknown':
            return {
                'success': False,
                'download_url': None,
                'service': 'unknown',
                'error': 'Unrecognized URL format. Please use Google Drive, Dropbox, OneDrive, or direct HTTP links.'
            }
        
        try:
            if service == 'google_drive':
                download_url = self.convert_google_drive_url(url)
                if not download_url:
                    return {
                        'success': False,
                        'download_url': None,
                        'service': service,
                        'error': 'Could not extract file ID from Google Drive URL'
                    }
            elif service == 'dropbox':
                download_url = self.convert_dropbox_url(url)
            elif service == 'onedrive':
                download_url = self.convert_onedrive_url(url)
            else:  # direct
                download_url = url
            
            return {
                'success': True,
                'download_url': download_url,
                'service': service,
                'error': None
            }
            
        except Exception as e:
            return {
                'success': False,
                'download_url': None,
                'service': service,
                'error': f'Error converting URL: {str(e)}'
            }
    
    def download_file_streaming(self, url, output_path, progress_callback=None):
        """
        Download file from URL using streaming (chunks) to avoid RAM issues.
        
        CRITICAL: This is the key function that prevents memory crashes!
        Downloads file in small chunks instead of loading entire file into RAM.
        
        Args:
            url (str): Direct download URL
            output_path (str): Where to save the file
            progress_callback (function): Optional callback(bytes_downloaded, total_bytes)
            
        Returns:
            dict: {
                'success': bool,
                'file_path': str or None,
                'file_size': int,
                'error': str or None
            }
        """
        try:
            # Start streaming download
            print(f"🔄 Starting streaming download from: {url[:50]}...")
            
            response = requests.get(url, stream=True, timeout=30)
            
            # Check for successful response
            if response.status_code != 200:
                return {
                    'success': False,
                    'file_path': None,
                    'file_size': 0,
                    'error': f'HTTP {response.status_code}: Could not download file. Please check sharing permissions.'
                }
            
            # Get file size if available
            total_size = int(response.headers.get('content-length', 0))
            
            # Check file size limit
            if total_size > self.max_file_size:
                return {
                    'success': False,
                    'file_path': None,
                    'file_size': total_size,
                    'error': f'File too large ({total_size / (1024*1024):.1f}MB). Maximum is {self.max_file_size / (1024*1024):.0f}MB.'
                }
            
            print(f"📊 File size: {total_size / (1024*1024):.1f}MB")
            
            # Create output directory if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Download in chunks (CRITICAL: prevents RAM overflow!)
            bytes_downloaded = 0
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if chunk:
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        
                        # Progress callback
                        if progress_callback:
                            progress_callback(bytes_downloaded, total_size)
                        
                        # Log progress every 10MB
                        if bytes_downloaded % (10 * 1024 * 1024) < self.chunk_size:
                            print(f"📥 Downloaded: {bytes_downloaded / (1024*1024):.1f}MB")
            
            print(f"✅ Download complete: {output_path}")
            
            return {
                'success': True,
                'file_path': output_path,
                'file_size': bytes_downloaded,
                'error': None
            }
            
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'file_path': None,
                'file_size': 0,
                'error': 'Download timeout. Please try again or check your internet connection.'
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'file_path': None,
                'file_size': 0,
                'error': f'Download failed: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'file_path': None,
                'file_size': 0,
                'error': f'Unexpected error: {str(e)}'
            }
    
    def handle_cloud_link(self, url, user_request, project_id=None):
        """
        Complete handler: Convert URL and download file.
        
        This is the main entry point for cloud file handling.
        
        Args:
            url (str): Cloud storage share link
            user_request (str): User's analysis request
            project_id (str): Optional project ID
            
        Returns:
            dict: {
                'success': bool,
                'file_path': str or None,
                'file_size': int,
                'service': str,
                'error': str or None
            }
        """
        print(f"🔗 Processing cloud link from: {self.detect_service(url)}")
        
        # Convert to download URL
        url_result = self.get_download_url(url)
        
        if not url_result['success']:
            return {
                'success': False,
                'file_path': None,
                'file_size': 0,
                'service': url_result['service'],
                'error': url_result['error']
            }
        
        # Generate output filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if project_id:
            output_dir = f'/tmp/projects/{project_id}'
        else:
            output_dir = '/tmp/cloud_downloads'
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Try to get filename from URL or use default
        filename = f'cloud_file_{timestamp}.xlsx'  # Assume Excel for now
        output_path = os.path.join(output_dir, filename)
        
        # Download file using streaming
        download_result = self.download_file_streaming(
            url_result['download_url'],
            output_path
        )
        
        if not download_result['success']:
            return {
                'success': False,
                'file_path': None,
                'file_size': 0,
                'service': url_result['service'],
                'error': download_result['error']
            }
        
        return {
            'success': True,
            'file_path': download_result['file_path'],
            'file_size': download_result['file_size'],
            'service': url_result['service'],
            'error': None
        }


# Singleton instance
_cloud_handler = None

def get_cloud_file_handler():
    """Get singleton CloudFileHandler instance"""
    global _cloud_handler
    if _cloud_handler is None:
        _cloud_handler = CloudFileHandler()
    return _cloud_handler


# I did no harm and this file is not truncated
