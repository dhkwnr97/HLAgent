#!/usr/bin/env python3
"""
IMGTHLA Automatic Downloader Module
===================================

Automatically downloads IPD-IMGTHLA database from GitHub releases
Supports both latest version and specific version downloads

Author: HLAgent Development Team
Version: 1.0.0
License: Academic Use Only
"""

import os
import sys
import requests
import zipfile
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import tempfile
import json
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class IMGTHLARelease:
    """IMGTHLA release information"""
    tag_name: str
    name: str
    published_at: str
    zipball_url: str
    tarball_url: str
    prerelease: bool
    draft: bool
    
    @property
    def version_number(self) -> str:
        """Extract version number from tag (e.g., 'v3.60.0' -> '3600')"""
        # Remove 'v' prefix and dots
        version = self.tag_name.lstrip('v').replace('.', '')
        return version
    
    @property
    def display_version(self) -> str:
        """Display version (e.g., '3.60.0')"""
        return self.tag_name.lstrip('v')


class IMGTHLADownloader:
    """
    IMGTHLA Database Automatic Downloader
    
    Downloads IPD-IMGTHLA database from GitHub releases and prepares
    it for use with HLAgent IMGT2Seq pipeline.
    """
    
    def __init__(self, download_dir: Optional[str] = None):
        """
        Initialize IMGTHLA downloader
        
        Args:
            download_dir: Directory to download IMGTHLA data (default: ./data/imgthla)
        """
        if download_dir is None:
            # Default to data/imgthla in the current module directory
            self.download_dir = Path(__file__).parent.parent / "data" / "imgthla"
        else:
            self.download_dir = Path(download_dir)
        
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # GitHub API endpoints
        self.github_api_base = "https://api.github.com/repos/ANHIG/IMGTHLA"
        self.releases_endpoint = f"{self.github_api_base}/releases"
        self.latest_endpoint = f"{self.releases_endpoint}/latest"
        
        logger.info(f"IMGTHLA Downloader initialized - Download dir: {self.download_dir}")
    
    def get_available_releases(self, include_prereleases: bool = False) -> List[IMGTHLARelease]:
        """
        Get list of available IMGTHLA releases from GitHub
        
        Args:
            include_prereleases: Include pre-release versions
            
        Returns:
            List of available releases
        """
        logger.info("Fetching available IMGTHLA releases from GitHub...")
        
        try:
            response = requests.get(self.releases_endpoint, timeout=30)
            response.raise_for_status()
            
            releases_data = response.json()
            releases = []
            
            for release_data in releases_data:
                release = IMGTHLARelease(
                    tag_name=release_data['tag_name'],
                    name=release_data['name'],
                    published_at=release_data['published_at'],
                    zipball_url=release_data['zipball_url'],
                    tarball_url=release_data['tarball_url'],
                    prerelease=release_data.get('prerelease', False),
                    draft=release_data.get('draft', False)
                )
                
                # Filter out drafts and optionally prereleases
                if not release.draft and (include_prereleases or not release.prerelease):
                    releases.append(release)
            
            logger.info(f"Found {len(releases)} available releases")
            return releases
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch releases from GitHub: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def get_latest_release(self) -> IMGTHLARelease:
        """Get the latest stable release"""
        logger.info("Fetching latest IMGTHLA release...")
        
        try:
            response = requests.get(self.latest_endpoint, timeout=30)
            response.raise_for_status()
            
            release_data = response.json()
            release = IMGTHLARelease(
                tag_name=release_data['tag_name'],
                name=release_data['name'],
                published_at=release_data['published_at'],
                zipball_url=release_data['zipball_url'],
                tarball_url=release_data['tarball_url'],
                prerelease=release_data.get('prerelease', False),
                draft=release_data.get('draft', False)
            )
            
            logger.info(f"Latest release: {release.display_version}")
            return release
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch latest release: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def find_release_by_version(self, version: str) -> Optional[IMGTHLARelease]:
        """
        Find release by version number
        Args:
            version: Version string (e.g., "3600", "3.60.0", "v3.60.0", "3.60.0-alpha", "latest")
        Returns:
            Matching release or None if not found
        """
        if version.lower() == "latest":
            return self.get_latest_release()

        releases = self.get_available_releases()

        # Normalize user input
        user_version = version.lower().replace('v', '').replace('_', '').replace('-', '').replace('.', '')
        user_version_dotted = '.'.join(user_version) if user_version.isdigit() and len(user_version) == 4 else version.lower().replace('v', '').replace('_', '').replace('-', '')

        for release in releases:
            tag = release.tag_name.lower()
            tag_nov = tag.lstrip('v')
            tag_nodash = tag.replace('-', '').replace('_', '').replace('.', '')
            tag_nov_nodash = tag_nov.replace('-', '').replace('_', '').replace('.', '')

            # Direct matches
            if (
                user_version == tag_nodash or
                user_version == tag_nov_nodash or
                user_version in tag_nodash or
                user_version in tag_nov_nodash or
                user_version_dotted in tag or
                user_version_dotted in tag_nov or
                user_version in tag or
                user_version in tag_nov
            ):
                return release

            # Try matching '3600' to '3.60.0-alpha' or similar
            if user_version.isdigit() and len(user_version) == 4:
                dotted = f"{user_version[0]}.{user_version[1:3]}.{user_version[3]}"
                if dotted in tag or dotted in tag_nov:
                    return release
                if f"{dotted}-alpha" in tag or f"{dotted}-alpha" in tag_nov:
                    return release

        return None
    
    def download_release(self, release: IMGTHLARelease, force_download: bool = False) -> str:
        """
        Download and extract IMGTHLA release
        
        Args:
            release: Release to download
            force_download: Force re-download even if already exists
            
        Returns:
            Path to extracted IMGTHLA directory
        """
        # Create version-specific directory
        version_dir = self.download_dir / f"IMGTHLA-{release.display_version}"
        
        # Check if already downloaded
        if version_dir.exists() and not force_download:
            logger.info(f"IMGTHLA {release.display_version} already exists at {version_dir}")
            if self._validate_imgthla_directory(version_dir):
                return str(version_dir)
            else:
                logger.warning("Existing directory incomplete, re-downloading...")
                shutil.rmtree(version_dir)
        
        logger.info(f"Downloading IMGTHLA {release.display_version}...")
        
        # Create temporary download directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            zip_file = temp_path / f"IMGTHLA-{release.display_version}.zip"
            
            # Download ZIP file
            logger.info(f"Downloading from: {release.zipball_url}")
            self._download_file(release.zipball_url, zip_file)
            
            # Extract ZIP file
            logger.info("Extracting downloaded archive...")
            extract_dir = temp_path / "extracted"
            extract_dir.mkdir()
            
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # Find the extracted directory (GitHub creates a directory with commit hash)
            extracted_dirs = list(extract_dir.iterdir())
            if not extracted_dirs:
                raise Exception("No directories found in extracted archive")
            
            source_dir = extracted_dirs[0]  # Should be the only directory
            
            # Move to final location
            if version_dir.exists():
                shutil.rmtree(version_dir)
            
            shutil.move(str(source_dir), str(version_dir))
            
        # Validate downloaded content
        if not self._validate_imgthla_directory(version_dir):
            raise Exception(f"Downloaded IMGTHLA directory is incomplete: {version_dir}")
        
        logger.info(f"✅ IMGTHLA {release.display_version} downloaded successfully to {version_dir}")
        return str(version_dir)
    
    def _download_file(self, url: str, output_path: Path, chunk_size: int = 8192):
        """Download file with progress tracking"""
        try:
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Log progress every 10MB
                        if downloaded_size % (10 * 1024 * 1024) == 0:
                            if total_size > 0:
                                progress = (downloaded_size / total_size) * 100
                                logger.info(f"Download progress: {progress:.1f}% ({downloaded_size // (1024*1024)} MB)")
                            else:
                                logger.info(f"Downloaded: {downloaded_size // (1024*1024)} MB")
            
            logger.info(f"Download completed: {output_path}")
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to download file from {url}: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def _validate_imgthla_directory(self, directory: Path) -> bool:
        """
        Validate that IMGTHLA directory contains required files
        
        Args:
            directory: Path to IMGTHLA directory
            
        Returns:
            True if directory contains all required files
        """
        required_files = [
            "Allelelist.txt",
            "Nomenclature_2009.txt",
            "wmda/hla_nom_g.txt",
            "wmda/hla_nom_p.txt"
        ]
        
        required_dirs = [
            "alignments"
        ]
        
        # Check required files
        for file_path in required_files:
            if not (directory / file_path).exists():
                logger.warning(f"Missing required file: {file_path}")
                return False
        
        # Check required directories
        for dir_path in required_dirs:
            if not (directory / dir_path).is_dir():
                logger.warning(f"Missing required directory: {dir_path}")
                return False
        
        # Check alignments directory has some content
        alignments_dir = directory / "alignments"
        alignment_files = list(alignments_dir.glob("*.txt"))
        if len(alignment_files) < 10:  # Should have many alignment files
            logger.warning(f"Alignments directory seems incomplete: only {len(alignment_files)} files")
            return False
        
        logger.info("IMGTHLA directory validation passed")
        return True
    
    def get_imgthla_directory(self, version: Optional[str] = None, auto_download: bool = True) -> str:
        """
        Get IMGTHLA directory path, downloading if necessary
        
        Args:
            version: Specific version to get ("latest", "3600", "3.60.0", etc.)
                    If None, tries to use existing or downloads latest
            auto_download: Automatically download if not found
            
        Returns:
            Path to IMGTHLA directory
        """
        if version is None or version.lower() == "latest":
            # Get latest version
            release = self.get_latest_release()
        else:
            # Find specific version
            release = self.find_release_by_version(version)
            if not release:
                available_releases = self.get_available_releases()
                available_versions = [r.display_version for r in available_releases[:10]]  # Show first 10
                raise Exception(
                    f"Version '{version}' not found. Available versions: {', '.join(available_versions)}"
                )
        
        # Check if already exists
        version_dir = self.download_dir / f"IMGTHLA-{release.display_version}"
        if version_dir.exists() and self._validate_imgthla_directory(version_dir):
            logger.info(f"Using existing IMGTHLA {release.display_version}: {version_dir}")
            return str(version_dir)
        
        # Download if auto_download is enabled
        if auto_download:
            return self.download_release(release)
        else:
            raise Exception(f"IMGTHLA {release.display_version} not found and auto_download is disabled")
    
    def list_downloaded_versions(self) -> List[str]:
        """List all downloaded IMGTHLA versions"""
        if not self.download_dir.exists():
            return []
        
        versions = []
        for item in self.download_dir.iterdir():
            if item.is_dir() and item.name.startswith("IMGTHLA-"):
                version = item.name.replace("IMGTHLA-", "")
                if self._validate_imgthla_directory(item):
                    versions.append(version)
        
        return sorted(versions, reverse=True)  # Latest first
    
    def cleanup_old_versions(self, keep_latest: int = 2):
        """
        Remove old IMGTHLA versions, keeping only the specified number of latest versions
        
        Args:
            keep_latest: Number of latest versions to keep
        """
        downloaded_versions = self.list_downloaded_versions()
        
        if len(downloaded_versions) <= keep_latest:
            logger.info(f"Only {len(downloaded_versions)} versions found, no cleanup needed")
            return
        
        versions_to_remove = downloaded_versions[keep_latest:]
        
        for version in versions_to_remove:
            version_dir = self.download_dir / f"IMGTHLA-{version}"
            if version_dir.exists():
                logger.info(f"Removing old IMGTHLA version: {version}")
                shutil.rmtree(version_dir)
        
        logger.info(f"Cleanup completed, kept {keep_latest} latest versions")


# Convenience functions for easy usage
def download_latest_imgthla(download_dir: Optional[str] = None) -> str:
    """
    Download latest IMGTHLA version
    
    Args:
        download_dir: Directory to download to
        
    Returns:
        Path to downloaded IMGTHLA directory
    """
    downloader = IMGTHLADownloader(download_dir)
    return downloader.get_imgthla_directory("latest")


def download_imgthla_version(version: str, download_dir: Optional[str] = None) -> str:
    """
    Download specific IMGTHLA version
    
    Args:
        version: Version to download ("3600", "3.60.0", etc.)
        download_dir: Directory to download to
        
    Returns:
        Path to downloaded IMGTHLA directory
    """
    downloader = IMGTHLADownloader(download_dir)
    return downloader.get_imgthla_directory(version)


def get_available_versions(include_prereleases: bool = False) -> List[str]:
    """
    Get list of available IMGTHLA versions
    
    Args:
        include_prereleases: Include pre-release versions
        
    Returns:
        List of version strings
    """
    downloader = IMGTHLADownloader()
    releases = downloader.get_available_releases(include_prereleases)
    return [release.display_version for release in releases]


# Example usage
if __name__ == "__main__":
    # Example: Download latest version
    downloader = IMGTHLADownloader()
    
    # List available versions
    print("Available IMGTHLA versions:")
    for version in get_available_versions()[:5]:  # Show first 5
        print(f"  - {version}")
    
    # Download latest
    imgthla_path = downloader.get_imgthla_directory("latest")
    print(f"IMGTHLA downloaded to: {imgthla_path}")
