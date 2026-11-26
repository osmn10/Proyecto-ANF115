from itertools import groupby
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.contrib.auth.models import Group, Permission
from django.db.models import Count, F
from django.contrib import messages
from django.urls import reverse_lazy

from bitacora.models import EventoBitacora
from bitacora.servicios import registrar_evento
from .models import Usuario
from .forms import UsuarioCrearForm, UsuarioEditarForm, RolForm, ResetearPasswordForm, APPS_NEGOCIO


_ACCIONES_ES = {
    'add': 'Agregar',
    'change': 'Modificar',
    'delete': 'Eliminar',
    'view': 'Ver',
}


def _permisos_agrupados():
    permisos = Permission.objects.filter(
        content_type__app_label__in=APPS_NEGOCIO
    ).select_related('content_type').order_by('content_type__app_label', 'codename')
    resultado = []
    for app_label, grupo in groupby(permisos, key=lambda p: p.content_type.app_label):
        items = []
        for p in grupo:
            accion = p.codename.split('_')[0]
            if accion in _ACCIONES_ES:
                modelo = p.content_type.model
                if p.content_type.app_label == 'bitacora' and modelo == 'eventobitacora':
                    modelo = 'eventos de bitácora'
                label = f"{_ACCIONES_ES[accion]} {modelo}"
            else:
                # Permiso personalizado (Meta.permissions): se muestra su nombre descriptivo
                label = p.name
            items.append({'pk': p.pk, 'label': label})
        resultado.append((app_label, items))
    return resultado


@login_required
@permission_required('seguridad.view_usuario', raise_exception=True)
def lista_usuarios(request):
    # Los eliminados se muestran al final de la lista
    usuarios = Usuario.objects.order_by(F('fecha_eliminacion').asc(nulls_first=True), 'username')
    return render(request, 'seguridad/lista_usuarios.html', {'usuarios': usuarios})


@login_required
@permission_required('seguridad.view_usuario', raise_exception=True)
def detalle_usuario(request, id):
    usuario = get_object_or_404(Usuario, pk=id)
    return render(request, 'seguridad/detalle_usuario.html', {'usuario': usuario})


@login_required
@permission_required('seguridad.add_usuario', raise_exception=True)
def crear_usuario(request):
    if request.method == 'POST':
        form = UsuarioCrearForm(request.POST)
        if form.is_valid():
            usuario = form.save(commit=False)
            usuario.debe_cambiar_password = True
            usuario.save()
            form.save_m2m()
            registrar_evento(
                usuario=request.user,
                accion=EventoBitacora.Accion.USUARIO_CREADO,
                resumen=f'Usuario "{usuario.username}" creado',
                entidad='Usuario',
                entidad_id=usuario.pk,
                detalles={
                    'nombre_usuario': usuario.username,
                    'roles': list(usuario.groups.values_list('name', flat=True)),
                },
            )
            messages.success(request, 'Usuario creado correctamente.')
            return redirect('seguridad:lista_usuarios')
    else:
        form = UsuarioCrearForm()
    return render(request, 'seguridad/form_usuario.html', {'form': form, 'accion': 'Crear'})


@login_required
@permission_required('seguridad.change_usuario', raise_exception=True)
def editar_usuario(request, id):
    usuario = get_object_or_404(Usuario, pk=id, fecha_eliminacion__isnull=True)
    if request.method == 'POST':
        roles_antes = list(usuario.groups.values_list('name', flat=True))
        nombre_antes = usuario.username
        form = UsuarioEditarForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            if form.changed_data:
                registrar_evento(
                    usuario=request.user,
                    accion=EventoBitacora.Accion.USUARIO_EDITADO,
                    resumen=f'Usuario "{usuario.username}" modificado',
                    entidad='Usuario',
                    entidad_id=usuario.pk,
                    detalles={
                        'campos_modificados': form.changed_data,
                        'nombre_usuario_antes': nombre_antes,
                        'nombre_usuario_despues': usuario.username,
                        'roles_antes': roles_antes,
                        'roles_despues': list(usuario.groups.values_list('name', flat=True)),
                    },
                )
            messages.success(request, 'Usuario actualizado correctamente.')
            return redirect('seguridad:lista_usuarios')
    else:
        form = UsuarioEditarForm(instance=usuario)
    return render(request, 'seguridad/form_usuario.html', {'form': form, 'accion': 'Editar', 'usuario': usuario})


@login_required
@permission_required('seguridad.delete_usuario', raise_exception=True)
def eliminar_usuario(request, id):
    usuario = get_object_or_404(Usuario, pk=id, fecha_eliminacion__isnull=True)
    if usuario == request.user:
        messages.error(request, 'No puedes eliminar tu propia cuenta.')
        return redirect('seguridad:lista_usuarios')
    if request.method == 'POST':
        usuario.eliminar()  # eliminacion logica: conserva la fila y sus registros
        registrar_evento(
            usuario=request.user,
            accion=EventoBitacora.Accion.USUARIO_DESACTIVADO,
            resumen=f'Usuario "{usuario.username}" desactivado',
            entidad='Usuario',
            entidad_id=usuario.pk,
        )
        messages.success(request, f'Usuario {usuario.username} eliminado correctamente.')
        return redirect('seguridad:lista_usuarios')
    return render(request, 'seguridad/eliminar_usuario.html', {'usuario': usuario})


# --- Roles ---

@login_required
@permission_required('auth.view_group', raise_exception=True)
def lista_roles(request):
    roles = Group.objects.annotate(total_usuarios=Count('user')).order_by('name')
    return render(request, 'seguridad/lista_roles.html', {'roles': roles})


@login_required
@permission_required('auth.add_group', raise_exception=True)
def crear_rol(request):
    if request.method == 'POST':
        form = RolForm(request.POST)
        if form.is_valid():
            rol = form.save()
            registrar_evento(
                usuario=request.user,
                accion=EventoBitacora.Accion.ROL_CREADO,
                resumen=f'Rol "{rol.name}" creado',
                entidad='Rol',
                entidad_id=rol.pk,
                detalles={'permisos': list(rol.permissions.values_list('codename', flat=True))},
            )
            messages.success(request, 'Rol creado correctamente.')
            return redirect('seguridad:lista_roles')
        permisos_seleccionados = set(int(pk) for pk in request.POST.getlist('permissions') if pk)
    else:
        form = RolForm()
        permisos_seleccionados = set()
    return render(request, 'seguridad/form_rol.html', {
        'form': form,
        'accion': 'Crear',
        'permisos_agrupados': _permisos_agrupados(),
        'permisos_seleccionados': permisos_seleccionados,
    })


@login_required
@permission_required('auth.change_group', raise_exception=True)
def editar_rol(request, id):
    rol = get_object_or_404(Group, pk=id)
    if request.method == 'POST':
        nombre_antes = rol.name
        permisos_antes = list(rol.permissions.values_list('codename', flat=True))
        form = RolForm(request.POST, instance=rol)
        if form.is_valid():
            form.save()
            permisos_despues = list(rol.permissions.values_list('codename', flat=True))
            if nombre_antes != rol.name or permisos_antes != permisos_despues:
                registrar_evento(
                    usuario=request.user,
                    accion=EventoBitacora.Accion.ROL_EDITADO,
                    resumen=f'Rol "{rol.name}" modificado',
                    entidad='Rol',
                    entidad_id=rol.pk,
                    detalles={
                        'nombre_antes': nombre_antes,
                        'nombre_despues': rol.name,
                        'permisos_antes': permisos_antes,
                        'permisos_despues': permisos_despues,
                    },
                )
            messages.success(request, 'Rol actualizado correctamente.')
            return redirect('seguridad:lista_roles')
        permisos_seleccionados = set(int(pk) for pk in request.POST.getlist('permissions') if pk)
    else:
        form = RolForm(instance=rol)
        permisos_seleccionados = set(rol.permissions.values_list('pk', flat=True))
    return render(request, 'seguridad/form_rol.html', {
        'form': form,
        'accion': 'Editar',
        'rol': rol,
        'permisos_agrupados': _permisos_agrupados(),
        'permisos_seleccionados': permisos_seleccionados,
    })


@login_required
@permission_required('auth.delete_group', raise_exception=True)
def eliminar_rol(request, id):
    rol = get_object_or_404(Group, pk=id)
    if request.method == 'POST':
        nombre_rol = rol.name
        permisos_rol = list(rol.permissions.values_list('codename', flat=True))
        rol.delete()
        registrar_evento(
            usuario=request.user,
            accion=EventoBitacora.Accion.ROL_ELIMINADO,
            resumen=f'Rol "{nombre_rol}" eliminado',
            entidad='Rol',
            entidad_id=id,
            detalles={'nombre': nombre_rol, 'permisos': permisos_rol},
        )
        messages.success(request, 'Rol eliminado correctamente.')
        return redirect('seguridad:lista_roles')
    return render(request, 'seguridad/eliminar_rol.html', {'rol': rol})


@login_required
@permission_required('auth.change_group', raise_exception=True)
def usuarios_rol(request, id):
    rol = get_object_or_404(Group, pk=id)
    if request.method == 'POST':
        accion = request.POST.get('accion')
        usuario_id = request.POST.get('usuario_id')
        usuario = get_object_or_404(Usuario, pk=usuario_id, fecha_eliminacion__isnull=True)
        if accion == 'agregar':
            usuario.groups.add(rol)
            registrar_evento(
                usuario=request.user,
                accion=EventoBitacora.Accion.USUARIO_AGREGADO_ROL,
                resumen=f'Usuario "{usuario.username}" agregado al rol "{rol.name}"',
                entidad='Usuario',
                entidad_id=usuario.pk,
                detalles={'nombre_usuario': usuario.username, 'rol': rol.name},
            )
            messages.success(request, f'Usuario {usuario.username} agregado al rol.')
        elif accion == 'quitar':
            usuario.groups.remove(rol)
            registrar_evento(
                usuario=request.user,
                accion=EventoBitacora.Accion.USUARIO_QUITADO_ROL,
                resumen=f'Usuario "{usuario.username}" retirado del rol "{rol.name}"',
                entidad='Usuario',
                entidad_id=usuario.pk,
                detalles={'nombre_usuario': usuario.username, 'rol': rol.name},
            )
            messages.success(request, f'Usuario {usuario.username} quitado del rol.')
        return redirect('seguridad:usuarios_rol', id=id)

    usuarios_con_rol = rol.user_set.all().order_by('username')
    usuarios_sin_rol = Usuario.objects.exclude(groups=rol).filter(
        fecha_eliminacion__isnull=True).order_by('username')
    return render(request, 'seguridad/usuarios_rol.html', {
        'rol': rol,
        'usuarios_con_rol': usuarios_con_rol,
        'usuarios_sin_rol': usuarios_sin_rol,
    })


# --- Reseteo de contraseña por administrador ---

@login_required
@permission_required('seguridad.change_usuario', raise_exception=True)
def resetear_password(request, id):
    usuario = get_object_or_404(Usuario, pk=id, fecha_eliminacion__isnull=True)
    if request.method == 'POST':
        form = ResetearPasswordForm(request.POST)
        if form.is_valid():
            usuario.set_password(form.cleaned_data['password1'])
            usuario.debe_cambiar_password = True
            usuario.save()
            registrar_evento(
                usuario=request.user,
                accion=EventoBitacora.Accion.PASSWORD_REINICIADA,
                resumen=f'Contraseña de "{usuario.username}" restablecida por administración',
                entidad='Usuario',
                entidad_id=usuario.pk,
            )
            messages.success(
                request,
                f'Contraseña de {usuario.username} restablecida. '
                'El usuario deberá cambiarla en su próximo acceso.'
            )
            return redirect('seguridad:detalle_usuario', id=id)
    else:
        form = ResetearPasswordForm()
    return render(request, 'seguridad/resetear_password.html', {'form': form, 'usuario': usuario})


# --- Perfil propio ---

@login_required
def mi_perfil(request):
    return render(request, 'seguridad/mi_perfil.html')


class CambiarPasswordView(LoginRequiredMixin, PasswordChangeView):
    template_name = 'seguridad/cambiar_password.html'
    success_url = reverse_lazy('seguridad:mi_perfil')

    def form_valid(self, form):
        self.request.user.debe_cambiar_password = False
        self.request.user.save(update_fields=['debe_cambiar_password'])
        registrar_evento(
            usuario=self.request.user,
            accion=EventoBitacora.Accion.PASSWORD_CAMBIADA,
            resumen='La persona actualizó su contraseña',
            entidad='Usuario',
            entidad_id=self.request.user.pk,
        )
        messages.success(self.request, 'Contraseña actualizada correctamente.')
        return super().form_valid(form)
