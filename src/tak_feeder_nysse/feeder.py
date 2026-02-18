"""
Nysse Vehicle Activity Worker module.
"""

import asyncio
import fnmatch
from typing import Dict, Any, Optional

import pytak
import aiohttp

from . import cot_utils


class NysseWorker(pytak.QueueWorker):  # type: ignore[misc]
    """
    Nysse Vehicle Activity Worker.
    Polls Nysse API and generates CoT events.
    """

    def __init__(self, queue: asyncio.Queue[bytes], config: Dict[str, Any]) -> None:
        super().__init__(queue, config)
        self.line_ref = config.get("NYSSE_LINE_REF", "60,60U,64,65,65A,66,67")
        self.poll_interval = int(config.get("UPDATE_INTERVAL", "3"))
        self.stop_cache: Dict[str, Dict[str, str]] = {}
        self.api_url = "https://data.itsfactory.fi/journeys/api/1"
        self.headers = {"User-Agent": "tak-feeder-nysse/0.1.0"}
        self.session: Optional[aiohttp.ClientSession] = None

    async def handle_data(self, data: bytes) -> None:
        """
        Handle data from the RX queue.
        Required by pytak.QueueWorker but unused in this producer worker.
        """

    async def get_stop_info(self, stop_ref: str) -> Dict[str, str]:
        """
        Fetch stop information (name, municipality) from Nysse API or cache.
        """
        if stop_ref in self.stop_cache:
            return self.stop_cache[stop_ref]

        if not self.session:
            return {"name": "Unknown", "city": "Unknown"}

        # stop_ref might be a full URL if extracted from onwardCalls[0].stopPointRef
        if stop_ref.startswith("http"):
            url = stop_ref
        else:
            url = f"{self.api_url}/stop-points/{stop_ref}"

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with self.session.get(
                url, headers=self.headers, timeout=timeout
            ) as response:
                response.raise_for_status()
                data = await response.json()
                if data and isinstance(data.get("body"), list) and data["body"]:
                    stop_data = data["body"][0]
                    name = stop_data.get("name", "Unknown")
                    municipality = stop_data.get("municipality", {}).get(
                        "name", "Unknown"
                    )
                    self.stop_cache[stop_ref] = {"name": name, "city": municipality}
                    return self.stop_cache[stop_ref]
        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            ValueError,
            TypeError,
            AttributeError,
        ) as exc:
            self._logger.error("Error fetching stop info for %s: %s", stop_ref, exc)

        return {"name": "Unknown", "city": "Unknown"}

    def _matches_filter(self, line_ref: str) -> bool:
        """Check if a line matches the configured filter (supports wildcards)."""
        if not self.line_ref:
            return True
        filters = [f.strip() for f in self.line_ref.split(",")]
        for pattern in filters:
            if fnmatch.fnmatch(line_ref, pattern):
                return True
        return False

    async def _process_vehicle(self, mvj: Dict[str, Any]) -> None:
        """
        Process a single monitored vehicle journey from the API response.
        """
        v_ref = mvj.get("vehicleRef")
        l_ref = mvj.get("lineRef")
        loc = mvj.get("vehicleLocation", {})
        lat = loc.get("latitude")
        lon = loc.get("longitude")

        if lat is None or lon is None or v_ref is None or l_ref is None:
            return

        # Apply wildcard filter
        if not self._matches_filter(l_ref):
            return

        # Get next stop info
        onward_calls = mvj.get("onwardCalls", [])
        ns_name, ns_city, ns_time = "Unknown", "Unknown", "--:--"

        if onward_calls:
            next_call = onward_calls[0]
            if ns_ref := next_call.get("stopPointRef"):
                s_info = await self.get_stop_info(ns_ref)
                ns_name, ns_city = s_info["name"], s_info["city"]

            exp_dep = next_call.get("expectedDepartureTime")
            if exp_dep and "T" in exp_dep:
                ns_time = exp_dep.split("T")[1][:5]

        # Get destination info
        d_name, d_city = "Unknown", "Unknown"
        if ds_name := mvj.get("destinationShortName"):
            d_info = await self.get_stop_info(ds_name)
            d_name, d_city = d_info["name"], d_info["city"]

        # Generate CoT
        try:
            speed = float(mvj.get("speed", 0.0))
            bearing = float(mvj.get("bearing", 0.0))

            cot_event = cot_utils.generate_nysse_cot(
                vehicle_ref=v_ref,
                line_ref=l_ref,
                lat=float(lat),
                lon=float(lon),
                speed=speed / 3.6,
                bearing=bearing,
                dest_city=d_city,
                dest_name=d_name,
                next_city=ns_city,
                next_stop_name=ns_name,
                next_stop_time=ns_time,
            )

            if cot_event:
                self._logger.debug("Enqueueing CoT for vehicle %s", v_ref)
                await self.put_queue(cot_event)
        except (ValueError, TypeError) as exc:
            self._logger.error("Error processing vehicle %s: %s", v_ref, exc)

    async def run(self, number_of_iterations: Optional[int] = None) -> None:
        """
        Main worker loop. Polls Nysse API and enqueues CoT events.
        """
        self._logger.info("Starting NysseWorker with line filter: %s", self.line_ref)

        async with aiohttp.ClientSession() as session:
            self.session = session
            iterations = 0
            while number_of_iterations is None or iterations < number_of_iterations:
                iterations += 1
                try:
                    self._logger.debug("Polling Nysse API...")
                    url = (
                        f"{self.api_url}/vehicle-activity?"
                        f"exclude-fields=recordedAtTime&lineRef={self.line_ref}"
                    )
                    timeout = aiohttp.ClientTimeout(total=10)
                    async with session.get(
                        url, headers=self.headers, timeout=timeout
                    ) as response:
                        response.raise_for_status()
                        data = await response.json()

                        if data and isinstance(data.get("body"), list):
                            self._logger.debug("Found %d vehicles", len(data["body"]))
                            for activity in data["body"]:
                                mvj = activity.get("monitoredVehicleJourney")
                                if mvj:
                                    await self._process_vehicle(mvj)

                except (
                    aiohttp.ClientError,
                    asyncio.TimeoutError,
                    ValueError,
                    TypeError,
                    AttributeError,
                ) as exc:
                    self._logger.error("Error in NysseWorker loop: %s", exc)

                await asyncio.sleep(self.poll_interval)


class NysseReceiver(pytak.QueueWorker):  # type: ignore[misc]
    """
    Drains the RX queue to prevent QueueFull errors.
    """

    async def handle_data(self, data: bytes) -> None:
        """
        Log received data if it's not a ping.
        """
        text = data.decode()
        if "takPing" not in text:
            self._logger.debug("Received CoT: %s", text)

    async def run(self, number_of_iterations: Optional[int] = None) -> None:
        """
        Main RX loop.
        """
        iterations = 0
        while number_of_iterations is None or iterations < number_of_iterations:
            if number_of_iterations is not None:
                iterations += 1
            await self.queue.get()
            await self.handle_data(bytes())  # Draining
