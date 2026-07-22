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

# Magic-byte signatures, checked before falling back to the file extension.
# Downloads are often written to a generic temp name (e.g. "download.tmp"),
# so the extension alone is not a reliable indicator of the archive format.
_ARCHIVE_SIGNATURES = (
    (b'PK\x03\x04', 'zip'),
    (b'PK\x05\x06', 'zip'),   # empty archive
    (b'PK\x07\x08', 'zip'),   # spanned archive
    (b'\x1f\x8b', 'tar.gz'),
    (b'BZh', 'tar.bz2'),
    (b'\xfd7zXZ\x00', 'tar.xz'),
)

_TAR_MODES = {
    'tar.gz': 'r:gz',
    'tar.bz2': 'r:bz2',
    'tar.xz': 'r:xz',
    'tar': 'r:',
}


class DownloadError(Exception):
    """Raised when download fails"""
    pass


class UnsafeArchiveError(DownloadError):
    """Raised when an archive member would extract outside the destination"""
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

            try:
                response_ctx = urlopen(request, timeout=self.timeout)
            except HTTPError as e:
                if e.code == 416 and start_pos > 0:
                    # The local file is already >= the remote size, which usually
                    # means a previous attempt finished but its consumer failed.
                    # Discard it and fetch from scratch rather than dead-ending.
                    logger.warning(
                        "Server rejected resume range (HTTP 416); "
                        "discarding partial file and restarting download"
                    )
                    dest_path.unlink(missing_ok=True)
                    start_pos = 0
                    mode = 'wb'
                    headers.pop('Range', None)
                    response_ctx = urlopen(Request(url, headers=headers), timeout=self.timeout)
                else:
                    raise

            with response_ctx as response:
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
            self._discard_partial(dest_path, start_pos)
            error_msg = f"HTTP Error {e.code}: {e.reason}"
            logger.error(error_msg)
            raise DownloadError(error_msg) from e

        except URLError as e:
            self._discard_partial(dest_path, start_pos)
            error_msg = f"URL Error: {e.reason}"
            logger.error(error_msg)
            raise DownloadError(error_msg) from e

        except Exception as e:
            self._discard_partial(dest_path, start_pos)
            error_msg = f"Download failed: {str(e)}"
            logger.error(error_msg)
            raise DownloadError(error_msg) from e
        
        # Verify hash if provided
        if expected_hash:
            if not self.verify_hash(dest_path, expected_hash):
                dest_path.unlink()  # Delete corrupted file
                raise DownloadError(f"Hash verification failed for {dest_path}")

        return dest_path

    @staticmethod
    def _discard_partial(dest_path: Path, start_pos: int) -> None:
        """
        Remove a partially written download so the next attempt starts clean.

        A partial file left behind is worse than no file: the next resume sends
        a Range header derived from its size, which the server may reject
        outright, leaving the user stuck with no way to recover from the UI.
        """
        if start_pos > 0:
            # Pre-existing bytes belong to an earlier attempt that may still be
            # resumable; only whole-file failures are cleaned up here.
            return
        try:
            if dest_path.exists():
                dest_path.unlink()
                logger.info(f"Removed partial download: {dest_path}")
        except OSError as e:
            logger.warning(f"Could not remove partial download {dest_path}: {e}")

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
        archive_format = self.detect_archive_format(archive_path)

        if archive_format is None:
            raise DownloadError(
                f"Unsupported archive format: {archive_path}. "
                "Expected a zip, tar, tar.gz, tar.bz2 or tar.xz archive."
            )

        try:
            if archive_format == 'zip':
                import zipfile
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    members = zip_ref.namelist()
                    for member in members:
                        self._assert_safe_member(member, destination)
                        if progress_callback:
                            progress_callback(member)
                        zip_ref.extract(member, destination)
            else:
                import tarfile
                with tarfile.open(archive_path, _TAR_MODES[archive_format]) as tar_ref:
                    members = tar_ref.getmembers()
                    for member in members:
                        self._assert_safe_member(member.name, destination)
                        if member.issym() or member.islnk():
                            # Link targets are resolved at extraction time and can
                            # escape the destination even when the name looks safe.
                            self._assert_safe_member(member.linkname, destination)
                        if progress_callback:
                            progress_callback(member.name)
                        tar_ref.extract(member, destination)

            logger.info(
                f"Extracted {len(members)} files from {archive_path} (format: {archive_format})"
            )
            return destination

        except UnsafeArchiveError:
            raise
        except Exception as e:
            error_msg = f"Extraction failed: {str(e)}"
            logger.error(error_msg)
            raise DownloadError(error_msg) from e

    @staticmethod
    def detect_archive_format(archive_path: Path) -> Optional[str]:
        """
        Identify an archive's format from its magic bytes, falling back to its
        extension.

        Content sniffing comes first because downloads are frequently saved
        under a generic temporary name that carries no meaningful extension.

        Returns:
            One of 'zip', 'tar.gz', 'tar.bz2', 'tar.xz', 'tar', or None if the
            format is not recognised.
        """
        try:
            with open(archive_path, 'rb') as f:
                header = f.read(264)
        except OSError as e:
            logger.warning(f"Could not read archive header from {archive_path}: {e}")
            header = b''

        for signature, fmt in _ARCHIVE_SIGNATURES:
            if header.startswith(signature):
                return fmt

        # Uncompressed tar carries its magic at offset 257, not at the start.
        if header[257:262] in (b'ustar', b'ustar'):
            return 'tar'

        name = str(archive_path).lower()
        if name.endswith('.zip'):
            return 'zip'
        if name.endswith(('.tar.gz', '.tgz')):
            return 'tar.gz'
        if name.endswith(('.tar.bz2', '.tbz2')):
            return 'tar.bz2'
        if name.endswith(('.tar.xz', '.txz')):
            return 'tar.xz'
        if name.endswith('.tar'):
            return 'tar'

        return None

    @staticmethod
    def _assert_safe_member(member_name: str, destination: Path) -> None:
        """
        Reject archive members that would be written outside `destination`.

        Guards against absolute paths and `..` traversal (zip-slip / tar-slip).
        `tarfile` performs no such validation of its own before Python 3.14.
        """
        if not member_name:
            return

        candidate = Path(member_name)
        if candidate.is_absolute() or member_name.startswith(('/', '\\')):
            raise UnsafeArchiveError(
                f"Refusing to extract absolute path from archive: {member_name}"
            )

        target = (destination / candidate).resolve()
        root = destination.resolve()
        if target != root and root not in target.parents:
            raise UnsafeArchiveError(
                f"Refusing to extract outside destination: {member_name}"
            )
    
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
