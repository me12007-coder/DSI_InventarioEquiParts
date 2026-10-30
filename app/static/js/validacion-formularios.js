document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('form').forEach(form => {
    const inicio = form.querySelector('[name="fecha_inicio"]');
    const fin = form.querySelector('[name="fecha_fin"]');
    if (!inicio || !fin) return;
    const check = () => {
      fin.min = inicio.value || '2024-01-01';
      if (inicio.value && fin.value && fin.value < inicio.value) {
        fin.setCustomValidity('La fecha final no puede ser anterior a la inicial.');
      } else { fin.setCustomValidity(''); }
    };
    inicio.addEventListener('change', check);
    fin.addEventListener('change', check);
    check();
  });
});
