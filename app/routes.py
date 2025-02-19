from flask import render_template, request, redirect, url_for, flash, jsonify, session
from functools import wraps
import pandas as pd
import qrcode
import os
from datetime import datetime
import bcrypt
from werkzeug.utils import secure_filename

# =======================
# Configuraciones y Constantes
# =======================
DATABASE_FILE = "BASE SOAT.xlsx"
USUARIOS = "ul.xlsx"
SHEET_NAME = "Sheet1"  # Hoja para la base de datos principal
QR_FOLDER = os.path.join(os.getcwd(), 'static', 'qr_codes')
ALLOWED_EXTENSIONS = ['xls', 'xlsx']

# Columnas estandarizadas para el Excel
COLUMNS = [
    "ID", "ESTADO", "CEDULA", "NOMBRES Y APELLIDOS", "EMPRESA", 
    "TIPO DE TRANSPORTE", "PLACA", "TARJETA DE PROPIEDAD", 
    "CATEGORIA(S)", "FECHA DE VENCIMIENTO", "SOAT", 
    "TECNOMECANICA", "OBSERVACIONES"
]

# Formato de fechas
INPUT_DATE_FORMAT = "%Y-%m-%d"
OUTPUT_DATE_FORMAT = "%Y/%m/%d"

# =======================
# Funciones Helper
# =======================

def login_required(f):
    """Decora rutas que requieren autenticación."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash("Debes iniciar sesión para acceder a esta página.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*roles):
    """Decora rutas que requieren ciertos roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] not in roles:
                flash("No tienes permisos para acceder a esta página.")
                return redirect(url_for('menu'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def convert_date(value):
    """Convierte una fecha a formato AAAA/MM/DD asegurando que el input sea siempre una cadena."""
    try:
        if pd.notnull(value):
            # Si ya es un Timestamp, lo formateamos directamente.
            if isinstance(value, pd.Timestamp):
                return value.strftime("%Y/%m/%d")
            date_str = str(value).strip()
            # Intentar primero con formato dd/mm/yyyy
            for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(date_str, fmt).strftime("%Y/%m/%d")
                except ValueError:
                    pass
    except Exception:
        pass
    return ""

def convert_to_int_str(valor):
    """Convierte un valor numérico a cadena sin decimales."""
    try:
        if pd.notnull(valor) and str(valor).strip() != '':
            return str(int(float(valor)))
    except Exception:
        pass
    return ''

def load_database():
    """Carga la base de datos del Excel usando el formato y hoja definidos."""
    try:
        df = pd.read_excel(DATABASE_FILE, sheet_name=SHEET_NAME, dtype=str)
    except Exception:
        df = pd.DataFrame(columns=COLUMNS)
    return df

def save_database(df):
    """Guarda el DataFrame en el archivo Excel usando la hoja definida."""
    with pd.ExcelWriter(DATABASE_FILE, engine="openpyxl", mode="w") as writer:
        df.to_excel(writer, sheet_name=SHEET_NAME, index=False)

def obtener_nuevo_id(df):
    """Genera un ID auto-incrementable, iniciando en 8000000."""
    if "ID" in df.columns and not df.empty:
        try:
            max_id = df["ID"].dropna().astype(int).max()
            return max(max_id + 1, 8000000)
        except:
            return 8000000
    return 8000000

def allowed_file(filename):
    """Verifica que el archivo tenga extensión Excel permitida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def calcular_estado(soat, tecnomecanica):
    """Determina si el estado es 'Activo' o 'Inactivo' según las fechas del SOAT y la tecnomecánica."""
    try:
        fecha_actual = datetime.today().date()
        soat_vencimiento = datetime.strptime(soat, "%Y/%m/%d").date()
        tecnomecanica_vencimiento = datetime.strptime(tecnomecanica, "%Y/%m/%d").date()
        return "Activo" if soat_vencimiento >= fecha_actual and tecnomecanica_vencimiento >= fecha_actual else "Inactivo"
    except ValueError:
        return "Inactivo"  # Si hay un error con la fecha, se marca como "Inactivo"

# =======================
# Rutas de la Aplicación
# =======================

def init_routes(app):

    @app.route('/index')
    def index():
        if 'username' not in session:
            return redirect(url_for('login'))
        return render_template('index.html')

    @app.route('/registrar', methods=['GET', 'POST'])
    @login_required
    @roles_required('admin')
    def registrar():
        if request.method == 'POST':
            # Recoger datos del formulario
            cedula = request.form['cedula']
            nombre = request.form['nombre']
            empresa = request.form['empresa']
            transporte = request.form['transporte']
            placa = request.form['placa']
            tarjeta = request.form['tarjeta']
            categoria = request.form['categoria']
            vencimiento = request.form['vencimiento']
            soat_input = request.form['soat']
            tecnomecanica_input = request.form['tecnomecanica']
            observaciones = request.form['observaciones']

            # Convertir fechas al formato estándar
            soat = convert_date(soat_input)
            tecnomecanica = convert_date(tecnomecanica_input)

            # Cargar la base de datos
            df = load_database()

            # Validar que no exista ya un registro para esa cédula y ese tipo de transporte
            if not df[(df["CEDULA"].astype(str) == cedula) & (df["TIPO DE TRANSPORTE"] == transporte)].empty:
                flash("Error: Ya se ha registrado un vehículo de este tipo para esta cédula.", "danger")
                return jsonify({"error": "Ya se ha registrado un vehículo de este tipo para esta cédula."})


            # Generar un nuevo ID y calcular el estado
            nuevo_id = obtener_nuevo_id(df)
            estado = calcular_estado(soat, tecnomecanica)

            # Crear el registro del nuevo usuario
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
            save_database(df)

            # Generar y guardar el código QR
            qr_data = f"ID: {nuevo_id}"
            qr = qrcode.make(qr_data)
            qr_path = os.path.join(QR_FOLDER, f"{cedula}.png")
            qr.save(qr_path)
            relative_qr_path = f"/static/qr_codes/{cedula}.png"

            return jsonify({"qr_path": relative_qr_path, "cedula": cedula})
        return render_template('register.html', qr_path=None)

    @app.route('/validar_qr')
    @login_required
    @roles_required('admin', 'validador')
    def validar_qr():
        return render_template('validar_qr.html')

    @app.route('/procesar_qr', methods=['POST'])
    @login_required
    @roles_required('admin', 'validador')
    def procesar_qr():
        try:
            data = request.get_json()
            qr_data = data.get("qr_data")
            if not qr_data:
                return jsonify({"message": "No se recibió código QR."})
            
            # Extraer el ID del QR
            id_usuario = None
            for line in qr_data.split("\n"):
                if "ID:" in line:
                    id_usuario = line.split(": ")[1].strip()
                    break
            if not id_usuario:
                return jsonify({"message": "No se encontró el ID en el QR."})
            
            # Buscar el usuario en la base de datos
            df = load_database()
            usuario = df[df["ID"] == id_usuario]
            if usuario.empty:
                return jsonify({"message": "Usuario no encontrado."})
            
            # Extraer y "limpiar" la placa
            placa = usuario["PLACA"].values[0]
            placa_str = str(placa).strip().lower() if placa is not None else ""
            # Se valida si la placa es una cadena vacía, "none" o "nan"
            if placa_str in ["", "none", "nan"]:
                return jsonify({"message": "❌ Acceso denegado: Datos incompletos"})
            
            estado = usuario["ESTADO"].values[0]
            mensaje = "✅ Acceso permitido" if estado == "Activo" else "❌ Acceso denegado"
            datos = {
                "ID": id_usuario,
                "Cédula": usuario["CEDULA"].values[0],
                "Nombre": usuario["NOMBRES Y APELLIDOS"].values[0],
                "Placa": usuario["PLACA"].values[0],
                "Estado": estado
            }
            return jsonify({"message": mensaje, "data": datos})
        except Exception as e:
            return jsonify({"message": f"Error: {str(e)}"})

    @app.route('/cargue_masivo', methods=['POST'])
    @login_required
    @roles_required('admin')
    def cargue_masivo():
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
        os.makedirs(temp_folder, exist_ok=True)
        temp_path = os.path.join(temp_folder, filename)
        file.save(temp_path)

        # Intentar leer el archivo Excel subido
        try:
            df_upload = pd.read_excel(temp_path)
        except Exception as e:
            flash(f'Error al leer el archivo: {e}')
            os.remove(temp_path)
            return redirect(url_for('index'))

        df = load_database()
        usuarios_agregados = 0

        for index, row in df_upload.iterrows():
            cedula = convert_to_int_str(row.get('CEDULA'))
            transporte = row.get('TIPO DE TRANSPORTE', '')
            # Validar que no exista ya un registro para la misma combinación (CEDULA y TIPO DE TRANSPORTE)
            if not df[(df["CEDULA"].astype(str) == cedula) & (df["TIPO DE TRANSPORTE"] == transporte)].empty:
                continue

            nombre = row.get('NOMBRES Y APELLIDOS', '')
            empresa = row.get('EMPRESA', '')
            placa = row.get('PLACA', '')
            tarjeta = convert_to_int_str(row.get('TARJETA DE PROPIEDAD'))
            categoria = row.get('CATEGORIA(S)', '')
            vencimiento = row.get('FECHA DE VENCIMIENTO', '')
            soat_val = row.get('SOAT', '')
            tecnomecanica_val = row.get('TECNOMECANICA', '')
            observaciones = row.get('OBSERVACIONES', '')

            soat = convert_date(soat_val)
            tecnomecanica = convert_date(tecnomecanica_val)
            nuevo_id = obtener_nuevo_id(df)
            estado = calcular_estado(soat, tecnomecanica)

            new_row = pd.DataFrame([{
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

            # Generar y guardar código QR
            qr_data = f"ID: {nuevo_id}"
            qr = qrcode.make(qr_data)
            qr_file_path = os.path.join(QR_FOLDER, f"{cedula}.png")
            qr.save(qr_file_path)
            usuarios_agregados += 1

        save_database(df)
        os.remove(temp_path)
        flash(f'Cargue completado exitosamente. Se agregaron {usuarios_agregados} usuarios.', 'Success')
        return redirect(url_for('index'))

    @app.route('/usuarios')
    @login_required
    def mostrar_usuarios():
        try:
            df = load_database()
            df = df.fillna('')
            for col in ['CEDULA', 'TARJETA DE PROPIEDAD']:
                if col in df.columns:
                    df[col] = df[col].apply(convert_to_int_str)
            usuarios = df.to_dict(orient='records')
            total_usuarios = len(usuarios)  # Contador de usuarios
            COLUMNAS_DESEADAS = [
                'ID', 'ESTADO', 'CEDULA', 'NOMBRES Y APELLIDOS', 'EMPRESA',
                'TIPO DE TRANSPORTE', 'PLACA', 'TARJETA DE PROPIEDAD',
                'CATEGORIA(S)', 'FECHA DE VENCIMIENTO', 'SOAT',
                'TECNOMECANICA', 'OBSERVACIONES'
            ]
            usuarios_filtrados = [
                {col: usuario.get(col, '') for col in COLUMNAS_DESEADAS}
                for usuario in usuarios
            ]
            return render_template('usuarios.html', usuarios=usuarios_filtrados, columnas=COLUMNAS_DESEADAS, total=total_usuarios)
        except Exception as e:
            return f"Error al leer el archivo: {str(e)}"

    @app.route('/eliminar_usuario/<int:id>', methods=['POST'])
    @login_required
    @roles_required('admin')
    def eliminar_usuario(id):
        try:
            df = load_database()
            # Convertir la columna "ID" a cadena para asegurar la comparación
            df['ID'] = df['ID'].astype(str)
            
            # Buscar el usuario usando la comparación de strings
            usuario = df[df['ID'] == str(id)]
            if not usuario.empty:
                cedula = usuario.iloc[0]['CEDULA']
                qr_path = os.path.join(QR_FOLDER, f"{cedula}.png")
                if os.path.exists(qr_path):
                    os.remove(qr_path)
            # Filtrar para eliminar el usuario
            df = df[df['ID'] != str(id)]
            save_database(df)
            flash("Usuario eliminado correctamente.", "Success")
            return redirect(url_for('mostrar_usuarios'))
        except Exception as e:
            return f"Error al eliminar el usuario y su código QR: {str(e)}"

    def load_users(ul):
        """Carga usuarios y contraseñas encriptadas desde el Excel."""
        try:
            df = pd.read_excel(ul)
            users = {row["username"]: {"password": row["password"], "role": row["role"]} for _, row in df.iterrows()}
            return users
        except FileNotFoundError:
            return {}

    users = load_users(USUARIOS)

    @app.route('/', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username_input = request.form.get('username').strip()
            password_input = request.form.get('password').strip().encode()
            if username_input in users:
                stored_password = users[username_input]['password'].encode()
                if bcrypt.checkpw(password_input, stored_password):
                    session['username'] = username_input
                    session['role'] = users[username_input]['role']
                    return redirect(url_for('index'))
                else:
                    flash("Usuario o contraseña incorrectos.")
            else:
                flash("Usuario o contraseña incorrectos.")
        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        session.clear()
        session.pop('username', None)
        return redirect(url_for('login'))
    
    @app.route('/editar_usuario', methods=['POST'])
    @login_required
    @roles_required('admin')
    def editar_usuario():
        user_id = request.form.get('id')
        if not user_id:
            flash("ID del usuario no proporcionado.", "error")
            return redirect(url_for('index'))
        try:
            df = load_database()
            df['ID'] = df['ID'].astype(int)
        except Exception as e:
            flash("Error al leer el archivo Excel: " + str(e), "error")
            return redirect(url_for('index'))
        try:
            user_id_int = int(float(user_id))
        except ValueError:
            flash("ID inválido.", "error")
            return redirect(url_for('index'))
        matching_rows = df[df['ID'] == user_id_int]
        if matching_rows.empty:
            flash("Usuario no encontrado.", "error")
            return redirect(url_for('index'))
        idx = matching_rows.index[0]
        cedula_input = request.form.get('cedula')
        try:
            cedula_int = int(float(cedula_input)) if cedula_input else ''
        except ValueError:
            cedula_int = cedula_input

        transporte_input = request.form.get('transporte', '')
    
        # Validar que no exista otro registro con la misma combinación de CEDULA y TIPO DE TRANSPORTE
        duplicate = df[(df["CEDULA"].astype(str) == cedula_int) & 
                    (df["TIPO DE TRANSPORTE"] == transporte_input) & 
                    (df["ID"] != user_id_int)]
        if not duplicate.empty:
            flash("Error: Ya se ha registrado un vehículo de este tipo para esta cédula.", "danger")
            return redirect(url_for('mostrar_usuarios'))

        # Actualizamos los campos; aplicamos conversión de fechas para soat y tecnomecánica
        df.at[idx, 'CEDULA'] = cedula_int
        df.at[idx, 'NOMBRES Y APELLIDOS'] = request.form.get('nombres')
        df.at[idx, 'EMPRESA'] = request.form.get('empresa')
        df.at[idx, 'TIPO DE TRANSPORTE'] = transporte_input
        df.at[idx, 'PLACA'] = request.form.get('placa')
        df.at[idx, 'TARJETA DE PROPIEDAD'] = request.form.get('tarjeta')
        df.at[idx, 'CATEGORIA(S)'] = request.form.get('categoria')
        df.at[idx, 'FECHA DE VENCIMIENTO'] = request.form.get('vencimiento')
        soat_str = request.form.get('soat')
        tecnomecanica_str = request.form.get('tecnomecanica')
        df.at[idx, 'SOAT'] = soat_str
        df.at[idx, 'TECNOMECANICA'] = tecnomecanica_str
        df.at[idx, 'OBSERVACIONES'] = request.form.get('observaciones')
        df.at[idx, 'ESTADO'] = calcular_estado(soat_str, tecnomecanica_str)
        
        try:
            save_database(df)
            flash("Usuario actualizado correctamente.", "Success")
        except Exception as e:
            flash("Error al guardar los cambios en el Excel: " + str(e), "error")
            return redirect(url_for('mostrar_usuarios'))
        return redirect(url_for('mostrar_usuarios'))
    
    @app.route('/eliminar_varios', methods=['POST'])
    @login_required
    @roles_required('admin')
    def eliminar_varios():
        try:
            # Obtener la lista de IDs seleccionados desde el formulario
            selected_ids = request.form.getlist('selected_ids')
            if not selected_ids:
                flash("No se seleccionaron usuarios para eliminar.", "warning")
                return redirect(url_for('mostrar_usuarios'))
            
            df = load_database()  # Función para cargar el DataFrame con tus datos
            
            # Iterar sobre cada ID seleccionado
            for id_sel in selected_ids:
                # Buscar el usuario en el DataFrame (aseguramos comparar cadenas)
                usuario = df[df['ID'] == str(id_sel)]
                if not usuario.empty:
                    cedula = usuario.iloc[0]['CEDULA']
                    qr_path = os.path.join(QR_FOLDER, f"{cedula}.png")
                    if os.path.exists(qr_path):
                        os.remove(qr_path)
            
            # Filtrar el DataFrame eliminando todos los registros cuyos IDs estén en selected_ids
            df = df[~df['ID'].isin(selected_ids)]
            save_database(df)  # Función para guardar el DataFrame actualizado
            
            flash("Usuarios eliminados correctamente.", "Success")
            return redirect(url_for('mostrar_usuarios'))
        except Exception as e:
            flash(f"Error al eliminar los usuarios: {str(e)}", "danger")
            return redirect(url_for('mostrar_usuarios'))