# can_parser.py
import config
from logger_setup import app_logger

def parse_can_id_struct(can_id_int_32bit):
    """
    Parses a 32-bit integer representing the CAN ID.
    The lower 3 bits are assumed to be padding and are shifted off.
    The MSB (bit 28) of the remaining 29-bit ID is an ACK flag.
    The other fields (Sender, Board, Component, Instance) are parsed from
    the base 29-bit ID (after the ACK bit is masked off).
    """
    if not isinstance(can_id_int_32bit, int):
        raise ValueError("CAN ID must be an integer.")

    # Shift off the lower 3 bits (padding) to get the 29-bit ID with potential ACK bit
    can_id_29bit_with_ack = can_id_int_32bit >> 3

    # Check if the ACK bit (MSB of the 29-bit ID, i.e., bit 28) is set
    is_ack = (can_id_29bit_with_ack & config.CAN_ID_ACK_BIT_IN_29BIT_ID) != 0

    # Get the base 29-bit CAN ID by masking off the ACK bit.
    # This base_id contains Sender, Board, Component, Instance fields.
    base_29bit_id = can_id_29bit_with_ack & ~config.CAN_ID_ACK_BIT_IN_29BIT_ID

    # Parse the fields from the base_29bit_id
    sender = (base_29bit_id & config.CAN_ID_SENDER_MASK) >> config.CAN_ID_SENDER_SHIFT
    board_id = (base_29bit_id & config.CAN_ID_BOARD_ID_MASK) >> config.CAN_ID_BOARD_ID_SHIFT
    component_type = (base_29bit_id & config.CAN_ID_COMPONENT_TYPE_MASK) >> config.CAN_ID_COMPONENT_TYPE_SHIFT
    instance = (base_29bit_id & config.CAN_ID_INSTANCE_MASK) >> config.CAN_ID_INSTANCE_SHIFT

    return {
        "is_ack": is_ack,
        "original_29bit_id_with_ack": can_id_29bit_with_ack, # The raw 29-bit value including ACK bit
        "base_29bit_id": base_29bit_id,                    # Raw 29-bit value excluding ACK bit (includes Sender)
        "sender_id": sender,                               # Parsed sender ID
        "board_id": board_id,                              # Parsed board ID (who the message is *for* or status *from*)
        "component_type_id": component_type,               # Parsed component type ID
        "instance_id": instance,                           # Parsed instance ID
    }

def get_component_info_by_id_tuple(board_id, component_type_id, instance_id):
    """
    Looks up component configuration from ALL_COMPONENTS_LOOKUP using a tuple key
    (board_id, component_type_id, instance_id).
    This ignores the sender ID as requested.
    """
    lookup_key = (board_id, component_type_id, instance_id)
    return config.ALL_COMPONENTS_LOOKUP.get(lookup_key)

# --- Deprecated ---
# def get_component_info_by_can_id(base_can_id_29bit):
#     """
#     DEPRECATED: Looks up component configuration from ALL_COMPONENTS_LOOKUP using the full base 29-bit CAN ID
#     (i.e., with the ACK bit already masked off, but potentially including sender).
#     Use get_component_info_by_id_tuple instead.
#     """
#     # Old logic, assuming ALL_COMPONENTS_LOOKUP was keyed by the full 29-bit ID
#     # return config.ALL_COMPONENTS_LOOKUP.get(base_can_id_29bit)
#     app_logger.warning("Deprecated function get_component_info_by_can_id called.")
#     return None # Or try to reconstruct the tuple key, but better to use the new function

def get_board_name(board_id_8bit):
    """
    Gets the human-readable board name from its 8-bit ID using BOARD_INFO_LOOKUP_TABLE.
    """
    board_info = config.BOARD_INFO_LOOKUP_TABLE.get(board_id_8bit)
    return board_info["name"] if board_info else f"Board 0x{board_id_8bit:02X}" # Return hex ID if unknown

def get_sender_name(sender_id_8bit):
    """Gets sender name using BOARD_CAN_ID_MAPPING."""
    for name, id_val in config.BOARD_CAN_ID_MAPPING.items():
        if id_val == sender_id_8bit:
            return name.replace("SENDER_", "") # Make it cleaner, e.g., "PAD_CONTROLLER"
    # Fallback: Check if it's a known board ID (sometimes sender might be the board itself)
    board_info = config.BOARD_INFO_LOOKUP_TABLE.get(sender_id_8bit)
    if board_info:
        return board_info["name"]
    return f"Sender 0x{sender_id_8bit:02X}"


def get_component_type_name(component_type_id_8bit):
    """Gets component type name from MESSAGE_TYPE map."""
    for name, id_val in config.MESSAGE_TYPE.items():
        if id_val == component_type_id_8bit:
            return name.replace("MSG_TYPE_", "") # Cleaner name, e.g., "SERVO"
    return f"CompType 0x{component_type_id_8bit:02X}"

if __name__ == '__main__':
    # Test parsing for a non-ACK ID (e.g., Servo status from Servo Board 2)
    # Sender=2, Board=1, Comp=1 (Servo), Inst=8 => 0x02010108 (base 29-bit ID)
    base_id_29bit_servo = 0x02010108
    example_id_32bit_servo = base_id_29bit_servo << 3 # Simulate padding
    print(f"--- Testing Non-ACK ID (Servo Example) ---")
    print(f"Input 29-bit ID: 0x{base_id_29bit_servo:07X}")
    print(f"Input 32-bit (simulated wire value): 0x{example_id_32bit_servo:08X}")
    parsed_servo = parse_can_id_struct(example_id_32bit_servo)
    print(f"Parsed: {parsed_servo}")

    if parsed_servo:
        board_name = get_board_name(parsed_servo["board_id"])
        sender_name = get_sender_name(parsed_servo["sender_id"])
        comp_type_name = get_component_type_name(parsed_servo["component_type_id"])
        print(f"Sender: {sender_name} ({parsed_servo['sender_id']}), Board: {board_name} ({parsed_servo['board_id']}), "
              f"CompType: {comp_type_name} ({parsed_servo['component_type_id']}), Instance: {parsed_servo['instance_id']}")

        # Test the NEW lookup function
        comp_details_tuple = get_component_info_by_id_tuple(
            parsed_servo["board_id"], parsed_servo["component_type_id"], parsed_servo["instance_id"]
        )
        print(f"Component Details (lookup by tuple key): {comp_details_tuple}")
        # Verify it matches the expected servo:
        expected_key = (1, config.MESSAGE_TYPE["MSG_TYPE_SERVO"], 8)
        print(f"Expected Lookup Key: {expected_key}")
        print(f"Lookup successful: {config.ALL_COMPONENTS_LOOKUP.get(expected_key) is not None}")


    # Test parsing for an ACK ID (using the same servo example)
    ack_example_id_29bit = config.CAN_ID_ACK_BIT_IN_29BIT_ID | base_id_29bit_servo
    ack_example_id_32bit = ack_example_id_29bit << 3

    print(f"\n--- Testing ACK ID (Servo Example) ---")
    print(f"Input 29-bit ID with ACK: 0x{ack_example_id_29bit:07X}")
    print(f"Input 32-bit (simulated wire value): 0x{ack_example_id_32bit:08X}")
    parsed_ack = parse_can_id_struct(ack_example_id_32bit)
    print(f"Parsed ACK: {parsed_ack}")

    if parsed_ack:
        print(f"Is ACK: {parsed_ack['is_ack']}")
        # Component lookup should use the same tuple key derived from the parsed fields
        comp_details_ack = get_component_info_by_id_tuple(
             parsed_ack["board_id"], parsed_ack["component_type_id"], parsed_ack["instance_id"]
        )
        print(f"Component Details for ACK (lookup by tuple key): {comp_details_ack}")
        # The board_id and sender_id in an ACK message usually represent the board *sending* the ACK
        board_name_ack = get_board_name(parsed_ack["board_id"])
        sender_name_ack = get_sender_name(parsed_ack["sender_id"])
        print(f"Board Name (source of ACK): {board_name_ack} ({parsed_ack['board_id']})")
        print(f"Sender Name (source of ACK): {sender_name_ack} ({parsed_ack['sender_id']})")

    # Example: Pad Controller (1) sending Igniter Status (20) for instance 0, board ID doesn't matter for lookup here
    # Let's assume the PAD Controller's board ID is 0x20 (as added in config)
    # Base 29-bit ID: Sender=1, Board=0x20, Comp=20, Inst=0 => (1<<21)|(0x20<<13)|(20<<5)|0 = 0x08A0A000
    # THIS IS WRONG - bit shifts are off.
    # Sender 1 (0x01) -> 0000 0001 << 21 -> 0x00200000
    # Board 32 (0x20) -> 0010 0000 << 13 -> 0x00040000
    # Comp 20 (0x14) -> 0001 0100 << 5  -> 0x00000280
    # Inst 0  (0x00) -> 0000 0000 << 0  -> 0x00000000
    # Sum = 0x240280 (base 29-bit ID)
    base_id_29bit_igniter = 0x00240280
    example_id_32bit_igniter = base_id_29bit_igniter << 3
    print(f"\n--- Testing Pad Controller Status Msg (Igniter Example) ---")
    print(f"Input 29-bit ID: 0x{base_id_29bit_igniter:07X}")
    print(f"Input 32-bit (simulated wire value): 0x{example_id_32bit_igniter:08X}")
    parsed_igniter = parse_can_id_struct(example_id_32bit_igniter)
    print(f"Parsed: {parsed_igniter}")
    # Note: Component lookup for these status messages might not be needed if handling is purely based on component_type_id
    # If a lookup were needed, it would use (board_id, comp_type_id, instance_id) = (32, 20, 0)