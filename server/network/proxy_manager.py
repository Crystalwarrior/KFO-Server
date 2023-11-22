import logging
import ipaddress

import asyncio
import aiohttp

logger = logging.getLogger(__name__)


class UnauthorizedProxy(Exception):
    """Exception raised when an unauthorized proxy is detected."""
    pass


class ProxyManager:
    def __init__(self):
        # IP addresses that are whitelisted for use
        self.ip_whitelist = []

    async def init(self):
        cloudflare_ips = await self.get_cloudflare_ips()
        self.ip_whitelist.extend(cloudflare_ips.splitlines())

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
                    return True
            except ValueError:
                try:
                    entry_ip_address = ipaddress.ip_address(entry)
                except ValueError:
                    # The entry is not a valid IP address, skip it
                    continue

                # Check if the IP address matches the entry
                if ip_address == entry_ip_address:
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
