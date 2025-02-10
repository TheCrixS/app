from flask import render_template, request, redirect, url_for, flash, jsonify, session
from functools import wraps
import pandas as pd
import qrcode
import os
from datetime import datetime
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from werkzeug.utils import secure_filename

DATABASE_FILE = "BASE SOAT.xlsx"
USUARIOS = "usuarios.xlsx"
SHEET_NAME_USERS = "USERS"
QR_FOLDER = os.path.join(os.getcwd(), 'static', 'qr_codes')
SHEET_NAME = "BASE"

def login_required(f):
    """
    Decorador para proteger rutas que requieren autenticación.
    Verifica que 'username' esté en la sesión. Si no, redirige al login.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash("Debes iniciar sesión para acceder a esta página.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

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
    @app.route('/index')
    def index():
        if 'username' not in session:
            return redirect(url_for('login'))
        return render_template('index.html')

    @app.route('/registrar', methods=['GET', 'POST'])
    @login_required
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
    @login_required
    def validar_qr():
        """Página para escanear y validar códigos QR."""
        return render_template('validar_qr.html')

    @app.route('/procesar_qr', methods=['POST'])
    @login_required
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
    @login_required
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
        
        flash('Cargue completado exitosamente.', 'Success')
        return redirect(url_for('index'))
    
    @app.route('/usuarios')
    @login_required
    def mostrar_usuarios():
        try:
            # Leer el archivo Excel
            df = pd.read_excel(DATABASE_FILE)
            
            # Convertir DataFrame a lista de diccionarios para pasarlo a la plantilla
            usuarios = df.to_dict(orient='records')
            
            return render_template('usuarios.html', usuarios=usuarios)
        except Exception as e:
            return f"Error al leer el archivo: {str(e)}"

    @app.route('/modificar_usuario')
    @login_required
    def modificar_usuario():
        return render_template('modificar_usuario.html')


    @app.route('/eliminar_usuario/<int:id>', methods=['POST'])
    @login_required
    def eliminar_usuario(id):
        try:
            df = pd.read_excel(DATABASE_FILE)
            usuario = df[df['ID'] == id]
            if not usuario.empty:
                cedula = usuario.iloc[0]['CEDULA']  # Obtener la cédula del usuario
                qr_path = os.path.join(QR_FOLDER, f"{cedula}.png")
                if os.path.exists(qr_path):
                    os.remove(qr_path)  # Eliminar el archivo QR
            df = df[df['ID'] != id]  # Filtrar el usuario a eliminar
            df.to_excel(DATABASE_FILE, index=False)  # Guardar cambios en el archivo Excel
            return redirect(url_for('mostrar_usuarios'))
        except Exception as e:
            return f"Error al eliminar el usuario y su código QR: {str(e)}"
        
    def load_users():
        try:
            # Lee el archivo Excel especificando la hoja 'USERS'
            df = pd.read_excel("usuarios.xlsx", sheet_name="USERS")
            print("Columnas encontradas:", df.columns.tolist())
            
            # Verifica que existan las columnas 'username' y 'password'
            if 'username' not in df.columns or 'password' not in df.columns:
                print("Error: Las columnas 'username' y/o 'password' no se encontraron en el archivo Excel.")
                return {}
            
            # Convierte el DataFrame a un diccionario
            users = dict(zip(df['username'], df['password']))
            return users
        except Exception as e:
            print("Error al leer el archivo Excel:", e)
            return {}

    # Cargar los usuarios al iniciar la aplicación
    users = load_users()
    print("Usuarios cargados:", users)

    @app.route('/', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            # Al comparar las credenciales, eliminamos espacios en blanco:
            username_input = request.form.get('username').strip()
            password_input = request.form.get('password').strip()

            # Asegúrate de que en el diccionario de usuarios también se eliminen los espacios:
            if username_input in users:
                stored_password = str(users[username_input]).strip()
                if stored_password == password_input:
                    session['username'] = username_input
                    return redirect(url_for('index'))
                else:
                    flash("Usuario o contraseña incorrectos.")
            else:
                flash("Usuario o contraseña incorrectos.")
        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        session.pop('username', None)
        return redirect(url_for('login'))