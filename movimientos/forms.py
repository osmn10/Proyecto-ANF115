from django import forms
from django.db.models import Q
from django.utils import timezone

from categorias.models import Categoria


class MovimientoForm(forms.ModelForm):
    """
    Formulario base de ingresos y gastos. Cada app lo hereda e indica su
    modelo proxy en Meta.model; el tipo de categoría se toma de Meta.model.TIPO.
    El tipo, el autor y la versión no son campos del formulario.
    """

    class Meta:
        fields = ('concepto', 'monto', 'fecha', 'categoria')
        labels = {
            'concepto': 'Concepto',
            'monto': 'Monto',
            'fecha': 'Fecha',
            'categoria': 'Categoría',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tipo = self._meta.model.TIPO

        # RN02: solo categorías activas del tipo del movimiento.
        # Al corregir (Fase 4) se conserva la categoría actual aunque se haya desactivado.
        disponibles = Q(activo=True)
        if self.instance.pk:
            disponibles |= Q(pk=self.instance.categoria_id)
        campo_categoria = self.fields['categoria']
        campo_categoria.queryset = Categoria.objects.filter(disponibles, tipo=tipo).order_by('nombre')
        campo_categoria.empty_label = 'Selecciona una categoría'
        campo_categoria.error_messages['invalid_choice'] = 'Selecciona una categoría activa de este tipo.'

        # RN03: la fecha no puede ser futura; se propone la de hoy en registros nuevos
        self.fecha_maxima = timezone.localdate()
        if not self.instance.pk:
            self.fields['fecha'].initial = self.fecha_maxima

    @property
    def hay_categorias(self):
        return self.fields['categoria'].queryset.exists()

    def clean_concepto(self):
        # Quita espacios repetidos: "Venta   de  contado" -> "Venta de contado"
        return ' '.join(self.cleaned_data['concepto'].split())