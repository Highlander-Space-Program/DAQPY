# logger_setup.py
import logging
import config # Imports LOG_FILE_NAME, DATA_LOG_FILE_NAME, and now XBEE_RAW_PACKET_LOG_FILE_NAME

def setup_logger():
    """Sets up the main application logger."""
    logger = logging.getLogger("ControlPanelApp")
    logger.setLevel(logging.DEBUG) 

    if logger.hasHandlers():
        logger.handlers.clear()

    # File Handler for general logs
    fh = logging.FileHandler(config.LOG_FILE_NAME, mode='a')
    fh.setLevel(logging.INFO) 
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Console Handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG) 
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    return logger

app_logger = setup_logger()

def setup_data_logger():
    """Sets up the logger for parsed sensor data (CSV format)."""
    data_logger = logging.getLogger("SensorData")
    data_logger.setLevel(logging.INFO)

    if data_logger.hasHandlers():
        data_logger.handlers.clear()
        
    fh_data = logging.FileHandler(config.DATA_LOG_FILE_NAME, mode='a')
    data_formatter = logging.Formatter('%(asctime)s,%(message)s') # CSV friendly
    fh_data.setFormatter(data_formatter)
    data_logger.addHandler(fh_data)
    
    try:
        with open(config.DATA_LOG_FILE_NAME, 'r') as f:
            if not f.readline(): 
                data_logger.info("timestamp,name,value,unit,board,component_type,instance_id") 
    except FileNotFoundError:
        data_logger.info("timestamp,name,value,unit,board,component_type,instance_id") 
        
    return data_logger

sensor_data_logger = setup_data_logger()

def setup_xbee_packet_logger():
    """Sets up the logger for raw XBee packets."""
    packet_logger = logging.getLogger("XBeeRawPackets")
    packet_logger.setLevel(logging.INFO) # Log all received packets

    if packet_logger.hasHandlers():
        packet_logger.handlers.clear()

    # File Handler for XBee raw packets
    fh_xbee = logging.FileHandler(config.XBEE_RAW_PACKET_LOG_FILE_NAME, mode='a')
    fh_xbee.setLevel(logging.INFO)
    # Simple format: timestamp - packet string representation
    packet_formatter = logging.Formatter('%(asctime)s - %(message)s')
    fh_xbee.setFormatter(packet_formatter)
    packet_logger.addHandler(fh_xbee)
    
    # Optionally, prevent propagation to the root logger if you don't want these in console/main log
    # packet_logger.propagate = False 
    
    return packet_logger

xbee_packet_logger = setup_xbee_packet_logger()
