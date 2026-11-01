#!/usr/bin/env python3
"""
SUP to SRT Converter

This script converts .sup (Blu-ray subtitle) files to .srt format.
It uses external tools for OCR to extract text from bitmap subtitles.

Requirements:
    - ffmpeg (for processing)
    - tesseract OCR engine
    - Python packages: pillow, pytesseract

Install dependencies:
    pip install pillow pytesseract
    # Install tesseract OCR:
    # Ubuntu/Debian: sudo apt-get install tesseract-ocr
    # macOS: brew install tesseract
    # Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki

Usage:
    python sup_to_srt.py input.sup [output.srt]
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple, Optional
import time

try:
    from PIL import Image
    import pytesseract
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Install with: pip install pillow pytesseract")
    sys.exit(1)


class SUPConverter:
    def __init__(self, input_file: str):
        self.input_file = Path(input_file)
        self.validate_input_file()
        
    def validate_input_file(self):
        """Validate the input file exists and has .sup extension."""
        if not self.input_file.exists():
            raise FileNotFoundError(f"Input file does not exist: {self.input_file}")
        
        if self.input_file.suffix.lower() != '.sup':
            raise ValueError(f"Input file must have .sup extension: {self.input_file}")
    
    def check_dependencies(self) -> bool:
        """Check if required external tools are available."""
        try:
            # Check ffmpeg
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            print("✓ ffmpeg found")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("✗ ffmpeg not found. Please install ffmpeg")
            return False
        
        try:
            # Check tesseract
            subprocess.run(['tesseract', '--version'], capture_output=True, check=True)
            print("✓ tesseract OCR found")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("✗ tesseract OCR not found. Please install tesseract-ocr")
            return False
        
        return True
    
    def extract_subtitles_with_ffmpeg(self) -> List[Tuple[float, float, str]]:
        """
        Extract subtitles from SUP file using ffmpeg and convert to images.
        
        Returns:
            List of tuples (start_time, end_time, text)
        """
        temp_dir = tempfile.mkdtemp()
        subtitle_data = []
        
        try:
            # First, try to extract subtitle information
            cmd_info = [
                'ffmpeg', '-i', str(self.input_file)
            ]
            
            result = subprocess.run(cmd_info, capture_output=True, text=True)
            
            # Try different extraction methods
            methods = [
                self.extract_method1,
                self.extract_method2,
                self.extract_method3
            ]
            
            for method in methods:
                try:
                    print(f"Trying extraction method: {method.__name__}")
                    subtitle_data = method(temp_dir)
                    if subtitle_data:
                        print(f"Successfully extracted {len(subtitle_data)} subtitles")
                        return subtitle_data
                except Exception as e:
                    print(f"Method {method.__name__} failed: {e}")
                    continue
            
            print("All extraction methods failed")
            return []
            
        finally:
            # Clean up temporary files
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def extract_method1(self, temp_dir: str) -> List[Tuple[float, float, str]]:
        """Method 1: Extract subtitle frames directly"""
        output_pattern = os.path.join(temp_dir, "subtitle_%04d.png")
        
        cmd = [
            'ffmpeg',
            '-i', str(self.input_file),
            '-map', '0:s:0',
            '-f', 'image2',
            '-vsync', 'vfr',
            '-y',
            output_pattern
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")
        
        return self.process_subtitle_images(temp_dir)
    
    def extract_method2(self, temp_dir: str) -> List[Tuple[float, float, str]]:
        """Method 2: Use filter_complex to extract subtitles"""
        output_pattern = os.path.join(temp_dir, "subtitle_%04d.png")
        
        cmd = [
            'ffmpeg',
            '-i', str(self.input_file),
            '-filter_complex', '[0:s:0]format=rgba,split=2[s1][s2];[s1]palettegen[p];[s2][p]paletteuse',
            '-f', 'image2',
            '-vsync', 'vfr',
            '-y',
            output_pattern
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")
        
        return self.process_subtitle_images(temp_dir)
    
    def extract_method3(self, temp_dir: str) -> List[Tuple[float, float, str]]:
        """Method 3: Extract to video then process frames"""
        video_file = os.path.join(temp_dir, "subtitles.mp4")
        
        cmd = [
            'ffmpeg',
            '-i', str(self.input_file),
            '-map', '0:s:0',
            '-c:s', 'copy',
            '-y',
            video_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")
        
        # Now extract frames from the video
        output_pattern = os.path.join(temp_dir, "frame_%04d.png")
        cmd = [
            'ffmpeg',
            '-i', video_file,
            '-f', 'image2',
            '-vsync', 'vfr',
            '-y',
            output_pattern
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")
        
        return self.process_subtitle_images(temp_dir)
    
    def process_subtitle_images(self, temp_dir: str) -> List[Tuple[float, float, str]]:
        """Process extracted subtitle images with OCR"""
        image_files = sorted(Path(temp_dir).glob("*.png"))
        
        if not image_files:
            return []
        
        subtitle_data = []
        
        for i, image_file in enumerate(image_files):
            try:
                # Extract text from image using OCR
                text = pytesseract.image_to_string(image_file, config='--psm 6').strip()
                
                if text and len(text) > 1:  # Filter out single characters
                    # Estimate timing (this is approximate)
                    start_time = i * 2.0  # Assume 2 seconds per subtitle
                    end_time = start_time + 1.5  # Assume 1.5 second duration
                    
                    subtitle_data.append((start_time, end_time, text))
                    print(f"Processed subtitle {i+1}/{len(image_files)}: {text[:50]}...")
                
            except Exception as e:
                print(f"Error processing image {image_file}: {e}")
                continue
        
        return subtitle_data
    
    def extract_subtitles_alternative(self) -> List[Tuple[float, float, str]]:
        """
        Alternative method using BDSup2Sub or other tools if available.
        """
        print("Trying alternative extraction method...")
        
        # Try to use BDSup2Sub if available (this would need to be installed separately)
        try:
            temp_dir = tempfile.mkdtemp()
            xml_file = os.path.join(temp_dir, "subtitles.xml")
            
            # This is a placeholder - BDSup2Sub would need to be installed
            cmd = ['java', '-jar', 'BDSup2Sub.jar', str(self.input_file), '-xml', xml_file]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return self.parse_xml_subtitles(xml_file)
        except Exception:
            pass
        
        # If no alternative method works, return empty list
        print("No alternative extraction method available.")
        return []
    
    def parse_xml_subtitles(self, xml_file: str) -> List[Tuple[float, float, str]]:
        """Parse XML subtitles (if available from alternative extraction)."""
        # This would implement XML parsing if BDSup2Sub or similar tool was used
        return []
    
    def format_time(self, seconds: float) -> str:
        """Format time in seconds to SRT time format (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
    
    def create_srt_content(self, subtitle_data: List[Tuple[float, float, str]]) -> str:
        """Create SRT content from subtitle data."""
        srt_content = []
        
        for i, (start_time, end_time, text) in enumerate(subtitle_data, 1):
            start_str = self.format_time(start_time)
            end_str = self.format_time(end_time)
            
            srt_content.append(f"{i}")
            srt_content.append(f"{start_str} --> {end_str}")
            srt_content.append(text)
            srt_content.append("")  # Empty line between entries
        
        return "\n".join(srt_content)
    
    def convert_to_srt(self, output_file: Optional[str] = None) -> str:
        """
        Convert SUP file to SRT format.
        
        Args:
            output_file: Optional output file path
            
        Returns:
            Path to the generated SRT file
        """
        if not self.check_dependencies():
            raise RuntimeError("Missing required dependencies")
        
        # Generate output filename if not provided
        if output_file is None:
            output_file = str(self.input_file.with_suffix('.srt'))
        
        output_path = Path(output_file)
        
        # Check if output file already exists
        if output_path.exists():
            response = input(f"Output file '{output_file}' already exists. Overwrite? (y/N): ")
            if response.lower() != 'y':
                raise KeyboardInterrupt("Operation cancelled by user")
        
        print(f"Converting {self.input_file} to {output_path}")
        
        # Extract subtitle data
        subtitle_data = self.extract_subtitles_with_ffmpeg()
        
        if not subtitle_data:
            raise RuntimeError("No subtitle data could be extracted")
        
        # Create SRT content
        srt_content = self.create_srt_content(subtitle_data)
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        
        print(f"✓ Successfully converted {len(subtitle_data)} subtitles")
        return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Convert .sup (Blu-ray subtitle) files to .srt format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python sup_to_srt.py movie.sup
    python sup_to_srt.py movie.sup -o movie.srt
    python sup_to_srt.py /path/to/subtitles.sup --verbose
        """
    )
    
    parser.add_argument('input_file', help='Path to the .sup file')
    parser.add_argument('-o', '--output', help='Output .srt file path (optional)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    try:
        converter = SUPConverter(args.input_file)
        output_file = converter.convert_to_srt(args.output)
        
        print(f"\n✓ Successfully converted to: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
