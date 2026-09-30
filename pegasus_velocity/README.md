# pegasus_velocity

Lleva la cantidad vendida por producto desde **PEGASUS** (fuente de verdad de
las ventas) hasta el campo `sales_velocity` de Odoo, que es el que ordena
`/shop` por "Mas vendidos".

Esta carpeta **no es un modulo de Odoo**: no tiene `__manifest__.py`, asi que
aunque quede dentro del `--addons-path` Odoo la ignora.

```
PEGASUS (SQL Server, LAN)  --SELECT-->  sync_velocity.py  --HTTPS-->  Odoo
```

La conexion a Odoo es **saliente desde la red local**. No hay que abrir
ningun puerto de PEGASUS ni exponer el ERP.

## Por que asi y no de otra forma

Se descartaron dos alternativas:

- **Odoo.sh consultando PEGASUS directo.** PEGASUS esta en la red local y
  Odoo.sh es saliente-a-internet; habria que exponer SQL Server o montar una
  VPN. Ademas los drivers: `pymssql` necesita FreeTDS y `pyodbc` el ODBC
  Driver de Microsoft — librerias del sistema, y en Odoo.sh no hay `apt`.
- **Export CSV/Excel importado a mano.** Sin idempotencia ni garantia de
  frescura, y un export parcial escribiria ceros masivos.

`python-tds` es Python puro: se instala con `pip` y listo.

## Instalacion

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy config.example.ini config.ini   # completar; esta en .gitignore
```

En Odoo, una sola vez:

1. Crear un **usuario tecnico** (ej. `pegasus-sync`), tipo *Usuario interno*.
2. Darle permiso de escritura sobre `product.template`.
3. Con ese usuario: *Preferencias -> Seguridad de la cuenta -> Nueva clave de
   API*. Copiar la clave al `config.ini`.
4. Instalar `website_sale_conversion` y activar, en *Ajustes -> eCommerce*,
   **"Ordenar la tienda por mas vendidos"** — recien cuando haya datos.

> **Limite honesto sobre los permisos.** Odoo no restringe la escritura a
> campos sueltos para un usuario normal sin recurrir a grupos por campo. El
> usuario tecnico puede, en teoria, escribir otros campos de
> `product.template`. La garantia real es que el script **nunca llama
> `write`**: llama al unico metodo `apply_pegasus_velocity`, que solo toca
> `sales_velocity`, `sales_velocity_date` y `sales_velocity_matched`.

## Uso

```powershell
python sync_velocity.py --config config.ini --dry-run   # probar sin escribir
python sync_velocity.py --config config.ini             # sincronizar
python sync_velocity.py --config config.ini --days 60   # otra ventana
```

Programar una vez por dia **en horario de baja carga** (madrugada), con el
Programador de tareas de Windows o `cron`.

## Que hace exactamente

1. `velocidad_unidades.sql` agrega `SUM(unidades)` por `CODIGO` en la ventana
   pedida, aplicando el whitelist de `TIPO_DOCUMEN`. Solo `SELECT`, con
   `READ UNCOMMITTED` para no bloquear al ERP.
2. Manda las filas a Odoo por `POST /json/2/product.template/apply_pegasus_velocity`
   con la API key como Bearer token. Es la API externa vigente de la v19:
   `/xmlrpc` y `/jsonrpc` estan deprecados y se remueven en la 22
   (`odoo/addons/rpc/controllers/__init__.py`).
3. Odoo cruza `CODIGO` contra `product.product.default_code`, suma a nivel
   plantilla y escribe los tres campos.
4. El reporte de no coincidentes —en las dos direcciones— queda en
   `reportes/velocidad_<fecha>.json`.

## Reversion y fallos

| Situacion | Que pasa |
|---|---|
| PEGASUS caido o lento | El script sale antes de tocar Odoo. **Se conserva el valor anterior.** |
| Extraccion vacia | Odoo levanta `UserError`. No se escribe nada. |
| Extraccion con menos del 50% de las filas de la corrida anterior | Odoo la rechaza por sospecha de extraccion parcial. No se escribe nada. |
| Odoo caido | El script loguea el error y sale. PEGASUS no se modifica nunca (solo se lee). |
| Volver atras del todo | Desactivar el toggle en *Ajustes -> eCommerce*: la tienda vuelve a "Destacado" al instante, sin borrar datos. |

Se guarda la fecha de la ultima sincronizacion exitosa en
`ir.config_parameter`, clave `website_sale_conversion.velocity_last_sync`.

## Dos cosas sin verificar

No tengo acceso a PEGASUS, asi que estas dos quedan pendientes de una
comprobacion tuya. Las dos afectan el signo de las unidades.

### 1. ¿Las notas de credito tienen `unidades` negativas?

El reporte original verifica que el 100% de sus lineas tiene **importe**
negativo. Importe, no unidades. Si el importe viene negativo pero las
unidades positivas, `SUM(unidades)` **suma** las devoluciones en vez de
restarlas, y los productos mas devueltos suben en el ranking.

```sql
SELECT TOP 20 a.TIPO_DOCUMEN, b.CODIGO, b.unidades, b.TOT_PRECIO
FROM dbo.ventas a
INNER JOIN dbo.ventas_det b ON a.NRO_REG = b.NRO_REG
WHERE a.TIPO_DOCUMEN IN (30,33,36,451,452,476,478,484)
ORDER BY a.FECHA DESC;
```

Si `unidades` sale positiva, hay que corregir el SQL asi:

```sql
SUM(CASE WHEN a.TIPO_DOCUMEN IN (30,33,36,451,452,476,478,484)
         THEN -ABS(b.unidades) ELSE b.unidades END)
```

### 2. ¿Las devoluciones de `ventas_devoluciones` ya estan como nota de credito?

`dbo.ventas` tiene la columna `nro_devolucion` y existe una tabla
`ventas_devoluciones` que este query no toca. Si una devolucion se registra
**solo** ahi y no genera nota de credito en `dbo.ventas`, las unidades quedan
sobrestimadas.

```sql
SELECT COUNT(*) AS devoluciones_sin_nota_de_credito
FROM dbo.ventas
WHERE nro_devolucion IS NOT NULL
  AND TIPO_DOCUMEN NOT IN (30,33,36,451,452,476,478,484);
```

Si da mayor que cero, hay que netear `ventas_devoluciones` aparte.
