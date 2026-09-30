# marketplace-conversion

Mejoras de conversion para la tienda de **marketplace.odoo.com** (Odoo 19
Community). Repositorio de **entrega**: contiene solo lo que hay que llevar
al repositorio principal del proyecto.

| Carpeta | Que es | Donde va |
|---|---|---|
| `website_sale_conversion/` | Modulo de Odoo | Al addons-path del repo principal, junto a `vir_website` y `website_market_v1` |
| `pegasus_velocity/` | Script de sincronizacion. **No es un modulo de Odoo** | A una maquina de la red local con acceso a PEGASUS. Fuera del addons-path |

## Que hace

- **Orden "Mas vendidos"** en `/shop`, alimentado por las unidades vendidas
  segun PEGASUS -fuente de verdad de las ventas-, cruzadas por referencia
  interna. Primera opcion del selector; las 5 nativas se conservan.
- **Sidebar compacto**: listas de 250px con scroll propio, sin "Ver mas",
  area de toque de 28px.
- **Sidebar sticky** en escritorio, con scroll interno. En movil no cambia nada.
- **Megamenu de marcas mas chico**: de 6,24 a 8,09 marcas por vista.
- **Pills de subcategorias** sobre la grilla.

Todo por herencia: no se modifica ningun archivo de `website_sale`,
`vir_website`, `website_market_v1` ni del modulo de terceros de Veloxio.

## Puesta en produccion

1. Instalar `website_sale_conversion`. Depende de `website_sale` y de
   `website_market_v1`, que ya esta instalado.
2. Crear un usuario tecnico y su clave de API
   (ver `pegasus_velocity/README.md`).
3. En la maquina de la red local: instalar el script, completar `config.ini`
   -esta en `.gitignore`, nunca commitearlo- y correr con `--dry-run`.
4. Validados los numeros, programar la tarea de madrugada.
5. **Recien entonces** activar *Ajustes -> eCommerce -> "Ordenar la tienda
   por mas vendidos"*. Antes de que haya datos, esa opcion ordenaria todo
   por `id`.

Los puntos 1 a 4 son independientes: el sidebar, el sticky, el megamenu y
las pills funcionan desde la instalacion, sin depender de PEGASUS.

## Por que leer los mensajes de commit

Cada decision no obvia esta justificada ahi, con la evidencia que la
respalda: por que el campo lleva `default=0.0` -PostgreSQL ordena NULLS
FIRST en DESC-, por que el sidebar se resuelve con SCSS y no con xpath
-copias COW por sitio y un xpath previo de `vir_website` sobre el mismo
nodo-, por que se usa la API JSON-2 y no XML-RPC -deprecado en la 19-, y
por que no se usa la metrica de rotacion del reporte de PEGASUS para
ordenar una vitrina.

## Estado

Verificado sobre una copia de la base de produccion: 5.361 productos
publicados, 4.547 codigos cruzados sin un solo fallo de coincidencia.
10 tests, 0 fallos.

Falta unicamente correr la sincronizacion con datos reales de PEGASUS.
