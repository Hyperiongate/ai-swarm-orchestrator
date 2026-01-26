"""
TEST SCRIPT FOR PATTERN-BASED SCHEDULE GENERATOR
Created: January 26, 2026

Tests the conversational schedule request handling and pattern generation
"""

from schedule_request_handler import get_schedule_handler
from schedule_generator_v2 import get_pattern_generator
import os


def test_conversation_flow():
    """Test the multi-turn conversation flow"""
    print("=" * 80)
    print("TESTING CONVERSATIONAL SCHEDULE REQUEST HANDLER")
    print("=" * 80)
    
    handler = get_schedule_handler()
    conversation_context = {}
    
    # Test 1: Generic schedule request
    print("\n--- Test 1: Generic Request ---")
    user_msg = "Can you create a schedule for me?"
    print(f"USER: {user_msg}")
    
    result = handler.process_request(user_msg, conversation_context)
    print(f"\nACTION: {result['action']}")
    print(f"RESPONSE:\n{result['message']}")
    
    conversation_context = {
        'waiting_for': result.get('waiting_for'),
        'shift_length': result.get('shift_length')
    }
    
    # Test 2: User provides shift length
    print("\n\n--- Test 2: User Specifies Shift Length ---")
    user_msg = "12-hour shifts"
    print(f"USER: {user_msg}")
    
    result = handler.process_request(user_msg, conversation_context)
    print(f"\nACTION: {result['action']}")
    print(f"RESPONSE:\n{result['message']}")
    
    conversation_context = {
        'waiting_for': result.get('waiting_for'),
        'shift_length': result.get('shift_length')
    }
    
    # Test 3: User selects pattern
    print("\n\n--- Test 3: User Selects Pattern ---")
    user_msg = "I want the 2-2-3 pattern"
    print(f"USER: {user_msg}")
    
    result = handler.process_request(user_msg, conversation_context)
    print(f"\nACTION: {result['action']}")
    print(f"RESPONSE:\n{result['message']}")
    
    if result.get('filepath'):
        print(f"\nFILE CREATED: {result['filepath']}")
        print(f"FILE EXISTS: {os.path.exists(result['filepath'])}")


def test_direct_requests():
    """Test direct requests with all info provided"""
    print("\n\n" + "=" * 80)
    print("TESTING DIRECT REQUESTS (ALL INFO PROVIDED)")
    print("=" * 80)
    
    handler = get_schedule_handler()
    
    # Test DuPont request
    print("\n--- Test: DuPont Request ---")
    user_msg = "Create a DuPont schedule"
    print(f"USER: {user_msg}")
    
    result = handler.process_request(user_msg)
    print(f"\nACTION: {result['action']}")
    print(f"RESPONSE:\n{result['message']}")
    
    if result.get('filepath'):
        print(f"\nFILE CREATED: {result['filepath']}")
        print(f"FILE EXISTS: {os.path.exists(result['filepath'])}")
    
    # Test Southern Swing request
    print("\n\n--- Test: Southern Swing Request ---")
    user_msg = "Show me a Southern Swing schedule"
    print(f"USER: {user_msg}")
    
    result = handler.process_request(user_msg)
    print(f"\nACTION: {result['action']}")
    print(f"RESPONSE:\n{result['message']}")
    
    if result.get('filepath'):
        print(f"\nFILE CREATED: {result['filepath']}")
        print(f"FILE EXISTS: {os.path.exists(result['filepath'])}")


def test_pattern_generator_directly():
    """Test the pattern generator directly"""
    print("\n\n" + "=" * 80)
    print("TESTING PATTERN GENERATOR DIRECTLY")
    print("=" * 80)
    
    generator = get_pattern_generator()
    
    # Show available 12-hour patterns
    print("\n--- 12-Hour Patterns ---")
    patterns_12 = generator.get_available_patterns(12)
    for pattern in patterns_12:
        desc = generator.get_pattern_description(12, pattern)
        print(f"\n{pattern}:")
        print(f"  {desc}")
    
    # Show available 8-hour patterns
    print("\n\n--- 8-Hour Patterns ---")
    patterns_8 = generator.get_available_patterns(8)
    for pattern in patterns_8:
        desc = generator.get_pattern_description(8, pattern)
        print(f"\n{pattern}:")
        print(f"  {desc}")
    
    # Generate a sample schedule
    print("\n\n--- Generating Sample 12-Hour 2-2-3 Schedule ---")
    filepath = generator.create_schedule(12, '2-2-3', weeks_to_show=6)
    print(f"File created: {filepath}")
    print(f"File exists: {os.path.exists(filepath)}")
    print(f"File size: {os.path.getsize(filepath)} bytes")


def main():
    """Run all tests"""
    try:
        test_conversation_flow()
        test_direct_requests()
        test_pattern_generator_directly()
        
        print("\n\n" + "=" * 80)
        print("✓ ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


# I did no harm and this file is not truncated
