import pandas as pd
import bcrypt

def encrypt_pass(password):
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode(), salt)
    return hashed.decode()

def add_users(excel_path, users):
    # Cargar el archivo excel si existe, o crear uno nuevo
    try:
        df = pd.read_excel(excel_path)
    except FileNotFoundError:
        df = pd.DataFrame(columns=['username','password','role'])

    # Agregar usuarios con contraseñas cifradas
    for username, password, role in users:
        if password:  # Verificar que la contraseña no sea None o vacía
            encrypted_pass = encrypt_pass(password)
            df = pd.concat([df, pd.DataFrame([[username, encrypted_pass, role]], columns=["username", "password", "role"])], ignore_index=True)
    
    #Guardar los cambios en el excel
    df.to_excel(excel_path, index=False)
    print('Usuarios agregados correctamente...')

user = input('Ingresa el username: ')
pw = input('Ingrese el password: ')
role = input('Ingrese el role: ')
usuarios = [(user,pw,role)]
ruta_excel = 'ul.xlsx'

add_users(ruta_excel,usuarios)