import hashlib
import pyasn
import ipaddress
import urllib.request
import tempfile
import gzip
import os
from pathlib import Path

class ValleyID:
    def __init__(self, server):
        self.server = server
        self.seed = server.config["strict_mode"]["seed"]
        from server import database
        self.database = database
        
        db_path = Path("storage/ipasn.dat")
        if not db_path.exists():
            self.download_asn_database()
        else:
        try:
            self.asndb = pyasn.pyasn(str(db_path))
        except Exception as e:
            self.asndb = None

    def get_asn(self, ip):
        """Get ASN for an IP address."""
        try:
            if not ip:
                print("No IP address provided")
                return "0"
            
            ip_obj = ipaddress.ip_address(ip)
            
            if ip_obj.is_private:
                return "64512"
            
            if ip_obj.is_loopback:
                return "64512"
                
            asn, prefix = self.asndb.lookup(str(ip))
            return str(asn if asn else "0")
        except Exception as e:
            import traceback
            traceback.print_exc()
            return "0"
        
    def download_asn_database(self):
        """Download and initialize the ASN database."""
        import tempfile
        import gzip
        
        os.makedirs("storage", exist_ok=True)
        print("Downloading ASN database...")
        
        # if this for whatever reason changes feel free to update
        url = "https://iptoasn.com/data/ip2asn-v4.tsv.gz"
        headers = {
            'User-Agent': 'Mozilla/5.0'
        }
        
        try:
            print(f"Downloading from URL: {url}")
            with tempfile.NamedTemporaryFile(delete=False) as temp_gz:
                request = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request) as response:
                    temp_gz.write(response.read())
                print(f"Downloaded to temporary file: {temp_gz.name}")

                print("Converting TSV to pyasn format...")
                with gzip.open(temp_gz.name, 'rt') as f_in:
                    with open("storage/ipasn.dat", 'w') as f_out:
                        f_out.write("; IP-ASN32-DAT file\n")
                        for line in f_in:
                            parts = line.strip().split('\t')
                            if len(parts) >= 3:
                                start_ip = parts[0]
                                end_ip = parts[1]
                                asn = parts[2]
                                if asn == "0" or not asn:
                                    continue
                                try:
                                    start = ipaddress.ip_address(start_ip)
                                    end = ipaddress.ip_address(end_ip)
                                    network = ipaddress.summarize_address_range(start, end)
                                    for net in network:
                                        f_out.write(f"{net}\t{asn}\n")
                                except Exception as e:
                                    print(f"Error processing line {line.strip()}: {e}")
                                    continue

            os.unlink(temp_gz.name)
        except Exception as e:
            print(f"Error type: {type(e)}")
            with open("storage/ipasn.dat", 'w') as f:
                f.write("; IP-ASN32-DAT file\n")
                f.write("1.1.1.1/32\t13335\n")
                f.write("8.8.8.8/32\t15169\n")

    def generate_valleyid(self, hdid, ip):
        """Generate a deterministic ValleyID from HDID and IP."""
        asn = self.get_asn(ip)
        
        data = f"{self.seed}:{hdid}:{asn}"
        
        initial_hash = hashlib.sha256(data.encode()).digest()
        
        num = int.from_bytes(initial_hash[:11], byteorder='big')
        chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        base36 = ''
        
        while num:
            num, i = divmod(num, 36)
            base36 = chars[i] + base36
            
        return base36.zfill(15)

    def verify_hdid_spoofing(self, test_hdid, test_ip, allowed_valleyids):
        """
        Check if this HDID is trying to connect from a different ASN
        when it's already whitelisted from another network.
        """
        test_valleyid = self.generate_valleyid(test_hdid, test_ip)
        
        if test_valleyid in allowed_valleyids:
            return False
        
        with self.database.db as conn:
            # probably gonna lag in bigger servers lol
            rows = conn.execute(
                "SELECT DISTINCT ip_address FROM ipids"
            ).fetchall()
            known_ips = [row["ip_address"] for row in rows if row["ip_address"]]
            
        print(f"[DEBUG] Checking against known IPs: {known_ips}")

        for other_ip in known_ips:
            if other_ip == test_ip:
                continue
            other_valleyid = self.generate_valleyid(test_hdid, other_ip)
            if other_valleyid in allowed_valleyids:
                return True
        
        return False