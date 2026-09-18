from flask import Flask, request, jsonify
from flask_cors import CORS
from database import conectar_bd
import json

app = Flask(__name__)
CORS(app)  # Permite peticiones desde React (Vite en puerto 5173)

@app.route("/")
def inicio():
    return jsonify({"mensaje": "API hoja de vida funcionando"})

@app.route("/probar")
def probar_data():
    conec = conectar_bd()
    if conec.is_connected():
        conec.close()
    return jsonify({"mensaje": "Conexion ok"})


# RUTAS DE HOJAS DE VIDA (CRUD Y REGISTRO COMPLETO)


@app.route("/api/hojas-vida", methods=["GET"])
def obtener_hojasvida():
    conec = conectar_bd()
    cursor = conec.cursor(dictionary=True)
    cursor.execute("SELECT * FROM hojas_vida")
    hojas_vida = cursor.fetchall()
    cursor.close()
    conec.close()
    return jsonify(hojas_vida), 200

@app.route("/api/hojas-vida/<int:id>", methods=["GET"])
def obtener_hojasvidaid(id):
    conec = conectar_bd()
    cursor = conec.cursor(dictionary=True)
    cursor.execute("SELECT * FROM hojas_vida WHERE id = %s", (id,))
    hoja_vida = cursor.fetchone()
    cursor.close()
    conec.close()
    if hoja_vida:
        return jsonify(hoja_vida), 200
    return jsonify({"mensaje": "Hoja de vida no encontrada"}), 404

@app.route("/api/registrohv", methods=["POST"])
def registrar_hojavida():
    conec = None
    cursor = None
    try:
        datos = request.get_json() or {}
        conec = conectar_bd()
        cursor = conec.cursor()

        # 1. Validar correo duplicado
        cursor.execute("SELECT id FROM hojas_vida WHERE correo = %s", (datos.get('correo'),))
        if cursor.fetchone():
            cursor.close()
            conec.close()
            return jsonify({"mensaje": "El correo ya está registrado con otra hoja de vida"}), 400

        # 2. Insertar datos principales en hojas_vida
        sql_hv = """
            INSERT INTO hojas_vida (nombre, edad, ciudad, correo, fotografia, programa, ficha, jornada)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql_hv, (
            datos.get('nombre'),
            datos.get('edad'),
            datos.get('ciudad'),
            datos.get('correo'),
            datos.get('fotografia', ''),
            datos.get('programa'),
            datos.get('ficha'),
            datos.get('jornada')
        ))
        id_hoja_vida = cursor.lastrowid

        # 3. Insertar Formación Académica (tabla estudios)
        if datos.get('nivel') or datos.get('institucion') or datos.get('titulo'):
            sql_estudio = """
                INSERT INTO estudios (hoja_vida_id, nivel, institucion, titulo, anio_graduacion)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(sql_estudio, (
                id_hoja_vida,
                datos.get('nivel', ''),
                datos.get('institucion', ''),
                datos.get('titulo', ''),
                datos.get('anio', '') or datos.get('anio_graduacion', '')
            ))

        # 4. Insertar Cursos realizados (tabla cursos)
        cursos = datos.get('cursos', [])
        if isinstance(cursos, list):
            sql_curso = "INSERT INTO cursos (hoja_vida_id, nombre) VALUES (%s, %s)"
            for curso in cursos:
                if curso and str(curso).strip():
                    cursor.execute(sql_curso, (id_hoja_vida, str(curso).strip()))

        # 5. Insertar Experiencias Laborales y sus Habilidades
        experiencias = datos.get('experiencias', [])
        if isinstance(experiencias, list):
            sql_exp = """
                INSERT INTO experiencias (hoja_vida_id, empresa, cargo, tiempo, funciones)
                VALUES (%s, %s, %s, %s, %s)
            """
            sql_hab = """
                INSERT INTO habilidades (experiencia_id, nombre)
                VALUES (%s, %s)
            """

            for exp in experiencias:
                # Convertir lista de funciones a string legible si viene como array
                funciones = exp.get('funciones', '')
                if isinstance(funciones, list):
                    funciones_str = ", ".join(funciones)
                else:
                    funciones_str = str(funciones)

                cursor.execute(sql_exp, (
                    id_hoja_vida,
                    exp.get('empresa', ''),
                    exp.get('cargo', ''),
                    exp.get('tiempo', ''),
                    funciones_str
                ))
                id_experiencia = cursor.lastrowid

                # Guardar las habilidades asociadas a esta experiencia
                habilidades = exp.get('habilidades', [])
                if isinstance(habilidades, list):
                    for hab in habilidades:
                        if hab and str(hab).strip():
                            cursor.execute(sql_hab, (id_experiencia, str(hab).strip()))

        # Si todo salió bien, confirmamos la transacción
        conec.commit()

        return jsonify({
            "mensaje": "Hoja de vida registrada con éxito",
            "id": id_hoja_vida
        }), 201

    except Exception as e:
        if conec:
            conec.rollback()
        print("Error en registrohv:", str(e))
        return jsonify({"mensaje": f"Error al procesar el registro: {str(e)}"}), 500

    finally:
        if cursor:
            cursor.close()
        if conec and conec.is_connected():
            conec.close()

@app.route("/api/actualizarhv/<int:id>", methods=["PUT"])
def actualizarhv(id):
    datos = request.get_json()
    conec = conectar_bd()
    cursor = conec.cursor(buffered=True)

    cursor.execute("SELECT id FROM hojas_vida WHERE id=%s", (id,))
    if cursor.fetchone() is None:
        cursor.close()
        conec.close()
        return jsonify({"Mensaje": "No se encontró la hoja de vida"}), 404

    cursor.execute("SELECT id FROM hojas_vida WHERE correo = %s AND id != %s", (datos["correo"], id))
    if cursor.fetchone() is not None:
        cursor.close()
        conec.close()
        return jsonify({"Mensaje": "El correo ya está registrado con otra hoja de vida"}), 400

    sql = """
        UPDATE hojas_vida
        SET nombre=%s, edad=%s, ciudad=%s, correo=%s,
            fotografia=%s, programa=%s, ficha=%s, jornada=%s
        WHERE id=%s
    """
    cursor.execute(sql, (
        datos["nombre"],
        datos["edad"],
        datos["ciudad"],
        datos["correo"],
        datos.get("fotografia", ""),
        datos["programa"],
        datos["ficha"],
        datos["jornada"],
        id
    ))
    conec.commit()
    cursor.close()
    conec.close()
    return jsonify({"Mensaje": "Hoja de vida actualizada", "id": id}), 200

@app.route("/api/eliminarhv/<int:id>", methods=["DELETE"])
def eliminar_hv(id):
    conec = conectar_bd()
    cursor = conec.cursor()
    cursor.execute("SELECT id FROM hojas_vida WHERE id=%s", (id,))
    if cursor.fetchone() is None:
        cursor.close()
        conec.close()
        return jsonify({"mensaje": "No se encontró la hoja de vida"}), 404

    cursor.execute("DELETE FROM hojas_vida WHERE id=%s", (id,))
    conec.commit()
    cursor.close()
    conec.close()
    return jsonify({"mensaje": "Hoja de vida eliminada"}), 200


# RUTAS INDIVIDUALES (Para operaciones atómicas)


@app.route("/api/hojas-vida/<int:hoja_vida_id>/estudios", methods=["POST"])
@app.route("/api/hojasvida/<int:hoja_vida_id>/estudios", methods=["POST"])
def registrar_estudio(hoja_vida_id):
    try:
        datos = request.get_json() or {}
        conec = conectar_bd()
        cursor = conec.cursor()
        sql = """
            INSERT INTO estudios (hoja_vida_id, nivel, institucion, titulo, anio_graduacion)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (
            hoja_vida_id,
            datos.get("nivel", ""),
            datos.get("institucion", ""),
            datos.get("titulo", ""),
            datos.get("anio_graduacion", "") or datos.get("anio", "")
        ))
        conec.commit()
        id_estudio = cursor.lastrowid
        cursor.close()
        conec.close()
        return jsonify({"mensaje": "Estudio registrado", "id": id_estudio, "hoja_vida_id": hoja_vida_id}), 201
    except Exception as e:
        return jsonify({"mensaje": str(e)}), 500

@app.route("/api/hojas-vida/<int:hoja_vida_id>/experiencias", methods=["POST"])
def registrar_experiencia(hoja_vida_id):
    try:
        datos = request.get_json() or {}
        conec = conectar_bd()
        cursor = conec.cursor()
        sql = """
            INSERT INTO experiencias (hoja_vida_id, empresa, cargo, tiempo, funciones)
            VALUES (%s, %s, %s, %s, %s)
        """
        funciones = datos.get("funciones", "")
        if isinstance(funciones, list):
            funciones = ", ".join(funciones)

        cursor.execute(sql, (
            hoja_vida_id,
            datos.get("empresa", ""),
            datos.get("cargo", ""),
            datos.get("tiempo", ""),
            funciones
        ))
        conec.commit()
        id_exp = cursor.lastrowid
        cursor.close()
        conec.close()
        return jsonify({"mensaje": "Experiencia registrada con éxito", "id": id_exp}), 201
    except Exception as e:
        return jsonify({"mensaje": str(e)}), 500

@app.route("/api/experiencias/<int:exp_id>/habilidades", methods=["POST"])
def registrar_habilidad(exp_id):
    try:
        datos = request.get_json() or {}
        conec = conectar_bd()
        cursor = conec.cursor()
        sql = "INSERT INTO habilidades (experiencia_id, nombre) VALUES (%s, %s)"
        cursor.execute(sql, (exp_id, datos.get("nombre", "")))
        conec.commit()
        id_hab = cursor.lastrowid
        cursor.close()
        conec.close()
        return jsonify({"mensaje": "Habilidad registrada con éxito", "id": id_hab}), 201
    except Exception as e:
        return jsonify({"mensaje": str(e)}), 500

@app.route("/api/hojas-vida/<int:hoja_vida_id>/cursos", methods=["POST"])
def registrar_curso(hoja_vida_id):
    try:
        datos = request.get_json() or {}
        conec = conectar_bd()
        cursor = conec.cursor()
        sql = "INSERT INTO cursos (hoja_vida_id, nombre) VALUES (%s, %s)"
        cursor.execute(sql, (hoja_vida_id, datos.get("nombre", "")))
        conec.commit()
        id_curso = cursor.lastrowid
        cursor.close()
        conec.close()
        return jsonify({"mensaje": "Curso registrado con éxito", "id": id_curso}), 201
    except Exception as e:
        return jsonify({"mensaje": str(e)}), 500


# CONSULTA COMPLETA ANIDADA


@app.route("/api/hojas-vida/<int:hoja_vida_id>/completa", methods=["GET"])
def obtener_hoja_vida_completa(hoja_vida_id):
    conec = conectar_bd()
    cursor = conec.cursor(dictionary=True)

    cursor.execute("SELECT * FROM hojas_vida WHERE id = %s", (hoja_vida_id,))
    hoja = cursor.fetchone()

    if not hoja:
        cursor.close()
        conec.close()
        return jsonify({"mensaje": "Hoja de vida no encontrada"}), 404

    cursor.execute("SELECT id, nivel, institucion, titulo, anio_graduacion FROM estudios WHERE hoja_vida_id = %s", (hoja_vida_id,))
    estudios = cursor.fetchall()

    cursor.execute("SELECT id, empresa, cargo, tiempo, funciones FROM experiencias WHERE hoja_vida_id = %s", (hoja_vida_id,))
    experiencias = cursor.fetchall()

    for exp in experiencias:
        cursor.execute("SELECT id, nombre FROM habilidades WHERE experiencia_id = %s", (exp["id"],))
        exp["habilidades"] = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM cursos WHERE hoja_vida_id = %s", (hoja_vida_id,))
    cursos = cursor.fetchall()

    cursor.close()
    conec.close()

    return jsonify({
        "datos_personales": hoja,
        "estudios": estudios,
        "experiencias": experiencias,
        "cursos": cursos
    }), 200

if __name__ == "__main__":
    app.run(debug=True, port=5000)