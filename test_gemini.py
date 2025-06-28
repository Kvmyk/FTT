#!/usr/bin/env python3
# Test script for Gemini API hate speech detection

import sys
import os
sys.path.append('app')

from dotenv import load_dotenv
load_dotenv()

from utils import is_hate_speech

def test_hate_speech_detection():
    print("Testing Gemini API hate speech detection...")
    
    # Test cases
    test_cases = [
        ("To jest miła toaleta, bardzo czysta!", False),  # Should be OK
        ("Świetne miejsce, polecam!", False),  # Should be OK
        ("Bardzo brudne i nieprzyjemne", False),  # Should be OK (just negative but not hate speech)
        ("głupie imbecyle", True),  # Should be NOT OK (hate speech)
    ]
    
    for text, expected_hate in test_cases:
        print(f"\nTesting: '{text}'")
        result = is_hate_speech(text)
        status = "NOT OK (hate speech detected)" if result else "OK (clean text)"
        expected = "NOT OK" if expected_hate else "OK"
        match = "✓" if result == expected_hate else "✗"
        print(f"Result: {status} | Expected: {expected} | {match}")

if __name__ == "__main__":
    test_hate_speech_detection()
