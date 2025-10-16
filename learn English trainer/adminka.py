# Works with PYTHON 3.12 and googletrans==4.0.0-rc1
# google allows to process <250 words at one launch

import sqlite3
import os
from datetime import datetime
from googletrans import Translator
from gtts import gTTS
import io
from tkinter import *
import tkinter as tk
import paths_info

# Current date and time
currant_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Initialize the translator
translator = Translator()

# User's data
user_name_1 = paths_info.user_1
user_name_2 = paths_info.user_2
user_name_3 = paths_info.user_3

# DB setup data
db_name = paths_info.data_base_name

# Number of words to be added to a table at once
nmb_of_wrds = 200

# IMAGES folder path
folder_for_images_path = paths_info.images_folder_path

# TEXT folder path
folder_for_texts_path = paths_info.texts_folder_path

def pick_up_table():
    """
    Chooses a table from the database based on user input.

    Returns:
    str: The name of the selected table.
    """
    # Tables in the database
    tables = ["general_words", "phrasal_verbs", "irregular_verbs", "main_groups"]
    for index, table in enumerate(tables):
        print(index, table)
    user_input = int(input("Pick up a number to enhance a corresponding table \n"))
    if user_input > len(tables):
        user_input = 0
    return tables[user_input]

# Select the table based on user input
table_name = pick_up_table()

# Path to the initial words file
initial_words_file = f"{folder_for_texts_path}\\{table_name}.txt"

class db_sql:
    """
    A class to handle database operations.

    Attributes:
    db_name (str): The name of the database file.
    nmb_of_wrds (int): The number of words to process at once.
    table_name (str): The name of the table to work with.
    user_name_1 (str): The first user's column name.
    user_name_2 (str): The second user's column name.
    user_name_3 (str): The third user's column name.
    initial_words_file (str): The path to the initial words file.
    """
    def __init__(self, db_name, nmb_of_wrds):
        self.table_name = table_name
        self.user_name_1 = user_name_1
        self.user_name_2 = user_name_2
        self.user_name_3 = user_name_3
        self.nmb_of_wrds = nmb_of_wrds
        self.initial_words_file = initial_words_file
        self.db_name = db_name

    def read_words_file(self, nmb_of_wrds):
        """
        Reads a limited number of words from the initial words file.

        Parameters:
        nmb_of_wrds (int): The number of words to read.

        Returns:
        list: A list of words read from the file.
        """
        words_from_open_file = []
        with open(self.initial_words_file) as open_file:
            for i, line in enumerate(open_file):  # Read line by line without `.readlines()`
                if not line.strip():  # Skip empty lines
                    continue
                words_from_open_file.append(line.rstrip())
                if len(words_from_open_file) >= nmb_of_wrds:  # Stop at 'num_words'
                    break
        return words_from_open_file

    def setup_base(self):
        """
        Sets up the database and establishes a connection.

        Returns:
        tuple: A tuple containing the path to the database, a cursor object, and a connection object.
        """
        path = os.path.dirname(os.path.abspath(__file__))
        conn = sqlite3.connect(path + '/' + self.db_name)
        cur = conn.cursor()
        return path, cur, conn

    def setup_table(self, li_from_file, cur, conn, table_name):
        """
        Adds new rows to the existing User table in the database.

        Parameters:
        li_from_file (list): A list of words to add.
        cur (sqlite3.Cursor): A cursor object.
        conn (sqlite3.Connection): A connection object.
        table_name (str): The name of the table to work with.
        """
        # Get translations
        translated_words = [translator.translate(word, dest="ru").text for word in li_from_file]

        # Get audio
        ru_sound_data_dict = {
            li_from_file[i]: self.get_tts_audio(translated_words[i], lang='ru')
            for i in range(len(translated_words))
        }

        en_sound_data_dict = {
            word: self.get_tts_audio(word, lang='en')
            for word in li_from_file
        }

        # Create table if not exists
        cur.execute(f"""CREATE TABLE IF NOT EXISTS {table_name} (
            id_nr INTEGER PRIMARY KEY AUTOINCREMENT,
            words TEXT UNIQUE,
            native_lang TEXT,
            en_sounds BLOB,
            ru_sounds BLOB,
            image BLOB,
            {user_name_1} TEXT, date_stamp_1 TEXT,
            {user_name_2} TEXT, date_stamp_2 TEXT,
            {user_name_3} TEXT, date_stamp_3 TEXT)""")

        for en_word, ru_word in zip(li_from_file, translated_words):
            # Skip if word already exists
            cur.execute(f"SELECT 1 FROM {table_name} WHERE words = ?", (en_word,))
            if cur.fetchone():
                continue

            en_sound_data = en_sound_data_dict.get(en_word)
            ru_sound_data = ru_sound_data_dict.get(en_word)

            image_path = f'images/{en_word}.png'
            image_data = self.convert_to_binary(image_path) if os.path.exists(image_path) else None

            # Set user_input values ("c" * word length)
            user_input = "c" * len(en_word)

            cur.execute(f"""INSERT INTO {table_name} (
                words, native_lang, en_sounds, ru_sounds, image,
                {user_name_1}, date_stamp_1,
                {user_name_2}, date_stamp_2,
                {user_name_3}, date_stamp_3
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (en_word, ru_word, en_sound_data, ru_sound_data, image_data,
             user_input, currant_date,
             user_input, currant_date,
             user_input, currant_date))

        conn.commit()

    def get_tts_audio(self, word, lang='ru'):
        """
        Generates audio pronunciation for a given word using gTTS.

        Parameters:
        word (str): The word to generate pronunciation for.
        lang (str): The language code for the pronunciation (default is 'ru').

        Returns:
        bytes or None: The binary audio data or None if an error occurs.
        """
        try:
            tts = gTTS(text=word, lang=lang)
            mp3_fp = io.BytesIO()
            tts.write_to_fp(mp3_fp)
            return mp3_fp.getvalue()
        except Exception as e:
            print(f"Error generating sound for {word}: {e}")
            return None

    def convert_to_binary(self, filename):
        """
        Converts an image file to binary format.

        Parameters:
        filename (str): The path to the image file.

        Returns:
        bytes: The binary data of the image.
        """
        with open(filename, 'rb') as file:
            return file.read()

    def change_ru_translation(self, conn, cur, table_name, wrd_id, new_native_lang_text):
        """
        Replaces the Russian translation text and pronunciation in the database.

        Parameters:
        conn (sqlite3.Connection): A connection object.
        cur (sqlite3.Cursor): A cursor object.
        table_name (str): The name of the table to work with.
        wrd_id (int): The ID number of the word to update.
        new_native_lang_text (str): The new Russian translation text.
        """
        inp_wrd_text = self.get_tts_audio(new_native_lang_text, lang='ru')
        try:
            cur.execute(f"""UPDATE {table_name}
                SET native_lang = ?, ru_sounds = ?
                WHERE id_nr = ?""",
                (new_native_lang_text, inp_wrd_text, wrd_id))

            conn.commit()
            print(f'Ru words successfully changed')
        except Exception as e:
            print(f"Error changing text for word ID {wrd_id}: {e}")
        return None

    def change_image(self, conn, cur, table_name, wrd_id, filename):
        """
        Replaces the image for a given word ID in the database.

        Parameters:
        conn (sqlite3.Connection): A connection object.
        cur (sqlite3.Cursor): A cursor object.
        table_name (str): The name of the table to work with.
        wrd_id (int): The ID number of the word to update.
        filename (str): The filename of the new image.
        """
        image_path = f'images/{filename}.png'
        with open(image_path, 'rb') as file:
            val_file = file.read()
        try:
            cur.execute(f"""UPDATE {table_name}
                SET image = ?
                WHERE id_nr = ?""",
                (val_file, wrd_id))
            conn.commit()
            print(f'The picture successfully replaced for word ID {wrd_id}')
        except Exception as e:
            print(f"Error changing picture for word ID {wrd_id}: {e}")
        return None

    def drop_a_table(self, conn, cur, table_name):
        """
        Drops a table from the database.

        Parameters:
        conn (sqlite3.Connection): A connection object.
        cur (sqlite3.Cursor): A cursor object.
        table_name (str): The name of the table to drop.
        """
        # THIS WILL DROP THE TABLE!!!
        cur.execute(f"""DROP TABLE IF EXISTS {table_name}""")
        conn.commit()

    def replace_change_en_pron(self, wrd_id, en_tran_new):
        """
        Replaces the English pronunciation for a given word ID in the database.

        Parameters:
        wrd_id (int): The ID number of the word to update.
        en_tran_new (str): The new English pronunciation text.
        """
        new_pron = self.get_tts_audio(en_tran_new, lang='en')
        cur.execute(f"UPDATE {table_name} SET en_sounds = ? WHERE id_nr = ?", (new_pron, wrd_id))
        conn.commit()

# Initialization of the class 'db_sql'
db_1 = db_sql(db_name, nmb_of_wrds)

# Creation of the database if used for the first time
path, cur, conn = db_1.setup_base()

# -------------------------------------------------------
# UNCOMMENT THIS BLOCK TO WRITE DOWN A NEW TABLE TO THE DB
# Loading and clearing of number of rows from initial file
# li_from_file = db_1.read_words_file(db_1.nmb_of_wrds)
# Tables creation in db, adding ids, words, patterns
# db_1.setup_table(li_from_file, cur, conn, table_name)
# -------------------------------------------------------

def main():
    """
    Main function to create the GUI and handle user interactions.
    """
    def change_ru():
        """
        Changes the Russian translation text and pronunciation for a given word ID.
        """
        wrd_id = int(wrd_id_input.get())
        new_native_lang_text = new_native_lang_text_input.get()
        db_1.change_ru_translation(conn, cur, db_1.table_name, wrd_id, new_native_lang_text)
        new_native_lang_text_label.config(text=f"changed to {new_native_lang_text}")
        # window.destroy()

    def change_picture():
        """
        Changes the image for a given word ID.
        """
        wrd_id = int(wrd_id_input.get())
        filename = filename_input.get()
        db_1.change_image(conn, cur, db_1.table_name, wrd_id, filename)
        filename_label.config(text=f"changed to {filename}")

    def add_row_to_table():
        """
        Adds a new row to the database table.
        """
        table_name = db_1.table_name
        li_from_file = []
        word_from_file = li_from_file_input.get()
        li_from_file.append(word_from_file)
        db_1.setup_table(li_from_file, cur, conn, table_name)
        li_from_file_label.config(text=f"{word_from_file} added to the table")

    def paste(event):
        """
        Adds the ability to use Ctrl+V to paste text from the clipboard.

        Parameters:
        event (tk.Event): The event object containing clipboard information.

        Returns:
        str: "break" to prevent default paste behavior.
        """
        widget = event.widget
        try:
            # Get clipboard content
            clip = widget.clipboard_get()

            # Get current selection range
            if widget.selection_present():
                start = widget.index("sel.first")
                end = widget.index("sel.last")
                widget.delete(start, end)

            # Insert clipboard content at cursor
            widget.insert(tk.INSERT, clip)
        except Exception as e:
            print("Paste error:", e)
        return "break"

    def change_en_pron():
        """
        Changes the English pronunciation for a given word ID.
        """
        wrd_id = int(wrd_id_input.get())
        en_tran_new = en_tran_new_input.get()
        db_1.replace_change_en_pron(wrd_id, en_tran_new)
        en_tran_new_label.config(text=f"EN pron changed to {en_tran_new}")

    # Create the main window
    window = Tk()
    window.minsize(width=500, height=500)
    window.title(f"CURRANT TABLE NAME {table_name}")
    window.config(pady=10, padx=10)

    # ----------------------enter a new native word--------------------
    table_label = Label(text=f"CURRANT TABLE {table_name}", font=("Arial", 14, "bold"))
    table_label.grid(column=0, row=0)

    wrd_id_input = Entry(width=5, font=("Arial", 16, "bold"))
    wrd_id_input.grid(column=3, row=0)

    wrd_id_label = Label(text="enter the word ID", font=("Arial", 16, "bold"))
    wrd_id_label.grid(column=1, row=0)
    wrd_id_label.config(pady=10, padx=10)

    new_native_lang_text_input = Entry(width=30, font=("Arial", 16, "bold"))
    new_native_lang_text_input.grid(column=0, row=2)
    new_native_lang_text_input.bind("<Control-v>", paste)  #---------<<<<<<<<Control-v>

    new_native_lang_text_label = Label(text="enter a new Ru word", font=("Arial", 16, "bold"))
    new_native_lang_text_label.grid(column=1, row=2)
    new_native_lang_text_label.config(pady=10, padx=10)

    ru_word_replace_button = Button(text="submit ru word", font=("Arial", 16, "bold"), command=change_ru)
    ru_word_replace_button.grid(column=3, row=2)

    # --------------------------enter file name of picture----------------
    filename_input = Entry(width=30, font=("Arial", 16, "bold"))
    filename_input.grid(column=0, row=5)

    filename_label = Label(text="enter file name of picture", font=("Arial", 16, "bold"))
    filename_label.grid(column=1, row=5)
    filename_label.config(pady=10, padx=10)

    picture_replace_button = Button(text="submit picture", font=("Arial", 16, "bold"), command=change_picture)
    picture_replace_button.grid(column=3, row=5)

    # ------------------------adds a new row to the table------------------
    li_from_file_input = Entry(width=30, font=("Arial", 16, "bold"))
    li_from_file_input.grid(column=0, row=6)
    li_from_file_input.bind("<Control-v>", paste)  #---------<<<<<<<<Control-v>

    li_from_file_label = Label(text="add En word to new row", font=("Arial", 16, "bold"))
    li_from_file_label.grid(column=1, row=6)
    li_from_file_label.config(pady=10, padx=10)

    li_from_file_button = Button(text="submit english word", font=("Arial", 16, "bold"), command=add_row_to_table)
    li_from_file_button.grid(column=3, row=6)

    # ------------------------change EN pronouncing------------------
    en_tran_new_input = Entry(width=30, font=("Arial", 16, "bold"))
    en_tran_new_input.grid(column=0, row=7)
    en_tran_new_input.bind("<Control-v>", paste)  #---------<<<<<<<<Control-v>

    en_tran_new_label = Label(text="add En word here", font=("Arial", 16, "bold"))
    en_tran_new_label.grid(column=1, row=7)
    en_tran_new_label.config(pady=10, padx=10)

    en_tran_new_button = Button(text="change EN pronouncing", font=("Arial", 16, "bold"), command=change_en_pron)
    en_tran_new_button.grid(column=3, row=7)

    # --This should be in the end
    window.mainloop()

# UNCOMMENT THIS TO CORRECT A TABLE OF THE DB
# main()
