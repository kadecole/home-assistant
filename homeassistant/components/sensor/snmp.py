"""
Support for displaying collected data over SNMP.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.snmp/
"""
import logging
from datetime import timedelta
import voluptuous as vol

from homeassistant.helpers.entity import Entity
from homeassistant.const import (CONF_HOST, CONF_PLATFORM, CONF_NAME,
                                 CONF_PORT, ATTR_UNIT_OF_MEASUREMENT)
from homeassistant.util import Throttle

REQUIREMENTS = ['pysnmp==4.3.2']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "SNMP"
DEFAULT_COMMUNITY = "public"
DEFAULT_PORT = "161"
CONF_COMMUNITY = "community"
CONF_BASEOID = "baseoid"

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'snmp',
    vol.Optional(CONF_NAME): vol.Coerce(str),
    vol.Required(CONF_HOST): vol.Coerce(str),
    vol.Optional(CONF_PORT): vol.Coerce(int),
    vol.Optional(CONF_COMMUNITY): vol.Coerce(str),
    vol.Required(CONF_BASEOID): vol.Coerce(str),
    vol.Optional(ATTR_UNIT_OF_MEASUREMENT): vol.Coerce(str),
})

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)


# pylint: disable=too-many-locals
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the SNMP sensor."""
    from pysnmp.hlapi import (getCmd, CommunityData, SnmpEngine,
                              UdpTransportTarget, ContextData, ObjectType,
                              ObjectIdentity)

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT, DEFAULT_PORT)
    community = config.get(CONF_COMMUNITY, DEFAULT_COMMUNITY)
    baseoid = config.get(CONF_BASEOID)

    errindication, _, _, _ = next(
        getCmd(SnmpEngine(),
               CommunityData(community, mpModel=0),
               UdpTransportTarget((host, port)),
               ContextData(),
               ObjectType(ObjectIdentity(baseoid))))

    if errindication:
        _LOGGER.error('Please check the details in the configuration file')
        return False
    else:
        data = SnmpData(host, port, community, baseoid)
        add_devices([SnmpSensor(data,
                                config.get('name', DEFAULT_NAME),
                                config.get('unit_of_measurement'))])


class SnmpSensor(Entity):
    """Representation of a SNMP sensor."""

    def __init__(self, data, name, unit_of_measurement):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._state = None
        self._unit_of_measurement = unit_of_measurement
        self.update()

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
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data and updates the states."""
        self.data.update()
        self._state = self.data.value


class SnmpData(object):
    """Get the latest data and update the states."""

    # pylint: disable=too-few-public-methods
    def __init__(self, host, port, community, baseoid):
        """Initialize the data object."""
        self._host = host
        self._port = port
        self._community = community
        self._baseoid = baseoid
        self.value = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the remote SNMP capable host."""
        from pysnmp.hlapi import (getCmd, CommunityData, SnmpEngine,
                                  UdpTransportTarget, ContextData, ObjectType,
                                  ObjectIdentity)
        errindication, errstatus, errindex, restable = next(
            getCmd(SnmpEngine(),
                   CommunityData(self._community, mpModel=0),
                   UdpTransportTarget((self._host, self._port)),
                   ContextData(),
                   ObjectType(ObjectIdentity(self._baseoid)))
            )

        if errindication:
            _LOGGER.error("SNMP error: %s", errindication)
        elif errstatus:
            _LOGGER.error('SNMP error: %s at %s', errstatus.prettyPrint(),
                          errindex and restable[-1][int(errindex) - 1] or '?')
        else:
            for resrow in restable:
                self.value = resrow[-1]
