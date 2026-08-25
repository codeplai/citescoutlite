"""
Envio de correo por SMTP. Se usa para el parte horario del pipeline.

Lee la configuracion del entorno y **nunca la imprime**: si falta algo, dice
que falta y cual, no lo que vale. La contrasena no aparece en ningun log ni en
ningun mensaje de error, que es la razon de que `configuracion()` devuelva la
lista de claves ausentes en vez de un volcado.

Variables (en `.env`):

    SMTP_HOST       por defecto smtp.gmail.com
    SMTP_PUERTO     por defecto 587 (STARTTLS)
    SMTP_USUARIO    la cuenta que envia
    SMTP_PASSWORD   contrasena de aplicacion de Google, NO la del correo
    SMTP_DESTINO    a quien va el parte

Con Gmail hace falta 2FA activo en la cuenta que envia y una contrasena de
aplicacion generada en <https://myaccount.google.com/apppasswords>. La
contrasena normal no sirve: Google la rechaza para SMTP desde 2022.
"""
import os
import smtplib
import ssl
from email.message import EmailMessage

CLAVES_OBLIGATORIAS = ("SMTP_USUARIO", "SMTP_PASSWORD", "SMTP_DESTINO")


def configuracion() -> tuple[dict, list[str]]:
    """(configuracion, claves que faltan). Nunca devuelve el valor secreto."""
    cfg = {
        "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "puerto": int(os.getenv("SMTP_PUERTO", "587")),
        "usuario": os.getenv("SMTP_USUARIO", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "destino": os.getenv("SMTP_DESTINO", ""),
    }
    faltan = [k for k in CLAVES_OBLIGATORIAS if not os.getenv(k)]
    return cfg, faltan


def enviar(asunto: str, cuerpo: str) -> tuple[bool, str]:
    """Envia el correo. Devuelve (exito, explicacion).

    No lanza: el pipeline no debe morir porque el servidor de correo tenga un
    mal dia. Un parte perdido es una molestia; perder seis horas de descarga
    por un fallo de SMTP seria absurdo.
    """
    cfg, faltan = configuracion()
    if faltan:
        return False, f"faltan variables en .env: {', '.join(faltan)}"

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = cfg["usuario"]
    mensaje["To"] = cfg["destino"]
    mensaje.set_content(cuerpo)

    try:
        contexto = ssl.create_default_context()
        with smtplib.SMTP(cfg["host"], cfg["puerto"], timeout=30) as s:
            s.starttls(context=contexto)
            s.login(cfg["usuario"], cfg["password"])
            s.send_message(mensaje)
        return True, f"enviado a {cfg['destino']}"
    except smtplib.SMTPAuthenticationError:
        return False, ("SMTP rechazo las credenciales. Con Gmail hace falta 2FA "
                       "y una contrasena de APLICACION, no la del correo.")
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
