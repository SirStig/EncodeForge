"""
Download Manager Utility for EncodeForge
Handles file downloads with progress tracking, resume support, and verification
"""

import hashlib
import logging
from pathlib import Path
from typing import Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class DownloadError(Exception):
    """Raised when download fails"""
    pass


class DownloadManager:
    """
    Manages file downloads with progress tracking and resume capability.
    
    Example usage:
        def progress_callback(downloaded, total, percentage):
            print(f"Downloaded: {percentage:.1f}% ({downloaded}/{total} bytes)")
        
        dm = DownloadManager()
        local_path = dm.download(
            url="https://example.com/file.zip",
            destination="./downloads/file.zip",
            progress_callback=progress_callback,
            expected_hash="sha256:abc123...",
            resume=True
        )
    """
    
    def __init__(self, chunk_size: int = 8192, timeout: int = 30):
        """
        Initialize download manager.
        
        Args:
            chunk_size: Size of download chunks in bytes (default: 8KB)
            timeout: Connection timeout in seconds (default: 30)
        """
        self.chunk_size = chunk_size
        self.timeout = timeout
    
    def download(
        self,
        url: str,
        destination: str,
        progress_callback: Optional[Callable[[int, int, float], None]] = None,
        expected_hash: Optional[str] = None,
        resume: bool = True,
        user_agent: Optional[str] = None
    ) -> Path:
        """
        Download a file from URL to destination.
        
        Args:
            url: URL to download from
            destination: Local file path to save to
            progress_callback: Optional callback(downloaded_bytes, total_bytes, percentage)
            expected_hash: Optional hash for verification (format: "sha256:hash" or "md5:hash")
            resume: Whether to resume partial downloads
            user_agent: Optional custom User-Agent header
        
        Returns:
            Path object of the downloaded file
        
        Raises:
            DownloadError: If download fails or hash verification fails
        """
        dest_path = Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Determine starting position for resume
        start_pos = 0
        mode = 'wb'
        
        if resume and dest_path.exists():
            start_pos = dest_path.stat().st_size
            mode = 'ab'
            logger.info(f"Resuming download from byte {start_pos}")
        
        # Build request with headers
        headers = {}
        if user_agent:
            headers['User-Agent'] = user_agent
        else:
            headers['User-Agent'] = 'EncodeForge/1.0'
        
        if start_pos > 0:
            headers['Range'] = f'bytes={start_pos}-'
        
        try:
            request = Request(url, headers=headers)
            
            with urlopen(request, timeout=self.timeout) as response:
                # Get content length
                content_length_header = response.getheader('Content-Length')
                
                if content_length_header:
                    total_size = int(content_length_header) + start_pos
                else:
                    total_size = start_pos
                    logger.warning("Server did not provide Content-Length header")
                
                # Check if server supports resume
                if start_pos > 0:
                    content_range = response.getheader('Content-Range')
                    if not content_range:
                        logger.warning("Server doesn't support resume, starting from beginning")
                        start_pos = 0
                        mode = 'wb'
                        total_size = int(content_length_header) if content_length_header else 0
                
                downloaded = start_pos
                
                # Download with progress tracking
                with open(dest_path, mode) as f:
                    while True:
                        chunk = response.read(self.chunk_size)
                        if not chunk:
                            break
                        
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Call progress callback
                        if progress_callback and total_size > 0:
                            percentage = (downloaded / total_size) * 100
                            progress_callback(downloaded, total_size, percentage)
                
                logger.info(f"Download complete: {dest_path} ({downloaded} bytes)")
        
        except HTTPError as e:
            error_msg = f"HTTP Error {e.code}: {e.reason}"
            logger.error(error_msg)
            raise DownloadError(error_msg) from e
        
        except URLError as e:
            error_msg = f"URL Error: {e.reason}"
            logger.error(error_msg)
            raise DownloadError(error_msg) from e
        
        except Exception as e:
            error_msg = f"Download failed: {str(e)}"
            logger.error(error_msg)
            raise DownloadError(error_msg) from e
        
        # Verify hash if provided
        if expected_hash:
            if not self.verify_hash(dest_path, expected_hash):
                dest_path.unlink()  # Delete corrupted file
                raise DownloadError(f"Hash verification failed for {dest_path}")
        
        return dest_path
    
    def verify_hash(self, file_path: Path, expected_hash: str) -> bool:
        """
        Verify file hash.
        
        Args:
            file_path: Path to file to verify
            expected_hash: Expected hash in format "algorithm:hash" (e.g., "sha256:abc123...")
        
        Returns:
            True if hash matches, False otherwise
        """
        try:
            # Parse algorithm and expected value
            if ':' in expected_hash:
                algorithm, expected_value = expected_hash.split(':', 1)
            else:
                # Default to SHA256 if no algorithm specified
                algorithm = 'sha256'
                expected_value = expected_hash
            
            algorithm = algorithm.lower()
            
            # Calculate file hash
            if algorithm == 'sha256':
                hasher = hashlib.sha256()
            elif algorithm == 'md5':
                hasher = hashlib.md5()
            elif algorithm == 'sha1':
                hasher = hashlib.sha1()
            else:
                logger.error(f"Unsupported hash algorithm: {algorithm}")
                return False
            
            with open(file_path, 'rb') as f:
                while chunk := f.read(self.chunk_size):
                    hasher.update(chunk)
            
            actual_hash = hasher.hexdigest()
            
            if actual_hash.lower() == expected_value.lower():
                logger.info(f"Hash verification passed for {file_path}")
                return True
            else:
                logger.error(f"Hash mismatch for {file_path}")
                logger.error(f"  Expected: {expected_value}")
                logger.error(f"  Actual:   {actual_hash}")
                return False
        
        except Exception as e:
            logger.error(f"Hash verification error: {e}")
            return False
    
    def extract_archive(
        self,
        archive_path: Path,
        destination: Path,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Path:
        """
        Extract an archive (zip, tar.gz, tar.bz2, etc.).
        
        Args:
            archive_path: Path to archive file
            destination: Directory to extract to
            progress_callback: Optional callback(current_file_name)
        
        Returns:
            Path to extraction directory
        
        Raises:
            DownloadError: If extraction fails
        """
        destination.mkdir(parents=True, exist_ok=True)
        
        try:
            archive_str = str(archive_path)
            
            if archive_str.endswith('.zip'):
                import zipfile
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    members = zip_ref.namelist()
                    for i, member in enumerate(members):
                        if progress_callback:
                            progress_callback(member)
                        zip_ref.extract(member, destination)
                logger.info(f"Extracted {len(members)} files from {archive_path}")
            
            elif archive_str.endswith(('.tar.gz', '.tgz')):
                import tarfile
                with tarfile.open(archive_path, 'r:gz') as tar_ref:
                    members = tar_ref.getmembers()
                    for i, member in enumerate(members):
                        if progress_callback:
                            progress_callback(member.name)
                        tar_ref.extract(member, destination)
                logger.info(f"Extracted {len(members)} files from {archive_path}")
            
            elif archive_str.endswith(('.tar.bz2', '.tbz2')):
                import tarfile
                with tarfile.open(archive_path, 'r:bz2') as tar_ref:
                    members = tar_ref.getmembers()
                    for i, member in enumerate(members):
                        if progress_callback:
                            progress_callback(member.name)
                        tar_ref.extract(member, destination)
                logger.info(f"Extracted {len(members)} files from {archive_path}")
            
            elif archive_str.endswith('.tar'):
                import tarfile
                with tarfile.open(archive_path, 'r') as tar_ref:
                    members = tar_ref.getmembers()
                    for i, member in enumerate(members):
                        if progress_callback:
                            progress_callback(member.name)
                        tar_ref.extract(member, destination)
                logger.info(f"Extracted {len(members)} files from {archive_path}")
            
            else:
                raise DownloadError(f"Unsupported archive format: {archive_path}")
            
            return destination
        
        except Exception as e:
            error_msg = f"Extraction failed: {str(e)}"
            logger.error(error_msg)
            raise DownloadError(error_msg) from e
    
    def download_and_extract(
        self,
        url: str,
        extract_to: Path,
        download_callback: Optional[Callable[[int, int, float], None]] = None,
        extract_callback: Optional[Callable[[str], None]] = None,
        cleanup: bool = True
    ) -> Path:
        """
        Download an archive and extract it in one step.
        
        Args:
            url: URL of archive to download
            extract_to: Directory to extract to
            download_callback: Optional progress callback for download
            extract_callback: Optional progress callback for extraction
            cleanup: Whether to delete archive after extraction
        
        Returns:
            Path to extraction directory
        """
        # Determine archive filename from URL
        filename = url.split('/')[-1]
        temp_dir = Path(extract_to).parent / 'temp'
        temp_dir.mkdir(parents=True, exist_ok=True)
        archive_path = temp_dir / filename
        
        try:
            # Download
            logger.info(f"Downloading {url}...")
            self.download(url, str(archive_path), progress_callback=download_callback)
            
            # Extract
            logger.info(f"Extracting to {extract_to}...")
            result = self.extract_archive(archive_path, extract_to, progress_callback=extract_callback)
            
            return result
        
        finally:
            # Cleanup temp archive
            if cleanup and archive_path.exists():
                try:
                    archive_path.unlink()
                    logger.info(f"Cleaned up temporary archive: {archive_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup {archive_path}: {e}")


def calculate_file_hash(file_path: Path, algorithm: str = 'sha256') -> str:
    """
    Calculate hash of a file.
    
    Args:
        file_path: Path to file
        algorithm: Hash algorithm ('sha256', 'md5', 'sha1')
    
    Returns:
        Hex digest of the hash
    """
    if algorithm == 'sha256':
        hasher = hashlib.sha256()
    elif algorithm == 'md5':
        hasher = hashlib.md5()
    elif algorithm == 'sha1':
        hasher = hashlib.sha1()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    
    return hasher.hexdigest()


if __name__ == "__main__":
    # Test download manager
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    print("=== Download Manager Test ===")
    print()
    
    # Example: Download a small test file
    def progress(downloaded, total, percentage):
        print(f"\rProgress: {percentage:.1f}% ({downloaded}/{total} bytes)", end='')
    
    dm = DownloadManager()
    
    # Test with a small public file (example)
    test_url = "https://www.python.org/static/favicon.ico"
    test_dest = Path("./temp_test_download.ico")
    
    try:
        print(f"Testing download from: {test_url}")
        result = dm.download(test_url, str(test_dest), progress_callback=progress)
        print()
        print(f"Downloaded to: {result}")
        print(f"File size: {result.stat().st_size} bytes")
        
        # Calculate hash
        file_hash = calculate_file_hash(result)
        print(f"SHA256: {file_hash}")
        
        # Cleanup
        result.unlink()
        print("Test file cleaned up")
    
    except DownloadError as e:
        print(f"Download failed: {e}")
    except Exception as e:
        print(f"Error: {e}")
