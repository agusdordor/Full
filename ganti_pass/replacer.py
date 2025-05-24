from mitmproxy import http
import re
import json
import os
from pathlib import Path

class ConfigurableHTMLReplacer:
    def __init__(self):
        self.config_file = "replacer_config.json"
        self.load_config()
        
    def load_config(self):
        """Load configuration from JSON file or create default"""
        default_config = {
            "field_values": {
                "answer1": "naruto",
                "answer2": "bakso", 
                "pwd": "procadet234",
                "surePwd": "procadet234"
            },
            "fixed_values": {
                "queId1": "1",
                "queId2": "1"
            },
            "clear_fields": ["bindPhone", "bindMail"],
            "enabled": True,
            "target_domains": [],  # Empty = all domains
            "target_paths": []     # Empty = all paths
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                print(f"[CONFIG] Loaded from {self.config_file}")
            else:
                self.config = default_config
                self.save_config()
                print(f"[CONFIG] Created default config: {self.config_file}")
                
        except Exception as e:
            print(f"[CONFIG ERROR] Using default config: {e}")
            self.config = default_config
            
        self.print_current_config()
    
    def save_config(self):
        """Save current configuration to JSON file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            print(f"[CONFIG] Saved to {self.config_file}")
        except Exception as e:
            print(f"[CONFIG ERROR] Failed to save: {e}")
    
    def print_current_config(self):
        """Print current configuration"""
        print("\n=== CURRENT CONFIGURATION ===")
        print(f"Enabled: {self.config['enabled']}")
        print(f"Field Values: {self.config['field_values']}")
        print(f"Fixed Values: {self.config['fixed_values']}")
        print(f"Clear Fields: {self.config['clear_fields']}")
        if self.config['target_domains']:
            print(f"Target Domains: {self.config['target_domains']}")
        if self.config['target_paths']:
            print(f"Target Paths: {self.config['target_paths']}")
        print("==============================\n")

    def response(self, flow: http.HTTPFlow) -> None:
        # Skip if disabled
        if not self.config.get('enabled', True):
            return
            
        # Filter by domain if specified
        if self.config['target_domains']:
            if not any(domain in flow.request.pretty_host for domain in self.config['target_domains']):
                return
        
        # Filter by path if specified  
        if self.config['target_paths']:
            if not any(path in flow.request.path for path in self.config['target_paths']):
                return
        
        # Filter HTML content only
        content_type = flow.response.headers.get("content-type", "")
        if "text/html" not in content_type:
            return
            
        try:
            content = flow.response.get_text()
            if not content:
                return
                
            modifications_made = []
            
            # 1. Clear specified fields (bindPhone, bindMail)
            for field in self.config['clear_fields']:
                old_content = content
                pattern = rf'(<input type="hidden" id="{field}" value=")[^"]*(")'
                content = re.sub(pattern, r'\1\2', content, flags=re.IGNORECASE)
                if old_content != content:
                    modifications_made.append(f"{field}_cleared")
            
            # 2. Set fixed values (queId1, queId2)
            for field_id, value in self.config['fixed_values'].items():
                old_content = content
                pattern = rf'id="{field_id}" value="([^"]*)"'
                content = re.sub(pattern, f'id="{field_id}" value="{value}"', content, flags=re.IGNORECASE)
                if old_content != content:
                    modifications_made.append(f"{field_id}_set_to_{value}")
            
            # 3. Add/update field values (answer1, answer2, pwd, surePwd)
            for field_id, value in self.config['field_values'].items():
                old_content = content
                
                # Replace existing value
                pattern1 = rf'(id="{field_id}"[^>]*value=")[^"]*(")'
                content = re.sub(pattern1, rf'\1{value}\2', content, flags=re.IGNORECASE)
                
                # Add value if doesn't exist
                pattern2 = rf'(<[^>]*id="{field_id}"[^>]*?)(?!\s+value=)([^>]*>)'
                content = re.sub(pattern2, rf'\1 value="{value}"\2', content, flags=re.IGNORECASE)
                
                if old_content != content:
                    modifications_made.append(f"{field_id}_set_to_{value}")
            
            # Update response if modifications were made
            if modifications_made:
                flow.response.set_text(content)
                url = f"{flow.request.pretty_host}{flow.request.path}"
                print(f"[MODIFIED] {url}")
                print(f"[CHANGES] {', '.join(modifications_made)}")
                    
        except Exception as e:
            print(f"[ERROR] {e}")

# Interactive configuration updater
class ConfigManager:
    def __init__(self, replacer):
        self.replacer = replacer
        
    def update_field_value(self, field_name, new_value):
        """Update a specific field value"""
        if field_name in self.replacer.config['field_values']:
            old_value = self.replacer.config['field_values'][field_name]
            self.replacer.config['field_values'][field_name] = new_value
            self.replacer.save_config()
            print(f"[UPDATE] {field_name}: '{old_value}' -> '{new_value}'")
            return True
        else:
            print(f"[ERROR] Field '{field_name}' not found")
            return False
    
    def toggle_enabled(self):
        """Toggle enabled/disabled state"""
        self.replacer.config['enabled'] = not self.replacer.config['enabled']
        self.replacer.save_config()
        state = "ENABLED" if self.replacer.config['enabled'] else "DISABLED"
        print(f"[TOGGLE] Replacer is now {state}")

# Global instances
replacer = ConfigurableHTMLReplacer()
config_manager = ConfigManager(replacer)

# Console commands for runtime configuration
def update_answer1(new_value):
    """Update answer1 value - Usage: update_answer1('new_value')"""
    return config_manager.update_field_value('answer1', new_value)

def update_answer2(new_value):
    """Update answer2 value - Usage: update_answer2('new_value')"""
    return config_manager.update_field_value('answer2', new_value)

def update_pwd(new_value):
    """Update pwd value - Usage: update_pwd('new_value')"""
    return config_manager.update_field_value('pwd', new_value)

def update_sure_pwd(new_value):
    """Update surePwd value - Usage: update_sure_pwd('new_value')"""
    return config_manager.update_field_value('surePwd', new_value)

def toggle_replacer():
    """Toggle replacer on/off - Usage: toggle_replacer()"""
    return config_manager.toggle_enabled()

def reload_config():
    """Reload configuration from file - Usage: reload_config()"""
    replacer.load_config()
    return True

def show_config():
    """Show current configuration - Usage: show_config()"""
    replacer.print_current_config()
    return True

# Print available commands on startup
print("\n=== AVAILABLE COMMANDS ===")
print("update_answer1('new_value')")
print("update_answer2('new_value')")  
print("update_pwd('new_password')")
print("update_sure_pwd('new_password')")
print("toggle_replacer()")
print("reload_config()")
print("show_config()")
print("==========================\n")

addons = [replacer]