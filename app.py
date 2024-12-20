from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from conexion import conectar_db
from fpdf import FPDF
import qrcode
import random
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "clave_secreta"

@app.route("/")
def index():
    # Generar el código QR que apunta a la ruta /identificacion
    url = "http://127.0.0.1:5000/identificacion"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")
    img.save("static/codigo_qr.png")
    return render_template("index.html")

@app.route("/identificacion", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        rut = request.form.get("rut")
        password = request.form.get("password")
        monto = request.form.get("monto")

        if not monto.isdigit() or int(monto) <= 0:
            flash("El monto ingresado no es válido.", "danger")
            return render_template("login.html")

        monto = int(monto)

        try:
            conexion = conectar_db()
            with conexion.cursor() as cursor:
                sql = "SELECT saldo FROM usuarios WHERE rut = %s AND password = %s"
                cursor.execute(sql, (rut, password))
                usuario = cursor.fetchone()

                if usuario:
                    saldo_actual = usuario["saldo"]
                    if monto <= saldo_actual:
                        nuevo_saldo = saldo_actual - monto

                        sql_update = "UPDATE usuarios SET saldo = %s, ultima_conexion = NOW() WHERE rut = %s"
                        cursor.execute(sql_update, (nuevo_saldo, rut))
                        conexion.commit()

                        boleta_path = generar_boleta_pdf(rut, monto, nuevo_saldo)

                        # Redirigir a página intermedia para mostrar mensaje y descargar boleta
                        return render_template(
                            "boleta_intermedia.html",
                            file_path=boleta_path,
                            monto=monto,
                            saldo=nuevo_saldo,
                        )
                    else:
                        flash(f"Saldo insuficiente. Tu saldo actual es: ${saldo_actual}", "danger")
                else:
                    flash("RUT o contraseña incorrectos.", "danger")
        except Exception as e:
            flash(f"Ocurrió un error: {str(e)}", "danger")
        finally:
            if conexion:
                conexion.close()

    return render_template("login.html")

@app.route("/editar/<rut>", methods=["GET", "POST"])
def editar_usuario(rut):
    try:
        conexion = conectar_db()
        if request.method == "POST":
            nombre_completo = request.form.get("nombre_completo")
            saldo = request.form.get("saldo")
            password = request.form.get("password")  # Capturamos el nuevo campo

            with conexion.cursor() as cursor:
                sql = """
                UPDATE usuarios 
                SET nombre_completo = %s, saldo = %s, password = %s 
                WHERE rut = %s
                """
                cursor.execute(sql, (nombre_completo, saldo, password, rut))
                conexion.commit()
                flash("Usuario actualizado correctamente.", "success")
                return redirect("/mostrar")
        else:
            with conexion.cursor() as cursor:
                sql = "SELECT rut, nombre_completo, saldo, password FROM usuarios WHERE rut = %s"
                cursor.execute(sql, (rut,))
                usuario = cursor.fetchone()
    except Exception as e:
        flash(f"Ocurrió un error: {str(e)}", "danger")
        usuario = None
    finally:
        if conexion:
            conexion.close()

    return render_template("editar.html", usuario=usuario)





@app.route("/agregar", methods=["GET", "POST"])
def agregar_usuario():
    if request.method == "POST":
        # Capturar datos del formulario
        rut = request.form.get("rut")
        nombre_completo = request.form.get("nombre_completo")
        password = request.form.get("password")
        saldo = request.form.get("saldo")

        # Validar datos básicos
        if not rut or not nombre_completo or not password or not saldo.isdigit():
            flash("Todos los campos son obligatorios y el saldo debe ser numérico.", "danger")
            return render_template("agregar.html")

        saldo = int(saldo)

        try:
            conexion = conectar_db()
            with conexion.cursor() as cursor:
                sql = """
                INSERT INTO usuarios (rut, nombre_completo, password, saldo, ultima_conexion)
                VALUES (%s, %s, %s, %s, NOW())
                """
                cursor.execute(sql, (rut, nombre_completo, password, saldo))
                conexion.commit()
                flash("Usuario agregado correctamente.", "success")
                return redirect("/mostrar")
        except Exception as e:
            flash(f"Ocurrió un error al agregar el usuario: {str(e)}", "danger")
        finally:
            if conexion:
                conexion.close()

    return render_template("agregar.html")







@app.route("/eliminar/<rut>")
def eliminar_usuario(rut):
    try:
        conexion = conectar_db()
        with conexion.cursor() as cursor:
            sql = "DELETE FROM usuarios WHERE rut = %s"
            cursor.execute(sql, (rut,))
            conexion.commit()
            flash("Usuario eliminado correctamente.", "success")
    except Exception as e:
        flash(f"Ocurrió un error al eliminar el usuario: {str(e)}", "danger")
    finally:
        if conexion:
            conexion.close()

    return redirect("/mostrar")




@app.route("/mostrar")
def mostrar_usuarios():
    try:
        conexion = conectar_db()
        with conexion.cursor() as cursor:
            # Ajustar los campos según la tabla 
            sql = "SELECT*FROM usuarios"
            cursor.execute(sql)
            usuarios = cursor.fetchall()  # Devuelve una lista de diccionarios
    except Exception as e:
        flash(f"Ocurrió un error al obtener los usuarios: {str(e)}", "danger")
        usuarios = []
    finally:
        if conexion:
            conexion.close()

    return render_template("mostrar.html", usuarios=usuarios)




@app.route("/descargar_boleta")
def descargar_boleta():
    file_path = request.args.get("file_path")
    return send_file(file_path, as_attachment=True)


def generar_boleta_pdf(rut, total_pago, saldo_disponible):
    """Genera un PDF compacto y personalizado con los detalles del pago."""
    # Configurar un tamaño personalizado para el PDF
    pdf = FPDF("P", "mm", (80, 120))  # 80mm x 120mm (tamaño de ticket pequeño)
    pdf.add_page()

    # Dibujar un marco
    pdf.set_line_width(0.5)
    pdf.set_draw_color(0, 0, 0)  # Negro
    pdf.rect(5, 5, 70, 110)  # Rectángulo en el margen

    # Título de la boleta
    pdf.set_font("Arial", style="B", size=12)
    pdf.set_text_color(0, 0, 0)  # Negro para el título
    pdf.cell(0, 10, txt="****** TAXI LA SERENA ******", ln=True, align="C")
    pdf.ln(5)

    # Línea divisoria
    pdf.set_draw_color(0, 0, 0)  # Negro
    pdf.line(10, 20, 70, 20)  # Línea horizontal debajo del título

    # Datos de la boleta
    pdf.set_font("Arial", size=10)
    pdf.set_text_color(0, 0, 0)  # Texto negro
    fecha_actual = datetime.now().strftime("%d-%m-%Y")
    hora_actual = datetime.now().strftime("%H:%M:%S")
    numero_boleta = random.randint(10000, 99999)
    codigo_pago = random.randint(100000, 999999)

    pdf.cell(0, 8, txt=f"Boleta N°: {numero_boleta}", ln=True, align="C")
    pdf.cell(0, 8, txt=f"Código de Pago: {codigo_pago}", ln=True, align="C")
    pdf.cell(0, 8, txt=f"Fecha: {fecha_actual}", ln=True, align="C")
    pdf.cell(0, 8, txt=f"Hora: {hora_actual}", ln=True, align="C")
    pdf.ln(2)  # Espacio adicional

    # Línea divisoria
    pdf.line(10, pdf.get_y(), 70, pdf.get_y())
    pdf.ln(4)

    pdf.cell(0, 8, txt=f"Total Pagado: ${total_pago}", ln=True, align="C")
    pdf.cell(0, 8, txt=f"Saldo Disponible: ${saldo_disponible}", ln=True, align="C")

    # Línea divisoria final
    pdf.ln(4)
    pdf.line(10, pdf.get_y(), 70, pdf.get_y())

    # Mensaje final
    pdf.ln(6)
    pdf.set_font("Arial", style="I", size=8)
    pdf.set_text_color(128, 128, 128)  # Gris claro
    pdf.cell(0, 10, txt="Gracias por su preferencia", ln=True, align="C")

    # Guardar el PDF en un archivo temporal
    pdf_path = os.path.join("static", f"boleta_{numero_boleta}.pdf")
    pdf.output(pdf_path)
    return pdf_path




if __name__ == "__main__":
    app.run(debug=True)
