/* =============================================================================
   VELOCIDAD DE VENTA PARA LA TIENDA  -  CODIGO + UNIDADES, nada mas.
   =============================================================================
   Version reducida del reporte de velocidad. Devuelve DOS columnas porque es
   lo unico que Odoo necesita para ordenar /shop por "Mas vendidos".

   Que se saco del reporte completo y por que:

   - productos / Seccion / Sub_seccion / MARCAS / PROVEEDORES /
     proveedor_condicion: 6 JOINs que solo aportan texto descriptivo. Odoo ya
     tiene esos datos. Sacarlos aliviana la consulta sobre el ERP.
   - INNER JOIN dbo.productos: ademas de costar, DESCARTA ventas cuyo maestro
     de producto falte. Para el cruce por CODIGO no hace falta.
   - cotizaciones / COD_MONEDA / TOT_PRECIO / TOT_IMP / TOT_COSTO: son plata.
     La velocidad de la tienda se mide en unidades.
   - MOVIMIENTOS_DEPOSITOS (stock): ver la nota sobre VELOCIDAD_PCT_DIA.
   - Filtro de secciones NOT IN ('-1','12','46','48','54','58'): quien decide
     que se ve en la tienda es Odoo (is_published). Si una seccion excluida
     tuviera un producto publicado, este filtro lo mandaria al fondo por un
     motivo que no tiene que ver con sus ventas.

   Que se conservo tal cual:

   - El whitelist de TIPO_DOCUMEN, aplicado TAMBIEN a las unidades. Es la
     correccion respecto de RPweb y es correcta: las notas de credito estan
     dentro del whitelist (30, 33, 36, 451, 452, 476, 478, 484) y vienen en
     negativo, asi que restan solas.
   - No se filtran anulados: no estan en dbo.ventas (se mueven a VENTAS_ANU).

   VERIFICADO el 2026-09-30: las lineas de nota de credito traen unidades
   NEGATIVAS (no solo el importe), asi que restan solas. No hace falta
   ningun CASE correctivo sobre el signo.

   VERIFICADO el 2026-09-30: los documentos con nro_devolucion que no son
   nota de credito dan 7.214 lineas y NINGUNA tiene unidades positivas. Los
   tipos 480 y 482 estan en el whitelist y vienen en negativo: ya restan. No
   hay devoluciones sumando. El SUM(unidades) de abajo es correcto tal cual.

   SOLO LECTURA. Un SELECT, sin hints de bloqueo, sin escrituras.
   ============================================================================= */

SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;  /* no bloquea al ERP */

DECLARE @Dias INT = ?;                                   /* ventana, ej. 30 */
DECLARE @FechaFin  DATE = CONVERT(date, GETDATE());
DECLARE @FechaIni  DATE = DATEADD(DAY, -(@Dias - 1), @FechaFin);

SELECT
    b.CODIGO                                   AS CODIGO,
    SUM(b.unidades)                            AS UNIDADES
FROM dbo.ventas a
INNER JOIN dbo.ventas_det b ON a.NRO_REG = b.NRO_REG
/* SARGABLE a proposito: CONVERT(date, a.fecha) BETWEEN ... -como lo hace el
   reporte original- aplica una funcion sobre la columna y anula cualquier
   indice sobre FECHA, forzando scan. Asi el rango se resuelve por indice. */
WHERE a.FECHA >= @FechaIni
  AND a.FECHA <  DATEADD(DAY, 1, @FechaFin)
  AND a.TIPO_DOCUMEN IN (12,13,18,19,29,30,32,33,35,36,210,215,216,217,218,223,
        225,226,229,449,450,451,452,453,454,455,456,457,458,462,463,464,465,466,
        467,468,469,470,471,472,475,476,477,478,479,480,481,482,483,484)
GROUP BY b.CODIGO
HAVING SUM(b.unidades) <> 0;
