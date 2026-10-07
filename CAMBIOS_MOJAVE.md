# Rediseño visual Mojave — Equi-Parts S&S

Este paquete conserva la lógica de Flask, rutas, formularios y base de datos del proyecto. Los cambios están concentrados en la presentación.

## Dirección visual

- Interfaz clara inspirada en macOS Mojave / Finder.
- Sidebar gris translúcido con selección azul.
- Tipografía basada en la pila de fuentes del sistema (`-apple-system`, Segoe UI, Roboto, etc.).
- Tarjetas blancas con bordes suaves y sombras discretas.
- Tablas de alto contraste, encabezados claros y filas más respiradas.
- Formularios blancos con borde visible y foco azul.
- Botones simplificados: azul para acción principal, gris para secundaria y rojo para acción destructiva.
- Estados de inventario diferenciados con pastillas discretas: disponible, stock bajo y sin stock.
- Modales, badges, alertas y reportes armonizados con la misma estética.
- Login renovado manteniendo la imagen industrial original.
- Auditoría integrada al mismo sidebar del resto de la aplicación.
- Ajustes responsive para tablet y móvil.

## Archivos principales modificados

- `app/static/css/mojave-theme.css` — nuevo tema global.
- `app/static/css/navbar.css` — sidebar estilo macOS/Finder.
- `app/static/css/login.css` — pantalla de acceso.
- `app/static/css/inventario.css` — estilos específicos de inventario y estados.
- `app/static/css/usuarios.css` — badges de roles.
- `app/plantillas/includes/navbar.html` — nueva estructura del sidebar.
- Plantillas HTML en `app/plantillas/` — inclusión del tema y normalización de colores heredados.

## Personalización rápida

Los colores principales están definidos como variables al inicio de:

`app/static/css/mojave-theme.css`

La variable principal de acento es:

```css
--mac-blue: #007aff;
```

Cambiarla permite adaptar el color de acción de toda la interfaz sin editar cada pantalla.

## Nota técnica

El proyecto contiene configuración sensible escrita directamente en archivos Python. No se modificó porque este trabajo se limitó al rediseño visual, pero para un despliegue real conviene mover credenciales de base de datos, correo y claves secretas a variables de entorno.
