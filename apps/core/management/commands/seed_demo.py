from django.core.management.base import BaseCommand

from apps.core.catalogo import USUARIOS_DEMO
from apps.core.seed import seed_base, seed_ejemplo


class Command(BaseCommand):
    help = 'Carga roles, pantallas, usuarios, el año 2026 y los datos de ejemplo del taller textil.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--solo-base',
            action='store_true',
            help='Carga usuarios, roles, tipos y el año 2026, sin el catálogo de ejemplo.',
        )

    def handle(self, *args, **opciones):
        seed_base()
        self.stdout.write(self.style.SUCCESS('Base lista: roles, pantallas, usuarios, tipos y año 2026.'))
        if opciones['solo_base']:
            self._usuarios()
            return
        ok, mensaje = seed_ejemplo()
        estilo = self.style.SUCCESS if ok else self.style.WARNING
        self.stdout.write(estilo(mensaje))
        self._usuarios()

    def _usuarios(self):
        self.stdout.write('Usuarios de la demo local:')
        for item in USUARIOS_DEMO:
            self.stdout.write(f"  {item['username']} / {item['password']}  ({item['rol']})")
