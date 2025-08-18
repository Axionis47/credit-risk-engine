import tempfile
import os
from google.cloud import storage
from typing import Tuple
from app.config import settings
import structlog

logger = structlog.get_logger()

class GCSClient:
    """Google Cloud Storage client for downloading CSV files"""
    
    def __init__(self):
        self.client = storage.Client()
        self.bucket = self.client.bucket(settings.gcs_bucket_name)
    
    def download_csv_files(self) -> Tuple[str, str]:
        """
        Download CSV files from GCS to temporary local files
        
        Returns:
            Tuple of (metrics_file_path, transcripts_file_path)
        """
        logger.info("Downloading CSV files from GCS", 
                   bucket=settings.gcs_bucket_name,
                   metrics_file=settings.gcs_metrics_file,
                   transcripts_file=settings.gcs_transcripts_file)
        
        # Download metrics file
        metrics_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
        metrics_blob = self.bucket.blob(settings.gcs_metrics_file)
        metrics_blob.download_to_filename(metrics_temp.name)
        metrics_temp.close()
        
        logger.info("Downloaded metrics file", 
                   local_path=metrics_temp.name,
                   size_bytes=os.path.getsize(metrics_temp.name))
        
        # Download transcripts file
        transcripts_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
        transcripts_blob = self.bucket.blob(settings.gcs_transcripts_file)
        transcripts_blob.download_to_filename(transcripts_temp.name)
        transcripts_temp.close()
        
        logger.info("Downloaded transcripts file", 
                   local_path=transcripts_temp.name,
                   size_bytes=os.path.getsize(transcripts_temp.name))
        
        return metrics_temp.name, transcripts_temp.name
    
    def cleanup_temp_files(self, *file_paths: str):
        """Clean up temporary files"""
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
                    logger.debug("Cleaned up temp file", path=file_path)
            except Exception as e:
                logger.warning("Failed to cleanup temp file", path=file_path, error=str(e))
