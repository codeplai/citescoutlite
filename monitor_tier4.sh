#!/bin/bash
# Monitor de TIER 4 - Embeddings masivos
# Uso: bash monitor_tier4.sh
# O:   watch -n 10 "bash monitor_tier4.sh"

echo "================================================================================"
echo "MONITOREO TIER 4 - Embeddings masivos con bge-m3"
echo "================================================================================"
echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 1. Verificar si el log existe
if [ ! -f "datasets/2026-07/embeddings.log" ]; then
    echo "[ESTADO] Log aún no creado - TIER 4 iniciando..."
    exit 0
fi

# 2. Contar líneas del log (indicador de actividad)
LOG_LINES=$(wc -l < datasets/2026-07/embeddings.log 2>/dev/null || echo "0")
echo "[INFO] Líneas del log: $LOG_LINES"
echo ""

# 3. Verificar si completó
if grep -q "SUCCESS" datasets/2026-07/embeddings.log; then
    echo "✓ TIER 4 COMPLETADO EXITOSAMENTE"
    echo ""
    tail -5 datasets/2026-07/embeddings.log
    exit 0
fi

# 4. Verificar si hay error
if grep -q "ERROR" datasets/2026-07/embeddings.log; then
    echo "✗ ERROR DETECTADO EN TIER 4"
    echo ""
    grep "ERROR" datasets/2026-07/embeddings.log | tail -5
    exit 1
fi

# 5. Mostrar progreso actual
echo "[PROGRESO]"
if grep -q "EMBED.*%" datasets/2026-07/embeddings.log; then
    grep "EMBED.*%" datasets/2026-07/embeddings.log | tail -3
else
    tail -10 datasets/2026-07/embeddings.log | grep -E "\[LOAD\]|\[MODEL\]|\[EMBED\]" || tail -5 datasets/2026-07/embeddings.log
fi

echo ""
echo "================================================================================"
echo "Próxima actualización: espera 30-60 segundos y vuelve a ejecutar"
echo "================================================================================"
