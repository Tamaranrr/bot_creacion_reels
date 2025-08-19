import os

def crear_directorio_si_no_existe(path):
    if not os.path.exists(path):
        os.makedirs(path)
