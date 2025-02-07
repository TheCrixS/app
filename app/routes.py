from flask import render_template, request, redirect, url_for, flash, jsonify, abort, send_from_directory
import pandas as pd
import qrcode
import os
from datetime import datetime
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from werkzeug.utils import secure_filename

DATABASE_FILE = "BASE SOAT.xlsx"
QR_FOLDER = os.path.join(os.getcwd(), 'static', 'qr_codes')
SHEET_NAME = "BASE"

def calcular_estado(soat, tecnomecanica):
    """Determina si el estado es 'Activo' o 'Inactivo' según las fechas del SOAT y la tecnomecánica."""
    try:
        fecha_actual = datetime.today().date()
        soat_vencimiento = datetime.strptime(soat, "%Y/%m/%d").date()
        tecnomecanica_vencimiento = datetime.strptime(tecnomecanica, "%Y/%m/%d").date()
        return "Activo" if soat_vencimiento >= fecha_actual and tecnomecanica_vencimiento >= fecha_actual else "Inactivo"
    except ValueError:
        return "Inactivo"  # Si hay un error con la fecha, se marca como "Inactivo"

def obtener_nuevo_id(df):
    """Genera un ID auto-incrementable, comenzando desde 8000000."""
    if "ID" in df.columns and not df.empty:
        try:
            max_id = df["ID"].dropna().astype(int).max()
            return max(max_id + 1, 8000000)  # Asegura que el primer ID sea 8000000
        except:
            return 8000000
    return 8000000

def init_routes(app):
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/registrar', methods=['GET', 'POST'])
    def registrar():
        if request.method == 'POST':
            # Obtener datos del formulario
            cedula = request.form['cedula']
            nombre = request.form['nombre']
            empresa = request.form['empresa']
            transporte = request.form['transporte']
            placa = request.form['placa']
            tarjeta = request.form['tarjeta']
            categoria = request.form['categoria']
            vencimiento = request.form['vencimiento']
            soat = request.form['soat']
            tecnomecanica = request.form['tecnomecanica']
            observaciones = request.form['observaciones']

            # Convertir fechas a formato AAAA/MM/DD
            vencimiento = datetime.strptime(vencimiento, "%Y-%m-%d").strftime("%Y/%m/%d")
            soat = datetime.strptime(soat, "%Y-%m-%d").strftime("%Y/%m/%d")
            tecnomecanica = datetime.strptime(tecnomecanica, "%Y-%m-%d").strftime("%Y/%m/%d")

            # Cargar la base de datos
            try:
                df = pd.read_excel(DATABASE_FILE, sheet_name=SHEET_NAME, dtype=str)
            except (FileNotFoundError, ValueError):
                df = pd.DataFrame(columns=["ID", "ESTADO", "CEDULA", "NOMBRES Y APELLIDOS", "EMPRESA", 
                                           "TIPO DE TRANSPORTE", "PLACA", "TARJETA DE PROPIEDAD", 
                                           "CATEGORIA(S)", "FECHA DE VENCIMIENTO", "SOAT", 
                                           "TECNOMECANICA", "OBSERVACIONES"])

            # Verificar si la cédula ya existe
            if cedula in df["CEDULA"].astype(str).values:
                flash("Error: La cédula ya está registrada.", "danger")
                return jsonify({"error": "La cédula ya está registrada."})

            # Generar un nuevo ID
            nuevo_id = obtener_nuevo_id(df)

            # Calcular el estado basado en el SOAT y la tecnomecánica
            estado = calcular_estado(soat, tecnomecanica)

            # Agregar nuevo usuario al DataFrame
            nuevo_usuario = pd.DataFrame([{
                "ID": nuevo_id,
                "ESTADO": estado,
                "CEDULA": cedula,
                "NOMBRES Y APELLIDOS": nombre,
                "EMPRESA": empresa,
                "TIPO DE TRANSPORTE": transporte,
                "PLACA": placa,
                "TARJETA DE PROPIEDAD": tarjeta,
                "CATEGORIA(S)": categoria,
                "FECHA DE VENCIMIENTO": vencimiento,
                "SOAT": soat,
                "TECNOMECANICA": tecnomecanica,
                "OBSERVACIONES": observaciones
            }])
            df = pd.concat([df, nuevo_usuario], ignore_index=True)

            # Guardar en el archivo Excel en la hoja "BASE"
            with pd.ExcelWriter(DATABASE_FILE, engine="openpyxl", mode="w") as writer:
                df.to_excel(writer, sheet_name=SHEET_NAME, index=False)

            # Generar código QR con ID
            qr_data = f"ID: {nuevo_id}"
            qr = qrcode.make(qr_data)
            qr_path = os.path.join(QR_FOLDER, f"{cedula}.png")
            qr.save(qr_path)

            # Generar ruta relativa para el navegador
            relative_qr_path = f"/static/qr_codes/{cedula}.png"
            return jsonify({"qr_path": relative_qr_path, "cedula": cedula})


        return render_template('register.html', qr_path=None)

    @app.route('/validar_qr')
    def validar_qr():
        """Página para escanear y validar códigos QR."""
        return render_template('validar_qr.html')

    @app.route('/procesar_qr', methods=['POST'])
    def procesar_qr():
        """Procesa el QR recibido y valida el estado en la base de datos."""
        try:
            data = request.get_json()
            qr_data = data.get("qr_data")

            if not qr_data:
                return jsonify({"message": "No se recibió código QR."})

            # Extraer el ID del QR
            lines = qr_data.split("\n")
            id_usuario = None
            for line in lines:
                if "ID:" in line:
                    id_usuario = line.split(": ")[1].strip()
                    break

            if not id_usuario:
                return jsonify({"message": "No se encontró el ID en el QR."})

            # Buscar en la base de datos
            df = pd.read_excel(DATABASE_FILE, sheet_name=SHEET_NAME, dtype=str)
            usuario = df[df["ID"] == id_usuario]

            if usuario.empty:
                return jsonify({"message": "Usuario no encontrado."})

            estado = usuario["ESTADO"].values[0]

            if estado == "Activo":
                return jsonify({
                    "message": "✅ Acceso permitido",
                    "data": {
                        "ID": id_usuario,
                        "Cédula": usuario["CEDULA"].values[0],
                        "Nombre": usuario["NOMBRES Y APELLIDOS"].values[0],
                        "Placa": usuario["PLACA"].values[0],
                        "Estado": estado
                    }
                })
            else:
                return jsonify({
                    "message": "❌ Acceso denegado",
                    "data": {
                        "ID": id_usuario,
                        "Cédula": usuario["CEDULA"].values[0],
                        "Nombre": usuario["NOMBRES Y APELLIDOS"].values[0],
                        "Placa": usuario["PLACA"].values[0],
                        "Estado": estado
                    }
                })

        except Exception as e:
            return jsonify({"message": f"Error: {str(e)}"})
        
    # Función que valida que el archivo tenga extensión Excel
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ['xls', 'xlsx']
    
    @app.route('/cargue_masivo', methods=['POST'])
    def cargue_masivo():
        # Verificar que se haya enviado el archivo
        if 'documento' not in request.files:
            flash('No se seleccionó ningún archivo.')
            return redirect(url_for('index'))
        file = request.files['documento']
        if file.filename == '':
            flash('No se seleccionó ningún archivo.')
            return redirect(url_for('index'))
        if not allowed_file(file.filename):
            flash('Solo se permiten archivos Excel (.xls, .xlsx).')
            return redirect(url_for('index'))
        
        # Guardar el archivo temporalmente
        filename = secure_filename(file.filename)
        temp_folder = 'temp'
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)
        temp_path = os.path.join(temp_folder, filename)
        file.save(temp_path)
        
        # Intentar leer el archivo Excel subido
        try:
            df_upload = pd.read_excel(temp_path)
        except Exception as e:
            flash(f'Error al leer el archivo: {e}')
            os.remove(temp_path)
            return redirect(url_for('index'))
        
        # Cargar la base de datos
        try:
            df = pd.read_excel(DATABASE_FILE, sheet_name=SHEET_NAME, dtype=str)
        except (FileNotFoundError, ValueError):
            df = pd.DataFrame(columns=["ID", "ESTADO", "CEDULA", "NOMBRES Y APELLIDOS", "EMPRESA", 
                                           "TIPO DE TRANSPORTE", "PLACA", "TARJETA DE PROPIEDAD", 
                                           "CATEGORIA(S)", "FECHA DE VENCIMIENTO", "SOAT", 
                                           "TECNOMECANICA", "OBSERVACIONES"])
        
        # Procesar cada registro del archivo subido
        for index, row in df_upload.iterrows():
            # Suponemos que las columnas en el Excel se llaman exactamente:
            # 'CEDULA', 'NOMBRES Y APELLIDOS', 'EMPRESA', 'TIPO DE TRANSPORTE',
            # 'PLACA', 'TARJETA DE PROPIEDAD', 'CATEGORIA(S)', 'FECHA DE VENCIMIENTO',
            # 'SOAT', 'TECNOMECANICA', 'OBSERVACIONES'
            cedula = str(row.get('CEDULA')).strip()
            # Si la cédula ya existe en la base, se omite este registro
            if cedula in df["CEDULA"].astype(str).values:
                continue
            
            nombre = row.get('NOMBRES Y APELLIDOS', '')
            empresa = row.get('EMPRESA', '')
            transporte = row.get('TIPO DE TRANSPORTE', '')
            placa = row.get('PLACA', '')
            tarjeta = row.get('TARJETA DE PROPIEDAD', '')
            categoria = row.get('CATEGORIA(S)', '')
            vencimiento_val = row.get('FECHA DE VENCIMIENTO', '')
            soat_val = row.get('SOAT', '')
            tecnomecanica_val = row.get('TECNOMECANICA', '')
            observaciones = row.get('OBSERVACIONES', '')
            
        # Convertir las fechas al formato "AAAA/MM/DD"
            def convert_date(value):
                try:
                    if pd.notnull(value):
                        if isinstance(value, pd.Timestamp):
                            return value.strftime("%Y/%m/%d")
                        else:
                            # Asumimos que viene en formato "AAAA-MM-DD"
                            return datetime.strptime(str(value), "%Y-%m-%d").strftime("%Y/%m/%d")
                except Exception:
                    return ""
                return ""
            
            vencimiento = convert_date(vencimiento_val)
            soat = convert_date(soat_val)
            tecnomecanica = convert_date(tecnomecanica_val)
            
            # Generar un nuevo ID y calcular el estado
            nuevo_id = obtener_nuevo_id(df)
            estado = calcular_estado(soat, tecnomecanica)
            
            # Crear el diccionario con la información del usuario
            new_row = pd.DataFrame ([{
                "ID": nuevo_id,
                "ESTADO": estado,
                "CEDULA": cedula,
                "NOMBRES Y APELLIDOS": nombre,
                "EMPRESA": empresa,
                "TIPO DE TRANSPORTE": transporte,
                "PLACA": placa,
                "TARJETA DE PROPIEDAD": tarjeta,
                "CATEGORIA(S)": categoria,
                "FECHA DE VENCIMIENTO": vencimiento,
                "SOAT": soat,
                "TECNOMECANICA": tecnomecanica,
                "OBSERVACIONES": observaciones
            }])
            
            df = pd.concat([df, new_row], ignore_index=True)

            # Generar el código QR para el usuario
            qr_data = f"ID: {nuevo_id}"
            qr = qrcode.make(qr_data)
            qr_file_path = os.path.join(QR_FOLDER, f"{cedula}.png")
            qr.save(qr_file_path)
        
        # Guardar la base de datos actualizada en el archivo Excel
        with pd.ExcelWriter(DATABASE_FILE, engine="openpyxl", mode="w") as writer:
            df.to_excel(writer, sheet_name=SHEET_NAME, index=False)
        
        # Eliminar el archivo temporal
        os.remove(temp_path)
        
        flash('Cargue masivo completado exitosamente.')
        return redirect(url_for('index'))