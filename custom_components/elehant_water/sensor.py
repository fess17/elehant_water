from time import sleep
from datetime import timedelta, datetime
import aioblescan as aiobs
import asyncio
import time
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval
from homeassistant.components.sensor import SensorEntity, SensorStateClass, SensorDeviceClass
import random
import logging
#from homeassistant.const import (
#	VOLUME_LITERS,
#	STATE_UNKNOWN,
#	VOLUME_CUBIC_METERS,
#	TEMP_CELSIUS,
#)
from homeassistant.const import STATE_UNKNOWN, UnitOfVolume, UnitOfTemperature
#counters_mac = {
#	gas: [
#		'b0:10:01',
#		'b0:11:01',
#		'b0:12:01',
#		'b0:32:01',
#		'b0:42:01'
#	],
#	water: [
#		'b0:01:02',
#		'b0:02:02'
#	],
#	water2: [
#		'b0:03:02',
#		'b0:05:02'
#	],
#	water3: [
#		'b0:04:02',
#		'b0:06:02'
#	],
#}

_LOGGER = logging.getLogger("elehant_water")
inf = {}
_LOGGER.debug("init")


def stop_loop(loop):
	#_LOGGER.debug("Entering function stop_loop()..")
	loop.stop()
	#_LOGGER.debug("Exiting function stop_loop()..")

def update_counters(call):
	global scan_duration, current_event_loop
	# _LOGGER.setLevel(logging.DEBUG)
	#_LOGGER.debug("scan_duration = %s, current_event_loop = %s", str(scan_duration), str(current_event_loop))

	def my_process(data):
		# _LOGGER.debug("Entering function <my_process> with arg = %s", str(data))
		ev = aiobs.HCI_Event()
		xx = ev.decode(data)
		try:
			mac = ev.retrieve("peer")[0].val
		except:
			return

		mac = str(mac).lower()

		# _LOGGER.debug("Found MAC = %s", str(mac))
		"""СГБТ-1.8, СГБТ-3.2, СГБТ-4.0, СГБТ-4.0 ТК, СОНИК G4ТК"""
		if (str(mac).find('b0:10:01') !=-1) or (str(mac).find('b0:11:01') !=-1) or (str(mac).find('b0:12:01') !=-1) or (str(mac).find('b0:32:01') !=-1) or (str(mac).find('b0:42:01') !=-1):
			#_LOGGER.debug("SEE gaz counter")
			manufacturer_data = ev.retrieve("Manufacturer Specific Data")
			payload = manufacturer_data[0].payload
			payload = payload[1].val
			_LOGGER.debug("Payload: %s", payload)
			c_num = int.from_bytes(payload[6:9], byteorder='little')
			c_count = int.from_bytes(payload[9:13], byteorder='little')
			if measurement_gas == 'm3':
				inf[c_num] = c_count/10000
			else:
				inf[c_num] = c_count/10

		"""СВД-15, СВД-20"""
		if (str(mac).find('b0:01:02') !=-1) or (str(mac).find('b0:02:02') !=-1):
			#_LOGGER.debug("SEE 1 tariff counter")
			manufacturer_data = ev.retrieve("Manufacturer Specific Data")
			payload = manufacturer_data[0].payload
			payload = payload[1].val
			c_num = int.from_bytes(payload[6:9], byteorder="little")
			c_count = int.from_bytes(payload[9:13], byteorder="little")
			c_temp = int.from_bytes(payload[14:16], byteorder="little") / 100
			inf[str(c_num) + '_temp'] = c_temp;
			#_LOGGER.debug("Test temperature: %s", str(c_temp))
			if measurement_water == "m3":
				inf[c_num] = c_count / 10000
			else:
				inf[c_num] = c_count / 10

		"""СВТ-15 холодная, СВТ-15 горячая, СВТ-20 холодная, СВТ-20 горячая"""
		if (str(mac).find('b0:03:02') !=-1) or (str(mac).find('b0:04:02') !=-1) or (str(mac).find('b0:05:02') !=-1) or (str(mac).find('b0:06:02') !=-1):
			#_LOGGER.debug("SEE 2 tariff counter")
			manufacturer_data = ev.retrieve("Manufacturer Specific Data")
			payload = manufacturer_data[0].payload
			payload = payload[1].val
			_LOGGER.info("SEE 2 tariff counter: %s", payload)
			c_num = int.from_bytes(payload[6:9], byteorder="little")
			if (str(mac).find('b0:03:02') !=-1) or (str(mac).find('b0:05:02') !=-1):
				c_num = str(c_num) + "_1"
			else:
				c_num = str(c_num) + "_2"
			c_count = int.from_bytes(payload[9:13], byteorder="little")
			c_temp = int.from_bytes(payload[14:16], byteorder="little") / 100
			inf[c_num.split("_")[0] + '_temp'] = c_temp
			if measurement_water == "m3":
				inf[c_num] = c_count / 10000
			else:
				inf[c_num] = c_count / 10
		#_LOGGER.debug(inf)

	if current_event_loop is None:
		#_LOGGER.debug("Starting new loop..")
		current_event_loop = asyncio.new_event_loop()
		asyncio.set_event_loop(current_event_loop)
	mysocket = aiobs.create_bt_socket(0)
	fac = getattr(current_event_loop, "_create_connection_transport")(
		mysocket, aiobs.BLEScanRequester, None, None
	)
	conn, btctrl = current_event_loop.run_until_complete(fac)
	btctrl.process = my_process
	#_LOGGER.debug("Send scan request..")
	current_event_loop.run_until_complete(btctrl.send_scan_request())
	#_LOGGER.debug("..finish scan request")
	current_event_loop.call_later(scan_duration, stop_loop, current_event_loop)
	try:
		#_LOGGER.debug("Run loop forever..")
		current_event_loop.run_forever()
		#_LOGGER.debug("Did we reach that point?")
	finally:
		#_LOGGER.debug("Close loop..")
		# current_event_loop(btctrl.stop_scan_request())
		current_event_loop.run_until_complete(btctrl.stop_scan_request())
		conn.close()
		current_event_loop.run_until_complete(asyncio.sleep(0))
		current_event_loop.close()
		current_event_loop = None


def setup_platform(hass, config, add_entities, discovery_info=None):
	global scan_interval, scan_duration, measurement_water, measurement_gas, current_event_loop
	ha_entities = []
	scan_interval = config["scan_interval"]
	scan_duration = config["scan_duration"]
	current_event_loop = None
	measurement_water = config.get("measurement_water")
	measurement_gas = config.get("measurement_gas")
	for device in config["devices"]:
		if device["type"] == "gas":
			inf[device["id"]] = STATE_UNKNOWN
			ha_entities.append(GasSensor(device["id"], device["name"]))
		else:
			inf[device["id"]] = STATE_UNKNOWN
			if "_1" in str(device["id"]):
				temp_id = device["id"].split("_")[0]
				inf[temp_id + '_temp'] = STATE_UNKNOWN
				ha_entities.append(WaterTempSensor(temp_id, device["name_temp"]))
				ha_entities.append(WaterSensorCold(device["id"], device["name"]))
			elif "_2" in str(device["id"]):
				ha_entities.append(WaterSensorHot(device["id"], device["name"]))
			else:
				inf[str(device["id"]) + '_temp'] = STATE_UNKNOWN
				ha_entities.append(WaterTempSensor(device["id"], device["name_temp"]))
				if device["water_type"] == "hot":
					ha_entities.append(WaterSensorHot(device["id"], device["name"]))
				else:
					ha_entities.append(WaterSensorCold(device["id"], device["name"]))


	add_entities(ha_entities, True)
	track_time_interval(hass, update_counters, scan_interval)


class WaterTempSensor(SensorEntity):
	"""Representation of a Sensor."""

	def __init__(self, counter_num, name):
		"""Initialize the sensor."""
		self._state = None
		self._name = name
		self._state = STATE_UNKNOWN
		self._num = counter_num

	@property
	def name(self):
		"""Return the name of the sensor."""
		return self._name

	@property
	def state(self):
		"""Return the state of the sensor."""
		return self._state

	@property
	def unit_of_measurement(self):
		"""Return the unit of measurement."""
		return  UnitOfTemperature.CELSIUS

	@property
	def device_class(self):
		return SensorDeviceClass.TEMPERATURE

	@property
	def state_class(self):
		return SensorStateClass.MEASUREMENT

	@property
	def icon(self):
		"""Return the unit of measurement."""
		return "mdi:thermometer-water"

	@property
	def unique_id(self):
		"""Return Unique ID"""
		return "elehant_temp_" + str(self._num)

	def update(self):
		"""Fetch new state data for the sensor.
		This is the only method that should fetch new data for Home Assistant.
		"""
		# update_counters()
		self._state = inf[str(self._num) + '_temp']


class WaterSensorCold(SensorEntity):
	"""Representation of a Sensor."""

	def __init__(self, counter_num, name):
		"""Initialize the sensor."""
		self._state = None
		self._name = name
		self._state = STATE_UNKNOWN
		self._num = counter_num

	@property
	def name(self):
		"""Return the name of the sensor."""
		return self._name

	@property
	def state(self):
		"""Return the state of the sensor."""
		return self._state

	@property
	def unit_of_measurement(self):
		"""Return the unit of measurement."""
		if measurement_water == "m3":
			return UnitOfVolume.CUBIC_METERS
		else:
			return UnitOfVolume.LITERS

	@property
	def device_class(self):
		return SensorDeviceClass.WATER

	@property
	def state_class(self):
		return SensorStateClass.TOTAL_INCREASING

	@property
	def icon(self):
		"""Return the unit of measurement."""
		return "mdi:water"

	@property
	def unique_id(self):
		"""Return Unique ID"""
		return "elehant_" + str(self._num)

	def update(self):
		"""Fetch new state data for the sensor.
		This is the only method that should fetch new data for Home Assistant.
		"""
		# update_counters()
		self._state = inf[self._num]


class WaterSensorHot(SensorEntity):
	"""Representation of a Sensor."""

	def __init__(self, counter_num, name):
		"""Initialize the sensor."""
		self._state = None
		self._name = name
		self._state = STATE_UNKNOWN
		self._num = counter_num

	@property
	def name(self):
		"""Return the name of the sensor."""
		return self._name

	@property
	def state(self):
		"""Return the state of the sensor."""
		return self._state

	@property
	def unit_of_measurement(self):
		"""Return the unit of measurement."""
		if measurement_water == "m3":
			return UnitOfVolume.CUBIC_METERS
		else:
			return UnitOfVolume.LITERS

	@property
	def device_class(self):
		return SensorDeviceClass.WATER

	@property
	def state_class(self):
		return SensorStateClass.TOTAL_INCREASING

	@property
	def icon(self):
		"""Return the unit of measurement."""
		return "mdi:water-thermometer"

	@property
	def unique_id(self):
		"""Return Unique ID"""
		return "elehant_" + str(self._num)

	def update(self):
		"""Fetch new state data for the sensor.
		This is the only method that should fetch new data for Home Assistant.
		"""
		# update_counters()
		self._state = inf[self._num]


class GasSensor(SensorEntity):
	"""Representation of a Sensor."""

	def __init__(self, counter_num, name):
		"""Initialize the sensor."""
		self._state = None
		self._name = name
		self._state = STATE_UNKNOWN
		self._num = counter_num

	@property
	def name(self):
		"""Return the name of the sensor."""
		return self._name

	@property
	def state(self):
		"""Return the state of the sensor."""
		return self._state

	@property
	def unit_of_measurement(self):
		"""Return the unit of measurement."""
		if measurement_gas == "m3":
			return UnitOfVolume.CUBIC_METERS
		else:
			return UnitOfVolume.LITERS

	@property
	def device_class(self):
		return SensorDeviceClass.GAS

	@property
	def state_class(self):
		return SensorStateClass.TOTAL_INCREASING

	@property
	def icon(self):
		"""Return the unit of measurement."""
		return "mdi:gas-burner"

	@property
	def unique_id(self):
		"""Return Unique ID"""
		return "elehant_" + str(self._num)

	def update(self):
		"""Fetch new state data for the sensor.
		This is the only method that should fetch new data for Home Assistant.
		"""
		# update_counters()
		self._state = inf[self._num]
