#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2023 Sensors & Signals LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""LINCOT Class Definitions."""

import asyncio
import json
import os

from typing import Optional

import pytak
import lincot

__author__ = "Greg Albrecht <gba@snstac.com>"
__copyright__ = "Copyright 2023 Sensors & Signals LLC"
__license__ = "Apache License, Version 2.0"


class LincotWorker(pytak.QueueWorker):
    """A worker that reads GPS information and outputs CoT.

    This worker reads GPS information using a command specified in the configuration,
    and converts it to CoT (Cursor on Target) format using the `lincot.gpspipe_to_cot` function.
    The resulting CoT event is then put into a queue for further processing.

    Attributes:
        gps_info_cmd (str): The command to use for reading GPS information.
            This is read from the configuration, or defaults to `lincot.DEFAULT_GPS_INFO_CMD`.
    """

    async def handle_data(self, data) -> None:
        """
        Handle received GPS Info data.

        Args:
            data: The GPS Info data to be handled.

        Returns:
            None

        Example:
            >>> data = b'$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47'
            >>> await handle_data(data)
        """
        event: Optional[bytes] = lincot.gpspipe_to_cot(data, self.config)
        if event:
            await self.put_queue(event)

    async def get_gps_info(self) -> None:
        """Get GPS Info data.

        This method retrieves GPS information using the `gps_info_cmd` command and parses the data to extract the
        relevant information. If no GPS data is found, the method returns `None`.

        Example data:
        {
            "class": "TPV",
            "device": "/dev/ttyUSB0",
            "mode": 3,
            "time": "2021-10-01T12:34:56.000Z",
            "ept": 0.005,
            "lat": 37.123456,
            "lon": -122.123456,
            "alt": 123.4,
            "epx": 0.005,
            "epy": 0.005,
            "epv": 0.005,
            "track": 0.0,
            "speed": 0.0,
            "climb": 0.0,
            "eps": 34.11,
            "epc": 23.45
        }

        Returns:
            None
        """
        gpspipe_data: Optional[str] = None
        gps_data: Optional[str] = None
        with os.popen(self.gps_info_cmd) as gps_info_cmd:
            gpspipe_data = gps_info_cmd.read()

        if not gpspipe_data:
            return

        if "\n" in gpspipe_data:
            for data in gpspipe_data.split("\n"):
                if "TPV" in data:
                    gps_data = data
                    continue

        if not gps_data:
            return None

        self._logger.debug("GPS_INFO=%s", gps_data)
        gps_info = json.loads(gps_data)
        await self.handle_data(gps_info)

    async def run(self, number_of_iterations=-1) -> None:
        """Run this Thread, reads GPS Info & outputs CoT."""
        self._logger.info("Sending to: %s", self.config.get("COT_URL"))

        poll_interval: int = int(
            self.config.get("POLL_INTERVAL", lincot.DEFAULT_POLL_INTERVAL)
        )
        self.gps_info_cmd = (
            self.config.get("GPS_INFO_CMD") or lincot.DEFAULT_GPS_INFO_CMD
        )

        while 1:
            self._logger.info("Polling every %ss: %s", poll_interval, self.gps_info_cmd)
            await self.get_gps_info()
            await asyncio.sleep(poll_interval)
