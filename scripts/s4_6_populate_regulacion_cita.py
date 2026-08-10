"""
S4.6: Poblar tabla regulacion_cita

Purpose:
  Crear la vista unificada de todas las regulaciones.
  Función buscar_regulacion(ingrediente, pais) para Etapa 5.

Strategy:
  1. Copiar datos de ecfr, efsa, codex, inacal, digesa → regulacion_cita
  2. Crear índices full-text
  3. Crear función SQL buscar_regulacion()
  4. Test básico
"""

import asyncio
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def populate_regulacion_cita():
    """Poblar tabla regulacion_cita desde todas las fuentes."""

    from config.regulaciones_config import get_repositorio

    logger.info("=" * 60)
    logger.info("S4.6: Poblando regulacion_cita")
    logger.info("=" * 60)

    repo = get_repositorio()
    if not repo:
        logger.error("❌ No hay repositorio configurado")
        return False

    try:
        import psycopg2

        conn = psycopg2.connect(repo.database_url)
        cur = conn.cursor()

        # 1. Limpiar tabla
        logger.info("\n1️⃣ Limpiando tabla regulacion_cita...")
        cur.execute("TRUNCATE TABLE regulacion_cita CASCADE")
        conn.commit()
        logger.info("   ✅ Limpiada")

        # 2. Copiar eCFR
        logger.info("\n2️⃣ Copiando eCFR...")
        cur.execute("""
            INSERT INTO regulacion_cita
            (ingrediente, tipo_regulacion, regulation_id, seccion_exacta, texto_cita, url_oficial, version_norma)
            SELECT
                CONCAT(part, '/', section) as ingrediente,
                'eCFR' as tipo_regulacion,
                regulation_id,
                CONCAT(title, ' CFR ', part, '.', section) as seccion_exacta,
                SUBSTRING(texto_completo, 1, 300) as texto_cita,
                url_oficial,
                CAST(fecha_efectiva AS TEXT) as version_norma
            FROM ecfr_regulations
            LIMIT 3500
        """)
        conn.commit()
        ecfr_count = cur.rowcount
        logger.info(f"   ✅ {ecfr_count} eCFR insertadas")

        # 3. Copiar EFSA
        logger.info("\n3️⃣ Copiando EFSA...")
        cur.execute("""
            INSERT INTO regulacion_cita
            (ingrediente, tipo_regulacion, regulation_id, seccion_exacta, texto_cita, url_oficial, version_norma)
            SELECT
                ingredient_name as ingrediente,
                'EFSA' as tipo_regulacion,
                regulation_id,
                e_number as seccion_exacta,
                CONCAT('Authorized uses: ', ARRAY_TO_STRING(authorized_uses, ', ')) as texto_cita,
                url_oficial,
                '' as version_norma
            FROM efsa_regulations
        """)
        conn.commit()
        efsa_count = cur.rowcount
        logger.info(f"   ✅ {efsa_count} EFSA insertadas")

        # 4. Copiar Codex
        logger.info("\n4️⃣ Copiando Codex...")
        cur.execute("""
            INSERT INTO regulacion_cita
            (ingrediente, tipo_regulacion, regulation_id, seccion_exacta, texto_cita, url_oficial, version_norma)
            SELECT
                nombre_estandar as ingrediente,
                'Codex' as tipo_regulacion,
                standard_id,
                codigo_cat as seccion_exacta,
                SUBSTRING(texto, 1, 300) as texto_cita,
                url_oficial,
                CAST(anio_publicacion AS TEXT) as version_norma
            FROM codex_standards
        """)
        conn.commit()
        codex_count = cur.rowcount
        logger.info(f"   ✅ {codex_count} Codex insertadas")

        # 5. Copiar INACAL
        logger.info("\n5️⃣ Copiando INACAL...")
        cur.execute("""
            INSERT INTO regulacion_cita
            (ingrediente, tipo_regulacion, regulation_id, seccion_exacta, texto_cita, url_oficial, version_norma)
            SELECT
                nombre_nts as ingrediente,
                'INACAL' as tipo_regulacion,
                nts_id,
                codigo_nts as seccion_exacta,
                SUBSTRING(texto, 1, 300) as texto_cita,
                url_oficial,
                CAST(version AS TEXT) as version_norma
            FROM inacal_nts
        """)
        conn.commit()
        inacal_count = cur.rowcount
        logger.info(f"   ✅ {inacal_count} INACAL insertadas")

        # 6. Copiar DIGESA
        logger.info("\n6️⃣ Copiando DIGESA...")
        cur.execute("""
            INSERT INTO regulacion_cita
            (ingrediente, tipo_regulacion, regulation_id, seccion_exacta, texto_cita, url_oficial, version_norma)
            SELECT
                ingrediente as ingrediente,
                'DIGESA' as tipo_regulacion,
                directiva_id,
                accion as seccion_exacta,
                CONCAT(asunto, '. ', justificacion) as texto_cita,
                archivo_pdf_url,
                CAST(fecha_emitida AS TEXT) as version_norma
            FROM digesa_directivas
        """)
        conn.commit()
        digesa_count = cur.rowcount
        logger.info(f"   ✅ {digesa_count} DIGESA insertadas")

        # 7. Validar totales
        logger.info("\n7️⃣ Validando totales...")
        cur.execute("SELECT COUNT(*) FROM regulacion_cita")
        total_citas = cur.fetchone()[0]
        logger.info(f"   ✅ Total en regulacion_cita: {total_citas}")

        # 8. Crear índices
        logger.info("\n8️⃣ Creando índices...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_cita_ingrediente_tipo
            ON regulacion_cita (ingrediente, tipo_regulacion)
        """)
        cur.execute("""
            REFRESH MATERIALIZED VIEW IF EXISTS regulacion_cita_fts
        """)
        conn.commit()
        logger.info("   ✅ Índices creados")

        # 9. Crear función SQL buscar_regulacion
        logger.info("\n9️⃣ Creando función SQL buscar_regulacion()...")
        cur.execute("""
            CREATE OR REPLACE FUNCTION buscar_regulacion(
                p_ingrediente TEXT,
                p_pais TEXT DEFAULT 'PE'
            )
            RETURNS TABLE (
                cita_id BIGINT,
                ingrediente VARCHAR,
                tipo_regulacion VARCHAR,
                seccion_exacta VARCHAR,
                texto_cita TEXT,
                url_oficial VARCHAR,
                version_norma VARCHAR
            ) AS $$
            BEGIN
                IF p_pais = 'PE' THEN
                    -- Prioridad: INACAL → DIGESA → Codex
                    RETURN QUERY
                    SELECT rc.cita_id, rc.ingrediente, rc.tipo_regulacion,
                           rc.seccion_exacta, rc.texto_cita, rc.url_oficial, rc.version_norma
                    FROM regulacion_cita rc
                    WHERE rc.ingrediente ILIKE '%' || p_ingrediente || '%'
                    ORDER BY
                        CASE rc.tipo_regulacion
                            WHEN 'INACAL' THEN 1
                            WHEN 'DIGESA' THEN 2
                            WHEN 'Codex' THEN 3
                            ELSE 4
                        END
                    LIMIT 10;

                ELSIF p_pais = 'EU' THEN
                    -- Prioridad: EFSA → Codex
                    RETURN QUERY
                    SELECT rc.cita_id, rc.ingrediente, rc.tipo_regulacion,
                           rc.seccion_exacta, rc.texto_cita, rc.url_oficial, rc.version_norma
                    FROM regulacion_cita rc
                    WHERE rc.ingrediente ILIKE '%' || p_ingrediente || '%'
                    ORDER BY
                        CASE rc.tipo_regulacion
                            WHEN 'EFSA' THEN 1
                            WHEN 'Codex' THEN 2
                            ELSE 3
                        END
                    LIMIT 10;

                ELSIF p_pais = 'US' THEN
                    -- Prioridad: eCFR → Codex
                    RETURN QUERY
                    SELECT rc.cita_id, rc.ingrediente, rc.tipo_regulacion,
                           rc.seccion_exacta, rc.texto_cita, rc.url_oficial, rc.version_norma
                    FROM regulacion_cita rc
                    WHERE rc.ingrediente ILIKE '%' || p_ingrediente || '%'
                    ORDER BY
                        CASE rc.tipo_regulacion
                            WHEN 'eCFR' THEN 1
                            WHEN 'Codex' THEN 2
                            ELSE 3
                        END
                    LIMIT 10;
                ELSE
                    -- Fallback: todas
                    RETURN QUERY
                    SELECT rc.cita_id, rc.ingrediente, rc.tipo_regulacion,
                           rc.seccion_exacta, rc.texto_cita, rc.url_oficial, rc.version_norma
                    FROM regulacion_cita rc
                    WHERE rc.ingrediente ILIKE '%' || p_ingrediente || '%'
                    LIMIT 10;
                END IF;
            END;
            $$ LANGUAGE plpgsql;
        """)
        conn.commit()
        logger.info("   ✅ Función SQL buscar_regulacion() creada")

        # 10. Test básico
        logger.info("\n🔟 Test básico de búsqueda...")
        cur.execute("SELECT * FROM buscar_regulacion('quinua', 'PE')")
        results = cur.fetchall()
        logger.info(f"   ✅ Búsqueda 'quinua' en PE retornó {len(results)} resultados")

        cur.execute("SELECT * FROM buscar_regulacion('sodium', 'US')")
        results = cur.fetchall()
        logger.info(f"   ✅ Búsqueda 'sodium' en US retornó {len(results)} resultados")

        cur.execute("SELECT * FROM buscar_regulacion('curcumin', 'EU')")
        results = cur.fetchall()
        logger.info(f"   ✅ Búsqueda 'curcumin' en EU retornó {len(results)} resultados")

        logger.info("\n" + "=" * 60)
        logger.info("✅ S4.6 COMPLETADO")
        logger.info("=" * 60)
        logger.info(f"\nResumen:")
        logger.info(f"  eCFR   : {ecfr_count:6} citas")
        logger.info(f"  EFSA   : {efsa_count:6} citas")
        logger.info(f"  Codex  : {codex_count:6} citas")
        logger.info(f"  INACAL : {inacal_count:6} citas")
        logger.info(f"  DIGESA : {digesa_count:6} citas")
        logger.info(f"  ──────────────────")
        logger.info(f"  TOTAL  : {total_citas:6} citas")
        logger.info(f"\nFunción buscar_regulacion(ingrediente, pais) ✅ LISTA PARA ETAPA 5")

        return True

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return False

    finally:
        cur.close()
        conn.close()


async def main():
    try:
        success = await populate_regulacion_cita()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
