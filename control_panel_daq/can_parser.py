# can_parser.py
import config

def parse_can_id_struct(can_id_int_32bit):
    """
    Parses a 32-bit integer representing the CAN ID (where 29 bits are actual ID).
    The provided example 0x01050401 (hex) = 00000001 00000101 00000100 00001 000 (binary)
    suggests the 29-bit ID is in the upper bits, and the lower 3 bits are padding.
    So, we right-shift by 3.
    """
    if not isinstance(can_id_int_32bit, int):
        raise ValueError("CAN ID must be an integer.")

    can_id_29bit = can_id_int_32bit >> 3 # Adjust if padding is different

    sender = (can_id_29bit & (0xFF << 21)) >> 21 # Sender field is top 8 bits of the 29 bits
    board_id = (can_id_29bit & (0xFF << 13)) >> 13 # Board ID is next 8 bits
    component_type = (can_id_29bit & (0xFF << 5)) >> 5 # Component type is next 8 bits
    instance = can_id_29bit & 0x1F # Instance is the last 5 bits

    return {
        "sender_id": sender,
        "board_id": board_id,
        "component_type_id": component_type,
        "instance_id": instance,
        "original_29bit_id": can_id_29bit
    }

def get_component_info_by_can_id(can_id_29bit):
    """
    Looks up component configuration from ALL_COMPONENTS_LOOKUP using the full 29-bit CAN ID.
    """
    return config.ALL_COMPONENTS_LOOKUP.get(can_id_29bit)

def get_board_name(board_id_8bit):
    """
    Gets the human-readable board name from its 8-bit ID.
    """
    board_info = config.BOARD_INFO_LOOKUP_TABLE.get(board_id_8bit)
    return board_info["name"] if board_info else "Unknown Board"

def get_sender_name(sender_id_8bit):
    for name, id_val in config.BOARD_CAN_ID_MAPPING.items():
        if id_val == sender_id_8bit:
            return name
    return "Unknown Sender"

def get_component_type_name(component_type_id_8bit):
    for name, id_val in config.MESSAGE_TYPE.items():
        if id_val == component_type_id_8bit:
            return name
    return "Unknown Component Type"

if __name__ == '__main__':
    # Test parsing
    example_id_hex = 0x01050401 # "Pad Controller (1) sending to Board 5, Heater (4), instance 1"
    parsed = parse_can_id_struct(example_id_hex)
    print(f"Parsed 0x{example_id_hex:08X}: {parsed}")
    # Expected: Sender=1, BoardID=5, Component=4, Instance=1

    example_servo_id = 0x02010108 # FV-N02: Sender=2, BoardID=1, Comp=1 (Servo), Inst=1
    parsed_servo = parse_can_id_struct(example_servo_id)
    print(f"Parsed 0x{example_servo_id:08X}: {parsed_servo}")
    
    component_details = get_component_info_by_can_id(parsed_servo["original_29bit_id"])
    print(f"Component Details for 0x{parsed_servo['original_29bit_id']:07X}: {component_details}")

    board_name = get_board_name(parsed_servo["board_id"])
    print(f"Board Name for ID {parsed_servo['board_id']}: {board_name}")


    example_servo_id = 0x20000324
    parsed_servo = parse_can_id_struct(example_servo_id)
    print(f"Parsed 0x{example_servo_id:08X}: {parsed_servo}")
    
    component_details = get_component_info_by_can_id(parsed_servo["original_29bit_id"])
    print(f"Component Details for 0x{parsed_servo['original_29bit_id']:07X}: {component_details}")

    board_name = get_board_name(parsed_servo["board_id"])
    print(f"Board Name for ID {parsed_servo['board_id']}: {board_name}")