from django import forms
from django.db.models import Q
from django.utils import timezone

from categorias.models import Categoria
from .servicios import aplicar_correccion, tomar_instantanea

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

class CorreccionMovimientoForm(MovimientoForm):
    """
    Formulario base para corregir un ingreso o un gasto (CU08). Se usa siempre con
    instance=<movimiento>. Agrega el motivo (obligatorio) y la version que la persona
    tenia en pantalla, para detectar si alguien mas cambio el registro (RNF09).
    El tipo y el autor no son campos: no se pueden cambiar (RN10).
    """

    motivo = forms.CharField(
        label='Motivo de la corrección', max_length=250, strip=True,
        error_messages={'required': 'Indica el motivo de la corrección.'},
    )
    version_esperada = forms.IntegerField(widget=forms.HiddenInput, min_value=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Se toma ahora: despues de is_valid() la instancia ya trae los valores nuevos.
        self.antes = tomar_instantanea(self.instance)
        self._originales = (
            self.instance.concepto, self.instance.monto,
            self.instance.fecha, self.instance.categoria_id,
        )
        self.fields['version_esperada'].initial = self.instance.version

    def clean(self):
        datos = super().clean()
        categoria = datos.get('categoria')
        nuevos = (datos.get('concepto'), datos.get('monto'), datos.get('fecha'), categoria.pk if categoria else None)
        if None not in nuevos and nuevos == self._originales:
            raise forms.ValidationError('No hay cambios que guardar. Modifica al menos un campo.')
        return datos

    def guardar_correccion(self, usuario):
        """Guarda el movimiento y su historial. Lanza ConflictoDeVersion si el registro cambio."""
        return aplicar_correccion(
            self.instance, antes=self.antes, motivo=self.cleaned_data['motivo'],
            version_esperada=self.cleaned_data['version_esperada'], usuario=usuario,
        )

class FiltroMovimientosForm(forms.Form):
    """
    Filtros de las listas de ingresos y gastos (RF08). Se envían por GET.
    El rango de fechas es inclusivo: "desde" y "hasta" entran en el resultado.
    """

    desde = forms.DateField(label='Desde', required=False)
    hasta = forms.DateField(label='Hasta', required=False)
    categoria = forms.ModelChoiceField(
        label='Categoría', queryset=Categoria.objects.none(),
        required=False, empty_label='Todas',
    )

    def __init__(self, *args, tipo, **kwargs):
        super().__init__(*args, **kwargs)
        # Se incluyen las inactivas: sirven para consultar registros históricos
        campo = self.fields['categoria']
        campo.queryset = Categoria.objects.filter(tipo=tipo).order_by('nombre')
        campo.label_from_instance = lambda c: c.nombre if c.activo else f'{c.nombre} (inactiva)'
        campo.error_messages['invalid_choice'] = 'La categoría seleccionada no es válida.'

    @property
    def hay_filtros(self):
        return any(self.data.get(nombre) for nombre in self.fields)

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get('desde'), datos.get('hasta')
        if desde and hasta and desde > hasta:
            raise forms.ValidationError('La fecha "Desde" no puede ser posterior a la fecha "Hasta".')
        return datos

    def filtrar(self, movimientos):
        """Aplica los filtros válidos a un queryset de movimientos."""
        datos = self.cleaned_data
        if datos.get('desde'):
            movimientos = movimientos.filter(fecha__gte=datos['desde'])
        if datos.get('hasta'):
            movimientos = movimientos.filter(fecha__lte=datos['hasta'])
        if datos.get('categoria'):
            movimientos = movimientos.filter(categoria=datos['categoria'])
        return movimientos