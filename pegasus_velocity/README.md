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

## Estado de la verificacion contra PEGASUS

### 1. Notas de credito: VERIFICADO, no hace falta corregir nada

Las lineas de nota de credito traen **`unidades` negativas**, no solo el
importe. `SUM(unidades)` las netea solo. Muestra del 2026-09-30:

```
TIPO_DOCUMEN  CODIGO   unidades   TOT_PRECIO
33            248835   -1.00000   -668182.00000
30            234850   -3.00000    -60000.00000
30            129090   -6.00000   -272727.00000
```

El whitelist de `TIPO_DOCUMEN` aplicado tambien a las unidades -la
correccion respecto de RPweb- es lo correcto y se conserva tal cual.

### 2. Devoluciones: VERIFICADO, tampoco hace falta corregir nada

Los 1.463 documentos con `nro_devolucion` no nulo que no son nota de credito
se desglosan en 7.214 lineas de detalle, y **ninguna tiene unidades
positivas**:

```
TIPO_DOCUMEN  lineas  negativas  positivas  unidades_netas  whitelist
482             7110       7110          0      -15817.100  CUENTA
480               74         74          0         -87.000  CUENTA
17                30         30          0         -64.000  IGNORADO
```

Los tipos 480 y 482 estan dentro del whitelist y vienen en negativo: ya
restan. El tipo 17 queda afuera del whitelist, o sea que sus -64 unidades no
se restan; contra las ~15.900 que si se netean es ruido, y si la venta
original tambien es tipo 17 queda excluida igual y no hay sesgo. No se
corrige.

**Conclusion: `SUM(unidades)` con el whitelist es correcto tal cual. No hay
devoluciones sumando en positivo.**
