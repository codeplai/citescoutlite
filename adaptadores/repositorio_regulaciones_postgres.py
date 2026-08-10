"""
Implementación PostgreSQL del repositorio de regulaciones.

Guarda y busca regulaciones en las tablas creadas en 006_create_regulaciones_s4.sql
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_batch

from puertos.repositorio_regulaciones import RepositorioRegulaciones

logger = logging.getLogger(__name__)


class RepositorioRegulacionesPostgres(RepositorioRegulaciones):
    """
    Implementación PostgreSQL para almacenamiento de regulaciones.

    Usa psycopg2 para conexión directa (ya disponible en el proyecto via Supabase).
    """

    def __init__(self, database_url: str):
        """
        Args:
            database_url: PostgreSQL connection string
                (e.g., postgresql://user:pass@host/db)
        """
        self.database_url = database_url
        self.logger = logger

    async def guardar_ecfr(self, regulaciones: List[Dict[str, Any]]) -> int:
        """Guardar regulaciones FDA en ecfr_regulations."""
        if not regulaciones:
            return 0

        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor()

            sql = """
                INSERT INTO ecfr_regulations
                (title, part, section, subsection, texto_completo, url_oficial,
                 fecha_efectiva, content_hash)
                VALUES (%(title)s, %(part)s, %(section)s, %(subsection)s,
                        %(texto_completo)s, %(url_oficial)s, %(fecha_efectiva)s,
                        %(content_hash)s)
                ON CONFLICT (title, part, section, subsection) DO UPDATE
                SET texto_completo = EXCLUDED.texto_completo,
                    content_hash = EXCLUDED.content_hash,
                    last_update = NOW()
            """

            execute_batch(cur, sql, regulaciones, page_size=100)
            conn.commit()

            inserted = len(regulaciones)
            self.logger.info(f"✅ Guardados {inserted} registros eCFR")
            return inserted

        except Exception as e:
            self.logger.error(f"❌ Error guardando eCFR: {e}")
            conn.rollback()
            raise

        finally:
            cur.close()
            conn.close()

    async def guardar_efsa(self, regulaciones: List[Dict[str, Any]]) -> int:
        """Guardar regulaciones EFSA en efsa_regulations."""
        if not regulaciones:
            return 0

        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor()

            sql = """
                INSERT INTO efsa_regulations
                (e_number, ingredient_name, authorized_uses, max_levels_pct,
                 url_oficial, content_hash)
                VALUES (%(e_number)s, %(ingredient_name)s, %(authorized_uses)s,
                        %(max_levels_pct)s, %(url_oficial)s, %(content_hash)s)
                ON CONFLICT (e_number) DO UPDATE
                SET ingredient_name = EXCLUDED.ingredient_name,
                    authorized_uses = EXCLUDED.authorized_uses,
                    max_levels_pct = EXCLUDED.max_levels_pct,
                    content_hash = EXCLUDED.content_hash,
                    last_update = NOW()
            """

            execute_batch(cur, sql, regulaciones, page_size=100)
            conn.commit()

            inserted = len(regulaciones)
            self.logger.info(f"✅ Guardados {inserted} registros EFSA")
            return inserted

        except Exception as e:
            self.logger.error(f"❌ Error guardando EFSA: {e}")
            conn.rollback()
            raise

        finally:
            cur.close()
            conn.close()

    async def guardar_codex(self, regulaciones: List[Dict[str, Any]]) -> int:
        """Guardar estándares Codex en codex_standards."""
        if not regulaciones:
            return 0

        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor()

            sql = """
                INSERT INTO codex_standards
                (nombre_estandar, codigo_cat, version, anio_publicacion,
                 texto, url_oficial, content_hash)
                VALUES (%(nombre_estandar)s, %(codigo_cat)s, %(version)s,
                        %(anio_publicacion)s, %(texto)s, %(url_oficial)s,
                        %(content_hash)s)
                ON CONFLICT (codigo_cat) DO UPDATE
                SET nombre_estandar = EXCLUDED.nombre_estandar,
                    version = EXCLUDED.version,
                    texto = EXCLUDED.texto,
                    content_hash = EXCLUDED.content_hash,
                    last_update = NOW()
            """

            execute_batch(cur, sql, regulaciones, page_size=100)
            conn.commit()

            inserted = len(regulaciones)
            self.logger.info(f"✅ Guardados {inserted} registros Codex")
            return inserted

        except Exception as e:
            self.logger.error(f"❌ Error guardando Codex: {e}")
            conn.rollback()
            raise

        finally:
            cur.close()
            conn.close()

    async def guardar_inacal(self, regulaciones: List[Dict[str, Any]]) -> int:
        """Guardar normas INACAL en inacal_nts."""
        if not regulaciones:
            return 0

        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor()

            sql = """
                INSERT INTO inacal_nts
                (nombre_nts, codigo_nts, version, texto, url_oficial, content_hash)
                VALUES (%(nombre_nts)s, %(codigo_nts)s, %(version)s,
                        %(texto)s, %(url_oficial)s, %(content_hash)s)
                ON CONFLICT (codigo_nts) DO UPDATE
                SET nombre_nts = EXCLUDED.nombre_nts,
                    version = EXCLUDED.version,
                    texto = EXCLUDED.texto,
                    content_hash = EXCLUDED.content_hash,
                    last_update = NOW()
            """

            execute_batch(cur, sql, regulaciones, page_size=100)
            conn.commit()

            inserted = len(regulaciones)
            self.logger.info(f"✅ Guardados {inserted} registros INACAL")
            return inserted

        except Exception as e:
            self.logger.error(f"❌ Error guardando INACAL: {e}")
            conn.rollback()
            raise

        finally:
            cur.close()
            conn.close()

    async def guardar_digesa(self, regulaciones: List[Dict[str, Any]]) -> int:
        """Guardar directivas DIGESA en digesa_directivas."""
        if not regulaciones:
            return 0

        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor()

            sql = """
                INSERT INTO digesa_directivas
                (asunto, ingrediente, accion, limite, justificacion,
                 fecha_emitida, archivo_pdf_url, ocr_accuracy)
                VALUES (%(asunto)s, %(ingrediente)s, %(accion)s, %(limite)s,
                        %(justificacion)s, %(fecha_emitida)s, %(archivo_pdf_url)s,
                        %(ocr_accuracy)s)
            """

            execute_batch(cur, sql, regulaciones, page_size=100)
            conn.commit()

            inserted = len(regulaciones)
            self.logger.info(f"✅ Guardados {inserted} registros DIGESA")
            return inserted

        except Exception as e:
            self.logger.error(f"❌ Error guardando DIGESA: {e}")
            conn.rollback()
            raise

        finally:
            cur.close()
            conn.close()

    async def buscar_por_ingrediente(
        self,
        ingrediente: str,
        pais: str = 'PE'
    ) -> List[Dict[str, Any]]:
        """
        Buscar regulaciones por ingrediente según país.

        Estrategia de prioridad:
        - 'PE': INACAL → DIGESA → Codex
        - 'EU': EFSA → Codex
        - 'US': eCFR → Codex
        """
        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor()

            # Normalizar búsqueda
            ingrediente_lower = ingrediente.lower()

            citas = []

            if pais == 'PE':
                # INACAL
                cur.execute("""
                    SELECT nts_id, codigo_nts, nombre_nts, texto
                    FROM inacal_nts
                    WHERE nombre_nts ILIKE %s
                    LIMIT 5
                """, (f"%{ingrediente_lower}%",))

                for row in cur.fetchall():
                    citas.append({
                        'tipo_regulacion': 'INACAL',
                        'regulation_id': row[0],
                        'seccion_exacta': row[1],  # codigo_nts
                        'texto_cita': row[3][:200] if row[3] else "",  # primeros 200 chars
                        'url_oficial': f"https://www.inacal.gob.pe/nts/{row[1]}",
                        'version_norma': row[2]
                    })

                # DIGESA
                cur.execute("""
                    SELECT directiva_id, ingrediente, accion, limite
                    FROM digesa_directivas
                    WHERE ingrediente ILIKE %s
                    LIMIT 5
                """, (f"%{ingrediente_lower}%",))

                for row in cur.fetchall():
                    citas.append({
                        'tipo_regulacion': 'DIGESA',
                        'regulation_id': row[0],
                        'seccion_exacta': f"{row[2]}: {row[3]}" if row[3] else row[2],
                        'texto_cita': f"Acción: {row[2]}",
                        'url_oficial': "",
                        'version_norma': ""
                    })

                # Codex (fallback)
                if not citas:
                    cur.execute("""
                        SELECT standard_id, codigo_cat, nombre_estandar, texto
                        FROM codex_standards
                        WHERE nombre_estandar ILIKE %s
                        LIMIT 5
                    """, (f"%{ingrediente_lower}%",))

                    for row in cur.fetchall():
                        citas.append({
                            'tipo_regulacion': 'Codex',
                            'regulation_id': row[0],
                            'seccion_exacta': row[1],
                            'texto_cita': row[3][:200] if row[3] else "",
                            'url_oficial': f"https://www.fao.org/fao-who-codexalimentarius/standards/{row[1]}",
                            'version_norma': row[2]
                        })

            elif pais == 'EU':
                # EFSA
                cur.execute("""
                    SELECT regulation_id, e_number, ingredient_name, authorized_uses
                    FROM efsa_regulations
                    WHERE ingredient_name ILIKE %s
                    LIMIT 5
                """, (f"%{ingrediente_lower}%",))

                for row in cur.fetchall():
                    citas.append({
                        'tipo_regulacion': 'EFSA',
                        'regulation_id': row[0],
                        'seccion_exacta': row[1],  # E-number
                        'texto_cita': f"Authorized uses: {', '.join(row[3]) if row[3] else 'N/A'}",
                        'url_oficial': f"https://www.efsa.europa.eu/en/additives/{row[1]}",
                        'version_norma': ""
                    })

                # Codex (fallback)
                if not citas:
                    cur.execute("""
                        SELECT standard_id, codigo_cat, nombre_estandar, texto
                        FROM codex_standards
                        WHERE nombre_estandar ILIKE %s
                        LIMIT 5
                    """, (f"%{ingrediente_lower}%",))

                    for row in cur.fetchall():
                        citas.append({
                            'tipo_regulacion': 'Codex',
                            'regulation_id': row[0],
                            'seccion_exacta': row[1],
                            'texto_cita': row[3][:200] if row[3] else "",
                            'url_oficial': "",
                            'version_norma': ""
                        })

            elif pais == 'US':
                # eCFR
                cur.execute("""
                    SELECT regulation_id, title, part, section, texto_completo
                    FROM ecfr_regulations
                    WHERE texto_completo ILIKE %s
                    LIMIT 5
                """, (f"%{ingrediente_lower}%",))

                for row in cur.fetchall():
                    citas.append({
                        'tipo_regulacion': 'eCFR',
                        'regulation_id': row[0],
                        'seccion_exacta': f"{row[1]} CFR {row[2]}.{row[3]}",
                        'texto_cita': row[4][:200] if row[4] else "",
                        'url_oficial': f"https://www.ecfr.gov/current/title-{row[1]}/part-{row[2]}",
                        'version_norma': ""
                    })

                # Codex (fallback)
                if not citas:
                    cur.execute("""
                        SELECT standard_id, codigo_cat, nombre_estandar, texto
                        FROM codex_standards
                        WHERE nombre_estandar ILIKE %s
                        LIMIT 5
                    """, (f"%{ingrediente_lower}%",))

                    for row in cur.fetchall():
                        citas.append({
                            'tipo_regulacion': 'Codex',
                            'regulation_id': row[0],
                            'seccion_exacta': row[1],
                            'texto_cita': row[3][:200] if row[3] else "",
                            'url_oficial': "",
                            'version_norma': ""
                        })

            self.logger.info(f"✅ Encontradas {len(citas)} citas para '{ingrediente}' en {pais}")
            return citas

        except Exception as e:
            self.logger.error(f"❌ Error en buscar_por_ingrediente: {e}")
            return []

        finally:
            cur.close()
            conn.close()

    async def buscar_por_tipo(
        self,
        tipo_regulacion: str
    ) -> List[Dict[str, Any]]:
        """Buscar todas las regulaciones de un tipo."""
        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor()

            if tipo_regulacion == 'eCFR':
                cur.execute("SELECT COUNT(*) FROM ecfr_regulations")
            elif tipo_regulacion == 'EFSA':
                cur.execute("SELECT COUNT(*) FROM efsa_regulations")
            elif tipo_regulacion == 'Codex':
                cur.execute("SELECT COUNT(*) FROM codex_standards")
            elif tipo_regulacion == 'INACAL':
                cur.execute("SELECT COUNT(*) FROM inacal_nts")
            elif tipo_regulacion == 'DIGESA':
                cur.execute("SELECT COUNT(*) FROM digesa_directivas")

            count = cur.fetchone()[0]
            self.logger.info(f"✅ {count} registros de tipo {tipo_regulacion}")

            return []  # Implementar según necesidad

        except Exception as e:
            self.logger.error(f"❌ Error en buscar_por_tipo: {e}")
            return []

        finally:
            cur.close()
            conn.close()

    async def obtener_mapping(
        self,
        ingrediente: str
    ) -> Optional[Dict[str, Any]]:
        """Obtener mapping unificado para un ingrediente."""
        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor()

            cur.execute("""
                SELECT mapping_id, ingrediente_canonico, ecfr_ref, efsa_ref,
                       codex_ref, inacal_ref, digesa_ref, mapping_confidence
                FROM mapping_regulaciones
                WHERE ingrediente_canonico ILIKE %s
                LIMIT 1
            """, (f"%{ingrediente}%",))

            row = cur.fetchone()
            if not row:
                self.logger.info(f"⚠️  No se encontró mapping para '{ingrediente}'")
                return None

            return {
                'mapping_id': row[0],
                'ingrediente_canonico': row[1],
                'ecfr_ref': row[2],
                'efsa_ref': row[3],
                'codex_ref': row[4],
                'inacal_ref': row[5],
                'digesa_ref': row[6],
                'mapping_confidence': float(row[7])
            }

        except Exception as e:
            self.logger.error(f"❌ Error en obtener_mapping: {e}")
            return None

        finally:
            cur.close()
            conn.close()

    async def guardar_mapping(
        self,
        ingrediente_canonico: str,
        ecfr_ref: Optional[int] = None,
        efsa_ref: Optional[int] = None,
        codex_ref: Optional[int] = None,
        inacal_ref: Optional[int] = None,
        digesa_ref: Optional[int] = None,
        mapping_confidence: float = 1.0,
        notas: str = "",
        validated_by: str = ""
    ) -> int:
        """Guardar mapping entre regulaciones."""
        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO mapping_regulaciones
                (ingrediente_canonico, ecfr_ref, efsa_ref, codex_ref,
                 inacal_ref, digesa_ref, mapping_confidence, notas, validated_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING mapping_id
            """, (ingrediente_canonico, ecfr_ref, efsa_ref, codex_ref,
                  inacal_ref, digesa_ref, mapping_confidence, notas, validated_by))

            mapping_id = cur.fetchone()[0]
            conn.commit()

            self.logger.info(f"✅ Mapping guardado para '{ingrediente_canonico}' (ID: {mapping_id})")
            return mapping_id

        except Exception as e:
            self.logger.error(f"❌ Error guardando mapping: {e}")
            conn.rollback()
            raise

        finally:
            cur.close()
            conn.close()

    async def contar_por_fuente(self) -> Dict[str, int]:
        """Obtener cantidad de registros por fuente."""
        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor()

            counts = {}

            cur.execute("SELECT COUNT(*) FROM ecfr_regulations")
            counts['ecfr'] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM efsa_regulations")
            counts['efsa'] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM codex_standards")
            counts['codex'] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM inacal_nts")
            counts['inacal'] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM digesa_directivas")
            counts['digesa'] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM mapping_regulaciones")
            counts['mapping'] = cur.fetchone()[0]

            self.logger.info(f"📊 Corpus: {counts}")
            return counts

        except Exception as e:
            self.logger.error(f"❌ Error en contar_por_fuente: {e}")
            return {}

        finally:
            cur.close()
            conn.close()

    async def registrar_cambio(
        self,
        tipo_fuente: str,
        accion: str,
        cantidad_cambios: int,
        hash_anterior: str,
        hash_nuevo: str,
        detalles: str = ""
    ) -> None:
        """Registrar cambios en audit_regulaciones."""
        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO audit_regulaciones
                (tipo_fuente, accion, cantidad_cambios, hash_anterior, hash_nuevo, detalles)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (tipo_fuente, accion, cantidad_cambios, hash_anterior, hash_nuevo, detalles))

            conn.commit()
            self.logger.info(f"✅ Cambio registrado: {tipo_fuente} ({cantidad_cambios} items)")

        except Exception as e:
            self.logger.error(f"❌ Error registrando cambio: {e}")
            conn.rollback()
            raise

        finally:
            cur.close()
            conn.close()

    async def limpiar_corpus(self) -> None:
        """Borrar todo el corpus (cuidado: usa en desarrollo/reinicio)."""
        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor()

            cur.execute("TRUNCATE TABLE regulacion_cita CASCADE")
            cur.execute("TRUNCATE TABLE mapping_regulaciones CASCADE")
            cur.execute("TRUNCATE TABLE digesa_directivas CASCADE")
            cur.execute("TRUNCATE TABLE inacal_nts CASCADE")
            cur.execute("TRUNCATE TABLE codex_standards CASCADE")
            cur.execute("TRUNCATE TABLE efsa_regulations CASCADE")
            cur.execute("TRUNCATE TABLE ecfr_regulations CASCADE")

            conn.commit()
            self.logger.warning("⚠️  Corpus limpiado (todas las tablas truncadas)")

        except Exception as e:
            self.logger.error(f"❌ Error limpiando corpus: {e}")
            conn.rollback()
            raise

        finally:
            cur.close()
            conn.close()
