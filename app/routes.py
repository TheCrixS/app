from flask import render_template, request, redirect, url_for, flash
import pandas as pd
import qrcode
import os
from datetime import datetime

DATABASE_FILE = "BASE SOAT.xlsx"
QR_FOLDER = "static/qr_codes"
SHEET_NAME = "BASE"

def calcular_estado(soat, tecnomecanica):
    """Determina si el estado es 'Activo' o 'Inactivo' según las fechas del SOAT y la tecnomecánica."""
    try:
        fecha_actual = datetime.today().date()
        soat_vencimiento = datetime.strptime(soat, "%d/%m/%Y").date()
        tecnomecanica_vencimiento = datetime.strptime(tecnomecanica, "%d/%m/%Y").date()

        return "Activo" if soat_vencimiento >= fecha_actual and tecnomecanica_vencimiento >= fecha_actual else "Inactivo"
    except ValueError:
        return "Inactivo"  # Si hay un error con la fecha, se marca como "Inactivo"

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

            # Cargar la base de datos
            try:
                df = pd.read_excel(DATABASE_FILE, sheet_name=SHEET_NAME)
            except ValueError:
                df = pd.DataFrame(columns=["ESTADO","CEDULA", "NOMBRES Y APELLIDOS", "EMPRESA", "TIPO DE TRANSPORTE", "PLACA", "TARJETA DE PROPIEDAD", "CATEGORIA(S)", "FECHA DE VENCIMIENTO", "SOAT", "TECNOMECANICA", "OBSERVACIONES"])

            # Verificar si la cédula ya existe
            if cedula in df["CEDULA"].astype(str).values:
                flash("Error: La cédula ya está registrada.", "danger")
                return redirect(url_for('registrar'))

            # Calcular el estado basado en el SOAT y la tecnomecánica
            estado = calcular_estado(soat, tecnomecanica)

            # Agregar nuevo usuario al DataFrame
            nuevo_usuario = pd.DataFrame([{
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

            # Generar código QR
            qr_data = f"Nombre: {nombre}\nCédula: {cedula}\nPlaca: {placa}"
            qr = qrcode.make(qr_data)
            qr_path = os.path.join(QR_FOLDER, f"{cedula}.png")
            qr.save(qr_path)

            flash("Usuario registrado con éxito.", "success")
            return render_template('register.html', qr_path=qr_path)

        return render_template('register.html', qr_path=None)
