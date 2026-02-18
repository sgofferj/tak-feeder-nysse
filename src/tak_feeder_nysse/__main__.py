"""
Main entry point for the Nysse TAK feeder.
"""

import asyncio
import os
import logging
from configparser import ConfigParser

import pytak
from dotenv import load_dotenv

from .feeder import NysseWorker, NysseReceiver


async def main() -> None:
    """
    Main function to initialize and run the Nysse feeder.
    """
    load_dotenv()

    # Explicitly check for None and provide defaults
    cot_url = os.getenv("COT_URL")
    if not cot_url or cot_url.lower() == "none":
        cot_url = "udp://239.2.3.1:6969"

    cert = os.getenv("CLIENT_CERT")
    if not cert or cert.lower() == "none":
        cert = ""

    key = os.getenv("CLIENT_KEY")
    if not key or key.lower() == "none":
        key = ""

    # Configuration from environment variables
    config_dict = {
        "COT_URL": cot_url,
        "PYTAK_TLS_CLIENT_CERT": cert,
        "PYTAK_TLS_CLIENT_KEY": key,
        "PYTAK_TLS_DONT_VERIFY": os.getenv("PYTAK_TLS_DONT_VERIFY", "0"),
        "NYSSE_LINE_REF": os.getenv("NYSSE_LINE_FILTER", "60,60U,64,65,65A,66,67"),
        "UPDATE_INTERVAL": os.getenv("UPDATE_INTERVAL", "3"),
        "DEBUG": os.getenv("DEBUG", "0"),
    }

    config_parser = ConfigParser()
    config_parser["mycottool"] = config_dict
    config = config_parser["mycottool"]

    # Setup logging level
    if config.get("DEBUG") == "1":
        logging.getLogger().setLevel(logging.DEBUG)

    # Setup CLI tool
    clitool = pytak.CLITool(config)
    await clitool.setup()

    # Add Nysse workers
    clitool.add_tasks(
        set(
            [
                NysseWorker(clitool.tx_queue, config_dict),
                NysseReceiver(clitool.rx_queue, config_dict),
            ]
        )
    )

    # Run the tool
    await clitool.run()


if __name__ == "__main__":
    asyncio.run(main())
