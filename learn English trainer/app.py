from flask import Flask, send_file, render_template, request, jsonify, redirect, url_for, session
import sqlite3
import io
from datetime import datetime, timedelta
from pydub import AudioSegment
import speech_recognition as sr
import tempfile
import os
import paths_info

app = Flask(__name__)
# Set the secret key for session management
app.secret_key = paths_info.secret_key

# Database path
db_path = paths_info.data_base_path

# Map of users to their date stamps and background colors
date_stamp_map = {
    paths_info.user_1: {"date_stamp": "date_stamp_1", "color": "#ddddff"},  # light red
    paths_info.user_2: {"date_stamp": "date_stamp_2", "color": "#ddffdd"},  # light green
    paths_info.user_3: {"date_stamp": "date_stamp_3", "color": "#ffdddd"}  # light blue
}

def get_db_connection():
    """
    Establishes a connection to the SQLite database.

    Returns:
    sqlite3.Connection: A connection object to the database.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_word_by_id_nr(id_nr):
    """
    Retrieves a word from the database by its ID number.

    Parameters:
    id_nr (int): The ID number of the word to retrieve.

    Returns:
    str or None: The word corresponding to the ID number, or None if not found.
    """
    table_name = session.get("table_name", "general_words")  # default fallback
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT words FROM {table_name} WHERE id_nr = ?", (id_nr,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

@app.route("/")
def login():
    """
    Renders the login page.

    Returns:
    str: The HTML content of the login page.
    """
    return render_template("login.html")

@app.route("/set_user", methods=["POST"])
def set_user():
    """
    Sets the user and initializes session variables based on user input.

    Returns:
    Response: A redirect to the word route with the chosen starting ID or an error message.
    """
    user = request.form["user"]
    table_name = request.form.get("table_name")  # NEW: get table choice
    start_id = int(request.form.get("start_id", 1))  # NEW: start from this ID
    max_id = int(request.form.get("max_id", 100))  # NEW: upper limit

    if user not in date_stamp_map:
        return "Invalid user", 400
    if not table_name:  # safety check
        return "Table name not selected", 400

    session["user_name_column"] = user
    session["date_stamp"] = date_stamp_map[user]["date_stamp"]
    session["bg_color"] = date_stamp_map[user]["color"]
    session["table_name"] = table_name  # NEW
    session["id_nr"] = start_id  # start point
    session["id_upper_limit"] = max_id  # limit

    # Redirect to training starting from chosen start_id
    return redirect(url_for("word_route", id_nr=start_id))

@app.route("/word/<int:id_nr>")
def word_route(id_nr):
    """
    Renders the word route page.

    Parameters:
    id_nr (int): The ID number of the word to display.

    Returns:
    str: The HTML content of the word route page.
    """
    user_name_column = session.get("user_name_column")
    table_name = session.get("table_name", "general_words")
    date_stamp = session.get("date_stamp")

    next_id, word = get_next_word(id_nr - 1, user_name_column, date_stamp)

    # Map of users to their background colors
    bg_map = {
        paths_info.user_1: "#e8f5e9",  # light green
        paths_info.user_2: "#e3f2fd",  # light blue
        paths_info.user_3: "#fce4ec"  # pink
    }
    bg_color = bg_map.get(user_name_column, "#ffffff")  # default white

    if next_id:
        word_text, pattern = get_word_and_pattern_by_id_nr(next_id, user_name_column)
        return render_template(
            "index.html",
            word_text=word_text,
            id_nr=next_id,
            pattern=pattern,
            table_name=table_name,
            bg_color=bg_color
        )

@app.route("/image/<int:id_nr>")
def get_image(id_nr):
    """
    Transfers an image to the rendering page index.html.

    Parameters:
    id_nr (int): The ID number of the image to retrieve.

    Returns:
    Response: The image file or an error message if the image is not found.
    """
    conn = get_db_connection()
    table_name = session.get("table_name", "general_words")
    cursor = conn.execute(f"SELECT image FROM {table_name} WHERE id_nr = ?", (id_nr,))
    row = cursor.fetchone()
    conn.close()

    if row and row["image"]:
        return send_file(
            io.BytesIO(row["image"]),
            mimetype='image/png',  # Adjust if your image is JPEG or another format
            as_attachment=False
        )
    return "Image not found", 404

@app.route("/sound/en/<int:id_nr>")
def get_en_sound(id_nr):
    """
    Transfers the English sound to the rendering page index.html.

    Parameters:
    id_nr (int): The ID number of the English sound to retrieve.

    Returns:
    Response: The English sound file or an error message if the sound is not found.
    """
    conn = get_db_connection()
    table_name = session.get("table_name", "general_words")
    cursor = conn.execute(f"SELECT en_sounds FROM {table_name} WHERE id_nr = ?", (id_nr,))
    row = cursor.fetchone()
    conn.close()

    if row and row["en_sounds"]:
        return send_file(
            io.BytesIO(row["en_sounds"]),
            mimetype='audio/mpeg',
            as_attachment=False
        )
    return "English sound not found", 404

@app.route("/sound/ru/<int:id_nr>")
def get_ru_sound(id_nr):
    """
    Transfers the Russian sound to the rendering page index.html.

    Parameters:
    id_nr (int): The ID number of the Russian sound to retrieve.

    Returns:
    Response: The Russian sound file or an error message if the sound is not found.
    """
    conn = get_db_connection()
    table_name = session.get("table_name", "general_words")
    cursor = conn.execute(f"SELECT ru_sounds FROM {table_name} WHERE id_nr = ?", (id_nr,))
    row = cursor.fetchone()
    conn.close()

    if row and row["ru_sounds"]:
        return send_file(
            io.BytesIO(row["ru_sounds"]),
            mimetype='audio/mpeg',
            as_attachment=False
        )
    return "Russian sound not found", 404

@app.route("/process", methods=["POST"])
def process_text():
    """
    Processes the text input from the user and updates the database.

    Returns:
    json: A JSON response containing the result and next ID number or a training completion message.
    """
    usr_input = request.form["userText"]
    current_id = int(request.form["id_nr"])  # from frontend
    table_name = session.get("table_name", "general_words")
    user_name_column = session.get("user_name_column")
    date_stamp = session.get("date_stamp")

    result = chk_wrd_chng_pattern(current_id, usr_input, user_name_column, date_stamp)

    next_id, next_word = get_next_word(current_id, user_name_column, date_stamp)
    if not next_id:
        return jsonify({"message": "Training complete! 🎉", "next_id": None})

    return jsonify({
        "message": result,
        "next_id": next_id
    })

@app.route("/check", methods=["POST"])
def check_pronunciation():
    """
    Checks the pronunciation of the spoken word against the target word in the database.

    Returns:
    json: A JSON response indicating success, match, and spoken text.
    """
    if "audio_data" not in request.files:
        return jsonify({"success": False, "error": "No audio uploaded"}), 400

    # uploaded audio from browser (usually webm/ogg)
    audio_file = request.files["audio_data"]

    # expected word from DB (hidden input in HTML)
    target_word = request.form.get("word", "").strip().lower()

    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_input:
            audio_file.save(temp_input.name)

        # Convert to WAV (needed for speech_recognition)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_wav:
            AudioSegment.from_file(temp_input.name).export(temp_wav.name, format="wav")

            recognizer = sr.Recognizer()
            with sr.AudioFile(temp_wav.name) as source:
                audio = recognizer.record(source)

            # Convert speech → text
            spoken_text = recognizer.recognize_google(audio).lower().strip()

            # cleanup temp files
            os.remove(temp_input.name)
            os.remove(temp_wav.name)

            # Compare with expected word
            if spoken_text == target_word:
                return jsonify({"success": True, "match": True, "spoken": spoken_text})
            else:
                return jsonify({"success": True, "match": False, "spoken": spoken_text})

    except sr.UnknownValueError:
        return jsonify({"success": False, "error": "Could not understand audio"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

def get_next_word(current_id, user_name_column, date_stamp_column):
    """
    Finds the next eligible word for this user based on training conditions.

    Parameters:
    current_id (int): The current ID number.
    user_name_column (str): The column name for the user.
    date_stamp_column (str): The column name for the date stamp.

    Returns:
    tuple: A tuple containing the next ID number and the corresponding word, or (None, None) if no eligible words are left.
    """
    table_name = session.get("table_name", "general_words")
    id_upper_limit = session.get("id_upper_limit", 20)
    conn = get_db_connection()
    cursor = conn.cursor()

    # Loop through IDs until we find a word that matches the training condition
    for next_id in range(current_id + 1, id_upper_limit + 1):
        cursor.execute(f"""
            SELECT words, {user_name_column}, {date_stamp_column}
            FROM {table_name}
            WHERE id_nr = ?
        """, (next_id,))
        row = cursor.fetchone()
        if not row:
            continue

        word, pattern, date_stamp_val = row[0], row[1], row[2]
        conn.close()
        return next_id, word

    conn.close()
    return None, None  # no eligible words left

def get_word_and_pattern_by_id_nr(id_nr, user_name_column):
    """
    Retrieves a word and its user-specific pattern from the database by its ID number.

    Parameters:
    id_nr (int): The ID number of the word to retrieve.
    user_name_column (str): The column name for the user.

    Returns:
    tuple: A tuple containing the word and its pattern, or (None, None) if not found.
    """
    table_name = session.get("table_name", "general_words")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT words, {user_name_column} FROM {table_name} WHERE id_nr = ?", (id_nr,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0], row[1] if row[1] else ""
    return None, None

def chk_wrd_chng_pattern(id_nr, usr_input, user_name_column, date_stamp):
    """
    Checks the word input and updates the user-specific pattern in the database.

    Parameters:
    id_nr (int): The ID number of the word.
    usr_input (str): The user's input.
    user_name_column (str): The column name for the user.
    date_stamp (str): The date stamp column.

    Returns:
    str: A message indicating the result of the update.
    """
    table_name = session.get("table_name", "general_words")
    word = get_word_by_id_nr(id_nr)
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(f"SELECT {user_name_column} FROM {table_name} WHERE id_nr = ?", (id_nr,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return f"No row with id_nr={id_nr}"

    pattern = row[0] if row[0] else ""

    try:
        checked_pattern = ""
        for i in range(len(word)):
            if i < len(usr_input) and word[i] == usr_input[i]:
                if i < len(pattern) and pattern[i] == "b":
                    checked_pattern += "a"
                elif i < len(pattern) and pattern[i] == "c":
                    checked_pattern += "b"
                else:
                    checked_pattern += "a"
            else:
                checked_pattern += "c"

        cursor.execute(f"""
            UPDATE {table_name}
            SET {user_name_column} = ?, {date_stamp} = ?
            WHERE id_nr = ?
        """, (checked_pattern, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), id_nr))
        conn.commit()
        conn.close()
        return f"Updated row {id_nr} for {user_name_column} with pattern {checked_pattern}"

    except Exception as e:
        conn.close()
        return f"Incorrect input: {e}"

# This line will run the script on a local device: uncomment to run locally.
if __name__ == "__main__":
    app.run(debug=True)

# This line will run the script to be accessible through local WI-FI: uncomment to run publicly.
# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=5000, debug=True)
