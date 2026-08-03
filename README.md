# AgroScout IA Lite MVP
Proyecto de demostración de evaluación de insumos agrícolas usando Modelos Fundacionales y arquitecturas locales.



## Cuentas de acceso

Las credenciales **no se publican en el repositorio**. Las dos cuentas de
demostración se crean con:

```bash
uv run python scripts/crear_usuarios_demo.py --generar
```

| Cuenta | Plan |
|---|---|
| `demo-gratuita@cite.gob.pe` | gratuito |
| `demo-premium@cite.gob.pe` | premium |

El script deja las contraseñas en `.env.local`, que está en `.gitignore`. Para
fijarlas tú mismo, usa `--password-gratuita` y `--password-premium` en vez de
`--generar`. Si se pierden, se vuelve a ejecutar: es idempotente y las
reemplaza.