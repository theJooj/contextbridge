#!/usr/bin/env python3
"""
ContextBridge - Mac to OpenClaw Context Streaming
Captures screen context and streams to OpenClaw for enhanced AI conversations.
"""

import time
import json
import requests
import argparse
import sys
import threading
from datetime import datetime
from typing import Dict, Optional, List

try:
    import PyScreenReader as psr
except ImportError:
    print("PyScreenReader not installed. Run: pip install PyScreenReader")
    sys.exit(1)

class ContextBridge:
    def __init__(self, config_path: str = "config.json"):
        self.config = self.load_config(config_path)
        self.running = False
        self.last_context = ""
        
    def load_config(self, path: str) -> Dict:
        """Load configuration from file"""
        default_config = {
            "openclaw_endpoint": "http://192.168.5.87:18789/api/context",
            "poll_interval": 5,  # seconds
            "min_text_length": 20,
            "ignored_apps": ["1Password", "Keychain Access", "Activity Monitor"],
            "ignored_keywords": ["password", "ssn", "credit card"],
            "max_context_length": 2000
        }
        
        try:
            with open(path, 'r') as f:
                config = json.load(f)
                # Merge with defaults
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        except FileNotFoundError:
            print(f"Config not found, creating {path} with defaults")
            self.save_config(default_config, path)
            return default_config
    
    def save_config(self, config: Dict, path: str):
        """Save configuration to file"""
        with open(path, 'w') as f:
            json.dump(config, f, indent=2)
    
    def get_active_window_context(self) -> Optional[Dict]:
        """Extract context from active window"""
        try:
            # Get active application and window
            active_app = psr.get_active_application()
            if not active_app:
                return None
                
            app_name = active_app.get_name()
            
            # Check if app is ignored
            if app_name in self.config["ignored_apps"]:
                return None
            
            # Get window content
            windows = active_app.get_windows()
            if not windows:
                return None
            
            active_window = windows[0]  # First window is typically active
            window_title = active_window.get_title()
            
            # Extract text content
            text_content = self.extract_text_from_element(active_window)
            
            # Filter sensitive content
            if self.contains_sensitive_content(text_content):
                return None
            
            # Check minimum length
            if len(text_content) < self.config["min_text_length"]:
                return None
            
            # Truncate if too long
            if len(text_content) > self.config["max_context_length"]:
                text_content = text_content[:self.config["max_context_length"]] + "..."
            
            return {
                "timestamp": datetime.now().isoformat(),
                "app_name": app_name,
                "window_title": window_title,
                "text_content": text_content,
                "source": "contextbridge_mac"
            }
            
        except Exception as e:
            print(f"Error getting context: {e}")
            return None
    
    def extract_text_from_element(self, element) -> str:
        """Recursively extract text from UI element"""
        try:
            text_parts = []
            
            # Get direct text value
            if hasattr(element, 'get_value'):
                value = element.get_value()
                if value and isinstance(value, str):
                    text_parts.append(value)
            
            # Get text from title/label
            if hasattr(element, 'get_title'):
                title = element.get_title()
                if title and isinstance(title, str):
                    text_parts.append(title)
            
            # Get children and recurse
            if hasattr(element, 'get_children'):
                children = element.get_children()
                for child in children[:10]:  # Limit to prevent deep recursion
                    child_text = self.extract_text_from_element(child)
                    if child_text:
                        text_parts.append(child_text)
            
            return " ".join(text_parts)
            
        except Exception:
            return ""
    
    def contains_sensitive_content(self, text: str) -> bool:
        """Check if text contains sensitive information"""
        text_lower = text.lower()
        for keyword in self.config["ignored_keywords"]:
            if keyword.lower() in text_lower:
                return True
        return False
    
    def send_context_to_openclaw(self, context: Dict) -> bool:
        """Send context data to OpenClaw"""
        try:
            response = requests.post(
                self.config["openclaw_endpoint"],
                json=context,
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Failed to send context to OpenClaw: {e}")
            return False
    
    def context_changed(self, new_context: str) -> bool:
        """Check if context has meaningfully changed"""
        if not self.last_context:
            return True
        
        # Simple change detection - could be made smarter
        similarity = len(set(new_context.split()) & set(self.last_context.split()))
        total_words = len(set(new_context.split()) | set(self.last_context.split()))
        
        if total_words == 0:
            return False
        
        similarity_ratio = similarity / total_words
        return similarity_ratio < 0.8  # Send if less than 80% similar
    
    def run_daemon(self):
        """Main daemon loop"""
        print(f"ContextBridge started - polling every {self.config['poll_interval']}s")
        print(f"Sending context to: {self.config['openclaw_endpoint']}")
        
        self.running = True
        
        while self.running:
            try:
                context = self.get_active_window_context()
                
                if context:
                    text_content = context["text_content"]
                    
                    if self.context_changed(text_content):
                        print(f"[{context['timestamp'][:19]}] {context['app_name']}: {text_content[:100]}...")
                        
                        if self.send_context_to_openclaw(context):
                            self.last_context = text_content
                        else:
                            print("Failed to send to OpenClaw")
                
                time.sleep(self.config["poll_interval"])
                
            except KeyboardInterrupt:
                print("\nShutting down ContextBridge...")
                break
            except Exception as e:
                print(f"Error in daemon loop: {e}")
                time.sleep(1)
        
        self.running = False

def main():
    parser = argparse.ArgumentParser(description="ContextBridge - Mac to OpenClaw Context Streaming")
    parser.add_argument("--config", default="config.json", help="Config file path")
    parser.add_argument("--setup", action="store_true", help="Setup configuration")
    parser.add_argument("--start", action="store_true", help="Start daemon")
    parser.add_argument("--test", action="store_true", help="Test screen reading")
    
    args = parser.parse_args()
    
    bridge = ContextBridge(args.config)
    
    if args.setup:
        print("ContextBridge Setup")
        print("==================")
        print("1. Install PyScreenReader: pip install PyScreenReader")
        print("2. Grant Accessibility permissions:")
        print("   System Preferences → Privacy & Security → Accessibility")
        print("   Add Terminal or your Python interpreter")
        print("3. Configure OpenClaw endpoint in config.json")
        print(f"4. Current config: {args.config}")
        return
    
    if args.test:
        print("Testing screen reading...")
        context = bridge.get_active_window_context()
        if context:
            print(f"App: {context['app_name']}")
            print(f"Window: {context['window_title']}")
            print(f"Content: {context['text_content'][:200]}...")
        else:
            print("No context captured (check accessibility permissions)")
        return
    
    if args.start:
        bridge.run_daemon()
        return
    
    parser.print_help()

if __name__ == "__main__":
    main()