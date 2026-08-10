"""
S3.8 Anti-corruption layer: Validate LLM-generated claims against CITE taxonomy.

Fuzzy matches proposed claims against known claims with >= 80% similarity.
Rejects claims that don't match and logs to audit_claims table.

Used in Stage 4 (Formulation) to prevent claim hallucinations.
"""

import logging
import psycopg
from typing import Optional, Tuple, List
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class ValidadorClaims:
    """Validate claims against CITE taxonomy with fuzzy matching."""

    def __init__(self, db_url: str, similitud_minima: float = 0.80):
        """
        Initialize validator.

        Args:
            db_url: PostgreSQL connection URL
            similitud_minima: Minimum similarity ratio for fuzzy match (0.0-1.0)
        """
        self.db_url = db_url
        self.similitud_minima = similitud_minima
        self._cache_taxonomia = {}

    def _cargar_taxonomia(self) -> dict:
        """Load taxonomy into cache (categoría → list of claims)."""
        if self._cache_taxonomia:
            return self._cache_taxonomia

        try:
            conn = psycopg.connect(self.db_url)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT nombre_categoria, claims
                    FROM taxonomia_cite
                    ORDER BY nombre_categoria
                """)
                for nombre_categoria, claims_array in cur.fetchall():
                    self._cache_taxonomia[nombre_categoria] = claims_array or []
            conn.close()
            logger.info(f"✅ Loaded {len(self._cache_taxonomia)} categories from taxonomy")
        except Exception as e:
            logger.error(f"❌ Error loading taxonomy: {e}")

        return self._cache_taxonomia

    def _similitud(self, s1: str, s2: str) -> float:
        """Calculate similarity ratio between two strings (0.0-1.0)."""
        s1_lower = s1.lower().strip()
        s2_lower = s2.lower().strip()
        return SequenceMatcher(None, s1_lower, s2_lower).ratio()

    def buscar_claim_canonico(
        self,
        claim_propuesto: str,
        categoria: str
    ) -> Tuple[Optional[str], float]:
        """
        Find best matching canonical claim for a proposed claim.

        Args:
            claim_propuesto: Claim from LLM (e.g., "alto en proteína")
            categoria: Insumo category (e.g., "quinua")

        Returns:
            (canonical_claim, similitud) or (None, 0.0) if no match >= similitud_minima
        """
        taxonomia = self._cargar_taxonomia()

        if categoria not in taxonomia:
            logger.warning(f"⚠️  Categoría no en taxonomía: {categoria}")
            return None, 0.0

        claims_canonicos = taxonomia[categoria]
        if not claims_canonicos:
            logger.warning(f"⚠️  Categoría sin claims: {categoria}")
            return None, 0.0

        # Find best match
        best_match = None
        best_similitud = 0.0

        for claim_canonico in claims_canonicos:
            sim = self._similitud(claim_propuesto, claim_canonico)
            if sim > best_similitud:
                best_similitud = sim
                best_match = claim_canonico

        # Return only if meets minimum threshold
        if best_similitud >= self.similitud_minima:
            return best_match, best_similitud

        return None, best_similitud

    def validar_claim(
        self,
        claim_propuesto: str,
        categoria: str,
        run_id: str,
        etapa: str = "4_formulacion"
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a single claim and record audit if rejected.

        Args:
            claim_propuesto: LLM-generated claim
            categoria: Insumo category
            run_id: Execution ID (for audit)
            etapa: Stage name (for audit)

        Returns:
            (is_valid, canonical_claim_or_error)
            - If valid: (True, canonical_claim)
            - If invalid: (False, rejection_reason)
        """
        claim_canonico, similitud = self.buscar_claim_canonico(claim_propuesto, categoria)

        if claim_canonico is not None:
            # Valid match found
            logger.info(
                f"✅ Claim '{claim_propuesto}' → '{claim_canonico}' "
                f"(similitud: {similitud:.1%})"
            )
            return True, claim_canonico

        # Rejected - record in audit
        if similitud > 0:
            motivo = f"Similitud insuficiente ({similitud:.1%} < {self.similitud_minima:.1%})"
        else:
            motivo = f"Claim no en taxonomía (similitud: {similitud:.1%})"

        logger.warning(f"❌ Claim rechazado: {claim_propuesto} ({motivo})")

        # Log to audit_claims
        try:
            self._registrar_rechazo(
                run_id=run_id,
                etapa=etapa,
                claim_propuesto=claim_propuesto,
                insumo_categoria=categoria,
                motivo_rechazo=motivo
            )
        except Exception as e:
            logger.error(f"⚠️  Error recording audit: {e}")

        return False, motivo

    def validar_claims_lote(
        self,
        claims_propuestos: List[str],
        categoria: str,
        run_id: str,
        etapa: str = "4_formulacion"
    ) -> Tuple[List[str], List[Tuple[str, str]]]:
        """
        Validate multiple claims and return separate lists.

        Args:
            claims_propuestos: List of LLM claims
            categoria: Insumo category
            run_id: Execution ID
            etapa: Stage name

        Returns:
            (valid_claims, rejected_claims)
            - valid_claims: List of canonical claims
            - rejected_claims: List of (original_claim, reason) tuples
        """
        valid_claims = []
        rejected_claims = []

        for claim in claims_propuestos:
            is_valid, result = self.validar_claim(claim, categoria, run_id, etapa)
            if is_valid:
                valid_claims.append(result)
            else:
                rejected_claims.append((claim, result))

        return valid_claims, rejected_claims

    def _registrar_rechazo(
        self,
        run_id: str,
        etapa: str,
        claim_propuesto: str,
        insumo_categoria: str,
        motivo_rechazo: str,
        claim_canonico: Optional[str] = None
    ) -> bool:
        """Record rejected claim in audit_claims table."""
        try:
            conn = psycopg.connect(self.db_url)
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO audit_claims
                    (run_id, etapa, claim_propuesto, insumo_categoria, claim_canonico, motivo_rechazo)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    run_id,
                    etapa,
                    claim_propuesto,
                    insumo_categoria,
                    claim_canonico,
                    motivo_rechazo
                ))
                conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ Error recording rejection: {e}")
            return False

    def obtener_auditoría(self, run_id: str) -> List[dict]:
        """Get all rejected claims for a run."""
        try:
            conn = psycopg.connect(self.db_url)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT audit_id, etapa, claim_propuesto, claim_canonico,
                           motivo_rechazo, timestamp
                    FROM audit_claims
                    WHERE run_id = %s
                    ORDER BY timestamp DESC
                """, (run_id,))

                return [
                    {
                        "audit_id": row[0],
                        "etapa": row[1],
                        "claim_propuesto": row[2],
                        "claim_canonico": row[3],
                        "motivo_rechazo": row[4],
                        "timestamp": row[5].isoformat() if row[5] else None,
                    }
                    for row in cur.fetchall()
                ]
        except Exception as e:
            logger.error(f"❌ Error fetching audit: {e}")
            return []
        finally:
            conn.close()

    def limpiar_cache(self):
        """Clear taxonomy cache (useful for testing)."""
        self._cache_taxonomia = {}
        logger.info("🔄 Taxonomy cache cleared")


# Singleton instance
_validador_global: Optional[ValidadorClaims] = None


def get_validador(db_url: str, similitud_minima: float = 0.80) -> ValidadorClaims:
    """Get or create global ValidadorClaims instance."""
    global _validador_global
    if _validador_global is None:
        _validador_global = ValidadorClaims(db_url, similitud_minima)
    return _validador_global


async def validar_claims_stage4(
    claims_propuestos: List[str],
    categoria: str,
    run_id: str,
    db_url: str
) -> Tuple[List[str], List[Tuple[str, str]]]:
    """
    Async wrapper for Stage 4 (Formulation) integration.

    Returns valid claims and logs rejected ones.
    """
    validador = get_validador(db_url)
    return validador.validar_claims_lote(claims_propuestos, categoria, run_id, "4_formulacion")
