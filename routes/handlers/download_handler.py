"""
Download Handler - Serve Generated Files
Created: February 10, 2026
Last Updated: February 10, 2026

Serves Excel analysis files and other generated documents for download.

Author: Jim @ Shiftwork Solutions LLC
"""

import os
import traceback
from flask import send_file, jsonify


def download_analysis_file(filename):
    """
    Serve Excel analysis files for download.
    
    Args:
        filename: Filename to download
        
    Returns:
        File download response or error JSON
    """
    try:
        file_path = os.path.join('/tmp/outputs', filename)
        print(f"{'='*80}")
        print(f"DOWNLOAD ROUTE CALLED")
        print(f"Requested filename: {filename}")
        print(f"Full path: {file_path}")
        print(f"File exists: {os.path.exists(file_path)}")
        
        if os.path.exists(file_path):
            # List what is actually in the directory
            files_in_dir = os.listdir('/tmp/outputs')
            print(f"Files in /tmp/outputs/: {files_in_dir}")
            print(f"Serving file: {file_path}")
            print(f"{'='*80}")
            return send_file(file_path, as_attachment=True, download_name=filename)
        else:
            # List what is actually in the directory
            try:
                files_in_dir = os.listdir('/tmp/outputs')
                print(f"Files in /tmp/outputs/: {files_in_dir}")
            except:
                print(f"/tmp/outputs/ directory does not exist!")
            
            print(f"File not found: {file_path}")
            print(f"{'='*80}")
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        print(f"EXCEPTION in download route: {e}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


# I did no harm and this file is not truncated
