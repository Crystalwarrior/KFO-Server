import logging
import ipaddress

import aiohttp

logger = logging.getLogger(__name__)


# Proxy Manager, authorizes IPs that claim to be proxies. Implemented as singleton
class ProxyManager:
    def __init__(self, server):
        # IP addresses that are whitelisted for use as proxies
        self.ip_whitelist = []
        self.server = server

    async def init(self):
        # Localhost is always a trusted IP address
        # This important for setups using CloudFlare tunnels
        # See https://www.cloudflare.com/products/tunnel/
        self.ip_whitelist.append("127.0.0.1")

        cloudflare_ips = await self.get_cloudflare_ips()
        self.ip_whitelist.extend(cloudflare_ips)

        if 'authorized_proxies' in self.server.config and \
                isinstance(self.server.config['authorized_proxies'], list):
            self.ip_whitelist.extend(self.server.config['authorized_proxies'])

    def is_ip_authorized_as_proxy(self, ip: str) -> bool:
        """
        Check if the specified IP address is authorized for use as a proxy.
        """
        # Convert the given IP address to an ipaddress.IPv4Address or ipaddress.IPv6Address object
        try:
            ip_address = ipaddress.ip_address(ip)
        except ValueError:
            # The given IP is not a valid IP address
            return False

        for entry in self.ip_whitelist:
            try:
                # Try to parse the entry as a CIDR block
                network = ipaddress.ip_network(entry, strict=False)
                # Check if the IP address is within the CIDR block
                if ip_address in network:
                    logger.debug('IP address %s is approved for use as a proxy. Found CIDR match in %s',
                                 ip, network)
                    return True
            except ValueError:
                try:
                    entry_ip_address = ipaddress.ip_address(entry)
                except ValueError:
                    # The entry is not a valid IP address, skip it
                    continue

                # Check if the IP address matches the entry
                if ip_address == entry_ip_address:
                    logger.debug('IP address %s is approved for use as a proxy. Found exact match in %s',
                                 ip_address, entry_ip_address)
                    return True

        return False

    @staticmethod
    async def get_cloudflare_ips() -> [str]:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://www.cloudflare.com/ips-v4/#') as response:
                if response.status == 200:
                    response_data = await response.text()
                    return response_data.splitlines()
                else:
                    logger.error('Failed to get Cloudflare IPs: %s, %s', response.status, response.text)
                    return []
