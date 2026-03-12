#!/usr/bin/env python3
"""
Camera Emulator - Virtual Camera Device for Windows 11
Displays images/videos at 1932x2576 resolution and outputs to virtual camera
Supports: JPG, Animated GIF, MP4 (auto-stretched to fit)
"""

import cv2
import numpy as np
from PIL import Image, ImageSequence
import sys
import os
import time
from pathlib import Path
import pyvirtualcam
import argparse

class VirtualCameraEmulator:
    def __init__(self, resolution=(1932, 2576), fps=30):
        """
        Initialize virtual camera emulator with specified resolution
        Default: 1932x2576 (portrait orientation)
        """
        self.width, self.height = resolution
        self.fps = fps
        self.window_name = f"Camera Emulator - {self.width}x{self.height}"
        self.running = False
        self.paused = False
        self.current_frame = None
        
        # Create window for preview (optional)
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, self.width // 2, self.height // 2)  # Smaller preview
        
        print(f"🎥 Virtual Camera Initialized: {self.width}x{self.height} @ {self.fps}fps")
        print("The camera will appear as 'OBS Virtual Camera' in applications")
        
    def stretch_frame(self, frame):
        """
        Stretch frame to target resolution
        """
        if frame.shape[:2] == (self.height, self.width):
            return frame
        
        # Resize frame to target dimensions (stretch)
        stretched = cv2.resize(frame, (self.width, self.height), 
                              interpolation=cv2.INTER_LINEAR)
        return stretched
    
    def process_frame(self, frame):
        """Process a single frame and prepare for virtual camera"""
        # Stretch to fit
        display_frame = self.stretch_frame(frame)
        
        # Convert BGR to RGB for pyvirtualcam
        frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        
        # Store for preview
        self.current_frame = display_frame
        
        return frame_rgb
    
    def run_virtual_camera(self, frame_generator):
        """
        Main loop that sends frames to virtual camera
        frame_generator: generator function that yields frames
        """
        try:
            with pyvirtualcam.Camera(self.width, self.height, self.fps) as cam:
                print(f"✅ Virtual camera active: {cam.device}")
                print("Controls:")
                print("  - Press 'q' or ESC to quit")
                print("  - Press SPACE to pause/resume")
                print("  - Press 'f' to toggle full preview")
                print("-" * 50)
                
                for frame_bgr in frame_generator:
                    if frame_bgr is None:
                        continue
                    
                    if not self.paused:
                        # Process frame for virtual camera
                        frame_rgb = self.process_frame(frame_bgr)
                        
                        # Send to virtual camera
                        cam.send(frame_rgb)
                        
                        # Show preview
                        preview_frame = self.current_frame.copy()
                        
                        # Add status overlay
                        if self.paused:
                            cv2.putText(preview_frame, "PAUSED", (50, 100), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)
                        
                        cv2.imshow(self.window_name, preview_frame)
                    
                    # Handle keyboard input
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q') or key == 27:  # 'q' or ESC
                        break
                    elif key == ord(' '):  # Space to pause
                        self.paused = not self.paused
                        print(f"{'Paused' if self.paused else 'Resumed'}")
                    
                    # Sync with virtual camera framerate
                    cam.sleep_until_next_frame()
                    
        except pyvirtualcam.errors.VirtualCamNotFoundError:
            print("❌ Error: No virtual camera found!")
            print("\nPlease install OBS Studio first:")
            print("1. Download from: https://obsproject.com/")
            print("2. Install OBS Studio")
            print("3. Run OBS at least once to initialize the virtual camera")
            print("4. Try running this script again")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
        
        return True
    
    def generate_frames_from_jpg(self, image_path):
        """Generate frames from a single JPG image"""
        frame = cv2.imread(str(image_path))
        if frame is None:
            print(f"Error: Could not read image {image_path}")
            return
        
        while True:
            yield frame
    
    def generate_frames_from_gif(self, gif_path):
        """Generate frames from an animated GIF"""
        try:
            gif = Image.open(gif_path)
            
            while True:  # Loop GIF
                for frame in ImageSequence.Iterator(gif):
                    # Convert PIL image to numpy array (RGB)
                    frame_rgb = np.array(frame.convert('RGB'))
                    # Convert RGB to BGR for OpenCV
                    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                    yield frame_bgr
                    
        except Exception as e:
            print(f"Error displaying GIF: {e}")
            yield None
    
    def generate_frames_from_mp4(self, video_path):
        """Generate frames from an MP4 video"""
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            print(f"Error: Could not open video {video_path}")
            return
        
        while True:
            ret, frame = cap.read()
            if not ret:
                # Loop video
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            
            yield frame
        
        cap.release()
    
    def generate_test_pattern(self):
        """Generate test pattern frames"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Fill with gradient
        for y in range(self.height):
            for x in range(self.width):
                r = int(255 * x / self.width)
                g = int(255 * y / self.height)
                b = int(255 * (x + y) / (self.width + self.height))
                frame[y, x] = [b, g, r]
        
        # Add grid lines
        grid_color = [255, 255, 255]
        for x in range(0, self.width, 100):
            cv2.line(frame, (x, 0), (x, self.height-1), grid_color, 1)
        for y in range(0, self.height, 100):
            cv2.line(frame, (0, y), (self.width-1, y), grid_color, 1)
        
        # Add resolution text
        text = f"{self.width}x{self.height}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 2.0
        thickness = 3
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        x = (self.width - text_width) // 2
        y = (self.height + text_height) // 2
        cv2.rectangle(frame, (x-10, y-text_height-10), (x+text_width+10, y+10), [0, 0, 0], -1)
        cv2.putText(frame, text, (x, y), font, font_scale, [255, 255, 255], thickness)
        
        while True:
            yield frame

def main():
    parser = argparse.ArgumentParser(description='Virtual Camera Emulator for Windows 11')
    parser.add_argument('file', nargs='?', help='Media file to display (jpg/gif/mp4)')
    parser.add_argument('--test', action='store_true', help='Show test pattern')
    parser.add_argument('--width', type=int, default=1932, help='Camera width (default: 1932)')
    parser.add_argument('--height', type=int, default=2576, help='Camera height (default: 2576)')
    parser.add_argument('--fps', type=int, default=30, help='Camera FPS (default: 30)')
    
    args = parser.parse_args()
    
    # Create virtual camera emulator
    camera = VirtualCameraEmulator(resolution=(args.width, args.height), fps=args.fps)
    
    # Select frame generator
    if args.test:
        print("📹 Starting test pattern...")
        generator = camera.generate_test_pattern()
    elif args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File not found: {file_path}")
            sys.exit(1)
        
        ext = file_path.suffix.lower()
        print(f"📹 Loading: {file_path}")
        
        if ext in ['.jpg', '.jpeg', '.png', '.bmp']:
            generator = camera.generate_frames_from_jpg(file_path)
        elif ext == '.gif':
            generator = camera.generate_frames_from_gif(file_path)
        elif ext in ['.mp4', '.avi', '.mov', '.mkv']:
            generator = camera.generate_frames_from_mp4(file_path)
        else:
            print(f"Unsupported format: {ext}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)
    
    # Run virtual camera
    success = camera.run_virtual_camera(generator)
    
    if not success:
        sys.exit(1)
    
    cv2.destroyAllWindows()
    print("👋 Camera emulator stopped")

if __name__ == "__main__":
    main()