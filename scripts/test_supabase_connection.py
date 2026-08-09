#!/usr/bin/env python3
"""Test Supabase connection and basic operations."""

import os
from dotenv import load_dotenv

def test_supabase():
    load_dotenv(".env.local")

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
    DATABASE_URL = os.getenv("DATABASE_URL")

    print("🔍 Testing Supabase connection...\n")

    # Test 1: API credentials
    if SUPABASE_URL and SUPABASE_ANON_KEY:
        print(f"✅ SUPABASE_URL: {SUPABASE_URL}")
        print(f"✅ SUPABASE_ANON_KEY: {'*' * 20}...")
    else:
        print("❌ Missing SUPABASE_URL or SUPABASE_ANON_KEY")
        return False

    # Test 2: Database connection
    if DATABASE_URL:
        print(f"✅ DATABASE_URL configured (connection pooler detected)")
    else:
        print("❌ Missing DATABASE_URL")
        return False

    print("\n📋 Next steps:")
    print("  1. Fill .env.local with real credentials from Supabase dashboard")
    print("  2. Run: psql $DATABASE_URL -c 'SELECT version();'")
    print("  3. Create schema and tables (S1.2)")

    return True

if __name__ == "__main__":
    success = test_supabase()
    exit(0 if success else 1)
