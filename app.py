from flask import Flask, request, jsonify
from flask_cors import CORS
from database import conectar_bd
from dotenv import load_dotenv
import os
from functools import wraps

load_dotenv()

from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
    get_jwt
)
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

# Inicialización de la app
app = Flask(__name__)
# Es buena práctica tener un valor por defecto para evitar que la app se caiga en desarrollo si falta el .env
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "super-secreta-2026") 
jwt = JWTManager(app)
CORS(app)

# Decorador corregido para validar roles
def rol_requerido(rol):
    def decorador(funcion):
        @wraps(funcion)
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            if claims.get("rol") != rol:
                return jsonify({"mensaje": "No tienes permisos para acceder"}), 403
            return funcion(*args, **kwargs)
        return wrapper
    return decorador


@app.route("/probar")
def probar_data():
    conec = conectar_bd()
    if conec.is_connected():
        conec.close()
    return {"mensaje": "Conexion ok"}


@app.route("/api/registro-usuario", methods=["POST"])
def registro_usuario():
    datos = request.get_json()

    if not datos:
        return jsonify({"mensaje": "No se recibieron datos"}), 400

    nombre = datos.get("nombre", "").strip()
    correo = datos.get("correo", "").strip().lower()
    password = datos.get("password", "")

    if not nombre or not correo or not password:
        return jsonify({"mensaje": "Todos los campos son obligatorios"}), 400

    if len(password) < 8:
        return jsonify({"mensaje": "Minimo 8 caracteres"}), 400

    conec = conectar_bd()
    cursor = conec.cursor()

    cursor.execute("SELECT id FROM usuarios WHERE correo = %s", (correo,))
    if cursor.fetchone():
        cursor.close()
        conec.close()
        return jsonify({"mensaje": "El correo ya está registrado"}), 400

    password_hash = generate_password_hash(password)

# El registro público siempre crea un aprendiz
    sql = """
        INSERT INTO usuarios (nombre, correo, password, rol, estado)
        VALUES (%s, %s, %s, %s, %s)
    """
    cursor.execute(sql, (nombre, correo, password_hash, 'aprendiz', True))
    conec.commit()
    id_usuario = cursor.lastrowid

    cursor.close()
    conec.close()

    return jsonify({"mensaje": "Usuario registrado correctamente", "id": id_usuario}), 201


@app.route("/api/login", methods=["POST"])
def login():
    datos = request.get_json()
    correo = datos.get("correo", "").strip().lower()
    password = datos.get("password", "")

    conec = conectar_bd()
    cursor = conec.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, nombre, correo, password, rol, estado 
        FROM usuarios WHERE correo = %s
    """, (correo,))
    usuario = cursor.fetchone()

    cursor.close()
    conec.close()

    # Validar credenciales
    if not usuario or not check_password_hash(usuario["password"], password):
        return jsonify({"mensaje": "Correo o contraseña incorrectos"}), 401

    if not usuario["estado"]:
        return jsonify({"mensaje": "Cuenta desactivada"}), 403

    # Generar el token
    token = create_access_token(
        identity=str(usuario["id"]),
        additional_claims={"rol": usuario["rol"]}
    )

    return jsonify({
        "mensaje": "Inicio de sesión exitoso",
        "token": token,
        "usuario": {
            "id": usuario["id"],
            "nombre": usuario["nombre"],
            "correo": usuario["correo"],
            "rol": usuario["rol"]
        }
    }), 200


@app.route("/api/registrohv", methods=["POST"])
@jwt_required()
def registrar_hojavida():
    # Obtener el id del usuario desde el token
    usuario_id = int(get_jwt_identity())
    rol = get_jwt().get("rol")

    if rol != "aprendiz":
        return jsonify({"mensaje": "Solo los aprendices pueden registrar HV"}), 403

    datos = request.get_json()
    conec = conectar_bd()
    cursor = conec.cursor()

    sql = """
        INSERT INTO hojas_vida
        (usuario_id, nombre, edad, ciudad, correo, fotografia, programa, ficha, jornada)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    valores = (
        usuario_id, 
        datos["nombre"], 
        datos["edad"],
        datos["ciudad"], 
        datos["correo"], 
        datos.get("fotografia"),
        datos["programa"], 
        datos["ficha"], 
        datos["jornada"]
    )

    cursor.execute(sql, valores)
    conec.commit()
    id_regenerado = cursor.lastrowid

    cursor.close()
    conec.close()

    return jsonify({"mensaje": "Registro de hoja de vida", "id": id_regenerado}), 201


@app.route("/api/mi-hoja-vida", methods=["GET"])
@jwt_required()
def mi_hoja_vida():
    usuario_id = int(get_jwt_identity())
    rol = get_jwt().get("rol")

    if rol != "aprendiz":
        return jsonify({"mensaje": "Consulta exclusiva para aprendices"}), 403

    conec = conectar_bd()
    cursor = conec.cursor(dictionary=True, buffered=True)

    # 1. Trae la última hoja de vida registrada por este aprendiz
    cursor.execute("""
        SELECT * FROM hojas_vida 
        WHERE usuario_id = %s 
        ORDER BY id DESC 
        LIMIT 1
    """, (usuario_id,))
    hv = cursor.fetchone()

    if not hv:
        cursor.close()
        conec.close()
        return jsonify({"mensaje": "No tienes una hoja de vida registrada"}), 404

    hoja_vida_id = hv["id"]

    # 2. Estudios
    cursor.execute("SELECT * FROM estudios WHERE hoja_vida_id = %s", (hoja_vida_id,))
    estudios = cursor.fetchall()

    # 3. Cursos
    cursor.execute("SELECT * FROM cursos WHERE hoja_vida_id = %s", (hoja_vida_id,))
    cursos = cursor.fetchall()

    # 4. Experiencias
    cursor.execute("SELECT * FROM experiencias WHERE hoja_vida_id = %s", (hoja_vida_id,))
    experiencias = cursor.fetchall()

    # 5. Habilidades vinculadas a las experiencias de esta HV
    cursor.execute("""
        SELECT h.id, h.nombre, h.experiencia_id 
        FROM habilidades h
        INNER JOIN experiencias e ON h.experiencia_id = e.id
        WHERE e.hoja_vida_id = %s
    """, (hoja_vida_id,))
    habilidades = cursor.fetchall()

    for experiencia in experiencias:
        experiencia["habilidades"] = [
            h for h in habilidades if h["experiencia_id"] == experiencia["id"]
        ]

    cursor.close()
    conec.close()

    return jsonify({
        "datos_personales": hv,
        "estudios": estudios,
        "cursos": cursos,
        "experiencias": experiencias
    }), 200


# LISTAR TODAS LAS HOJAS DE VIDA (Ruta protegida para reclutadores)
@app.route("/api/hojas-vida", methods=["GET"])
@rol_requerido("reclutador")
def obtener_hojasvida():
    conec = conectar_bd()
    cursor = conec.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM hojas_vida")
        hojas_vida = cursor.fetchall()
        
        if not hojas_vida:
            return jsonify({"mensaje": "No hay hojas de vida registradas en el sistema"}), 404
            
        return jsonify(hojas_vida), 200
        
    except Exception as error:
        print("Error al obtener las hojas de vida:", error)
        return jsonify({"mensaje": "Ocurrió un error en el servidor al consultar los datos"}), 500
    finally:
        cursor.close()
        conec.close()


@app.route("/api/hojasvida/<int:hoja_vida_id>/estudios", methods=["POST"])
def registrar_estudio(hoja_vida_id):
    datos = request.get_json()
    conec = conectar_bd()
    cursor = conec.cursor()

    sql = """
        INSERT INTO estudios
        (hoja_vida_id, nivel, institucion, titulo, anio_graduacion)
        VALUES (%s, %s, %s, %s, %s)
    """
    valores = (hoja_vida_id, datos["nivel"], datos["institucion"], datos["titulo"], datos["anio_graduacion"])
    cursor.execute(sql, valores)
    conec.commit()
    id_estudio = cursor.lastrowid
    cursor.close()
    conec.close()
    return jsonify({"mensaje": "Estudio registrado correctamente", "id": id_estudio, "hoja_vida_id": hoja_vida_id}), 201


@app.route("/api/hojasvida/<int:hoja_vida_id>/experiencias", methods=["POST"])
def registrar_experiencia(hoja_vida_id):
    datos = request.get_json()
    conec = conectar_bd()
    cursor = conec.cursor()

    sql = """
        INSERT INTO experiencias
        (hoja_vida_id, empresa, cargo, tiempo, funciones)
        VALUES (%s, %s, %s, %s, %s)
    """
    valores = (hoja_vida_id, datos["empresa"], datos["cargo"], datos["tiempo"], datos["funciones"])
    cursor.execute(sql, valores)
    conec.commit()
    id_experiencia = cursor.lastrowid
    cursor.close()
    conec.close()
    return jsonify({"mensaje": "Experiencia registrada correctamente", "id": id_experiencia, "hoja_vida_id": hoja_vida_id}), 201


@app.route("/api/experiencias/<int:experiencia_id>/habilidades", methods=["POST"])
@jwt_required()
def registrar_habilidad(experiencia_id):
    usuario_id = int(get_jwt_identity())
    datos = request.get_json() or {}

    if get_jwt().get("rol") != "aprendiz":
        return jsonify({"mensaje": "No tienes permiso"}), 403

    conec = conectar_bd()
    cursor = conec.cursor()

    # Verificar que la experiencia pertenece al aprendiz
    cursor.execute("""
        SELECT e.id
        FROM experiencias e
        INNER JOIN hojas_vida hv ON hv.id = e.hoja_vida_id
        WHERE e.id = %s AND hv.usuario_id = %s
    """, (experiencia_id, usuario_id))

    if not cursor.fetchone():
        cursor.close()
        conec.close()
        return jsonify({"mensaje": "Experiencia no encontrada"}), 404

    cursor.execute("""
        INSERT INTO habilidades (experiencia_id, nombre)
        VALUES (%s, %s)
    """, (experiencia_id, datos["nombre"]))
    
    conec.commit()
    id_habilidad = cursor.lastrowid
    
    cursor.close()
    conec.close()

    return jsonify({"mensaje": "Habilidad registrada correctamente", "id": id_habilidad}), 201

@app.route("/api/hojasvida/<int:hoja_vida_id>/cursos", methods=["POST"])
def registrar_curso(hoja_vida_id):
    datos = request.get_json()
    conec = conectar_bd()
    cursor = conec.cursor()

    # Asegúrate de que estas columnas coincidan con las de tu tabla 'cursos' en MySQL
    sql = """
        INSERT INTO cursos
        (hoja_vida_id, nombre)
        VALUES (%s, %s)
    """
    # Si en tu base de datos pusiste más columnas (como institucion o anio), agrégalas aquí y en el SQL
    valores = (hoja_vida_id, datos["nombre"])
    
    cursor.execute(sql, valores)
    conec.commit()
    id_curso = cursor.lastrowid
    
    cursor.close()
    conec.close()
    
    return jsonify({
        "mensaje": "Curso registrado correctamente", 
        "id": id_curso, 
        "hoja_vida_id": hoja_vida_id
    }), 201


# INICIO DEL SERVIDOR LOCAL DE FLASK
if __name__ == "__main__":
    app.run(debug=True, port=5001)