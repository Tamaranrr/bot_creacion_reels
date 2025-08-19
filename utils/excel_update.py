import pandas as pd
from sqlalchemy.orm import sessionmaker
from utils.db_connection import engine, Videos
from tkinter import filedialog, messagebox

def cargar_datos(archivo_excel):
    """Carga los datos desde el archivo Excel y lo convierte en un DataFrame."""
    df = pd.read_excel(archivo_excel)
    return df

def insertar_datos(df):
    """Inserta los datos del DataFrame a la base de datos."""
    Session = sessionmaker(bind=engine)
    session = Session()
    for _, row in df.iterrows():
        nuevo_video = Videos(
            description=row['Tema'],
            platform_video=row['Plataforma']
        )
        session.add(nuevo_video)
    session.commit()
    session.close()
    print("✅ Datos cargados exitosamente en la base de datos.")

def guardar_datos(ventana):
    """Abre el diálogo para seleccionar un archivo Excel y cargarlo en la base de datos."""
    archivo_excel = filedialog.askopenfilename(
        title="Seleccionar Archivo Excel",
        filetypes=[("Archivos Excel", "*.xlsx;*.xls")]
    )
    
    if archivo_excel:
        try:
            df = cargar_datos(archivo_excel)  # Cargar datos desde el archivo Excel
            insertar_datos(df)  # Insertar los datos en la base de datos
            messagebox.showinfo("Éxito", f"Los datos se cargaron exitosamente desde el archivo: {archivo_excel}")
            ventana.quit()  # Cerrar la ventana de tkinter
            return True  # Retornar True cuando los datos se cargan correctamente
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al cargar los datos: {e}")
            ventana.quit()  # Cerrar la ventana si hay error
            return False  # Retornar False si hay error
    return False  # Si no se seleccionó archivo, retornar False
