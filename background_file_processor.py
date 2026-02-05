"""
Background File Processor - Process Large Files Asynchronously
Created: February 5, 2026
Last Updated: February 5, 2026

Manages background processing jobs for large files:
- Spawns separate threads for long-running tasks
- Tracks job progress and status
- Posts results to conversation when complete
- Prevents server timeouts

Author: Jim @ Shiftwork Solutions LLC
"""

import threading
import queue
import time
import traceback
from typing import Dict, Any, Optional
from datetime import datetime
import os

from streaming_excel_analyzer import get_streaming_analyzer
from database import get_db, add_message
from orchestration.ai_clients import call_gpt4


class BackgroundFileProcessor:
    """
    Manages background file processing jobs.
    Each job runs in a separate thread to prevent blocking.
    """
    
    def __init__(self):
        """Initialize the background processor."""
        self.jobs = {}  # job_id -> job_info
        self.job_queue = queue.Queue()
        self.worker_thread = None
        self.running = False
    
    
    def start(self):
        """Start the background worker thread."""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._worker, daemon=True)
            self.worker_thread.start()
            print("🚀 Background file processor started")
    
    
    def stop(self):
        """Stop the background worker thread."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        print("🛑 Background file processor stopped")
    
    
    def submit_job(self, job_id: str, file_path: str, user_request: str,
                   conversation_id: str, task_id: int, user_name: str = "User") -> Dict[str, Any]:
        """
        Submit a file processing job to the background queue.
        
        Args:
            job_id: Unique job identifier
            file_path: Path to file to process
            user_request: User's original request
            conversation_id: Conversation ID for posting results
            task_id: Task ID for tracking
            user_name: User's name (for personalization)
            
        Returns:
            Dict with job submission status
        """
        try:
            # Get file info
            file_size = os.path.getsize(file_path)
            file_size_mb = round(file_size / (1024 * 1024), 2)
            
            # Estimate processing time (rough: 1MB = 2 seconds)
            estimated_seconds = int(file_size_mb * 2)
            estimated_minutes = max(1, estimated_seconds // 60)
            
            # Create job record
            job_info = {
                'job_id': job_id,
                'file_path': file_path,
                'file_name': os.path.basename(file_path),
                'file_size_mb': file_size_mb,
                'user_request': user_request,
                'conversation_id': conversation_id,
                'task_id': task_id,
                'user_name': user_name,
                'status': 'queued',
                'submitted_at': datetime.now().isoformat(),
                'started_at': None,
                'completed_at': None,
                'progress': 0,
                'current_step': 'Queued for processing',
                'estimated_minutes': estimated_minutes,
                'result': None,
                'error': None
            }
            
            self.jobs[job_id] = job_info
            
            # Add to queue
            self.job_queue.put(job_id)
            
            # Store in database
            db = get_db()
            db.execute('''
                INSERT INTO background_jobs 
                (job_id, file_path, file_name, file_size_mb, user_request, 
                 conversation_id, task_id, status, estimated_minutes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                job_id, file_path, job_info['file_name'], file_size_mb, user_request,
                conversation_id, task_id, 'queued', estimated_minutes, datetime.now()
            ))
            db.commit()
            db.close()
            
            print(f"📥 Job {job_id} submitted: {job_info['file_name']} ({file_size_mb}MB)")
            
            return {
                'success': True,
                'job_id': job_id,
                'estimated_minutes': estimated_minutes,
                'message': f"Processing {job_info['file_name']} in background (~{estimated_minutes} min)"
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status of a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job info dict or None if not found
        """
        return self.jobs.get(job_id)
    
    
    def _worker(self):
        """
        Background worker thread that processes jobs from the queue.
        Runs continuously until stopped.
        """
        print("👷 Background worker thread started")
        
        while self.running:
            try:
                # Get next job (with timeout to allow checking self.running)
                try:
                    job_id = self.job_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                if job_id not in self.jobs:
                    print(f"⚠️ Job {job_id} not found")
                    continue
                
                # Process the job
                self._process_job(job_id)
                
            except Exception as e:
                print(f"❌ Worker thread error: {e}")
                traceback.print_exc()
        
        print("👷 Background worker thread stopped")
    
    
    def _process_job(self, job_id: str):
        """
        Process a single job.
        
        Args:
            job_id: Job identifier
        """
        job = self.jobs[job_id]
        
        try:
            # Update status to processing
            job['status'] = 'processing'
            job['started_at'] = datetime.now().isoformat()
            job['current_step'] = 'Analyzing file structure'
            
            self._update_job_db(job_id, 'processing', 0, 'Analyzing file structure')
            
            print(f"🔄 Processing job {job_id}: {job['file_name']}")
            
            # Create streaming analyzer
            analyzer = get_streaming_analyzer(chunk_size=1000)
            
            # Progress callback
            def progress_callback(progress: Dict[str, Any]):
                job['progress'] = int((progress['rows_processed'] / progress['estimated_total']) * 100)
                job['current_step'] = f"Analyzing rows {progress['rows_processed']:,} / {progress['estimated_total']:,}"
                self._update_job_db(job_id, 'processing', job['progress'], job['current_step'])
                print(f"  📊 Job {job_id}: {job['current_step']}")
            
            # Process file
            result = analyzer.process_file_streaming(
                file_path=job['file_path'],
                progress_callback=progress_callback
            )
            
            if result['success']:
                # Generate consulting report
                from analysis_accumulator import AnalysisAccumulator
                accumulator = AnalysisAccumulator()
                
                # Rebuild accumulator from result (simplified)
                analysis = result['analysis']
                report_text = f"""# 📊 BACKGROUND ANALYSIS COMPLETE

**File:** {job['file_name']}  
**Total Rows:** {analysis['total_rows']:,}  
**Processing Time:** {self._get_elapsed_time(job)}

---

## KEY FINDINGS

"""
                
                # Add numeric summaries
                if 'numeric_summary' in analysis:
                    report_text += "### 📈 Numeric Data:\n\n"
                    for col, stats in list(analysis['numeric_summary'].items())[:5]:
                        report_text += f"**{col}:** Total={stats['sum']:,}, Avg={stats['mean']:,}, Range={stats['min']:,} to {stats['max']:,}\n\n"
                
                # Add categorical summaries
                if 'categorical_summary' in analysis:
                    report_text += "\n### 📋 Categorical Data:\n\n"
                    for col, stats in list(analysis['categorical_summary'].items())[:3]:
                        top_vals = ', '.join([f"{k} ({v})" for k, v in list(stats['top_values'].items())[:3]])
                        report_text += f"**{col}:** {stats['unique_values']} unique values. Top: {top_vals}\n\n"
                
                report_text += f"\n✅ **Complete analysis of all {analysis['total_rows']:,} rows.**\n"
                
                # Post result to conversation
                add_message(
                    job['conversation_id'],
                    'assistant',
                    report_text,
                    job['task_id'],
                    {'orchestrator': 'background_file_processor', 'job_id': job_id}
                )
                
                # Update job
                job['status'] = 'completed'
                job['completed_at'] = datetime.now().isoformat()
                job['progress'] = 100
                job['current_step'] = 'Complete'
                job['result'] = report_text
                
                self._update_job_db(job_id, 'completed', 100, 'Complete')
                
                print(f"✅ Job {job_id} completed successfully")
                
            else:
                # Job failed
                error_msg = result.get('error', 'Unknown error')
                job['status'] = 'failed'
                job['error'] = error_msg
                job['completed_at'] = datetime.now().isoformat()
                
                self._update_job_db(job_id, 'failed', job['progress'], f"Error: {error_msg}")
                
                # Post error to conversation
                add_message(
                    job['conversation_id'],
                    'assistant',
                    f"❌ Background analysis failed: {error_msg}",
                    job['task_id'],
                    {'orchestrator': 'background_file_processor', 'job_id': job_id, 'error': True}
                )
                
                print(f"❌ Job {job_id} failed: {error_msg}")
                
        except Exception as e:
            # Unexpected error
            error_msg = str(e)
            job['status'] = 'failed'
            job['error'] = error_msg
            job['completed_at'] = datetime.now().isoformat()
            
            self._update_job_db(job_id, 'failed', job.get('progress', 0), f"Error: {error_msg}")
            
            # Post error to conversation
            add_message(
                job['conversation_id'],
                'assistant',
                f"❌ Background analysis encountered an error: {error_msg}",
                job['task_id'],
                {'orchestrator': 'background_file_processor', 'job_id': job_id, 'error': True}
            )
            
            print(f"❌ Job {job_id} crashed: {error_msg}")
            traceback.print_exc()
    
    
    def _update_job_db(self, job_id: str, status: str, progress: int, current_step: str):
        """Update job status in database."""
        try:
            db = get_db()
            db.execute('''
                UPDATE background_jobs 
                SET status = ?, progress = ?, current_step = ?, updated_at = ?
                WHERE job_id = ?
            ''', (status, progress, current_step, datetime.now(), job_id))
            db.commit()
            db.close()
        except Exception as e:
            print(f"⚠️ Failed to update job {job_id} in DB: {e}")
    
    
    def _get_elapsed_time(self, job: Dict[str, Any]) -> str:
        """Calculate elapsed time for a job."""
        if job.get('started_at') and job.get('completed_at'):
            start = datetime.fromisoformat(job['started_at'])
            end = datetime.fromisoformat(job['completed_at'])
            elapsed = (end - start).total_seconds()
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            return f"{minutes}m {seconds}s"
        return "Unknown"


# Global singleton instance
_processor_instance = None


def get_background_processor():
    """Get the global background processor instance."""
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = BackgroundFileProcessor()
        _processor_instance.start()
    return _processor_instance


# I did no harm and this file is not truncated
