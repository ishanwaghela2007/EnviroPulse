from app.connectors import cpcb, events, factory, ogd_aqi, openaq, water_sensor
from app.connectors.simulated import SIM_AIR

SIMULATED_SOURCES = [SIM_AIR, water_sensor.INFO, factory.INFO, events.INFO]
EXTERNAL_SOURCES = [openaq.INFO, ogd_aqi.INFO, cpcb.INFO]
ALL_SOURCES = SIMULATED_SOURCES + EXTERNAL_SOURCES
SOURCE_NAMES = {s.name for s in ALL_SOURCES}
