import logging
import ipaddress

import asyncio
import aiohttp

logger = logging.getLogger(__name__)


class UnauthorizedProxy(Exception):
    """Exception raised when an unauthorized proxy is detected."""
    pass


# Proxy Manager, authorizes IPs that claim to be proxies. Implemented as singleton
class ProxyManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls.instance = super(ProxyManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    def instance(cls):
        return cls._instance

    def __init__(self):
        # IP addresses that are whitelisted for use as proxies
        self.ip_whitelist = []

    async def init(self):
        # Localhost is always a trusted IP address
        # This important for setups using CloudFlare tunnels
        # See https://www.cloudflare.com/products/tunnel/
        self.ip_whitelist.append("127.0.0.1")

        cloudflare_ips = await self.get_cloudflare_ips()
        self.ip_whitelist.extend(cloudflare_ips)

        # TODO: Implement additional manual IP whitelist in configuration

    def is_ip_approved(self, ip: str) -> bool:
        """
        Check if the specified IP address is approved for use as a proxy.
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
