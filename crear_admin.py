from werkzeug.security import (generate_password_hash,check_password_hash)
from database import conectar_bd
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask import Flask, request, jsonify
from flask_cors import CORS
from database import conectar_bd
from dotenv import load_dotenv
import os
from getpass import getpass

def crear_administrador():
    # Usamos .strip() para evitar que envíen solo espacios en blanco
    nombre = input("Ingresar nombre del rol reclutador: ").strip()
    correo = input("Ingresar correo del rol reclutador: ").strip().lower()
    password = getpass("Contraseña: ").strip()

    # Sin campos vacíos
    if not nombre or not correo or not password:
        print("Error: Todos los campos son obligatorios. No se permiten campos vacíos.")
        return

    # Contraseña entre 8 y 15 caracteres
    if len(password) < 8 or len(password) > 15:
        print("Error: La contraseña debe tener entre 8 y 15 caracteres.")
        return

    conexion = conectar_bd()
    cursor = conexion.cursor()

    try:
        # El correo electrónico no puede estar registrado
        cursor.execute("SELECT id FROM usuarios WHERE correo = %s", (correo,))
        existente = cursor.fetchone()

        if existente:
            print("Error: Este correo ya está registrado en el sistema. No se puede registrar.")
            return

        # La contraseña debe estar encriptada
        password_hash = generate_password_hash(password)

        # Si pasa todas las validaciones, se registra el usuario
        sql = """INSERT INTO usuarios (nombre, correo, password, rol, estado) 
                 VALUES (%s, %s, %s, 'reclutador', 1)"""

        cursor.execute(sql, (nombre, correo, password_hash))
        conexion.commit()
        
        print("¡Éxito! Reclutador creado correctamente cumpliendo todas las reglas.")
        
    except Exception as error:
        conexion.rollback()
        print("Error en la base de datos:", error)
        
    finally:
        cursor.close()
        conexion.close()

if __name__ == "__main__":
    crear_administrador()