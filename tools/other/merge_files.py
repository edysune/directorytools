#!/usr/bin/env python3
"""
Audio/Video File Merger

This script merges split audio/video files that follow the pattern:
{directory}/{title}.part{XX}.{extension}

Example:
    python merge_files.py '/home/robit/Downloads/Merlin/Merlin (1998).part01.mkv'
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple, Optional


class FileMerger:
    SUPPORTED_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', 
                           '.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma'}
    
    def __init__(self, input_file: str):
        self.input_file = Path(input_file)
        self.validate_input_file()
        
    def validate_input_file(self):
        """Validate the input file exists and has supported extension."""
        if not self.input_file.exists():
            raise FileNotFoundError(f"Input file does not exist: {self.input_file}")
        
        if not self.input_file.suffix.lower() in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file extension: {self.input_file.suffix}")
    
    def parse_file_pattern(self) -> Tuple[str, str, str, int]:
        """
        Parse the input file pattern and extract components.
        
        Returns:
            Tuple of (directory, title, extension, part_number)
        """
        # Pattern: {title}.part{XX}.{extension}
        filename = self.input_file.name
        pattern = r'^(.+)\.part(\d+)\.(.+)$'
        
        match = re.match(pattern, filename)
        if not match:
            raise ValueError(f"File does not match expected pattern: {filename}")
        
        title = match.group(1)
        part_str = match.group(2)
        extension = match.group(3)
        
        # Validate part number format (should be 2 digits)
        if not re.match(r'^\d{2}$', part_str):
            raise ValueError(f"Part number should be 2 digits: {part_str}")
        
        part_number = int(part_str)
        
        return str(self.input_file.parent), title, extension, part_number
    
    def find_matching_files(self, directory: str, title: str, extension: str) -> List[Path]:
        """
        Find all files matching the pattern in the same directory.
        
        Args:
            directory: Directory to search in
            title: Title part of the filename
            extension: File extension
            
        Returns:
            List of matching file paths
        """
        dir_path = Path(directory)
        pattern = f"{title}.part*.{extension}"
        
        matching_files = []
        for file_path in dir_path.glob(pattern):
            # Validate the file matches the exact pattern
            filename = file_path.name
            match = re.match(rf'^{re.escape(title)}\.part(\d+)\.{re.escape(extension)}$', filename)
            if match:
                part_num = int(match.group(1))
                matching_files.append((file_path, part_num))
        
        # Sort by part number
        matching_files.sort(key=lambda x: x[1])
        
        return [file_path for file_path, _ in matching_files]
    
    def validate_sequence(self, files: List[Path]) -> bool:
        """
        Validate that files form a complete sequence without gaps.
        
        Args:
            files: List of file paths sorted by part number
            
        Returns:
            True if sequence is complete, False otherwise
        """
        if not files:
            return False
        
        # Extract part numbers
        part_numbers = []
        for file_path in files:
            filename = file_path.name
            match = re.match(r'^.+\.part(\d+)\..+$', filename)
            if match:
                part_numbers.append(int(match.group(1)))
        
        if not part_numbers:
            return False
        
        # Check if sequence is consecutive
        part_numbers.sort()
        for i in range(1, len(part_numbers)):
            if part_numbers[i] != part_numbers[i-1] + 1:
                return False
        
        return True
    
    def check_ffmpeg_available(self) -> bool:
        """Check if ffmpeg is available in the system."""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def merge_files(self, files: List[Path], output_file: Optional[str] = None) -> str:
        """
        Merge files using ffmpeg.
        
        Args:
            files: List of file paths to merge
            output_file: Output file path (optional)
            
        Returns:
            Path to the merged file
        """
        if not self.check_ffmpeg_available():
            raise RuntimeError("ffmpeg is not installed or not available in PATH")
        
        if not files:
            raise ValueError("No files to merge")
        
        # Generate output filename if not provided
        if output_file is None:
            directory, title, extension, _ = self.parse_file_pattern()
            output_file = f"{directory}/{title}.{extension}"
        
        output_path = Path(output_file)
        
        # Check if output file already exists
        if output_path.exists():
            response = input(f"Output file '{output_file}' already exists. Overwrite? (y/N): ")
            if response.lower() != 'y':
                raise KeyboardInterrupt("Operation cancelled by user")
        
        # Create temporary file list for ffmpeg
        file_list_path = output_path.parent / "filelist.txt"
        with open(file_list_path, 'w') as f:
            for file_path in files:
                f.write(f"file '{file_path.absolute()}'\n")
        
        try:
            # Use ffmpeg concat demuxer for lossless merging
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(file_list_path),
                '-c', 'copy',
                str(output_path)
            ]
            
            print(f"Merging {len(files)} files into {output_path}")
            print("Running ffmpeg command...")
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            print("Merge completed successfully!")
            return str(output_path)
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"ffmpeg failed: {e.stderr}")
        finally:
            # Clean up temporary file
            if file_list_path.exists():
                file_list_path.unlink()
    
    def run(self, output_file: Optional[str] = None) -> str:
        """
        Run the complete merge process.
        
        Args:
            output_file: Optional output file path
            
        Returns:
            Path to the merged file
        """
        # Parse the input file pattern
        directory, title, extension, part_number = self.parse_file_pattern()
        
        print(f"Input file: {self.input_file}")
        print(f"Directory: {directory}")
        print(f"Title: {title}")
        print(f"Extension: {extension}")
        print(f"Part: {part_number:02d}")
        
        # Find matching files
        matching_files = self.find_matching_files(directory, title, extension)
        
        if not matching_files:
            raise ValueError(f"No matching files found for pattern: {title}.part*.{extension}")
        
        print(f"\nFound {len(matching_files)} matching files:")
        for i, file_path in enumerate(matching_files, 1):
            filename = file_path.name
            match = re.match(r'^.+\.part(\d+)\..+$', filename)
            part_num = match.group(1) if match else "??"
            print(f"  {i}. {filename} (part {part_num})")
        
        # Validate sequence
        if not self.validate_sequence(matching_files):
            raise ValueError("Files do not form a complete sequence - there are gaps in the numbering")
        
        print("\nSequence validation: PASSED")
        
        # Merge files
        return self.merge_files(matching_files, output_file)


def main():
    parser = argparse.ArgumentParser(
        description="Merge split audio/video files that follow the pattern {title}.part{XX}.{extension}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python merge_files.py '/home/robit/Downloads/Merlin/Merlin (1998).part01.mkv'
    python merge_files.py '/path/to/movie.part01.mp4' -o '/path/to/merged_movie.mp4'
        """
    )
    
    parser.add_argument('input_file', help='Path to the first part of the split files')
    parser.add_argument('-o', '--output', help='Output file path (optional)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    try:
        merger = FileMerger(args.input_file)
        output_file = merger.run(args.output)
        
        print(f"\n✓ Successfully merged files to: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
