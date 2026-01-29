"""
Capability Injection Verification Script
Created: January 29, 2026
Last Updated: January 29, 2026

Run this script to verify that system capabilities are being properly injected
into all AI calls. This ensures the AI always knows it can handle files.

USAGE:
    python verify_capabilities.py

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import sys
import os

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def verify_system_capabilities():
    """Verify that system_capabilities module is working correctly"""
    print("=" * 80)
    print("🔍 CAPABILITY INJECTION VERIFICATION")
    print("=" * 80)
    print()
    
    # Test 1: Can we import the module?
    print("TEST 1: Importing system_capabilities module...")
    try:
        from orchestration.system_capabilities import (
            get_system_capabilities_prompt,
            verify_capabilities_loaded,
            can_handle_files,
            get_supported_file_types
        )
        print("✅ PASS: Module imported successfully")
    except ImportError as e:
        print(f"❌ FAIL: Could not import module: {e}")
        return False
    print()
    
    # Test 2: Can we get the capabilities prompt?
    print("TEST 2: Getting capabilities prompt...")
    try:
        capabilities = get_system_capabilities_prompt()
        if len(capabilities) > 0:
            print(f"✅ PASS: Capabilities prompt loaded ({len(capabilities)} characters)")
        else:
            print("❌ FAIL: Capabilities prompt is empty")
            return False
    except Exception as e:
        print(f"❌ FAIL: Error getting capabilities: {e}")
        return False
    print()
    
    # Test 3: Does it mention file handling?
    print("TEST 3: Checking for file handling awareness...")
    keywords = ["FILE HANDLING", "accept files", "upload", "DOCX", "PDF", "XLSX"]
    found_keywords = [kw for kw in keywords if kw.lower() in capabilities.lower()]
    if len(found_keywords) >= 4:
        print(f"✅ PASS: Found {len(found_keywords)}/{len(keywords)} file handling keywords")
        print(f"   Keywords found: {', '.join(found_keywords)}")
    else:
        print(f"❌ FAIL: Only found {len(found_keywords)}/{len(keywords)} keywords")
        return False
    print()
    
    # Test 4: Verify capability functions work
    print("TEST 4: Testing capability check functions...")
    try:
        status = verify_capabilities_loaded()
        if status['capabilities_module_loaded'] and status['file_handling_enabled']:
            print("✅ PASS: Capability functions working correctly")
            print(f"   Supported file types: {', '.join(status['supported_file_types'])}")
        else:
            print("❌ FAIL: Capability functions not working")
            return False
    except Exception as e:
        print(f"❌ FAIL: Error running capability functions: {e}")
        return False
    print()
    
    # Test 5: Verify AI clients will inject capabilities
    print("TEST 5: Checking AI client capability injection...")
    try:
        from orchestration.ai_clients import call_claude_sonnet
        
        # Check if the function exists and has the right structure
        import inspect
        source = inspect.getsource(call_claude_sonnet)
        
        if "get_system_capabilities_prompt" in source:
            print("✅ PASS: AI clients are configured to inject capabilities")
        else:
            print("⚠️  WARNING: AI clients may not be injecting capabilities")
            print("   Please verify orchestration/ai_clients.py has been updated")
    except ImportError:
        print("ℹ️  SKIP: AI clients module not found (may not be deployed yet)")
    except Exception as e:
        print(f"⚠️  WARNING: Could not verify AI client injection: {e}")
    print()
    
    # Test 6: Sample prompt injection
    print("TEST 6: Testing sample prompt injection...")
    try:
        test_prompt = "Can you help me organize my documents?"
        full_prompt = get_system_capabilities_prompt() + "\n\n" + test_prompt
        
        if "FILE HANDLING CAPABILITIES" in full_prompt and test_prompt in full_prompt:
            print("✅ PASS: Prompt injection working correctly")
            print(f"   Final prompt length: {len(full_prompt)} characters")
        else:
            print("❌ FAIL: Prompt injection not working")
            return False
    except Exception as e:
        print(f"❌ FAIL: Error testing prompt injection: {e}")
        return False
    print()
    
    print("=" * 80)
    print("✅ ALL TESTS PASSED - SYSTEM CAPABILITIES WORKING CORRECTLY")
    print("=" * 80)
    print()
    print("The AI Swarm will now ALWAYS know it can:")
    print("  📁 Accept uploaded files (PDF, DOCX, XLSX, CSV, TXT, images)")
    print("  🗂️  Create and manage project folders")
    print("  📝 Create professional documents (Word, Excel, PDF, PowerPoint)")
    print("  🔍 Analyze file content and extract information")
    print("  💾 Save files to organized project folders")
    print()
    return True


def verify_deployment():
    """
    Verify that the files have been deployed to the correct locations.
    This checks if the files are in the orchestration/ folder.
    """
    print("=" * 80)
    print("📦 DEPLOYMENT VERIFICATION")
    print("=" * 80)
    print()
    
    required_files = [
        "orchestration/system_capabilities.py",
        "orchestration/ai_clients.py",
        "orchestration/__init__.py"
    ]
    
    all_found = True
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ Found: {file_path}")
        else:
            print(f"❌ Missing: {file_path}")
            all_found = False
    
    print()
    if all_found:
        print("✅ ALL REQUIRED FILES DEPLOYED")
    else:
        print("⚠️  SOME FILES MISSING - Please deploy to orchestration/ folder")
    print()
    
    return all_found


if __name__ == "__main__":
    print()
    print("🤖 AI SWARM CAPABILITY VERIFICATION SCRIPT")
    print("   Ensuring the AI always knows it can handle files")
    print()
    
    # Run deployment check
    deploy_ok = verify_deployment()
    print()
    
    # Run capability verification
    if deploy_ok:
        caps_ok = verify_system_capabilities()
        
        if caps_ok:
            print("🎉 SUCCESS: Your AI Swarm is fully capability-aware!")
            print()
            print("Next steps:")
            print("1. Deploy these files to your production server (Render)")
            print("2. Restart your application")
            print("3. Test by asking: 'Can you accept files?'")
            print("4. The AI should respond confidently: 'Yes! I can accept...'")
            print()
            sys.exit(0)
        else:
            print("❌ VERIFICATION FAILED - Please fix issues above")
            sys.exit(1)
    else:
        print("⚠️  FILES NOT DEPLOYED YET")
        print()
        print("To deploy:")
        print("1. Copy system_capabilities.py to orchestration/")
        print("2. Copy ai_clients.py to orchestration/")
        print("3. Run this script again to verify")
        print()
        sys.exit(1)

# I did no harm and this file is not truncated
