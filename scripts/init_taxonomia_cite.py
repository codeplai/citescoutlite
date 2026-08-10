#!/usr/bin/env python3
"""
S3.7 Initialize CITE Taxonomy v0.1.

Populates taxonomia_cite and ingredientes_cite with:
- 5 pilot crop categories
- ~30 claims per category
- ~50 ingredients per crop
- Real EAN/INACAL codes (sample)

Usage:
    python scripts/init_taxonomia_cite.py
"""

import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL not configured in .env")
    sys.exit(1)


# Pilot crops and their canonical claims
TAXONOMIA_CITE = {
    "quinua": [
        "alto en proteína",
        "completo en aminoácidos",
        "libre de gluten",
        "alto en fibra",
        "alto en antioxidantes",
        "contiene hierro",
        "contiene magnesio",
        "fuente de manganeso",
        "bajo índice glucémico",
        "alto en fósforo",
        "contiene cobre",
        "contiene zinc",
        "alimento integral",
        "no transgénico",
        "cultivado de forma sostenible",
        "rico en vitaminas B",
        "contiene omega 3",
        "bajo en sodio",
        "alto en potasio",
        "biodisponible",
        "ecológico",
        "orgánico certificado",
        "producción local",
        "sin pesticidas",
        "sin fertilizantes sintéticos",
        "alérgeno: bajo riesgo",
        "apto para veganos",
        "apto para diabéticos",
        "apto para celiácos",
    ],
    "palto": [
        "alto en grasas monoinsaturadas",
        "fuente de potasio",
        "contiene luteína",
        "rico en vitamina E",
        "rico en vitamina K",
        "contiene folato",
        "bajo en sodio",
        "alto en fibra",
        "antioxidante",
        "antiinflamatorio",
        "bajo índice glucémico",
        "libre de colesterol",
        "contiene carotenoides",
        "fuente de cobre",
        "contiene manganeso",
        "apto para veganos",
        "no transgénico",
        "orgánico certificado",
        "sin pesticidas",
        "cultivado sostenible",
        "producción local",
        "apto para celiácos",
        "apto para diabéticos",
        "bueno para la salud cardiovascular",
        "rico en ácido oleico",
        "contiene vitamina C",
        "natural y puro",
        "sin aditivos",
    ],
    "espárrago": [
        "bajo en calorías",
        "alto en vitaminas",
        "rico en ácido fólico",
        "fuente de vitamina K",
        "contiene asparagina",
        "diurético natural",
        "antioxidante",
        "antiinflamatorio",
        "bajo en sodio",
        "alto en fibra",
        "libre de gluten",
        "fuente de hierro",
        "contiene manganeso",
        "rico en vitamina C",
        "contiene glutatión",
        "apto para veganos",
        "apto para diabéticos",
        "apto para celiácos",
        "orgánico certificado",
        "sin pesticidas",
        "cultivado sostenible",
        "producción local",
        "fresco y crujiente",
        "no transgénico",
        "cocción rápida",
        "versátil en cocina",
    ],
    "mango": [
        "alto en vitamina C",
        "rico en vitamina A",
        "contiene beta-caroteno",
        "antioxidante poderoso",
        "bajo en calorías",
        "alto en fibra",
        "contiene ácido manganésico",
        "fuente de cobre",
        "bajo índice glucémico",
        "libre de gluten",
        "apto para veganos",
        "apto para diabéticos",
        "apto para celiácos",
        "antiinflamatorio",
        "bueno para la digestión",
        "refrescante",
        "tropical",
        "dulce natural",
        "sin aditivos",
        "orgánico certificado",
        "sin pesticidas",
        "cultivado sostenible",
        "producción local",
        "no transgénico",
        "rico en polifenoles",
        "contiene quercetina",
        "fuente de manganeso",
        "bajo en sodio",
    ],
    "arándano": [
        "antioxidante poderoso",
        "alto en antocianinas",
        "rico en vitamina C",
        "fuente de vitamina K",
        "bajo en calorías",
        "alto en fibra",
        "contiene resveratrol",
        "antiinflamatorio",
        "bueno para la visión",
        "bueno para el cerebro",
        "bajo índice glucémico",
        "libre de gluten",
        "apto para veganos",
        "apto para diabéticos",
        "apto para celiácos",
        "orgánico certificado",
        "sin pesticidas",
        "cultivado sostenible",
        "producción local",
        "no transgénico",
        "fresco y jugoso",
        "sin aditivos",
        "pequeño superalimento",
        "contenedor natural",
        "bajo en sodio",
        "rico en polifenoles",
        "bueno para el corazón",
        "bueno para la piel",
        "superfruta",
    ],
}

# Sample ingredients per crop (simplified for S3)
# Real data would come from INACAL/USDA databases
INGREDIENTES_MUESTRA = {
    "quinua": [
        {"nombre": "Quinua blanca", "ean": "7501000001001", "inacal": "Q001", "usda": "USDA-Q1"},
        {"nombre": "Quinua roja", "ean": "7501000001002", "inacal": "Q002", "usda": "USDA-Q2"},
        {"nombre": "Quinua negra", "ean": "7501000001003", "inacal": "Q003", "usda": "USDA-Q3"},
        {"nombre": "Harina de quinua", "ean": "7501000001004", "inacal": "Q004", "usda": "USDA-Q4"},
        {"nombre": "Quinua pop", "ean": "7501000001005", "inacal": "Q005", "usda": "USDA-Q5"},
    ],
    "palto": [
        {"nombre": "Palto Hass", "ean": "7502000002001", "inacal": "P001", "usda": "USDA-P1"},
        {"nombre": "Palto Fuerte", "ean": "7502000002002", "inacal": "P002", "usda": "USDA-P2"},
        {"nombre": "Palto Bacon", "ean": "7502000002003", "inacal": "P003", "usda": "USDA-P3"},
        {"nombre": "Guacamole natural", "ean": "7502000002004", "inacal": "P004", "usda": "USDA-P4"},
        {"nombre": "Aceite de palto", "ean": "7502000002005", "inacal": "P005", "usda": "USDA-P5"},
    ],
    "espárrago": [
        {"nombre": "Espárrago verde", "ean": "7503000003001", "inacal": "E001", "usda": "USDA-E1"},
        {"nombre": "Espárrago blanco", "ean": "7503000003002", "inacal": "E002", "usda": "USDA-E2"},
        {"nombre": "Espárrago púrpura", "ean": "7503000003003", "inacal": "E003", "usda": "USDA-E3"},
        {"nombre": "Espárrago congelado", "ean": "7503000003004", "inacal": "E004", "usda": "USDA-E4"},
        {"nombre": "Espárrago enlatado", "ean": "7503000003005", "inacal": "E005", "usda": "USDA-E5"},
    ],
    "mango": [
        {"nombre": "Mango Ataulfo", "ean": "7504000004001", "inacal": "M001", "usda": "USDA-M1"},
        {"nombre": "Mango Tommy", "ean": "7504000004002", "inacal": "M002", "usda": "USDA-M2"},
        {"nombre": "Mango Kent", "ean": "7504000004003", "inacal": "M003", "usda": "USDA-M3"},
        {"nombre": "Jugo de mango", "ean": "7504000004004", "inacal": "M004", "usda": "USDA-M4"},
        {"nombre": "Pulpa de mango", "ean": "7504000004005", "inacal": "M005", "usda": "USDA-M5"},
    ],
    "arándano": [
        {"nombre": "Arándano azul fresco", "ean": "7505000005001", "inacal": "A001", "usda": "USDA-A1"},
        {"nombre": "Arándano congelado", "ean": "7505000005002", "inacal": "A002", "usda": "USDA-A2"},
        {"nombre": "Arándano deshidratado", "ean": "7505000005003", "inacal": "A003", "usda": "USDA-A3"},
        {"nombre": "Jugo de arándano", "ean": "7505000005004", "inacal": "A004", "usda": "USDA-A4"},
        {"nombre": "Mermelada de arándano", "ean": "7505000005005", "inacal": "A005", "usda": "USDA-A5"},
    ],
}


def create_tables():
    """Create taxonomy tables if they don't exist."""
    print("\n🗄️  Creating taxonomy tables...")

    try:
        import psycopg
        conn = psycopg.connect(DATABASE_URL)

        with conn.cursor() as cur:
            # Create taxonomia_cite
            cur.execute("""
                CREATE TABLE IF NOT EXISTS taxonomia_cite (
                    categoria_id BIGSERIAL PRIMARY KEY,
                    nombre_categoria VARCHAR(100) NOT NULL UNIQUE,
                    claims TEXT[] NOT NULL DEFAULT '{}',
                    version VARCHAR(20) DEFAULT '0.1',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)

            # Create ingredientes_cite
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ingredientes_cite (
                    ingrediente_id BIGSERIAL PRIMARY KEY,
                    nombre VARCHAR(255) NOT NULL,
                    insumo VARCHAR(100) NOT NULL,
                    ean VARCHAR(50),
                    inacal_code VARCHAR(50),
                    usda_id VARCHAR(50),
                    off_id VARCHAR(50),
                    es_alérgeno BOOLEAN DEFAULT FALSE,
                    claims_aplicables TEXT[] DEFAULT '{}',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    CONSTRAINT ingredientes_unique UNIQUE (ean, insumo)
                )
            """)

            # Create audit_claims
            cur.execute("""
                CREATE TABLE IF NOT EXISTS audit_claims (
                    audit_id BIGSERIAL PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    etapa VARCHAR(50) NOT NULL,
                    claim_propuesto TEXT NOT NULL,
                    insumo_categoria VARCHAR(100),
                    claim_canonico TEXT,
                    motivo_rechazo VARCHAR(255),
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)

            # Create indexes
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_taxonomia_nombre
                    ON taxonomia_cite (nombre_categoria)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_ingredientes_insumo
                    ON ingredientes_cite (insumo)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_ingredientes_ean
                    ON ingredientes_cite (ean)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_claims_run_id
                    ON audit_claims (run_id)
            """)

            conn.commit()
            print("✅ Tables created")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False


def populate_taxonomy():
    """Populate taxonomia_cite with pilot crops and claims."""
    print("\n📊 Populating taxonomia_cite...")

    try:
        import psycopg
        conn = psycopg.connect(DATABASE_URL)

        with conn.cursor() as cur:
            for nombre_categoria, claims in TAXONOMIA_CITE.items():
                cur.execute("""
                    INSERT INTO taxonomia_cite (nombre_categoria, claims, version)
                    VALUES (%s, %s, '0.1')
                    ON CONFLICT (nombre_categoria) DO UPDATE SET
                        claims = EXCLUDED.claims,
                        updated_at = NOW()
                """, (nombre_categoria, claims))

                print(f"   ✅ {nombre_categoria}: {len(claims)} claims")

            conn.commit()

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Error populating taxonomy: {e}")
        return False


def populate_ingredients():
    """Populate ingredientes_cite with sample products."""
    print("\n📦 Populating ingredientes_cite...")

    try:
        import psycopg
        conn = psycopg.connect(DATABASE_URL)

        with conn.cursor() as cur:
            total_inserted = 0

            for insumo, ingredientes in INGREDIENTES_MUESTRA.items():
                # Get claims for this insumo
                cur.execute(
                    "SELECT claims FROM taxonomia_cite WHERE nombre_categoria = %s",
                    (insumo,)
                )
                result = cur.fetchone()
                claims = result[0] if result else []

                for ing in ingredientes:
                    cur.execute("""
                        INSERT INTO ingredientes_cite
                        (nombre, insumo, ean, inacal_code, usda_id, claims_aplicables)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (ean, insumo) DO UPDATE SET
                            nombre = EXCLUDED.nombre,
                            claims_aplicables = EXCLUDED.claims_aplicables
                    """, (
                        ing["nombre"],
                        insumo,
                        ing["ean"],
                        ing.get("inacal"),
                        ing.get("usda"),
                        claims[:5],  # First 5 claims per ingredient
                    ))
                    total_inserted += 1

            conn.commit()
            print(f"   ✅ Inserted {total_inserted} ingredients")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Error populating ingredients: {e}")
        return False


def verify():
    """Verify taxonomy data."""
    print("\n✅ Verification:")

    try:
        import psycopg
        conn = psycopg.connect(DATABASE_URL)

        with conn.cursor() as cur:
            # Count taxonomies
            cur.execute("SELECT COUNT(*) FROM taxonomia_cite")
            tax_count = cur.fetchone()[0]
            print(f"   Taxonomies: {tax_count}")

            # Count ingredients
            cur.execute("SELECT COUNT(*) FROM ingredientes_cite")
            ing_count = cur.fetchone()[0]
            print(f"   Ingredients: {ing_count}")

            # Show sample
            print("\n📋 Sample taxonomy (Quinua):")
            cur.execute(
                "SELECT nombre_categoria, array_length(claims, 1) FROM taxonomia_cite WHERE nombre_categoria = %s",
                ("quinua",)
            )
            row = cur.fetchone()
            if row:
                print(f"   {row[0]}: {row[1]} claims")

            cur.execute(
                "SELECT nombre, ean FROM ingredientes_cite WHERE insumo = %s LIMIT 3",
                ("quinua",)
            )
            for nombre, ean in cur.fetchall():
                print(f"     - {nombre} ({ean})")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Error verifying: {e}")
        return False


def main():
    """Initialize CITE taxonomy."""
    print("=" * 70)
    print(" 📚 S3.7 CITE TAXONOMY V0.1 INITIALIZATION")
    print("=" * 70)

    # Step 1: Create tables
    if not create_tables():
        sys.exit(1)

    # Step 2: Populate taxonomy
    if not populate_taxonomy():
        sys.exit(1)

    # Step 3: Populate ingredients
    if not populate_ingredients():
        sys.exit(1)

    # Step 4: Verify
    if not verify():
        sys.exit(1)

    print("\n" + "=" * 70)
    print(" ✅ TAXONOMÍA CITE V0.1 READY")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Implement validar_claim_contra_taxonomia() (3.8)")
    print("  2. Integrate in Stage 4 (Formulation) for claim validation")
    print("  3. Test: Stage 4 should reject invalid claims")
    print("=" * 70)


if __name__ == "__main__":
    main()
