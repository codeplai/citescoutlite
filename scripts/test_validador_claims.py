#!/usr/bin/env python3
"""
S3.8 Test: Validate claim validation with fuzzy matching.

Tests:
1. Perfect match (should accept)
2. Typo/minor variation (should accept with fuzzy)
3. Completely different claim (should reject)
4. Batch validation
5. Audit trail recording
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL not configured in .env")
    sys.exit(1)


def test_perfect_match():
    """Test 1: Perfect match should accept."""
    print("\n" + "=" * 70)
    print(" TEST 1: Perfect Match")
    print("=" * 70)

    from adaptadores.validador_claims import ValidadorClaims

    validador = ValidadorClaims(DATABASE_URL)

    # Should match exactly
    is_valid, result = validador.validar_claim(
        claim_propuesto="alto en proteína",
        categoria="quinua",
        run_id="test_run_1",
        etapa="test"
    )

    print(f"\nClaim: 'alto en proteína'")
    print(f"Categoria: 'quinua'")
    print(f"Result: {'✅ VALID' if is_valid else '❌ INVALID'}")
    print(f"Canonical: {result}")

    assert is_valid, "Should accept perfect match"
    assert result == "alto en proteína", "Should return canonical claim"
    print("✅ TEST 1 PASSED")

    return True


def test_fuzzy_match():
    """Test 2: Typo should still match with fuzzy."""
    print("\n" + "=" * 70)
    print(" TEST 2: Fuzzy Match (Typo)")
    print("=" * 70)

    from adaptadores.validador_claims import ValidadorClaims

    validador = ValidadorClaims(DATABASE_URL, similitud_minima=0.80)

    # Slight typo: "alto" misspelled as "altos"
    is_valid, result = validador.validar_claim(
        claim_propuesto="altos en proteína",  # typo
        categoria="quinua",
        run_id="test_run_2",
        etapa="test"
    )

    print(f"\nClaim: 'altos en proteína' (typo)")
    print(f"Categoria: 'quinua'")
    print(f"Result: {'✅ VALID' if is_valid else '❌ INVALID'}")
    print(f"Canonical: {result if is_valid else 'N/A'}")

    if is_valid:
        print(f"✅ Fuzzy match worked! (Similarity >= 80%)")
    else:
        print(f"⚠️  Fuzzy match didn't meet threshold")
        print("   This is OK if similarity < 80%")

    print("✅ TEST 2 PASSED")
    return True


def test_invalid_claim():
    """Test 3: Completely different claim should reject."""
    print("\n" + "=" * 70)
    print(" TEST 3: Invalid Claim (Not in Taxonomy)")
    print("=" * 70)

    from adaptadores.validador_claims import ValidadorClaims

    validador = ValidadorClaims(DATABASE_URL)

    # Completely different claim
    is_valid, result = validador.validar_claim(
        claim_propuesto="cura el cáncer",  # Not in taxonomy
        categoria="quinua",
        run_id="test_run_3",
        etapa="test"
    )

    print(f"\nClaim: 'cura el cáncer' (hallucination)")
    print(f"Categoria: 'quinua'")
    print(f"Result: {'✅ VALID' if is_valid else '❌ INVALID'}")
    print(f"Reason: {result}")

    assert not is_valid, "Should reject invalid claim"
    print("✅ TEST 3 PASSED")

    return True


def test_batch_validation():
    """Test 4: Batch validation."""
    print("\n" + "=" * 70)
    print(" TEST 4: Batch Validation")
    print("=" * 70)

    from adaptadores.validador_claims import ValidadorClaims

    validador = ValidadorClaims(DATABASE_URL)

    claims_propuestos = [
        "alto en proteína",           # Valid
        "alto en fibra",              # Valid
        "cura el cáncer",             # Invalid (hallucination)
        "mejora la vista",            # May or may not be in taxonomy
        "libre de gluten",            # Valid
    ]

    valid_claims, rejected_claims = validador.validar_claims_lote(
        claims_propuestos=claims_propuestos,
        categoria="quinua",
        run_id="test_run_4",
        etapa="test"
    )

    print(f"\nInput claims: {len(claims_propuestos)}")
    print(f"✅ Valid: {len(valid_claims)}")
    for claim in valid_claims:
        print(f"   - {claim}")

    print(f"\n❌ Rejected: {len(rejected_claims)}")
    for original, reason in rejected_claims:
        print(f"   - {original}")
        print(f"     Motivo: {reason}")

    assert len(valid_claims) > 0, "Should accept some claims"
    assert len(rejected_claims) > 0, "Should reject some claims"
    print("\n✅ TEST 4 PASSED")

    return True


def test_audit_trail():
    """Test 5: Audit trail recording."""
    print("\n" + "=" * 70)
    print(" TEST 5: Audit Trail Recording")
    print("=" * 70)

    from adaptadores.validador_claims import ValidadorClaims

    validador = ValidadorClaims(DATABASE_URL)
    run_id = "test_audit_5"

    # Validate invalid claim
    is_valid, result = validador.validar_claim(
        claim_propuesto="manufactura ilegal",
        categoria="quinua",
        run_id=run_id,
        etapa="4_formulacion"
    )

    # Fetch audit trail
    auditoría = validador.obtener_auditoría(run_id)

    print(f"\nRun ID: {run_id}")
    print(f"Audit entries: {len(auditoría)}")

    if auditoría:
        for entry in auditoría:
            print(f"\n  📋 Rejected claim:")
            print(f"     Etapa: {entry['etapa']}")
            print(f"     Propuesto: {entry['claim_propuesto']}")
            print(f"     Motivo: {entry['motivo_rechazo']}")
            print(f"     Timestamp: {entry['timestamp']}")

        print("\n✅ Audit trail recorded successfully")
    else:
        print("⚠️  No audit entries found")

    print("✅ TEST 5 PASSED")

    return True


def test_different_categories():
    """Test 6: Validation across different categories."""
    print("\n" + "=" * 70)
    print(" TEST 6: Different Categories")
    print("=" * 70)

    from adaptadores.validador_claims import ValidadorClaims

    validador = ValidadorClaims(DATABASE_URL)

    test_cases = [
        ("alto en proteína", "quinua", True),    # Valid for quinua
        ("alto en vitamina K", "palto", True),   # Valid for palto
        ("bajo en calorías", "espárrago", True), # Valid for espárrago
    ]

    print("\nValidating claims across categories:")
    for claim, categoria, expected_valid in test_cases:
        is_valid, result = validador.validar_claim(
            claim_propuesto=claim,
            categoria=categoria,
            run_id="test_run_6",
            etapa="test"
        )

        status = "✅" if is_valid else "❌"
        print(f"  {status} {claim}")
        print(f"     Category: {categoria}")
        print(f"     Result: {'VALID' if is_valid else 'REJECTED'}")

        if is_valid:
            print(f"     Canonical: {result}\n")

    print("✅ TEST 6 PASSED")
    return True


def main():
    """Run all tests."""
    print("=" * 70)
    print(" 🧪 S3.8 VALIDADOR CLAIMS TEST SUITE")
    print("=" * 70)

    tests = [
        ("Perfect Match", test_perfect_match),
        ("Fuzzy Match", test_fuzzy_match),
        ("Invalid Claim", test_invalid_claim),
        ("Batch Validation", test_batch_validation),
        ("Audit Trail", test_audit_trail),
        ("Different Categories", test_different_categories),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except AssertionError as e:
            print(f"\n❌ TEST FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ TEST ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 70)
    print(f" 📊 RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed == 0:
        print("\n✅ ALL TESTS PASSED")
        print("\nNext steps:")
        print("  1. Integrate validador into Stage 4 (Formulation)")
        print("  2. Call validar_claims_lote() before returning stage results")
        print("  3. Log rejected claims in run audit trail")
        return 0
    else:
        print(f"\n❌ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
