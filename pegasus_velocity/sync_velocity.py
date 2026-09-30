#!/usr/bin/env python3
"""Lleva la velocidad de venta de PEGASUS a Odoo.

Corre en un equipo de la RED LOCAL (Programador de tareas de Windows o cron).
La conexion hacia Odoo es SALIENTE: no hay que abrir ningun puerto de PEGASUS,
ni exponer el ERP, ni montar una VPN.

    PEGASUS (SQL Server, LAN)  --SELECT-->  este script  --HTTPS-->  Odoo

Todo o nada: si la extraccion falla o viene corta, Odoo no toca ningun valor
y el dato de la corrida anterior sobrevive. Nunca se pone el catalogo en 0
por un fallo de la fuente.

Uso:
    python sync_velocity.py --config config.ini [--days 30] [--dry-run]
"""
import argparse
import configparser
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime

_log = logging.getLogger("pegasus_velocity")

SQL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "velocidad_unidades.sql")


def extract(cfg, days):
    """Trae [(CODIGO, UNIDADES), ...] de PEGASUS. Solo SELECT."""
    import pytds

    with open(SQL_FILE, encoding="utf-8") as fh:
        sql = fh.read()

    _log.info("Conectando a PEGASUS %s/%s...", cfg["host"], cfg["database"])
    conn = pytds.connect(
        server=cfg["host"], port=int(cfg.get("port", 1433)),
        database=cfg["database"], user=cfg["user"], password=cfg["password"],
        login_timeout=30, timeout=600, autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (days,))
            rows = [[r[0], float(r[1] or 0)] for r in cur.fetchall()]
    finally:
        conn.close()
    _log.info("PEGASUS devolvio %s codigos con movimiento.", len(rows))
    return rows


def push(cfg, rows, days):
    """Manda las filas a Odoo por la API JSON-2 de la v19.

    POST /json/2/<model>/<method> con auth='bearer'
    (odoo/addons/rpc/controllers/json2.py). /xmlrpc y /jsonrpc estan
    deprecados en la 19 y se remueven en la 22.
    """
    url = "%s/json/2/product.template/apply_pegasus_velocity" % cfg["url"].rstrip("/")
    payload = json.dumps({"rows": rows, "window_days": days}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer %s" % cfg["api_key"],
            "X-Odoo-Database": cfg["database"],
        },
    )
    _log.info("Enviando %s filas a %s...", len(rows), cfg["url"])
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read().decode("utf-8"))


def write_report(report, report_dir):
    """Deja el reporte de no coincidentes en disco, como pide el brief."""
    os.makedirs(report_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(report_dir, "velocidad_%s.json" % stamp)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    _log.info("Reporte: %s", path)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.ini")
    parser.add_argument("--days", type=int, default=None,
                        help="Ventana en dias (default: la del config).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Extrae de PEGASUS y muestra el resumen, "
                             "sin escribir nada en Odoo.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if not os.path.exists(args.config):
        _log.error("No existe %s. Copia config.example.ini y completalo.",
                   args.config)
        return 2

    parser_ini = configparser.ConfigParser()
    parser_ini.read(args.config, encoding="utf-8")
    pegasus = parser_ini["pegasus"]
    odoo = parser_ini["odoo"]
    sync = parser_ini["sync"] if parser_ini.has_section("sync") else {}
    days = args.days or int(sync.get("window_days", 30))

    # --- Extraccion -------------------------------------------------------
    # Si PEGASUS falla, se sale ANTES de tocar Odoo: el valor anterior queda.
    try:
        rows = extract(pegasus, days)
    except Exception:
        _log.exception("Fallo la extraccion de PEGASUS. "
                       "Odoo NO fue modificado; el dato anterior se conserva.")
        return 1

    if not rows:
        _log.error("PEGASUS no devolvio filas. Odoo NO fue modificado.")
        return 1

    total = sum(r[1] for r in rows)
    _log.info("Ventana de %s dias: %s codigos, %s unidades netas.",
              days, len(rows), int(total))

    if args.dry_run:
        for code, units in sorted(rows, key=lambda r: -r[1])[:15]:
            _log.info("  %-10s %10.2f", code, units)
        _log.info("Dry run: no se escribio nada en Odoo.")
        return 0

    # --- Envio ------------------------------------------------------------
    # El corte de cordura y el todo-o-nada viven del lado de Odoo, en
    # product.template.apply_pegasus_velocity.
    try:
        report = push(odoo, rows, days)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:1000]
        _log.error("Odoo rechazo la carga (HTTP %s): %s", exc.code, body)
        _log.error("Ningun valor fue modificado.")
        return 1
    except Exception:
        _log.exception("Fallo el envio a Odoo. Ningun valor fue modificado.")
        return 1

    _log.info("OK: %s codigos cruzados de %s, %s plantillas actualizadas.",
              report.get("codes_matched"), report.get("codes_received"),
              report.get("templates_updated"))
    if report.get("unmatched_pegasus_total"):
        _log.warning("%s codigos con ventas en PEGASUS sin producto en Odoo.",
                     report["unmatched_pegasus_total"])
    if report.get("unmatched_odoo_total"):
        _log.warning("%s productos publicados sin ventas en la ventana.",
                     report["unmatched_odoo_total"])

    write_report(report, sync.get("report_dir", "./reportes"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
