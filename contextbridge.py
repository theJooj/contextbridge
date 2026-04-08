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
    import atomacos
except ImportError:
    print("atomacos not installed. Run: pip3 install atomacos")
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
            # Get all running applications and find the best one to read
            target_apps = [
                ('com.apple.Safari', 'Safari'),
                ('com.google.Chrome', 'Chrome'), 
                ('com.microsoft.VSCode', 'VSCode'),
                ('com.apple.TextEdit', 'TextEdit'),
                ('com.apple.Notes', 'Notes'),
                ('com.apple.mail', 'Mail'),
                ('com.slack.Slack', 'Slack'),
                ('co.zeit.hyper', 'Hyper'),
                ('dev.warp.Warp-Stable', 'Warp'),
            ]
            
            best_app = None
            best_window = None
            app_name = "Unknown"
            
            # Try each target app to see if it's running and has content
            for bundle_id, name in target_apps:
                try:
                    app = atomacos.getAppRefByBundleId(bundle_id)
                    if app and hasattr(app, 'windows') and app.windows():
                        windows = app.windows()
                        if windows:
                            # Found an app with windows - use it
                            best_app = app
                            best_window = windows[0]  # Use first window
                            app_name = name
                            break
                except Exception:
                    continue  # App not running or accessible
            
            # Fallback: try frontmost app if no target apps found
            if not best_app:
                try:
                    frontmost_app = atomacos.getFrontmostApp()
                    if frontmost_app:
                        app_name = getattr(frontmost_app, 'AXTitle', '') or "Unknown"
                        
                        # Skip system apps
                        system_apps = ['Notification Center', 'Dock', 'Control Center', 'Spotlight']
                        if app_name not in system_apps:
                            best_app = frontmost_app
                            if hasattr(best_app, 'AXFocusedWindow') and best_app.AXFocusedWindow:
                                best_window = best_app.AXFocusedWindow
                            elif hasattr(best_app, 'AXMainWindow') and best_app.AXMainWindow:
                                best_window = best_app.AXMainWindow
                except Exception:
                    pass
            
            if not best_app or not best_window:
                return None
            
            # Check if app is ignored
            if app_name in self.config["ignored_apps"]:
                return None
            
            window_title = getattr(best_window, 'AXTitle', '') or ''
            
            # Extract text content
            text_content = self.extract_text_from_element(best_window)
            
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
            import traceback
            traceback.print_exc()
            return None
    
    def extract_text_from_element(self, element, depth=0) -> str:
        """Recursively extract text from UI element"""
        if depth > 3:  # Prevent deep recursion
            return ""
            
        try:
            text_parts = []
            
            # Get direct text value
            if hasattr(element, 'AXValue') and element.AXValue:
                if isinstance(element.AXValue, str):
                    text_parts.append(element.AXValue)
            
            # Get text from title/label
            if hasattr(element, 'AXTitle') and element.AXTitle:
                if isinstance(element.AXTitle, str):
                    text_parts.append(element.AXTitle)
            
            # Get text from description
            if hasattr(element, 'AXDescription') and element.AXDescription:
                if isinstance(element.AXDescription, str):
                    text_parts.append(element.AXDescription)
            
            # Get children and recurse (limit to prevent performance issues)
            try:
                if hasattr(element, 'AXChildren') and element.AXChildren:
                    for child in element.AXChildren[:5]:  # Limit children
                        child_text = self.extract_text_from_element(child, depth + 1)
                        if child_text:
                            text_parts.append(child_text)
            except Exception:
                pass
            
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
        print("1. Install atomacos: pip3 install atomacos")
        print("2. Grant Accessibility permissions:")
        print("   System Preferences → Privacy & Security → Accessibility")
        print("   Add Terminal or your Python interpreter")
        print("3. Configure OpenClaw endpoint in config.json")
        print(f"4. Current config: {args.config}")
        return
    
    if args.test:
        print("Testing screen reading...")
        try:
            context = bridge.get_active_window_context()
            if context:
                print(f"✅ Success!")
                print(f"App: {context['app_name']}")
                print(f"Window: {context['window_title']}")
                print(f"Content: {context['text_content'][:200]}...")
            else:
                print("❌ No context captured")
                print("Check accessibility permissions in System Preferences")
        except Exception as e:
            print(f"❌ Error: {e}")
            print("Make sure accessibility permissions are granted")
        return
    
    if args.start:
        bridge.run_daemon()
        return
    
    parser.print_help()

if __name__ == "__main__":
    main()