import yaml
import time
from collections import defaultdict

class RaidManager:
    def __init__(self, server):
        self.server = server
        self.current_level = 0
        self.raid_config = self.load_config()
        self.connection_counts = defaultdict(lambda: {'connections': [], 'times': []})
        self.global_connections = {'connections': [], 'times': []}
        self.client_warnings = defaultdict(int)
        self.modcall_times = defaultdict(list)
        self.last_modcall_time = defaultdict(float)
        self.whitelisted_hdids = self.load_whitelist()
        self.whitelist_enabled = True
        self.last_check = time.time()
    
    def add_warning(self, client, reason):
        """Add a warning to a client."""
        if self.is_exempt(client):
            return False
                
        config = self.get_current_config()
        if not config.get('enabled', False):
            return False
                
        warning_config = config.get('warnings', {})
        if not warning_config.get('enabled', False):
            return False
                
        self.client_warnings[client.hdid] += 1
        current_warnings = self.client_warnings[client.hdid]
        max_warnings = warning_config.get('amount', 5)
        
        client.send_ooc(f"Warning ({current_warnings}/{max_warnings}): {reason}")
        
        if current_warnings >= max_warnings:
            self.client_warnings[client.hdid] = 0
            
            if warning_config.get('ban_enabled', False):
                duration = warning_config.get('duration', '1h')
                duration_secs = self.parse_time(duration)
                from datetime import datetime, timedelta
                unban_date = datetime.now() + timedelta(seconds=duration_secs) if duration_secs > 0 else None

                class SystemBanner:
                    name = "RaidControl"
                    ipid = "SYSTEM"
                
                try:
                    ban_id = self.server.database.ban(
                        target_id=client.ipid,
                        reason="[SYSTEM] Exceeded warning limit",
                        ban_type="ipid",
                        banned_by=SystemBanner(),
                        unban_date=unban_date
                    )
                    
                    self.server.database.ban(
                        target_id=client.hdid,
                        reason="[SYSTEM] Exceeded warning limit",
                        ban_type="hdid",
                        ban_id=ban_id,
                        banned_by=SystemBanner()
                    )
                    
                    client.send_command("KB", "[SYSTEM] Exceeded warning limit")
                    client.disconnect()
                    
                except Exception as e:
                    print(f"Failed to ban {client.hdid}: {e}")
                    client.disconnect()
            else:
                client.disconnect()
            return True
        return False

    def is_exempt(self, client):
        """Check if client is exempt from raid mode restrictions"""
        return (client.is_mod or
                (self.whitelist_enabled and self.is_whitelisted(client)) or
                self.current_level == 0 or
                not self.get_current_config().get('enabled', False))
        
    def load_whitelist(self):
        try:
            with open('storage/whitelist.txt', 'r') as f:
                return {line.strip() for line in f if line.strip()}
        except:
            return set()
 
    def is_whitelisted(self, client):
        return client.hdid in self.whitelisted_hdids
        
    def load_config(self):
        try:
            with open('config/raidmode.yaml', 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading raidmode.yaml: {e}")
            return {'levels': {0: {'enabled': False, 'description': 'Normal operation'}}}

    def parse_time(self, time_str):
        """Convert time string (e.g. '5m', '1h') to seconds"""
        if not time_str:
            return 0
        
        units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        unit = time_str[-1]
        if unit in units:
            try:
                return int(time_str[:-1]) * units[unit]
            except ValueError:
                return 0
        return 0

    def get_current_config(self):
        """Get current level configuration"""
        return self.raid_config['levels'].get(str(self.current_level), {})

    def can_connect(self, hdid):
        """Check if client can connect based on connection limits"""
        if self.current_level == 0:
            return True
                
        config = self.get_current_config()
        if not config.get('enabled', False):
            return True

        if hdid in self.whitelisted_hdids:
            return True
                
        limit_config = config.get('limit_connections', {})
        if isinstance(limit_config, dict):
            current_time = time.time()
            limit = limit_config.get('amount', 0)
            duration = self.parse_time(limit_config.get('duration', '0s'))
            
            cutoff = current_time - duration
            self.global_connections['times'] = [t for t in self.global_connections['times'] 
                                              if t > cutoff]

            if len(self.global_connections['times']) >= limit:
                print(f"Connection rejected: {len(self.global_connections['times'])} connections in last {duration}s")
                return False
                
        return True
        
    def record_connection(self, hdid):
        """Record a connection attempt"""
        if not self.current_level:
            return
                
        config = self.get_current_config()
        if not config.get('enabled', False):
            return
                    
        limit_config = config.get('limit_connections', {})
        if isinstance(limit_config, dict):
            current_time = time.time()
            limit = limit_config.get('amount', 0)
            duration = self.parse_time(limit_config.get('duration', '0s'))

            cutoff = current_time - duration
            self.global_connections['times'] = [t for t in self.global_connections['times'] 
                                              if t > cutoff]

            if len(self.global_connections['times']) < limit:
                self.global_connections['times'].append(current_time)
                print(f"Connection recorded. Total connections: {len(self.global_connections['times'])}")

    def can_send_packet(self, client):
        """Check if client can send packets based on delay setting"""
        if self.is_exempt(client):
            return True
            
        if self.current_level == 0:
            return True
            
        config = self.get_current_config()
        if not config.get('enabled', False):
            return True
            
        if not client.first_packet_sent:
            delay = self.parse_time(config.get('delay', '0s'))
            if delay > 0:
                time_since_connect = time.time() - client.connection_time
                if time_since_connect < delay:
                    remaining = round(delay - time_since_connect, 1)
                    client.send_ooc(f"Please wait {remaining}s before sending commands during raid mode.")
                    return False
            client.first_packet_sent = True
        return True

    def check_time_exclusive(self, client):
        """Check if client meets time requirement"""
        if self.is_exempt(client):
            return True
            
        if self.current_level == 0:
            return True
            
        config = self.get_current_config()
        if not config.get('enabled', False):
            return True
            
        required_time = self.parse_time(config.get('time_exclusive', '0s'))
        if required_time > 0:
            total_time = self.server.database.get_hdid_time(client.hdid) or 0
            if total_time < required_time:
                client.send_ooc(f"You need {required_time - total_time}s more server time to participate during raid mode.")
                return False
        return True

    def can_modcall(self, client):
        """Check if client can make a modcall"""
        if self.current_level == 0:
            print("Level 0 - Modcall allowed")
            return True
                
        config = self.get_current_config()
        if not config.get('enabled', False):
            print("Raidmode disabled - Modcall allowed")
            return True

        if self.is_exempt(client):
            print("Client exempt - Modcall allowed")
            return True
                
        modcall_config = config.get('limit_modcalls', {})
        print(f"Modcall config: {modcall_config}")
        
        if isinstance(modcall_config, dict):
            current_time = time.time()
            print(f"Current time: {current_time}")
            
            print(f"Client HDID: {client.hdid}")
            print(f"Stored modcall times: {self.modcall_times[client.hdid]}")
            print(f"Last modcall time: {self.last_modcall_time[client.hdid]}")
            
            cooldown = self.parse_time(modcall_config.get('cooldown', '0s'))
            print(f"Cooldown setting: {cooldown}s")
            
            last_time = self.last_modcall_time[client.hdid]
            print(f"Last modcall absolute time: {last_time}")
            
            if last_time > 0:
                time_since_last = current_time - last_time
                print(f"Time since last modcall: {time_since_last}s")
                
                if time_since_last < cooldown:
                    remaining = round(cooldown - time_since_last, 1)
                    client.send_ooc(f"Please wait {remaining}s between modcalls.")
                    print(f"Modcall rejected: {remaining}s remaining")
                    return False
                else:
                    print(f"Cooldown passed: {time_since_last}s > {cooldown}s")
            else:
                print("First modcall for this client")
            
            limit = modcall_config.get('amount', 0)
            duration = self.parse_time(modcall_config.get('duration', '0s'))
            
            if duration > 0:
                old_count = len(self.modcall_times[client.hdid])
                recent_calls = [t for t in self.modcall_times[client.hdid] 
                              if (current_time - t) < duration]
                self.modcall_times[client.hdid] = recent_calls
                new_count = len(recent_calls)
                
                print(f"Cleaned modcall list: {old_count} -> {new_count} calls")
                print(f"Recent calls: {recent_calls}")
                
                if len(recent_calls) >= limit:
                    client.send_ooc(f"You have exceeded the modcall limit ({limit} per {modcall_config['duration']}).")
                    print(f"Modcall rejected: {len(recent_calls)} >= limit {limit}")
                    return False
                else:
                    print(f"Under limit: {len(recent_calls)} < {limit}")
        
        print("All checks passed - Modcall allowed")
        return True


    def record_modcall(self, client):
        """Record a modcall attempt"""
        current_time = time.time()
        print(f"\nRecording modcall:")
        print(f"Client HDID: {client.hdid}")
        print(f"Current time: {current_time}")
        
        print(f"Before recording:")
        print(f"Modcall times: {self.modcall_times[client.hdid]}")
        print(f"Last modcall time: {self.last_modcall_time[client.hdid]}")
        
        self.modcall_times[client.hdid].append(current_time)
        self.last_modcall_time[client.hdid] = current_time
        
        print(f"After recording:")
        print(f"Modcall times: {self.modcall_times[client.hdid]}")
        print(f"Last modcall time: {self.last_modcall_time[client.hdid]}")
        print(f"Total modcalls in tracking: {len(self.modcall_times[client.hdid])}")

    def can_send_ic(self, client, config=None):
        """Check if client can send IC message"""
        if self.is_exempt(client):
            return True
            
        if self.current_level == 0:
            return True
            
        if config is None:
            config = self.get_current_config()
            
        if not config.get('enabled', False):
            return True

        ic_delay = self.parse_time(config.get('ic_delay', '0s'))
        if ic_delay > 0 and client.last_ic_time > 0:  # Only check if they've sent a message before
            time_since_last = time.time() - client.last_ic_time
            if time_since_last < ic_delay:
                remaining = round(ic_delay - time_since_last, 1)
                client.send_ooc(f"Please wait {remaining}s between IC messages.")
                return False

        limit_config = config.get('limit_ic', {})
        if isinstance(limit_config, dict):
            limit = limit_config.get('amount', 0)
            duration = self.parse_time(limit_config.get('duration', '0s'))
            
            if limit > 0 and duration > 0:
                current_time = time.time()
                
                client.ic_message_times = [msg_time for msg_time in client.ic_message_times 
                                         if current_time - msg_time < duration]
                
                if len(client.ic_message_times) >= limit:
                    client.send_ooc(f"You have exceeded the limit of {limit} messages per {limit_config['duration']}.")
                    client.disconnect()
                    return False
                    
        return True


    def record_modcall(self, client):
        """Record a modcall for this client"""
        client.modcall_count += 1

    def record_ic(self, client):
        """Record an IC message for this client"""
        client.ic_message_times.append(time.time())

    def set_level(self, level):
        """Set the raid control level"""
        if str(level) in self.raid_config['levels']:
            old_level = self.current_level
            self.current_level = int(level)
            if level > 0 and old_level == 0:
                for client in self.server.client_manager.clients:
                    client.reset_raid_tracking()
            return True
        return False

    def can_send_ooc(self, client):
        """Check if client can send OOC message"""
        if self.is_exempt(client):
            return True
            
        if self.current_level == 0:
            return True
            
        config = self.get_current_config()
        if not config.get('enabled', False):
            return True

        ooc_delay = self.parse_time(config.get('ooc_delay', '0s'))
        if ooc_delay > 0:
            time_since_last = time.time() - client.last_ooc_time
            if time_since_last < ooc_delay:
                remaining = round(ooc_delay - time_since_last, 1)
                client.send_ooc(f"Please wait {remaining}s between OOC messages.")
                return False
        return True

    def can_switch_area(self, client):
        """Check if client can switch areas"""
        if self.is_exempt(client):
            return True
            
        if self.current_level == 0:
            return True
            
        config = self.get_current_config()
        if not config.get('enabled', False):
            return True

        area_delay = self.parse_time(config.get('area_delay', '0s'))
        if area_delay > 0:
            time_since_last = time.time() - client.last_area_time
            if time_since_last < area_delay:
                remaining = round(area_delay - time_since_last, 1)
                client.send_ooc(f"Please wait {remaining}s between area switches.")
                return False
        return True

    def can_create_evidence(self, client):
        """Check if evidence creation is allowed"""
        if self.is_exempt(client):
            return True
            
        if self.current_level == 0:
            return True
            
        config = self.get_current_config()
        if not config.get('enabled', False):
            return True

        if config.get('no_evidence', False):
            client.send_ooc("Evidence creation is disabled during raid mode.")
            return False
        return True

    # listen it sounded really funny
    def check_racism(self, text, client=None):
        """Check if text contains banned character sets"""
        config = self.get_current_config()
        if not config.get('racism_mode', False):
            return False
            
        if not text:
            return False
            
        if self.is_exempt(client):
            return False
            
        # racism mode
        banned_ranges = [
            # arabic
            (0x0600, 0x06FF),
            (0x0750, 0x077F),
            (0x08A0, 0x08FF),
            (0xFB50, 0xFDFF),
            (0xFE70, 0xFEFF),
            
            # egyptian hieroglypics
            (0x13000, 0x1342F),
            (0x13430, 0x1343F),
            
            # wingdings
            (0xF020, 0xF0FF),
            (0x2700, 0x27BF),
        ]
        
        for c in text:
            char_code = ord(c)
            for start, end in banned_ranges:
                if start <= char_code <= end:
                    return True
        return False
        
    def get_banned_char_type(self, text):
        """Returns what type of banned characters were found"""
        char_code = ord(text[0])
        
        if 0x0600 <= char_code <= 0xFEFF:
            return "Arabic"
        elif 0x13000 <= char_code <= 0x1343F:
            return "Egyptian Hieroglyphs"
        elif (0xF020 <= char_code <= 0xF0FF) or (0x2700 <= char_code <= 0x27BF):
            return "Wingdings"
        return "banned characters"
        
    def get_status_message(self):
        """Get current raid control status"""
        if self.current_level == 0:
            return "Raid Control: Disabled"
            
        config = self.get_current_config()
        if not config:
            return "Invalid raid control level"
            
        msg = [f"Raid Control Level: {self.current_level}"]
        msg.append(f"Description: {config.get('description', 'None')}")
        msg.append(f"Whitelist Exemptions: {'Enabled' if self.whitelist_enabled else 'Disabled'}")
        
        modcall_config = config.get('limit_modcalls')
        if isinstance(modcall_config, dict):
            amount = modcall_config.get('amount', 0)
            duration = modcall_config.get('duration', '0s')
            msg.append(f"- Modcall Limit: {amount} per {duration}")
            
        if config.get('time_exclusive'):
            msg.append(f"- Time Requirement: {config['time_exclusive']}")
            
        if isinstance(config.get('limit_connections'), dict):
            conn = config['limit_connections']
            msg.append(f"- Connection Limit: {conn['amount']} per {conn['duration']}")
            msg.append(f"  HDID Tracking: {'Per-User' if conn.get('hdid_exclusive', True) else 'Global'}")
            
        if isinstance(config.get('limit_ic'), dict):
            ic = config['limit_ic']
            msg.append(f"- IC Message Limit: {ic['amount']} per {ic['duration']}")
            
        if config.get('delay'):
            msg.append(f"- New Connection Delay: {config['delay']}")
            
        if config.get('ic_delay'):
            msg.append(f"- IC Message Delay: {config['ic_delay']}")
    
        if config.get('ooc_delay'):
            msg.append(f"- OOC Message Delay: {config['ooc_delay']}")
            
        if config.get('area_delay'):
            msg.append(f"- Area Switch Delay: {config['area_delay']}")
            
        if config.get('racism_mode'):
            msg.append("- Special Character Filter: Enabled (Arabic/Hieroglyphs/Wingdings)")
            
        if config.get('no_evidence'):
            msg.append("- Evidence creation disabled")
            
        return "\n".join(msg)