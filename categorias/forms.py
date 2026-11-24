from django import forms

from .models import Categoria


class CategoriaForm(forms.ModelForm):

    class Meta:
        model = Categoria
        fields = ('nombre', 'tipo')
        labels = {
            'nombre': 'Nombre de la categoría',
            'tipo': 'Tipo de movimiento',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # RN09: si la categoría ya clasifica movimientos, su tipo no puede cambiar.
        # Un campo "disabled" ignora lo que llegue por POST y conserva el valor original.
        self.tipo_bloqueado = bool(self.instance.pk and self.instance.esta_en_uso())
        if self.tipo_bloqueado:
            self.fields['tipo'].disabled = True

    def clean_nombre(self):
        # Quita espacios repetidos: "Servicios   basicos" -> "Servicios basicos"
        nombre = self.cleaned_data['nombre']
        return ' '.join(nombre.split())